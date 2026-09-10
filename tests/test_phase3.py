"""Tests for Phase 3 additions: perimeter views, transformer/ensemble,
multistage + evasion simulators, persistence, replay, reports, intel."""
import sys
from pathlib import Path

import numpy as np
import pytest
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aegis.ml.model import (BiLSTMAttention, EnsembleForecaster,
                            TransformerForecaster)
from aegis.ml.perimeter import (bucket_perimeter_windows,
                                perimeter_packets_for_host)
from aegis.simulator.evasion import default_evasion_scenarios, evasion_packets
from aegis.simulator.multistage import (HOSTS, default_multi_scenario,
                                        is_internal_ip, multi_host_benign,
                                        multi_stage_packets)

ROOT = Path(__file__).resolve().parents[1]


# ------------------------------------------------------------------ perimeter
def test_is_internal_ip():
    assert is_internal_ip("10.20.0.10")
    assert is_internal_ip("10.20.1.7")
    assert not is_internal_ip("203.0.113.50")
    assert not is_internal_ip("8.8.8.8")


def test_perimeter_filters_internal():
    pkts = [
        (1.0, "10.20.1.5", "10.20.0.10", 50000, 443, "tcp", 0x18, 400),
        (1.1, "203.0.113.50", "10.20.0.10", 40000, 443, "tcp", 0x02, 60),
        (1.2, "10.20.0.10", "203.0.113.50", 443, 40000, "tcp", 0x12, 60),
        (2.0, "10.20.0.10", "10.20.0.20", 50001, 3306, "tcp", 0x18, 300),
    ]
    web = HOSTS["WEB"]["ip"]
    out = perimeter_packets_for_host(pkts, 0.0, 5.0, web)
    # only the 2 external-peer packets survive; internal chatter dropped
    assert len(out) == 2
    assert all("203.0.113.50" in (p[1], p[2]) for p in out)


