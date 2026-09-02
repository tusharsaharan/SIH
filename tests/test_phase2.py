"""Tests for Phase 2 additions: AST scanner, evaluate harness, CIC loader."""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aegis.features import FEATURE_DIM, SEQ_LEN, SequenceFeaturizer
from aegis.ml import cic_loader
from aegis.playbooks import generate_playbook
from aegis.playbooks.ast_scanner import scan_file, scan_tree
from aegis.simulator import AttackScenario, attack_packets, benign_packets
from aegis.flows import windows_from_packets

ROOT = Path(__file__).resolve().parents[1]
SANDBOX_APP = ROOT / "sandbox" / "vulnerable-app" / "app.py"


# ---------------------------------------------------------------- ast scanner
def test_ast_scanner_finds_planted_vulns():
    fs = scan_file(SANDBOX_APP)
    rules = {f.rule_id for f in fs}
    assert {"SQLI-001", "CMD-001", "SEC-001", "SEC-002", "SEC-003"} <= rules
    assert all(f.scanner == "aegis-ast" for f in fs)


def test_ast_scanner_clean_code():
    src = ROOT / "aegis" / "features" / "__init__.py"
    fs = scan_file(src)
    # features module has no planted vulns
    assert not [f for f in fs if f.severity == "HIGH"]


def test_scanner_feeds_playbook():
    fs = scan_file(SANDBOX_APP)
    pb = generate_playbook(fs, stage_ctx={"mitre": "TA0006"})
    families = {s["family"] for s in pb["steps"]}
    assert "sql-injection" in families
    assert "command-injection" in families
    assert "hardcoded-secret" in families


def test_scan_tree_bounded():
    fs = scan_tree(ROOT / "aegis", max_files=5)
    assert isinstance(fs, list)


# ------------------------------------------------------------------ evaluate
def test_lead_time_and_fp_smoke():
    """Tiny battery: the harness functions run and return sane shapes."""
    from aegis.ml.evaluate import (false_positive_rate, lead_time_distribution,
                                  calibrate, sweep_thresholds)
    mp = ROOT / "aegis" / "ml" / "artifacts" / "forecast_model.pt"
    if not mp.exists():
        pytest.skip("model artifact not trained yet")

    fp = false_positive_rate(mp, n_sessions=1, seed=42)
    assert fp["monitored_windows"] > 0
    assert fp["alerts_per_hour"] >= 0.0

    lt = lead_time_distribution(mp, n_scenarios=1, seed=43)
    assert lt["n_scenarios"] == 1
    assert lt["coverage_pct"] in (0.0, 100.0)

    sweep = sweep_thresholds(mp, thresholds=(0.9,), n_benign=1, n_attacks=1, seed=44)
    assert len(sweep) == 1 and sweep[0]["threshold"] == 0.9
    chosen = calibrate(mp, sweep)
    assert 0.5 <= chosen <= 0.99


# ------------------------------------------------------------------- cic
def test_cic_row_mapping():
    row = {
        " Total Forward Packets": "10", " Total Backward Packets": "8",
        "SYN Flag Count": "5", "FIN Flag Count": "0", "RST Flag Count": "0",
        "ACK Flag Count": "6", "PSH Flag Count": "3",
        "Flow IAT Mean": "1200.0", "Flow IAT Std": "300.0",
        "Flow Duration": "500000", "Source IP": "192.168.10.5",
        "Destination IP": "192.168.10.50", "Source Port": "443",
        "Destination Port": "8080", "Label": "PortScan",
    }
    f = cic_loader.cic_row_to_flow(row)
    assert f["pkts"] == 18 and f["syn"] == 5 and f["_attack"] == 1
    assert f["dport"] == 8080

    benign = dict(row, **{"Label": "BENIGN"})
    assert cic_loader.cic_row_to_flow(benign)["_attack"] == 0


def test_cic_pipeline_synthetic(tmp_path):
    """End-to-end CIC path on a synthetic CSV: rows -> windows -> X,y."""
    import csv
    csv_path = tmp_path / "mini.csv"
    cols = [" Total Forward Packets", " Total Backward Packets", "SYN Flag Count",
            "FIN Flag Count", "RST Flag Count", "ACK Flag Count", "PSH Flag Count",
            "Flow IAT Mean", "Flow IAT Std", "Flow Duration", "Source IP",
            "Destination IP", "Source Port", "Destination Port", "Label"]
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for i in range(2000):
            # first 300 rows benign-only, then interleaved PortScan
            label = "BENIGN" if i < 300 else ("PortScan" if i % 5 in (1, 2) else "BENIGN")
            w.writerow({
                " Total Forward Packets": "4", " Total Backward Packets": "2",
                "SYN Flag Count": "4" if label != "BENIGN" else "1",
                "FIN Flag Count": "0", "RST Flag Count": "0",
                "ACK Flag Count": "2", "PSH Flag Count": "0",
                "Flow IAT Mean": "1000", "Flow IAT Std": "200",
                "Flow Duration": "300000", "Source IP": "192.168.10.5",
                "Destination IP": "192.168.10.50", "Source Port": "51000",
                "Destination Port": str(8000 + (i % 40)), "Label": label,
            })

    flows = cic_loader.load_cic_csv(csv_path)
    assert len(flows) == 2000
    windows, labels = cic_loader.flows_to_windows(flows)
    assert windows and len(windows) == len(labels)
    assert any(labels), "expected some attack windows"
    X, y = cic_loader.windows_to_sequences(windows, labels, seq_len=16, stride=1)
    assert X.ndim == 3 and X.shape[1:] == (16, FEATURE_DIM)
    assert set(np.unique(y)) <= {0, 1}


def test_featurizer_parity_train_vs_eval():
    """SequenceFeaturizer produces identical vectors for the same stream."""
    sc = AttackScenario("t", "203.0.113.9", "10.20.0.1", 5.0, 7.0, "apt")
    pkts = benign_packets(7.5, seed=9) + attack_packets(sc, seed=10)
    pkts.sort(key=lambda p: p[0])
    windows = windows_from_packets(pkts)
    fz1 = SequenceFeaturizer()
    fz2 = SequenceFeaturizer()
    for rows in windows[:40]:
        a, b = fz1.feed(rows), fz2.feed(rows)
        assert a == b, "featurizer is stateful per-stream; identical streams must match"
