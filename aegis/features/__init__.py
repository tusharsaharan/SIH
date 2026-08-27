"""Feature engineering: flow windows -> model-ready feature vectors.

Schema is CIC-IDS2017-compatible: per-window aggregates over all flows -
bidirectional packet counts, byte volumes, TCP flag ratios, inter-arrival
statistics, port entropy, and distinct-endpoint counts - plus two
**temporal ramp features** (least-squares slopes over the recent windows)
that expose the low-and-slow reconnaissance ramp to the forecaster early.

Each window becomes one FEATURE_DIM vector; a sequence of T consecutive
vectors is the model input tensor (T x FEATURE_DIM).

`SequenceFeaturizer` is the single shared path used by BOTH training and
live inference, guaranteeing feature parity between lab and deployment.
"""

from __future__ import annotations

import math
from collections import Counter, deque
from typing import Deque, Dict, List

FEATURE_NAMES = [
    "pkt_rate",          # packets / window
    "byte_rate",         # bytes / window
    "flow_count",        # distinct bidirectional flows
    "syn_ratio",         # SYN pkts / total pkts
    "synack_ratio",
    "rst_ratio",
    "fin_ratio",
    "psh_ratio",
    "ack_ratio",
    "udp_ratio",         # udp pkts / total pkts
    "iat_mean",          # mean inter-arrival (s) across flows
    "iat_std",
    "iat_max",
    "port_entropy",      # Shannon entropy over destination ports
    "distinct_dports",
    "distinct_hosts",
    "small_pkt_ratio",   # pkts < 100 bytes (probes/beacons)
    "mean_pkt_size",
    "pkt_size_std",
    "max_flow_pkts",     # busiest single flow
    "syn_slope",         # ramp: total predicted SYN-ratio rise over SLOPE_WIN
    "rate_slope",        # ramp: total predicted pkt-rate rise over SLOPE_WIN
]

FEATURE_DIM = len(FEATURE_NAMES)          # 22
SEQ_LEN = 48                              # 48 x 5s = 4 minutes of lookback
SLOPE_WIN = 12                            # slope fitted over last 12 windows


def _entropy(counts: Counter) -> float:
    total = sum(counts.values())
    if total <= 1:
        return 0.0
    ent = 0.0
    for c in counts.values():
        p = c / total
        if p > 0:
            ent -= p * math.log2(p)
    return ent / math.log2(total)     # normalized to [0, 1]


def window_to_features(rows: List[dict]) -> List[float]:
    """Aggregate one window's flow rows into the 20 base features."""
    if not rows:
        return [0.0] * (FEATURE_DIM - 2)

    total_pkts = sum(r["pkts"] for r in rows) or 1
    total_bytes = sum(r["bytes"] for r in rows)
    total_syn = sum(r["syn"] for r in rows)
    total_synack = sum(r["synack"] for r in rows)
    total_rst = sum(r["rst"] for r in rows)
    total_fin = sum(r["fin"] for r in rows)
    total_psh = sum(r["psh"] for r in rows)
    total_ack = sum(r["ack"] for r in rows)
    udp_pkts = sum(r["pkts"] for r in rows if r["proto"] == "udp")

    # inter-arrival stats weighted by flow packet counts
    iat_mean_w = sum(r["iat_mean"] * r["pkts"] for r in rows) / total_pkts
    iat_var_w = sum(r["iat_var"] * r["pkts"] for r in rows) / total_pkts
    iat_std = math.sqrt(max(iat_var_w, 0.0))
    iat_max = max((r["iat_mean"] for r in rows), default=0.0)

    dport_counts = Counter()
    hosts = set()
    small_pkts = 0
    sizes: List[float] = []
    for r in rows:
        dport_counts[r["dport"]] += r["pkts"]
        hosts.add(r["src"]); hosts.add(r["dst"])
        if r["bytes"] and r["pkts"]:
            mean_size = r["bytes"] / r["pkts"]
            sizes.append(mean_size)
            if mean_size < 100:
                small_pkts += r["pkts"]
    mean_size = sum(sizes) / len(sizes) if sizes else 0.0
    size_std = (sum((s - mean_size) ** 2 for s in sizes) / len(sizes)) ** 0.5 if len(sizes) > 1 else 0.0

    return [
        total_pkts / 500.0,
        total_bytes / 500_000.0,
        len(rows) / 100.0,
        total_syn / total_pkts,
        total_synack / total_pkts,
        total_rst / total_pkts,
        total_fin / total_pkts,
        total_psh / total_pkts,
        total_ack / total_pkts,
        udp_pkts / total_pkts,
        min(iat_mean_w, 10.0),
        min(iat_std, 10.0),
        min(iat_max, 10.0),
        _entropy(dport_counts),
        min(len(dport_counts), 64) / 64.0,
        min(len(hosts), 64) / 64.0,
        small_pkts / total_pkts,
        mean_size / 1500.0,
        size_std / 1500.0,
        max((r["pkts"] for r in rows), default=0) / 100.0,
    ]


def clip_features(vec: List[float]) -> List[float]:
    """Clip to [0, 1]-ish ranges for stable training."""
    return [max(0.0, min(1.0, v)) for v in vec]


def _lsq_slope_total(series: List[float]) -> float:
    """Least-squares slope over the series, scaled to total change across it.

    slope*len ≈ predicted first->last rise, so values land in ~[-1, 1] for
    our [0, 1]-clipped features. Returns 0.0 for < 2 points.
    """
    n = len(series)
    if n < 2:
        return 0.0
    mean_x = (n - 1) / 2.0
    mean_y = sum(series) / n
    num = sum((i - mean_x) * (y - mean_y) for i, y in enumerate(series))
    den = sum((i - mean_x) ** 2 for i in range(n))
    slope = num / den if den else 0.0
    return max(-1.0, min(1.0, slope * n))


class SequenceFeaturizer:
    """Stateful per-stream featurizer: base features + temporal ramp slopes.

    Shared by dataset building and live inference so the model always sees
    identically-computed tensors (train/serve parity).
    """

    def __init__(self, use_slope: bool = True, slope_win: int = SLOPE_WIN):
        self.use_slope = use_slope
        self.slope_win = slope_win
        self.hist: Deque[List[float]] = deque(maxlen=slope_win)

    def reset(self) -> None:
        self.hist.clear()

    def feed(self, rows: List[dict]) -> List[float]:
        """Fold one window of flow rows into a full FEATURE_DIM vector."""
        base = clip_features(window_to_features(rows))
        self.hist.append(base)
        if not self.use_slope:
            return base + [0.0, 0.0]
        syn_series = [v[3] for v in self.hist]     # syn_ratio
        rate_series = [v[0] for v in self.hist]    # pkt_rate
        return base + [
            max(-1.0, min(1.0, _lsq_slope_total(syn_series))),
            max(-1.0, min(1.0, _lsq_slope_total(rate_series))),
        ]

    def feature_dim(self) -> int:
        return FEATURE_DIM