def test_bucket_perimeter_windows():
    pkts = multi_host_benign(0.6, seed=11)
    n_win = int(max(p[0] for p in pkts) // 5.0) + 1
    buckets = bucket_perimeter_windows(pkts, n_win)
    assert set(buckets) == set(HOSTS)
    # pure-internal benign traffic -> (near-)empty perimeter views
    total = sum(len(w) for ws in buckets.values() for w in ws)
    assert total <= len(pkts)


# ----------------------------------------------------------------- multistage
def test_multistage_topology_hosts():
    assert set(HOSTS) == {"DC", "WEB", "DB", "FILE", "WS1"}
    assert HOSTS["WEB"]["ip"] == "10.20.0.10"


def test_multistage_attack_traverses_hosts():
    sc = default_multi_scenario(seed=3)
    atk = multi_stage_packets(sc, seed=4)
    touched = {ip for p in atk for ip in (p[1], p[2])}
    for h in ("WEB", "FILE", "DB", "DC"):
        assert HOSTS[h]["ip"] in touched, f"{h} never touched by attack"


# ------------------------------------------------------------------- evasion
def test_evasion_families_present():
    evs = default_evasion_scenarios(seed=5)
    fams = {e.family for e in evs}
    assert {"slow_scan", "mimicry"} <= fams
    for ev in evs:
        pkts = evasion_packets(ev, seed=6)
        assert len(pkts) > 50
        assert ev.detonation_minute > ev.recon_minutes


def test_evasion_slowscan_is_sparse():
    evs = [e for e in default_evasion_scenarios(seed=5) if e.family == "slow_scan"]
    pkts = evasion_packets(evs[0], seed=6)
    recon = [p for p in pkts if p[0] < evs[0].recon_minutes * 60]
    rate = len(recon) / (evs[0].recon_minutes * 60)
    assert rate < 0.5, f"slow scan too dense: {rate:.2f} pkt/s"


# ------------------------------------------------------------------ models
def _small_batch():
    return torch.rand(2, 48, 22)


def test_transformer_output_contract():
    m = TransformerForecaster(input_dim=22, seq_len=48)
    m.eval()
    out = m(_small_batch())
    assert set(out) == {"attack", "stage", "horizon", "attention"}
    assert out["attack"].shape == (2,)
    assert out["stage"].shape == (2, 5)
    assert out["horizon"].shape == (2,)
    assert bool(((out["attack"] >= 0) & (out["attack"] <= 1)).all())


def test_transformer_param_efficiency():
    t = TransformerForecaster(input_dim=22, seq_len=48)
    b = BiLSTMAttention(input_dim=22, seq_len=48)
    nt = sum(p.numel() for p in t.parameters())
    nb = sum(p.numel() for p in b.parameters())
    assert nt < nb, "transformer should be the lighter model"


def test_ensemble_forward_and_weights():
    a = BiLSTMAttention(input_dim=22, seq_len=48)
    b = TransformerForecaster(input_dim=22, seq_len=48)
    ens = EnsembleForecaster(a, b, weight_a=0.5)
    ens.eval()
    out = ens(_small_batch())
    assert out["attack"].shape == (2,)
    # weight extremes must reproduce members
    ens0 = EnsembleForecaster(a, b, weight_a=0.0)
    ens1 = EnsembleForecaster(a, b, weight_a=1.0)
    x = _small_batch()
    assert torch.allclose(ens1(x)["attack"], a(x)["attack"], atol=1e-5)
    assert torch.allclose(ens0(x)["attack"], b(x)["attack"], atol=1e-5)


def test_ensemble_checkpoint_roundtrip(tmp_path):
    from aegis.ml.inference import ForecastEngine
    a = BiLSTMAttention(input_dim=22, seq_len=48)
    b = TransformerForecaster(input_dim=22, seq_len=48)
    ens = EnsembleForecaster(a, b, weight_a=0.4)
    ckpt_path = tmp_path / "ens.pt"
    torch.save({"state_dict_a": a.state_dict(),
                "state_dict_b": b.state_dict(),
                "weight_a": 0.4, "seq_len": 48, "feature_dim": 22,
                "use_slope": True, "model_name": "ensemble"}, ckpt_path)
    eng = ForecastEngine(model_path=ckpt_path)
    assert eng.model_name == "ensemble"
    assert abs(eng.model.weight_a - 0.4) < 1e-9


# --------------------------------------------------------------- db + intel
@pytest.fixture()
def isolated_db(tmp_path, monkeypatch):
    from aegis.server import db
    import aegis.server.db as dbmod
    monkeypatch.setattr(dbmod, "DB_PATH", tmp_path / "t.db")
    monkeypatch.setattr(dbmod, "_conn", None)
    db.reset_db()
    return db


def test_db_session_alert_action_roundtrip(isolated_db):
    db = isolated_db
    db.start_session("s1", "multi", "demo", 18.0)
    db.record_alert("s1", "WEB", 4.0, 0.9, "TA0043", "recon", 5.0,
                    [{"feature": "syn_ratio", "importance": 0.5}])
    db.record_action("s1", "s1:WEB", "WEB", "isolate", actor="analyst",
                     state="contained")
    db.end_session("s1", 1, "ok")
    assert len(db.session_alerts("s1")) == 1
    assert db.session_actions("s1")[0]["state"] == "contained"
    assert db.list_sessions()[0]["n_alerts"] == 1


def test_intel_enrichment(isolated_db):
    from aegis.server import intel as intelmod
    from aegis.server import db as _db
    _db.seed_intel_if_empty([{
        "ip": "203.0.113.50", "reputation": 0.08, "geo": "Eastern Europe",
        "first_seen": "2026-06-14", "campaigns": ["SILENT-MONGOOSE"]}])
    e = intelmod.enrich_alert("203.0.113.50", 0.9, "TA0043", [])
    assert e["verdict"] == "known-bad"
    assert e["primaryCampaign"] == "SILENT-MONGOOSE"
    e2 = intelmod.enrich_alert("9.9.9.9", 0.5, "TA0043", [])
    assert e2["verdict"] == "unlisted"


# ------------------------------------------------------------------ replay
def _replay_mod():
    import importlib
    return importlib.import_module("aegis.server.replay")


def test_replay_save_load_roundtrip(tmp_path, monkeypatch):
    repl = _replay_mod()
    monkeypatch.setattr(repl, "REPLAY_DIR", tmp_path)
    pkts = [(0.5, "a", "b", 1, 80, "tcp", 0x02, 60),
            (5.5, "b", "a", 80, 1, "tcp", 0x12, 60)]
    p = repl.save_recording("t1", "single", pkts, 12.0, "1.2.3.4", "demo")
    assert p.exists()
    rec = repl.load_recording("t1")
    assert rec["n_packets"] == 2 and rec["detonation_min"] == 12.0
    assert [r["session_id"] for r in repl.list_recordings()] == ["t1"]


def test_replay_ab_short_session():
    from aegis.ml.inference import ForecastEngine
    repl = _replay_mod()
    pkts = []
    for i in range(1500):
        t = i * 0.4  # 600s span -> 120 windows > 48-window buffer
        pkts.append((t, "203.0.113.9", "10.20.0.1", 40000 + i % 500, 443,
                     "tcp", 0x02, 60))
    a = ForecastEngine()
    b = ForecastEngine()
    out = repl.replay_ab(pkts, a, b)
    assert "trajectoryA" in out and "trajectoryB" in out
    assert len(out["trajectoryA"]) == len(out["trajectoryB"])
    assert len(out["trajectoryA"]) > 0


# ------------------------------------------------------------------ reports
def test_report_generation(isolated_db):
    from aegis.server import reports
    db = isolated_db
    db.start_session("r1", "multi", "demo", 18.0)
    db.record_alert("r1", "WEB", 4.0, 0.95, "TA0043", "Network Scan / Probe",
                    9.5, [{"feature": "syn_ratio", "importance": 0.6}])
    db.record_action("r1", "r1:WEB", "WEB", "isolate", actor="auto-soar",
                     state="contained")
    r = reports.generate_incident_report("r1")
    assert "r1" in r["title"]
    assert "## Timeline" in r["markdown"]
    assert "<html" in r["html"]
    assert db.get_report("r1")["title"] == r["title"]
