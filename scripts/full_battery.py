"""Full honest battery for the current (perimeter) checkpoint.

FP: 6 benign sessions (same seed as recalibrate for comparability).
Lead: 12 attack scenarios.
Writes docs/metrics.md + eval_report.json via evaluate.main-equivalent.
"""

from __future__ import annotations

import io
import json
import sys
import time
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aegis.ml.evaluate import (false_positive_rate, lead_time_distribution,
                               sweep_thresholds, write_metrics_md)

ART = Path("aegis/ml/artifacts")
mp = ART / "forecast_model.pt"
t0 = time.time()

print("== FP battery (6 benign, seed 4242) ==", flush=True)
fp = false_positive_rate(mp, n_sessions=6, seed=4242, threshold=0.72)
print(f"FP@0.72: {fp['alerts']} alerts / {fp['monitored_hours']}h -> "
      f"{fp['alerts_per_hour']}/hr  per-session={fp['per_session']}", flush=True)

print("== lead battery (12 attacks, seed 4243) ==", flush=True)
lt = lead_time_distribution(mp, n_scenarios=12, seed=4243, threshold=0.72)
print(f"Lead@0.72: coverage {lt['coverage_pct']}% median {lt['lead_median_min']}m "
      f"p10 {lt['lead_p10_min']}m p90 {lt['lead_p90_min']}m", flush=True)

print("== threshold sweep (small batteries) ==", flush=True)
sweep = sweep_thresholds(mp, thresholds=(0.65, 0.70, 0.72, 0.75),
                         n_benign=2, n_attacks=4, seed=909)
for s in sweep:
    print(f"  th={s['threshold']:.2f} fp={s['fp_alerts_per_hour']}/hr "
          f"cov={s['attack_coverage_pct']}% lead={s['lead_median_min']}m",
          flush=True)

model_metrics = json.loads((ART / "metrics.json").read_text())
evasion_rep = {}
evp = ART / "evasion_report.json"
if evp.exists():
    evasion_rep = {"evasion": json.loads(evp.read_text())}
write_metrics_md(model_metrics, fp, lt, sweep, 0.72, extra=evasion_rep or None)

report = {"false_positive": fp, "lead_time": lt, "threshold_sweep": sweep,
          "calibrated_threshold": 0.72,
          "eval_seconds": round(time.time() - t0, 1)}
(ART / "eval_report.json").write_text(json.dumps(report, indent=2))
print(f"done in {report['eval_seconds']}s — metrics.md + eval_report.json updated",
      flush=True)
