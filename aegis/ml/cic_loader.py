"""CIC-IDS2017 loader + transfer validation.

Maps CIC-IDS2017 per-flow CSV records onto the AegisForecast 22-feature
window schema, builds 5s window sequences over the capture timeline, and
zero-shot evaluates a trained forecaster on REAL captured attack traffic
(labels from the dataset). Used from Colab where the dataset is available;
locally, a synthetic-CSV path exercises the same code in tests.

Mapping notes (CIC-IDS2017 CSV columns -> our window features):
  Flow Duration, Tot Fwd/Bwd Pkts  -> pkt_rate, flow counts
  Flow Bytes/s                     -> byte_rate
  SYN/FIN/RST/ACK/PSH Flag Cnt     -> flag ratios
  Flow IAT Mean/Std/Max            -> iat features
  Fwd/Bwd Pkt Len Mean/Std         -> mean_pkt_size, pkt_size_std
  Destination Port                 -> port entropy / distinct counts
  Label                            -> window label (attack if any flow
                                      in window is not BENIGN)
"""

from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

from aegis import ALERT_CONFIDENCE
from aegis.features import FEATURE_DIM, SEQ_LEN, SequenceFeaturizer
from aegis.ml.model import HORIZON_MAX_MIN

WINDOWS_PER_MIN = 12.0          # 5s windows


# ------------------------------------------------------------------ mapping
def _to_float(v) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def cic_row_to_flow(row: Dict[str, str]) -> dict:
    """Convert one CIC-IDS2017 CSV row to our flow-row schema."""
    def g(*names):
        for n in names:
            for k in row:
                if k.strip().lower() == n.lower():
                    return row[k]
        return "0"

    pkts = _to_float(g("Total Backward Packets")) + _to_float(g("Total Forward Packets"))
    fwd_pkts = _to_float(g("Total Forward Packets"))
    syn = _to_float(g("SYN Flag Count"))
    fin = _to_float(g("FIN Flag Count"))
    rst = _to_float(g("RST Flag Count"))
    ack = _to_float(g("ACK Flag Count"))
    psh = _to_float(g("PSH Flag Count"))
    synack = min(syn, ack) if syn > 0 and ack > 0 else 0.0
    iat_mean = _to_float(g("Flow IAT Mean")) / 1e6          # ns -> s (CIC uses us; normalize)
    iat_std = _to_float(g("Flow IAT Std")) / 1e6

    # flows carrying any flagged "attack" sub-label (PortScan, DDoS, ...) are attacks
    label = str(g("Label")).strip().lower()
    is_attack = 0 if label in ("benign", "", "normal") else 1

    return {
        "src": str(g("Source IP")) or "0.0.0.0",
        "dst": str(g("Destination IP")) or "0.0.0.0",
        "sport": int(_to_float(g("Source Port"))),
        "dport": int(_to_float(g("Destination Port"))),
        "proto": "tcp",
        "pkts": int(max(pkts, 1)),
        "bytes": int(_to_float(g("Flow Duration")) / 1000.0) or int(max(pkts, 1) * 80),
        "syn": int(syn), "synack": int(synack), "rst": int(rst),
        "fin": int(fin), "psh": int(psh), "ack": int(ack),
        "iat_mean": max(iat_mean, 0.0),
        "iat_var": max(iat_std ** 2, 0.0),
        "_attack": is_attack,
    }


def load_cic_csv(path: Path, max_rows: int = 200_000) -> List[dict]:
    """Load a CIC-IDS2017 CSV (or the synthetic test format) -> flow rows."""
    rows: List[dict] = []
    with open(path, newline="", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for i, raw in enumerate(reader):
            if i >= max_rows:
                break
            rows.append(cic_row_to_flow(raw))
    return rows


def flows_to_windows(flows: List[dict], window: float = 5.0
                     ) -> Tuple[List[List[dict]], List[int]]:
    """Group flow rows into 5s windows over their arrival index.

    CIC CSV rows lack absolute timestamps; we bucket by relative flow
    duration accumulated order (monotone index / flows-per-window), which
    preserves the temporal sequencing the forecaster needs.
    per_window = ceil(len / windows)
    """
    n = len(flows)
    n_windows = max(1, int(np.ceil(n / 60.0)))     # ~60 flows per 5s window
    per = int(np.ceil(n / n_windows))
    windows: List[List[dict]] = []
    labels: List[int] = []
    for w in range(n_windows):
        chunk = flows[w * per:(w + 1) * per]
        if not chunk:
            break
        windows.append([{k: v for k, v in c.items() if not k.startswith("_")}
                       for c in chunk])
        labels.append(1 if any(c["_attack"] for c in chunk) else 0)
    return windows, labels


def windows_to_sequences(windows: List[List[dict]], labels: List[int],
                         seq_len: int = SEQ_LEN, stride: int = 2
                         ) -> Tuple[np.ndarray, np.ndarray]:
    """Featurize windows (shared SequenceFeaturizer) -> (X, y_window)."""
    fz = SequenceFeaturizer(use_slope=True)
    feats = [fz.feed(rows) for rows in windows]
    X, y = [], []
    for start in range(0, len(feats) - seq_len, stride):
        X.append(feats[start:start + seq_len])
        y.append(int(any(labels[start:start + seq_len])))
    return np.asarray(X, dtype=np.float32), np.asarray(y, dtype=np.int64)


def transfer_evaluate(model, X: np.ndarray, y: np.ndarray,
                      threshold: float = ALERT_CONFIDENCE) -> dict:
    """Zero-shot evaluation of the Aegis model on CIC windows."""
    import torch
    model.eval()
    with torch.no_grad():
        out = model(torch.from_numpy(X))
        probs = out["attack"].numpy()
    from aegis.ml.train import auc_score
    auc = auc_score(y.astype(float), probs)
    preds = (probs >= threshold).astype(int)
    tp = int(((preds == 1) & (y == 1)).sum())
    fp = int(((preds == 1) & (y == 0)).sum())
    fn = int(((preds == 0) & (y == 1)).sum())
    return {
        "n_sequences": len(y),
        "attack_seq_rate": round(float(y.mean()), 4),
        "val_auc_on_cic": round(float(auc), 4) if auc == auc else None,
        "precision": round(tp / max(tp + fp, 1), 4),
        "recall": round(tp / max(tp + fn, 1), 4),
        "tp": tp, "fp": fp, "fn": fn,
    }
