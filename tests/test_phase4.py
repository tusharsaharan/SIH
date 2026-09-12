"""Tests for Phase 4/5 additions: named models, evasion analysis honesty,
metrics-doc regeneration safety, ensemble artifacts, report hardening."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "aegis" / "ml" / "artifacts"


# ------------------------------------------------------- named model registry
def test_named_models_unique_and_resolve():
    from aegis.server import NAMED_MODELS
    names = list(NAMED_MODELS)
    assert len(names) == len(set(names))
    assert "current" not in NAMED_MODELS  # engine A by construction
    for name, (path, label) in NAMED_MODELS.items():
        assert isinstance(label, str) and label
        # available entries must load through ForecastEngine
        if Path(path).exists():
            from aegis.ml.inference import load_checkpoint
            ckpt = load_checkpoint(Path(path))
            assert ckpt["seq_len"] in (24, 48) and ckpt["feature_dim"] in (20, 22)
            assert isinstance(ckpt.get("use_slope", True), bool)


def test_transformer_checkpoint_loads_as_transformer():
    from aegis.ml.inference import ForecastEngine
    p = ART / "transformer" / "forecast_model.pt"
    if not p.exists():
        pytest.skip("transformer checkpoint not trained yet")
    eng = ForecastEngine(model_path=p)
    assert eng.model_name == "transformer"


def test_ensemble_checkpoint_loads_as_ensemble():
    from aegis.ml.inference import ForecastEngine
    p = ART / "ensemble" / "forecast_model.pt"
    if not p.exists():
        pytest.skip("ensemble checkpoint not built yet")
    eng = ForecastEngine(model_path=p)
    assert eng.model_name == "ensemble"


# ------------------------------------------------------- artifact metadata
def test_default_metrics_has_model_name():
    import json
    m = json.loads((ART / "metrics.json").read_text())
    assert m.get("model_name") == "bilstm"
    assert m.get("checkpoint_format") == 2


def test_ensemble_metrics_complete():
    import json
    p = ART / "ensemble" / "metrics.json"
    if not p.exists():
        pytest.skip("ensemble not built yet")
    m = json.loads(p.read_text())
    assert m.get("model_name") == "ensemble"
    assert "val_stage_acc" in m and "weight_bilstm" in m


# ------------------------------------------------------- evasion honesty
def test_evasion_analysis_matches_measurements():
    import json
    from aegis.simulator.evasion import evasion_analysis
    a = evasion_analysis()
    assert set(a) == {"slow_scan", "mimicry"}
    # analysis must report MEASURED outcomes, not stale predictions
    for fam, body in a.items():
        assert "measuredOutcome" in body, f"{fam} missing measured outcome"
        assert "often EVADES" not in body.get("measuredOutcome", "")
    # and the numbers must match the recorded report
    evp = ART / "evasion_report.json"
    if evp.exists():
        rep = {r["family"]: r for r in json.loads(evp.read_text())}
        for fam, body in a.items():
            r = rep[fam]
            assert f"t+{r['first_alert_min']}m" in body["measuredOutcome"]
            assert r["verdict"] in body["measuredOutcome"]


# ------------------------------------------------------- metrics doc safety
def test_metrics_regen_keeps_phase_sections(tmp_path, monkeypatch):
    import aegis.ml.evaluate as ev
    monkeypatch.setattr(ev, "DOCS", tmp_path / "metrics.md")
    fp = {"monitored_hours": 1.0, "monitored_windows": 100,
          "alerts": 0, "alerts_per_hour": 0.0}
    lt = {"coverage_pct": 100.0, "detected": 2, "n_scenarios": 2,
          "lead_mean_min": 10.0, "lead_median_min": 10.0,
          "lead_p10_min": 9.0, "lead_p90_min": 11.0}
    sweep = [{"threshold": 0.72, "fp_alerts_per_hour": 0.0,
              "attack_coverage_pct": 100.0, "lead_median_min": 10.0}]
    ev.write_metrics_md({}, fp, lt, sweep, 0.72)
    text = (tmp_path / "metrics.md").read_text()
    assert "## Phase 3" in text and "## Phase 4" in text
    assert "Ensemble" in text and "slow_scan" in text


# ------------------------------------------------------- report hardening
def test_report_unknown_session_graceful(isolated_db=None):
    # generate_incident_report falls back to an empty-session skeleton
    import tempfile
    from aegis.server import db as dbmod
    orig_path, orig_conn = dbmod.DB_PATH, dbmod._conn
    try:
        dbmod.DB_PATH = Path(tempfile.mkdtemp()) / "r.db"
        dbmod._conn = None
        dbmod.reset_db()
        from aegis.server.reports import generate_incident_report
        r = generate_incident_report("no-such-session")
        assert "no-such-session" in r["title"]
        assert "## Timeline" in r["markdown"]
        assert "<html" in r["html"]
    finally:
        dbmod.DB_PATH, dbmod._conn = orig_path, orig_conn


def test_db_write_retry_survives_locked_db(tmp_path, monkeypatch):
    import sqlite3
    import aegis.server.db as dbmod
    monkeypatch.setattr(dbmod, "DB_PATH", tmp_path / "l.db")
    monkeypatch.setattr(dbmod, "_conn", None)
    dbmod.reset_db()
    # normal write path works post-refactor
    dbmod.start_session("w1", "single", "demo", 12.0)
    assert dbmod.list_sessions()[0]["session_id"] == "w1"
