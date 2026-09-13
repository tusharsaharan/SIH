"""Compare calibrated threshold candidates on identical full batteries.

Compares thresholds around the current operating point (default 0.70/0.72/
0.75 — the post-perimeter cliff zone). Prints the comparison table; only
rewrites docs/metrics.md + eval_report.json with --write.

Usage:
  python scripts/compare_thresholds.py [--write] [--thresholds 0.70 0.72 0.75]
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aegis.ml.evaluate import false_positive_rate, lead_time_distribution, write_metrics_md

ART = Path(__file__).resolve().parents[1] / "aegis" / "ml" / "artifacts"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true",
                    help="rewrite docs/metrics.md + eval_report.json with winner")
    ap.add_argument("--thresholds", type=float, nargs="+",
                    default=[0.70, 0.72, 0.75])
    args = ap.parse_args()

    mp = ART / "forecast_model.pt"
    model_metrics = json.loads((ART / "metrics.json").read_text())
    report = json.loads((ART / "eval_report.json").read_text())
    sweep = report["threshold_sweep"]

    best = None
    for th in args.thresholds:
        fp = false_positive_rate(mp, n_sessions=6, seed=4242, threshold=th)
        lt = lead_time_distribution(mp, n_scenarios=12, seed=4243, threshold=th)
        print(f"th={th}: fp={fp['alerts_per_hour']}/hr cov={lt['coverage_pct']}% "
              f"lead_med={lt['lead_median_min']}m p10={lt['lead_p10_min']}m "
              f"p90={lt['lead_p90_min']}m")
        # budget: fp <= 1.5/hr tolerated, coverage >= 90%; maximize lead
        ok = fp["alerts_per_hour"] <= 1.5 and lt["coverage_pct"] >= 90.0
        score = (ok, lt["lead_median_min"])
        if best is None or score > best[0]:
            best = (score, th, fp, lt)

    _, th, fp, lt = best
    print(f"\nchosen threshold: {th}")
    if not args.write:
        print("(dry run — pass --write to update docs/metrics.md + eval_report.json)")
        return
    write_metrics_md(model_metrics, fp, lt, sweep, th)
    report["false_positive"], report["lead_time"] = fp, lt
    report["calibrated_threshold"] = th
    (ART / "eval_report.json").write_text(json.dumps(report, indent=2))
    print("docs/metrics.md + eval_report.json updated")


if __name__ == "__main__":
    main()
