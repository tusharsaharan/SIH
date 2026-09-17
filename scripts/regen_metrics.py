"""Regenerate docs/metrics.md from saved battery results (no recompute)."""
import io
import json
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aegis.ml.evaluate import write_metrics_md

ART = Path("aegis/ml/artifacts")
model_metrics = json.loads((ART / "metrics.json").read_text())
report = json.loads((ART / "eval_report.json").read_text())
write_metrics_md(model_metrics, report["false_positive"], report["lead_time"],
                 report["threshold_sweep"], report["calibrated_threshold"])
print("regenerated with baked-in Phase 3/4 sections")
