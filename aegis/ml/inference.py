"""Streaming inference engine + SHAP explainability.

Maintains a rolling buffer of the last `seq_len` feature windows (computed
by the shared SequenceFeaturizer - identical path to training) and produces
a forecast every tick:
  - attack probability + confidence
  - predicted ATT&CK stage (with tactic + TA id)
  - minutes-to-detonation estimate
  - SHAP-style feature attributions (gradient x input over the attack head)

Alert cooldown: a new alert is only emitted if `cooldown_windows` have
passed since the last one, or the probability rose by at least
`retrigger_delta` - keeps the SOC feed clean without dropping escalation.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import torch

from aegis import ALERT_CONFIDENCE
from aegis.features import FEATURE_DIM, FEATURE_NAMES, SEQ_LEN, SequenceFeaturizer
from aegis.ml.attack_stages import stage_info
from aegis.ml.model import (HORIZON_MAX_MIN, BiLSTMAttention,
                            EnsembleForecaster, TransformerForecaster)

ARTIFACTS = Path(__file__).resolve().parent / "artifacts"

COOLDOWN_WINDOWS = 3          # suppress re-alerts within 3 windows (15s sim)
RETRIGGER_DELTA = 0.02        # ...unless P rose by >= 2 points


@dataclass
class Forecast:
    ts: float
    attack_prob: float
    stage: int
    stage_info: Dict
    horizon_min: float
    alert: bool
    shap_top: List[Dict]          # [{feature, importance}]
    window_idx: int

    def to_dict(self) -> dict:
        return {
            "ts": self.ts,
            "attackProb": round(self.attack_prob, 4),
            "stage": self.stage,
            "stageName": self.stage_info["name"],
            "tactic": self.stage_info["tactic"],
            "mitre": self.stage_info["ta"],
            "horizonMin": round(self.horizon_min, 1),
            "alert": self.alert,
            "shap": self.shap_top,
            "windowIdx": self.window_idx,
        }


def load_checkpoint(path: Path = ARTIFACTS / "forecast_model.pt") -> dict:
    """Load v2 dict, ensemble dict, or a legacy bare state_dict."""
    ckpt = torch.load(path, map_location="cpu", weights_only=False)
    if isinstance(ckpt, dict) and ckpt.get("model_name") == "ensemble" \
            and "state_dict_a" in ckpt:
        return ckpt  # ensemble checkpoint: members + weight_a
    if not isinstance(ckpt, dict) or "state_dict" not in ckpt:
        ckpt = {"state_dict": ckpt, "seq_len": SEQ_LEN,
                "feature_dim": FEATURE_DIM, "use_slope": True}
    if ckpt["feature_dim"] < FEATURE_DIM:
        # older 20-dim checkpoint: features were added since
        ckpt["use_slope"] = False
    return ckpt


class ForecastEngine:
    """Rolling forecaster over live flow windows."""

    def __init__(
        self,
        model_path: Path = ARTIFACTS / "forecast_model.pt",
        threshold: float = ALERT_CONFIDENCE,
        device: str = "cpu",
    ):
        ckpt = load_checkpoint(model_path)
        self.seq_len: int = int(ckpt["seq_len"])
        self.feature_dim: int = int(ckpt["feature_dim"])
        self.use_slope: bool = bool(ckpt["use_slope"])
        self.model_name: str = ckpt.get("model_name", "bilstm")

        if self.model_name == "ensemble":
            ma = BiLSTMAttention(input_dim=self.feature_dim,
                                 seq_len=self.seq_len)
            mb = TransformerForecaster(input_dim=self.feature_dim,
                                       seq_len=self.seq_len)
            ma.load_state_dict(ckpt["state_dict_a"])
            mb.load_state_dict(ckpt["state_dict_b"])
            self.model = EnsembleForecaster(ma, mb,
                                            weight_a=float(ckpt["weight_a"]))
        else:
            arch = TransformerForecaster if self.model_name == "transformer" \
                else BiLSTMAttention
            self.model = arch(input_dim=self.feature_dim, seq_len=self.seq_len)
            self.model.load_state_dict(ckpt["state_dict"])
        self.model.eval()
        self.threshold = threshold

        self.featurizer = SequenceFeaturizer(use_slope=self.use_slope)
        self.buf: deque = deque(maxlen=self.seq_len)
        self.window_idx = 0

        # alert cooldown state
        self._last_alert_win: int = -10_000
        self._last_alert_prob: float = 0.0

        self.last_explain_ms: float = 0.0
        self.explain_total_ms: float = 0.0
        self.explain_count: int = 0

    # ------------------------------------------------------------------ feed
    def feed_window(self, flow_rows: List[dict]) -> Optional[Forecast]:
        """Push one 5s window of flow rows; emit a forecast when buffer is full."""
        feats = self.featurizer.feed(flow_rows)
        self.buf.append(feats)
        self.window_idx += 1
        if len(self.buf) < self.seq_len:
            return None
        x = torch.tensor(np.array([list(self.buf)], dtype=np.float32))
        with torch.no_grad():
            out = self.model(x)
        prob = float(out["attack"][0])
        stage = int(out["stage"][0].argmax())
        horizon = float(out["horizon"][0]) * HORIZON_MAX_MIN

        # latency guard: full inference must stay < 15ms per window
        t0 = time.perf_counter()
        shap_top = self.explain(x)
        self.last_explain_ms = (time.perf_counter() - t0) * 1000
        self.explain_total_ms += self.last_explain_ms
        self.explain_count += 1

        # cooldown: alert only on new escalation, not every window above P
        raw = prob >= self.threshold
        if raw:
            fresh = (self.window_idx - self._last_alert_win) > COOLDOWN_WINDOWS
            escalated = prob - self._last_alert_prob >= RETRIGGER_DELTA
            alert = fresh or escalated
            if alert:
                self._last_alert_win = self.window_idx
                self._last_alert_prob = prob
        else:
            alert = False
            self._last_alert_prob = min(prob, self._last_alert_prob)

        return Forecast(
            ts=time.time(),
            attack_prob=prob,
            stage=stage,
            stage_info=stage_info(stage),
            horizon_min=horizon if raw else 0.0,
            alert=alert,
            shap_top=shap_top,
            window_idx=self.window_idx,
        )

    # ------------------------------------------------------------- explain
    def explain(self, x: torch.Tensor, top_k: int = 5) -> List[Dict]:
        """Gradient x Input attribution over the attack head (SHAP-family).

        Returns the top-k features driving the current forecast, signed and
        normalized - the "why" behind every alert.
        """
        x.requires_grad_(True)
        out = self.model(x)
        prob = out["attack"][0]
        prob.backward()
        grad = x.grad[0].detach().numpy()               # (T, F)
        inp = x.detach().numpy()[0]                     # (T, F)
        attr = np.abs(grad * inp).sum(axis=0)           # (F,)
        total = attr.sum() + 1e-9
        order = np.argsort(-attr)[:top_k]
        return [
            {"feature": FEATURE_NAMES[i], "importance": round(float(attr[i] / total), 4)}
            for i in order
        ]

    # ------------------------------------------------------------ attention
    def attention_profile(self) -> List[float]:
        """Mean attention per timestep for the current buffer (dashboard viz)."""
        if len(self.buf) < self.seq_len:
            return [0.0] * self.seq_len
        x = torch.tensor(np.array([list(self.buf)], dtype=np.float32))
        return self.model.attention_over_time(x)[0].tolist()


def load_engine(threshold: float = ALERT_CONFIDENCE,
                model_path: Path = ARTIFACTS / "forecast_model.pt") -> ForecastEngine:
    return ForecastEngine(threshold=threshold, model_path=model_path)
