"""Build + evaluate the BiLSTM+Transformer ensemble.

Loads the perimeter BiLSTM (default checkpoint) and the Transformer
challenger, evaluates each plus their AUC-weighted ensemble on the CURRENT
dataset val split (same seed/params as training), and saves an ensemble
checkpoint that ForecastEngine can load directly (model_name="ensemble").

Usage: python scripts/build_ensemble.py [--seed 7]
"""

from __future__ import annotations

import argparse
import io
import json
import sys
import time
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import torch

from aegis.ml.dataset import build_dataset
from aegis.ml.model import (BiLSTMAttention, EnsembleForecaster,
                            TransformerForecaster)
from aegis.ml.train import auc_score, evaluate

ART = Path("aegis/ml/artifacts")
OUT = ART / "ensemble"


def load_member(path: Path, arch, device="cpu"):
    ckpt = torch.load(path, map_location=device, weights_only=False)
    m = arch(input_dim=int(ckpt["feature_dim"]), seq_len=int(ckpt["seq_len"]))
    m.load_state_dict(ckpt["state_dict"])
    m.eval()
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()

    t0 = time.time()
    print("building current val split (cached windows)...")
    Xtr, Xva, Atr, Ava, Str, Sva, Htr, Hva = build_dataset(seed=args.seed)
    print(f"val: {len(Xva)} sequences, attack rate {Ava.mean():.2%}")

    bilstm = load_member(ART / "forecast_model.pt", BiLSTMAttention)
    trans = load_member(ART / "transformer" / "forecast_model.pt",
                        TransformerForecaster)

    pa, _, _ = evaluate(bilstm, Xva, Ava, Sva, Hva)
    auc_b = auc_score(Ava, pa)
    pt, _, _ = evaluate(trans, Xva, Ava, Sva, Hva)
    auc_t = auc_score(Ava, pt)
    print(f"BiLSTM AUC={auc_b:.4f} | Transformer AUC={auc_t:.4f}")

    w = auc_b / (auc_b + auc_t)
    ens = EnsembleForecaster(bilstm, trans, weight_a=w)
    pe, ps_e, _ = evaluate(ens, Xva, Ava, Sva, Hva)
    auc_e = auc_score(Ava, pe)
    print(f"Ensemble (w_bilstm={w:.3f}) AUC={auc_e:.4f} "
          f"stage_acc={(ps_e == Sva).mean():.4f}")

    OUT.mkdir(parents=True, exist_ok=True)
    torch.save({
        "state_dict_a": bilstm.state_dict(),
        "state_dict_b": trans.state_dict(),
        "weight_a": float(w),
        "seq_len": 48, "feature_dim": 22, "use_slope": True,
        "model_name": "ensemble",
    }, OUT / "forecast_model.pt")
    metrics = {
        "val_auc": round(float(auc_e), 4),
        "val_stage_acc": round(float((ps_e == Sva).mean()), 4),
        "val_auc_bilstm": round(float(auc_b), 4),
        "val_auc_transformer": round(float(auc_t), 4),
        "weight_bilstm": round(float(w), 4),
        "n_val": len(Xva), "seq_len": 48, "feature_dim": 22,
        "eval_seconds": round(time.time() - t0, 1),
        "model_name": "ensemble",
    }
    (OUT / "metrics.json").write_text(json.dumps(metrics, indent=2))
    print("saved:", OUT / "forecast_model.pt")
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
