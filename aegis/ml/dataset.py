"""Dataset builder: scenarios -> (X, y_attack, y_stage, y_horizon).

For each attack scenario we generate the full packet timeline, slice it into
5s flow windows, featurize via the shared SequenceFeaturizer (base features
+ temporal ramp slopes), and label each sequence with:
  y_attack  : 1.0 if a detonation will occur within HORIZON minutes AFTER the
              sequence ends (the forecasting target), else 0
  y_stage   : current ATT&CK stage (max of window labels)
  y_horizon : minutes from sequence end to detonation / 30 (if attack)

Benign sequences get y_attack=0, y_stage=0.

Sequences are strided every 2 windows (10s) for training density.
"""

from __future__ import annotations

import random
from typing import List, Tuple

import numpy as np

from aegis import WINDOW_SECONDS
from aegis.features import FEATURE_DIM, SEQ_LEN, SequenceFeaturizer
from aegis.ml.model import HORIZON_MAX_MIN
from aegis.ml.wincache import benign_windows, scenario_windows
from aegis.simulator import AttackScenario

WINDOWS_PER_MIN = 60.0 / WINDOW_SECONDS


def _stage_label(rows: List[dict], scenario: AttackScenario, win_end_min: float) -> int:
    """Assign the current ATT&CK stage for a window ending at win_end_min."""
    s = scenario
    recon_end = s.recon_minutes
    enum_end = recon_end + max(2.0, s.recon_minutes * 0.2)
    c2_end = enum_end + max(2.0, s.recon_minutes * 0.15)
    if win_end_min < recon_end * 0.35:
        # early ramp may be too quiet to call - still recon (low and slow)
        return 1 if any(r["syn"] > 0 for r in rows) else 0
    if win_end_min < recon_end:
        return 1
    if win_end_min < enum_end:
        return 2
    if win_end_min < max(c2_end, s.detonation_minute):
        return 3
    return 4


def _featurize_stream(windows: List[List[dict]], use_slope: bool) -> List[List[float]]:
    """Run one SequenceFeaturizer over a full window stream (slope stateful)."""
    fz = SequenceFeaturizer(use_slope=use_slope)
    return [fz.feed(rows) for rows in windows]


def _rows_from_packets(packets: List[tuple]) -> List[dict]:
    """Aggregate a packet slice into flow rows (one window)."""
    from aegis.flows import FlowAggregator
    agg = FlowAggregator(5.0)
    agg.feed(packets)
    return agg.tick()


