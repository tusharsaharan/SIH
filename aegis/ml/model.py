"""Bi-LSTM + Attention forecasting model.

Architecture (PyTorch):
  input (B, T, F)
    -> BiLSTM(64, bidirectional)           temporal context both directions
    -> Self-Attention (scaled dot-product)  focus on anomalous bursts
    -> concat(lstm_out, attended)
    -> Linear(96) shared trunk
    -> heads:
         attack_head  : sigmoid  P(attack escalating within horizon)
         stage_head   : softmax over 5 MITRE stages
         horizon_head : sigmoid  predicted minutes-to-detonation / 30

Forecast objective: given the last 2 minutes of 5s flow windows, predict
whether an attack will escalate to detonation within the next 30 minutes
and which ATT&CK stage the network is currently in.
"""

from __future__ import annotations

import torch
import torch.nn as nn

from aegis.features import FEATURE_DIM, SEQ_LEN
from aegis.ml.attack_stages import NUM_STAGES

HORIZON_MAX_MIN = 30.0


class SelfAttention(nn.Module):
    """Scaled dot-product self-attention over the time axis."""

    def __init__(self, dim: int):
        super().__init__()
        self.scale = dim ** -0.5
        self.query = nn.Linear(dim, dim)
        self.key = nn.Linear(dim, dim)
        self.value = nn.Linear(dim, dim)

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        # x: (B, T, D)
        q, k, v = self.query(x), self.key(x), self.value(x)
        scores = torch.softmax(q @ k.transpose(-2, -1) * self.scale, dim=-1)  # (B, T, T)
        out = scores @ v                                                     # (B, T, D)
        return out, scores


class BiLSTMAttention(nn.Module):
    def __init__(
        self,
        input_dim: int = FEATURE_DIM,
        hidden: int = 64,
        layers: int = 2,
        seq_len: int = SEQ_LEN,
    ):
        super().__init__()
        self.seq_len = seq_len
        self.lstm = nn.LSTM(
            input_dim, hidden, num_layers=layers,
            batch_first=True, bidirectional=True, dropout=0.15,
        )
        self.attn = SelfAttention(hidden * 2)
        self.trunk = nn.Sequential(
            nn.Linear(hidden * 4, 96), nn.ReLU(), nn.Dropout(0.15),
        )
        self.attack_head = nn.Linear(96, 1)                  # P(escalation)
        self.stage_head = nn.Linear(96, NUM_STAGES)         # ATT&CK stage
        self.horizon_head = nn.Linear(96, 1)                # lead time

    def forward(self, x: torch.Tensor):
        # x: (B, T, F)
        h, _ = self.lstm(x)              # (B, T, 2H)
        attended, attn_w = self.attn(h)  # (B, T, 2H), (B, T, T)
        ctx = attended.mean(dim=1)       # (B, 2H)
        feat = torch.cat([h.mean(dim=1), ctx], dim=-1)   # (B, 4H)
        z = self.trunk(feat)
        return {
            "attack": torch.sigmoid(self.attack_head(z)).squeeze(-1),
            "stage": self.stage_head(z),
            "horizon": torch.sigmoid(self.horizon_head(z)).squeeze(-1),
            "attention": attn_w,
        }

    @torch.no_grad()
    def attention_over_time(self, x: torch.Tensor) -> torch.Tensor:
        """Mean attention received by each timestep (B, T) - SHAP-adjacent."""
        out = self.forward(x)
        return out["attention"].mean(dim=1)


class TransformerForecaster(nn.Module):
    """Transformer-encoder variant (comparable params to BiLSTMAttention).

    input (B, T, F) -> Linear project to d_model -> learned positional
    embedding -> 2 x TransformerEncoderLayer (4 heads) -> mean-pool ->
    same 3 heads (attack / stage / horizon). Returns the same output dict
    (+ averaged encoder attention) so inference, SHAP, and eval code paths
    are unchanged.
    """

    def __init__(
        self,
        input_dim: int = FEATURE_DIM,
        d_model: int = 64,
        heads: int = 4,
        layers: int = 2,
        seq_len: int = SEQ_LEN,
        dropout: float = 0.15,
    ):
        super().__init__()
        self.seq_len = seq_len
        self.proj = nn.Linear(input_dim, d_model)
        self.pos = nn.Parameter(torch.zeros(1, seq_len, d_model))
        layer = nn.TransformerEncoderLayer(
            d_model=d_model, nhead=heads, dim_feedforward=d_model * 2,
            dropout=dropout, batch_first=True, activation="gelu")
        self.encoder = nn.TransformerEncoder(layer, num_layers=layers)
        self.trunk = nn.Sequential(
            nn.Linear(d_model, 96), nn.ReLU(), nn.Dropout(dropout))
        self.attack_head = nn.Linear(96, 1)
        self.stage_head = nn.Linear(96, NUM_STAGES)
        self.horizon_head = nn.Linear(96, 1)

    def forward(self, x: torch.Tensor):
        # x: (B, T, F) - pad/crop positionally to trained seq_len
        t = x.shape[1]
        h = self.proj(x) + self.pos[:, :t, :]
        h = self.encoder(h)                       # (B, T, D)
        z = self.trunk(h.mean(dim=1))             # (B, 96)
        return {
            "attack": torch.sigmoid(self.attack_head(z)).squeeze(-1),
            "stage": self.stage_head(z),
            "horizon": torch.sigmoid(self.horizon_head(z)).squeeze(-1),
            "attention": h.mean(dim=-1, keepdim=True).expand(-1, -1, t),
        }

    @torch.no_grad()
    def attention_over_time(self, x: torch.Tensor) -> torch.Tensor:
        out = self.forward(x)
        return out["attention"].mean(dim=1)


class EnsembleForecaster(nn.Module):
    """Weighted average of BiLSTM + Transformer heads (no extra training).

    Both members must share seq_len/feature_dim. Weights default to
    validation-AUC proportions; set explicitly via .weights.
    """

    def __init__(self, model_a: nn.Module, model_b: nn.Module,
                 weight_a: float = 0.5):
        super().__init__()
        self.a = model_a
        self.b = model_b
        self.weight_a = weight_a
        for m in (self.a, self.b):
            m.eval()
            for p in m.parameters():
                p.requires_grad_(False)

    def forward(self, x: torch.Tensor):
        oa, ob = self.a(x), self.b(x)
        w = self.weight_a
        return {
            "attack": w * oa["attack"] + (1 - w) * ob["attack"],
            "stage": w * oa["stage"] + (1 - w) * ob["stage"],
            "horizon": w * oa["horizon"] + (1 - w) * ob["horizon"],
            "attention": (oa["attention"] + ob["attention"]) / 2,
        }

    @torch.no_grad()
    def attention_over_time(self, x: torch.Tensor) -> torch.Tensor:
        return self.forward(x)["attention"].mean(dim=1)


def count_params(model: nn.Module) -> int:
    return sum(p.numel() for p in model.parameters() if p.requires_grad)
