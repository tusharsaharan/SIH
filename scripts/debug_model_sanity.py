"""Sanity: does the NEW checkpoint reproduce val AUC 0.981 offline?"""
import io
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import torch

from aegis.ml.dataset import build_dataset
from aegis.ml.model import BiLSTMAttention
from aegis.ml.train import auc_score

ckpt = torch.load("aegis/ml/artifacts/forecast_model.pt",
                  map_location="cpu", weights_only=False)
print("ckpt keys:", list(ckpt.keys()))
print("seq_len:", ckpt["seq_len"], "feature_dim:", ckpt["feature_dim"],
      "use_slope:", ckpt["use_slope"])

model = BiLSTMAttention(input_dim=ckpt["feature_dim"], seq_len=ckpt["seq_len"])
model.load_state_dict(ckpt["state_dict"])
model.eval()

# fresh dataset with identical params
Xtr, Xva, Atr, Ava, Str, Sva, Htr, Hva = build_dataset(
    n_scenarios=24, n_benign=8, seed=7, seq_len=ckpt["seq_len"],
    use_slope=ckpt["use_slope"], n_multihost_benign=6)
print("val size:", len(Xva), "attack rate:", f"{Ava.mean():.2%}")

with torch.no_grad():
    out = model(torch.from_numpy(Xva[:400]))
probs = out["attack"].numpy()
print("prob stats: min", probs.min().round(3), "max", probs.max().round(3),
      "mean", probs.mean().round(3))
print("AUC on this slice:", round(auc_score(Ava[:400], probs), 3))
# distribution on attack vs benign samples
att = probs[Ava[:400] > 0.5]
ben = probs[Ava[:400] <= 0.5]
print("attack-sample probs: mean", round(float(att.mean()), 3),
      "max", round(float(att.max()), 3))
print("benign-sample probs: mean", round(float(ben.mean()), 3),
      "max", round(float(ben.max()), 3))
