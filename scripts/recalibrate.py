"""Calibrate the retrained model: FP + lead-time batteries + threshold pick."""
import io
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aegis.ml.evaluate import (false_positive_rate, lead_time_distribution,
                               sweep_thresholds, calibrate, write_metrics_md)
from aegis.server import db as _  # noqa: F401  (import check)
import json

ART = Path(__file__).resolve().parents[1] / "aegis" / "ml" / "artifacts"
mp = ART / "forecast_model.pt"

print("== sweep (small batteries) ==")
sweep = sweep_thresholds(mp, thresholds=(0.60, 0.65, 0.70, 0.72, 0.75),
                         n_benign=3, n_attacks=6, seed=909)
for s in sweep:
    print(f"  th={s['threshold']:.2f}  fp={s['fp_alerts_per_hour']}/hr  "
          f"cov={s['attack_coverage_pct']}%  lead={s['lead_median_min']}m")

chosen = calibrate(mp, sweep, fp_budget=1.5)
print(f"\nchosen threshold: {chosen:.2f}")

# full batteries at the chosen threshold
print("\n== full FP battery ==")
fp = false_positive_rate(mp, n_sessions=6, seed=4242, threshold=chosen)
print(f"  {fp['alerts']} alerts / {fp['monitored_hours']}h -> {fp['alerts_per_hour']}/hr")

print("\n== full lead battery ==")
lt = lead_time_distribution(mp, n_scenarios=12, seed=4243, threshold=chosen)
print(f"  coverage {lt['coverage_pct']}%  median {lt['lead_median_min']}m  "
      f"p10 {lt['lead_p10_min']}m  p90 {lt['lead_p90_min']}m")

model_metrics = json.loads((ART / "metrics.json").read_text())
model_metrics["calibrated_threshold"] = chosen
(ART / "metrics.json").write_text(json.dumps(model_metrics, indent=2))
write_metrics_md(model_metrics, fp, lt, sweep, chosen)
print("\nmetrics.md regenerated")
