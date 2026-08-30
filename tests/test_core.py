"""Unit tests for simulator, flows, features, model, inference, playbooks."""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aegis.features import FEATURE_DIM, SEQ_LEN, SequenceFeaturizer, clip_features, window_to_features
from aegis.flows import FlowAggregator, windows_from_packets
from aegis.ml.attack_stages import NUM_STAGES, stage_info
from aegis.ml.dataset import build_dataset
from aegis.ml.model import BiLSTMAttention
from aegis.playbooks import Finding, generate_playbook, map_finding, render_markdown
from aegis.simulator import AttackScenario, attack_packets, benign_packets


# ------------------------------------------------------------------ simulator
def test_benign_packets_shape():
    pkts = benign_packets(2.0, seed=1)
    assert pkts and all(len(p) == 8 for p in pkts)
    assert all(p[0] <= 120.5 for p in pkts)


def test_attack_phases_present():
    sc = AttackScenario("t", "1.2.3.4", "10.20.0.1", 10.0, 14.0, "apt")
    pkts = attack_packets(sc, seed=2)
    syns = [p for p in pkts if p[6] == 0x02]
    dets = [p for p in pkts if p[0] >= sc.detonation_minute * 60]
    assert syns, "recon SYN packets missing"
    assert dets, "detonation burst missing"


# --------------------------------------------------------------------- flows
def test_flow_aggregator_bidirectional():
    agg = FlowAggregator()
    agg.feed([
        (1.0, "10.0.0.2", "10.0.0.1", 55555, 443, "tcp", 0x02, 60),
        (1.1, "10.0.0.1", "10.0.0.2", 443, 55555, "tcp", 0x12, 60),
    ])
    rows = agg.tick()
    assert len(rows) == 1
    r = rows[0]
    assert r["pkts"] == 2 and r["syn"] == 1 and r["synack"] == 1
    assert r["src"] == "10.0.0.1"  # canonical ordering


def test_windows_slice():
    pkts = benign_packets(0.5, seed=3)
    ws = windows_from_packets(pkts)
    assert 1 <= len(ws) <= 8


# ------------------------------------------------------------------ features
def test_feature_dim():
    assert FEATURE_DIM == 22
    v = window_to_features([{"src": "a", "dst": "b", "sport": 1, "dport": 443,
                             "proto": "tcp", "pkts": 10, "bytes": 5000,
                             "syn": 9, "synack": 0, "rst": 0, "fin": 0,
                             "psh": 5, "ack": 8, "iat_mean": 0.1, "iat_var": 0.01}])
    assert len(v) == FEATURE_DIM - 2          # base features (slopes separate)
    assert 0.0 < v[3] < 1.0                   # syn ratio
    clipped = clip_features([0.5, 2.0, -1.0])
    assert clipped == [0.5, 1.0, 0.0]


def test_sequence_featurizer_slopes():
    fz = SequenceFeaturizer(use_slope=True)
    empty_rows = [{"src": "a", "dst": "b", "sport": 1, "dport": 443,
                   "proto": "tcp", "pkts": 1, "bytes": 60, "syn": 0,
                   "synack": 0, "rst": 0, "fin": 0, "psh": 0, "ack": 1,
                   "iat_mean": 0.0, "iat_var": 0.0}]
    ramp_rows = [{"src": "a", "dst": "b", "sport": 1, "dport": 443,
                  "proto": "tcp", "pkts": 20, "bytes": 1200, "syn": 20,
                  "synack": 0, "rst": 0, "fin": 0, "psh": 0, "ack": 0,
                  "iat_mean": 0.0, "iat_var": 0.0}]
    vecs = [fz.feed(empty_rows if i < 6 else ramp_rows) for i in range(12)]
    assert all(len(v) == FEATURE_DIM for v in vecs)
    # after a rising SYN ramp, syn_slope must be clearly positive
    assert vecs[-1][FEATURE_DIM - 2] > 0.1
    # no-slope mode zeroes the tail
    fz2 = SequenceFeaturizer(use_slope=False)
    v2 = [fz2.feed(ramp_rows) for _ in range(3)][-1]
    assert v2[-2:] == [0.0, 0.0]


# --------------------------------------------------------------------- model
def test_model_shapes():
    m = BiLSTMAttention(input_dim=FEATURE_DIM, seq_len=SEQ_LEN)
    import torch
    x = torch.rand(4, SEQ_LEN, FEATURE_DIM)
    out = m(x)
    assert out["attack"].shape == (4,)
    assert out["stage"].shape == (4, NUM_STAGES)
    assert out["horizon"].shape == (4,)


def test_stage_info_bounds():
    assert stage_info(0)["ta"] is None
    assert stage_info(4)["ta"] == "TA0042"
    assert stage_info(99)["id"] == 4     # clamps


def test_dataset_small():
    Xtr, Xva, Atr, Ava, Str, Sva, Htr, Hva = build_dataset(n_scenarios=2, n_benign=1, seed=5)
    assert Xtr.ndim == 3 and Xtr.shape[1:] == (SEQ_LEN, FEATURE_DIM)
    assert Ava.sum() >= 0                 # val may be tiny but valid
    assert ((Atr == 0) | (Atr == 1)).all()


# ----------------------------------------------------------------- playbooks
def test_playbook_generation():
    fs = [
        Finding("bandit", "B608", "HIGH", "app.py", 30, "SQL injection via f-string"),
        Finding("bandit", "B602", "HIGH", "app.py", 40, "subprocess shell=True"),
        Finding("semgrep", "xss.render.unescaped", "MEDIUM", "ui.py", 12, "unescaped output"),
    ]
    pb = generate_playbook(fs, stage_ctx={"mitre": "TA0006", "confidence": 0.94})
    assert pb["steps"], "no steps generated"
    assert pb["steps"][0]["severity"] == "HIGH"
    assert all(s["contain"] and s["harden"] and s["verify"] for s in pb["steps"])
    md = render_markdown(pb)
    assert "Mitigation Playbook" in md and "contain" in md.lower()


def test_finding_mapping():
    assert map_finding(Finding("bandit", "B608", "HIGH", "a", 1, "x")) == "sql-injection"
    assert map_finding(Finding("semgrep", "python.lang.security.audit.subprocess-shell", "H", "a", 1, "x")) == "command-injection"


# ----------------------------------------------------------------- inference
@pytest.mark.skipif(
    not (Path(__file__).resolve().parents[1] / "aegis" / "ml" / "artifacts" / "forecast_model.pt").exists(),
    reason="model artifact not trained yet - run python -m aegis.ml.train")
def test_inference_engine():
    from aegis.ml.inference import ForecastEngine
    eng = ForecastEngine()
    # scenario long enough to fill the seq_len window buffer + emit forecasts
    sc = AttackScenario("t", "203.0.113.9", "10.20.0.1", 8.0, 12.0, "apt")
    pkts = benign_packets(12.5, seed=9) + attack_packets(sc, seed=10)
    pkts.sort(key=lambda p: p[0])
    fired = 0
    for rows in windows_from_packets(pkts):
        f = eng.feed_window(rows)
        if f:
            assert 0 <= f.attack_prob <= 1
            assert f.shap_top
            fired += 1
    assert fired >= eng.seq_len // 2