def build_scenario_tensor(
    scenario: AttackScenario,
    seed: int | None = None,
    with_benign: bool = True,
    seq_len: int = SEQ_LEN,
    use_slope: bool = True,
    stride: int = 2,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Return (X, y_attack, y_stage, y_horizon) arrays for one scenario."""
    rng = random.Random(seed if seed is not None else hash(scenario.name) & 0xFFFF)
    sseed = rng.randint(0, 10**6)
    windows = scenario_windows(scenario, sseed, with_benign=with_benign)

    feats = _featurize_stream(windows, use_slope)
    stages: List[int] = []
    for i, rows in enumerate(windows):
        end_min = (i + 1) / WINDOWS_PER_MIN
        stages.append(_stage_label(rows, scenario, end_min))

    X, ya, ys, yh = [], [], [], []
    det_win = int(scenario.detonation_minute * WINDOWS_PER_MIN)
    for start in range(0, len(feats) - seq_len, stride):
        seq = feats[start:start + seq_len]
        end_win = start + seq_len
        mins_to_det = (det_win - end_win) / WINDOWS_PER_MIN
        within = 0 < mins_to_det <= HORIZON_MAX_MIN
        X.append(seq)
        ya.append(1.0 if within else 0.0)
        ys.append(max(stages[start:end_win]))
        yh.append(min(max(mins_to_det, 0.0), HORIZON_MAX_MIN) / HORIZON_MAX_MIN if within else 0.0)
    return (
        np.asarray(X, dtype=np.float32),
        np.asarray(ya, dtype=np.float32),
        np.asarray(ys, dtype=np.int64),
        np.asarray(yh, dtype=np.float32),
    )


def build_dataset(
    n_scenarios: int = 24,
    n_benign: int = 8,
    seed: int = 7,
    seq_len: int = SEQ_LEN,
    use_slope: bool = True,
    n_multihost_benign: int = 6,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Full dataset: attack scenarios + benign sessions -> train/val split.

    Benign sessions include both the classic single-server profile AND
    per-host views of the multi-host segment (so models learn role-based
    benign baselines: DC kerberos/LDAP, DB query chatter, SMB file ops...).
    """
    from aegis.simulator import default_scenarios
    from aegis.simulator.multistage import (
        HOSTS, HOST_IPS as HOST_IP_TO_NAME, multi_host_benign,
    )
    from aegis.ml.perimeter import bucket_perimeter_windows

    Xs, As, Ss, Hs = [], [], [], []
    for i, sc in enumerate(default_scenarios(n_scenarios, seed=seed)):
        X, ya, ys, yh = build_scenario_tensor(
            sc, seed=seed * 1000 + i, seq_len=seq_len, use_slope=use_slope)
        if len(X):
            Xs.append(X); As.append(ya); Ss.append(ys); Hs.append(yh)

    # pure benign sessions (y=0 everywhere, stage 0)
    Xs_b, As_b, Ss_b, Hs_b = [], [], [], []

    def _add_benign_seq(windows):
        feats = _featurize_stream(windows, use_slope)
        for start in range(0, len(feats) - seq_len, 2):
            seq = np.asarray(feats[start:start + seq_len], dtype=np.float32)
            Xs_b.append(seq[np.newaxis, :, :])
            As_b.append(np.array([0.0], dtype=np.float32))
            Ss_b.append(np.array([0], dtype=np.int64))
            Hs_b.append(np.array([0.0], dtype=np.float32))

    for j in range(n_benign):
        dur = random.uniform(25.0, 50.0)
        windows = benign_windows(dur, seed=seed * 777 + j)
        _add_benign_seq(windows)

    # multi-host segment benign: PERIMETER view per host (mirrors live engines
    # - traffic with non-internal peers; attacks live here, internal chatter
    # is the benign baseline the model must learn)
    for j in range(n_multihost_benign):
        dur = random.uniform(25.0, 45.0)
        pkts = multi_host_benign(dur, seed=seed * 555 + j)
        pkts.sort(key=lambda p: p[0])
        n_win = int(pkts[-1][0] // 5.0) + 1
        buckets = bucket_perimeter_windows(pkts, n_win)
        for hname in HOSTS:
            fz = SequenceFeaturizer(use_slope=use_slope)
            feats = [fz.feed(_rows_from_packets(win_pkts))
                     for win_pkts in buckets[hname]]
            for start in range(0, len(feats) - seq_len, 4):
                seq = np.asarray(feats[start:start + seq_len], dtype=np.float32)
                Xs_b.append(seq[np.newaxis, :, :])
                As_b.append(np.array([0.0], dtype=np.float32))
                Ss_b.append(np.array([0], dtype=np.int64))
                Hs_b.append(np.array([0.0], dtype=np.float32))

    # multi-host LATERAL attack scenarios: PERIMETER view per host, labeled
    # y=1 while the kill-chain is active and this host's perimeter view
    # carries attack traffic (keeps live multi-session traffic in-distribution)
    for j in range(n_multihost_benign // 2):
        from aegis.simulator.multistage import (default_multi_scenario,
                                                multi_stage_packets)
        msc = default_multi_scenario(seed=seed * 991 + j * 13)
        pkts = multi_host_benign(msc.detonation_minute + 2.0,
                                 seed=seed * 556 + j)
        atk = multi_stage_packets(msc, seed=seed * 992 + j * 17)
        pkts = sorted(pkts + atk, key=lambda p: p[0])
        n_win = int(pkts[-1][0] // 5.0) + 1
        buckets = bucket_perimeter_windows(pkts, n_win)
        det_win = int(msc.detonation_minute * 12)
        for hname in HOSTS:
            fz = SequenceFeaturizer(use_slope=use_slope)
            feats = [fz.feed(_rows_from_packets(win_pkts))
                     for win_pkts in buckets[hname]]
            # first window where this host's perimeter view carries ANY
            # traffic (precomputed once - O(n) instead of per-sequence scans)
            first_touched = next(
                (i for i, b in enumerate(buckets[hname]) if b), None)
            for start in range(0, len(feats) - seq_len, 4):
                end_win = start + seq_len
                mins = end_win / 12.0
                # sequence overlaps traffic in this host's perimeter view?
                touched = (first_touched is not None
                           and first_touched < end_win + 24)
                if not touched:
                    y, stage = 0.0, 0
                elif mins >= msc.detonation_minute:
                    y, stage = 0.0, 4      # after detonation: label stays 0
                elif mins > msc.recon_minutes:
                    y, stage = 1.0, 3
                else:
                    y, stage = 1.0, 1
                seq = np.asarray(feats[start:start + seq_len], dtype=np.float32)
                Xs_b.append(seq[np.newaxis, :, :])
                As_b.append(np.array([y], dtype=np.float32))
                Ss_b.append(np.array([stage], dtype=np.int64))
                if y:
                    mins_to_det = (det_win - end_win) / 12.0
                    Hs_b.append(np.array([max(0.0, min(mins_to_det / 30.0, 1.0))],
                                         dtype=np.float32))
                else:
                    Hs_b.append(np.array([0.0], dtype=np.float32))

    X_all = np.concatenate(
        [np.asarray(x, dtype=np.float32) for x in Xs + Xs_b], axis=0)
    A_all = np.concatenate(
        [np.asarray(x, dtype=np.float32) for x in As + As_b]).astype(np.float32)
    S_all = np.concatenate(
        [np.asarray(x, dtype=np.int64) for x in Ss + Ss_b]).astype(np.int64)
    H_all = np.concatenate(
        [np.asarray(x, dtype=np.float32) for x in Hs + Hs_b]).astype(np.float32)

    # shuffle then split 80/20
    idx = np.random.RandomState(seed).permutation(len(X_all))
    n_train = int(len(idx) * 0.8)
    tr, va = idx[:n_train], idx[n_train:]
    return (
        X_all[tr], X_all[va],
        A_all[tr], A_all[va],
        S_all[tr], S_all[va],
        H_all[tr], H_all[va],
    )
