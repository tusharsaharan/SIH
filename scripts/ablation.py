"""Ablation matrix: {seq_len 24, 48} x {slope, no-slope} -> pick winner.

Trains each config with the same seed/scenarios, evaluates FP rate +
lead time on a fixed holdout battery, writes ablation_report.json and
prints a comparison table. Winner is saved as the default forecast_model.pt.

Usage: python scripts/ablation.py [--epochs 8] [--quick]
"""

from __future__ import annotations

import argparse
import io
import json
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import torch

from aegis.ml.evaluate import false_positive_rate, lead_time_distribution
from aegis.ml.train import train

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "aegis" / "ml" / "artifacts"


def run_config(name: str, seq_len: int, use_slope: bool, epochs: int,
               n_scenarios: int, n_benign: int, seed: int,
               fp_sessions: int, lt_scenarios: int, out: Path) -> dict:
    print(f"\n{'=' * 70}\nCONFIG {name}: seq_len={seq_len} use_slope={use_slope}\n{'=' * 70}")
    t0 = time.time()
    _, metrics = train(
        epochs=epochs, seed=seed, out=out,
        seq_len=seq_len, use_slope=use_slope,
        n_scenarios=n_scenarios, n_benign=n_benign,
    )
    train_s = time.time() - t0

    model_path = out / "forecast_model.pt"
    fp = false_positive_rate(model_path, n_sessions=fp_sessions, seed=909)
    lt = lead_time_distribution(model_path, n_scenarios=lt_scenarios, seed=910)
    score = {
        "config": name, "seq_len": seq_len, "use_slope": use_slope,
        "val_auc": metrics["val_auc"],
        "stage_acc": metrics["val_stage_acc"],
        "horizon_mae": metrics["val_horizon_mae_min"],
        "fp_alerts_per_hour": fp["alerts_per_hour"],
        "attack_coverage_pct": lt["coverage_pct"],
        "lead_mean_min": lt["lead_mean_min"],
        "lead_median_min": lt["lead_median_min"],
        "lead_p10_min": lt["lead_p10_min"],
        "train_seconds": round(train_s, 1),
        "params": None,
    }
    return score


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=8)
    ap.add_argument("--quick", action="store_true",
                    help="2 configs only (48+slope vs 24-no-slope baseline)")
    ap.add_argument("--n-scenarios", type=int, default=24)
    ap.add_argument("--n-benign", type=int, default=8)
    ap.add_argument("--fp-sessions", type=int, default=5)
    ap.add_argument("--lt-scenarios", type=int, default=10)
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()

    configs = [
        ("A-seq48-slope", 48, True),
        ("B-seq48-base", 48, False),
        ("C-seq24-slope", 24, True),
        ("D-seq24-base", 24, False),     # original baseline
    ]
    if args.quick:
        configs = [configs[0], configs[3]]

    tmp = ARTIFACTS / "ablation"
    tmp.mkdir(parents=True, exist_ok=True)

    results = []
    for name, sl, slope in configs:
        out = tmp / name
        out.mkdir(parents=True, exist_ok=True)
        results.append(run_config(
            name, sl, slope, args.epochs,
            args.n_scenarios, args.n_benign, args.seed,
            args.fp_sessions, args.lt_scenarios, out))

    # ---- score: gate on FP <= 1/hr, then maximize median lead -------------
    def ok(r):
        return r["fp_alerts_per_hour"] <= 1.0 and r["attack_coverage_pct"] >= 80.0

    passing = [r for r in results if ok(r)]
    pool = passing if passing else results
    winner = max(pool, key=lambda r: (r["attack_coverage_pct"],
                                      r["lead_median_min"], r["val_auc"]))

    # promote winner to the default artifact
    for f in ("forecast_model.pt", "metrics.json"):
        src = tmp / winner["config"] / f
        shutil.copy2(src, ARTIFACTS / f)
    print(f"\npromoted winner '{winner['config']}' -> aegis/ml/artifacts/forecast_model.pt")

    report = {"winner": winner["config"], "results": results,
              "gates": "FP<=1/hr AND coverage>=80%"}
    (ARTIFACTS / "ablation_report.json").write_text(json.dumps(report, indent=2))

    print("\n" + "=" * 70)
    print("ABLATION RESULTS (same seed, same scenarios, same eval battery)")
    print("=" * 70)
    hdr = (f"{'config':<16} {'auc':>6} {'stage':>6} {'fp/hr':>7} "
           f"{'cov%':>6} {'lead-med':>9} {'lead-p10':>9} {'sec':>6}")
    print(hdr)
    for r in results:
        print(f"{r['config']:<16} {r['val_auc']:>6.3f} {r['stage_acc']:>6.2f} "
              f"{r['fp_alerts_per_hour']:>7.2f} {r['attack_coverage_pct']:>6.1f} "
              f"{r['lead_median_min']:>9.2f} {r['lead_p10_min']:>9.2f} "
              f"{r['train_seconds']:>6.0f}")
    print(f"\nWINNER: {winner['config']}")
    print(f"report: {ARTIFACTS / 'ablation_report.json'}")


if __name__ == "__main__":
    main()
