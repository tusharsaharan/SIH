"""Training loop for the Bi-LSTM + Attention forecaster.

Loss = weighted BCE(attack) + CE(stage) * 0.6 + MSE(horizon) * 0.4
(attack samples only). The BCE term is class-weighted (pos_weight) to
compensate attack/benign imbalance.

Checkpoint format (v2): {"state_dict", "seq_len", "feature_dim", "use_slope"}
so the inference engine can rebuild the exact model + featurizer config.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

from aegis.features import FEATURE_DIM, SEQ_LEN
from aegis.ml.dataset import build_dataset
from aegis.ml.model import (HORIZON_MAX_MIN, BiLSTMAttention,
                            TransformerForecaster)

ARTIFACTS = Path(__file__).resolve().parent / "artifacts"

MODELS = {"bilstm": BiLSTMAttention, "transformer": TransformerForecaster}


def evaluate(model, X, A, S, H, batch=256):
    model.eval()
    preds_a, preds_s, preds_h = [], [], []
    with torch.no_grad():
        for i in range(0, len(X), batch):
            xb = torch.from_numpy(X[i:i + batch])
            out = model(xb)
            preds_a.append(out["attack"].numpy())
            preds_s.append(out["stage"].argmax(dim=1).numpy())
            preds_h.append(out["horizon"].numpy() * HORIZON_MAX_MIN)
    pa = np.concatenate(preds_a); ps = np.concatenate(preds_s)
    ph = np.concatenate(preds_h)
    return pa, ps, ph


def auc_score(y: np.ndarray, p: np.ndarray) -> float:
    y = y.astype(int)
    if y.sum() == 0 or (1 - y).sum() == 0:
        return float("nan")
    order = np.argsort(p)
    ranks = np.empty_like(order, dtype=float)
    ranks[order] = np.arange(1, len(p) + 1)
    pos = ranks[y == 1].sum()
    n_pos, n_neg = y.sum(), len(y) - y.sum()
    return float((pos - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg))


def train(
    epochs: int = 12,
    lr: float = 2e-3,
    seed: int = 7,
    out: Path = ARTIFACTS,
    seq_len: int = SEQ_LEN,
    use_slope: bool = True,
    n_scenarios: int = 24,
    n_benign: int = 8,
    epochs_pos_weight_cap: float = 5.0,
    model_name: str = "bilstm",
):
    torch.manual_seed(seed)
    np.random.seed(seed)
    out.mkdir(parents=True, exist_ok=True)

    Xtr, Xva, Atr, Ava, Str, Sva, Htr, Hva = build_dataset(
        n_scenarios=n_scenarios, n_benign=n_benign, seed=seed,
        seq_len=seq_len, use_slope=use_slope)
    print(f"dataset: train={len(Xtr)} val={len(Xva)} "
          f"({Xtr.shape[1]}x{Xtr.shape[2]} tensors, "
          f"attack-rate train={Atr.mean():.2%})")

    model = MODELS[model_name](input_dim=Xtr.shape[2], seq_len=seq_len)
    print(f"model: {model_name} params: "
          f"{sum(p.numel() for p in model.parameters() if p.requires_grad):,} "
          f"(seq_len={seq_len}, use_slope={use_slope})")

    # class weighting for the attack head
    n_pos = float((Atr > 0.5).sum()); n_neg = float((Atr <= 0.5).sum())
    pos_w = float(np.clip(n_neg / max(n_pos, 1.0), 1.0, epochs_pos_weight_cap))
    print(f"attack-head pos_weight: {pos_w:.2f}")

    opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    ce = nn.CrossEntropyLoss(); mse = nn.MSELoss()
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=epochs)

    Xtr_t = torch.from_numpy(Xtr); Atr_t = torch.from_numpy(Atr)
    Str_t = torch.from_numpy(Str); Htr_t = torch.from_numpy(Htr)
    # per-sample BCE weights: positives scaled by pos_w
    Wtr_t = Atr_t * pos_w + (1.0 - Atr_t)

    t0 = time.time()
    for ep in range(1, epochs + 1):
        model.train()
        perm = torch.randperm(len(Xtr_t))
        total = 0.0
        for i in range(0, len(perm), 128):
            b = perm[i:i + 128]
            fwd = model(Xtr_t[b])
            la = F.binary_cross_entropy(fwd["attack"], Atr_t[b], weight=Wtr_t[b])
            ls = ce(fwd["stage"], Str_t[b])
            attack_mask = Atr_t[b] > 0.5
            lh = mse(fwd["horizon"][attack_mask], Htr_t[b][attack_mask]) if attack_mask.any() else torch.tensor(0.0)
            loss = la + 0.6 * ls + 0.4 * lh
            opt.zero_grad(); loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
            total += loss.item() * len(b)
        scheduler.step()

        pa, ps, ph = evaluate(model, Xva, Ava, Sva, Hva)
        auc = auc_score(Ava, pa)
        stage_acc = (ps == Sva).mean()
        det_mask = Ava > 0.5
        horizon_mae = np.abs(ph - Hva * HORIZON_MAX_MIN)[det_mask].mean() if det_mask.any() else float("nan")
        print(f"epoch {ep:02d}  loss={total/len(Xtr):.4f}  val_auc={auc:.3f}  "
              f"stage_acc={stage_acc:.3f}  horizon_mae={horizon_mae:.1f} min")

    pa, ps, ph = evaluate(model, Xva, Ava, Sva, Hva)
    auc = auc_score(Ava, pa)
    print(f"\ntraining done in {time.time()-t0:.1f}s")
    print(f"final val AUC={auc:.3f}")

    ckpt = {
        "state_dict": model.state_dict(),
        "seq_len": int(seq_len),
        "feature_dim": int(Xtr.shape[2]),
        "use_slope": bool(use_slope),
        "model_name": model_name,
    }
    torch.save(ckpt, out / "forecast_model.pt")
    metrics = {
        "val_auc": round(auc, 4),
        "val_stage_acc": round(float((ps == Sva).mean()), 4),
        "val_horizon_mae_min": round(float(horizon_mae), 2),
        "n_train": len(Xtr), "n_val": len(Xva),
        "seq_len": int(seq_len), "feature_dim": int(Xtr.shape[2]),
        "use_slope": bool(use_slope), "pos_weight": round(pos_w, 2),
        "epochs": epochs, "train_seconds": round(time.time() - t0, 1),
        "checkpoint_format": 2, "model_name": model_name,
    }
    (out / "metrics.json").write_text(json.dumps(metrics, indent=2))
    print("saved:", out / "forecast_model.pt")
    return model, metrics


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=12)
    ap.add_argument("--lr", type=float, default=2e-3)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--seq-len", type=int, default=SEQ_LEN,
                    help="lookback windows (default 48 = 4 minutes)")
    ap.add_argument("--no-slope", action="store_true",
                    help="disable syn/rate ramp-slope features (ablation)")
    ap.add_argument("--n-scenarios", type=int, default=24)
    ap.add_argument("--n-benign", type=int, default=8)
    ap.add_argument("--out", type=str, default=str(ARTIFACTS))
    ap.add_argument("--model", type=str, default="bilstm",
                    choices=["bilstm", "transformer"])
    args = ap.parse_args()
    train(
        epochs=args.epochs, lr=args.lr, seed=args.seed,
        out=Path(args.out), seq_len=args.seq_len,
        use_slope=not args.no_slope,
        n_scenarios=args.n_scenarios, n_benign=args.n_benign,
        model_name=args.model,
    )
