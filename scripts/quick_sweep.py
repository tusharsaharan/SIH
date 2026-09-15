"""Smaller threshold sweep for the perimeter-trained checkpoint."""
import io
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aegis.ml.evaluate import sweep_thresholds

s = sweep_thresholds("aegis/ml/artifacts/forecast_model.pt",
                     thresholds=(0.65, 0.70, 0.72, 0.75),
                     n_benign=2, n_attacks=4, seed=909)
for x in s:
    print(f"th={x['threshold']:.2f} fp={x['fp_alerts_per_hour']}/hr "
          f"cov={x['attack_coverage_pct']}% lead={x['lead_median_min']}m",
          flush=True)
print("SWEEP DONE", flush=True)
