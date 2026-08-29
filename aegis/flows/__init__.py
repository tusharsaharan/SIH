"""Bidirectional flow aggregator.

Mirrors the production eBPF rolling-window aggregation: packets are folded
into 5-second bidirectional flow statistics held **in memory only** - the
zero-upload design (no raw pcap ever hits disk). Produces the feature tensor
consumed by the forecasting model.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, Iterable, List, Tuple

from aegis import WINDOW_SECONDS

FlowKey = Tuple[str, str, int, int, str]  # (src, dst, sport, dport, proto)


@dataclass
class FlowStats:
    pkts: int = 0
    bytes: int = 0
    syn_count: int = 0
    synack_count: int = 0
    rst_count: int = 0
    fin_count: int = 0
    psh_count: int = 0
    ack_count: int = 0
    iat_sum: float = 0.0
    iat_sqsum: float = 0.0
    last_ts: float | None = None
    first_ts: float | None = None

    def add(self, ts: float, flags: int, size: int) -> None:
        if self.last_ts is not None:
            dt = ts - self.last_ts
            self.iat_sum += dt
            self.iat_sqsum += dt * dt
        if self.first_ts is None:
            self.first_ts = ts
        self.last_ts = ts
        self.pkts += 1
        self.bytes += size
        if flags & 0x02 and not flags & 0x10:
            self.syn_count += 1
        elif flags & 0x02 and flags & 0x10:
            self.synack_count += 1
        if flags & 0x04:
            self.rst_count += 1
        if flags & 0x01:
            self.fin_count += 1
        if flags & 0x08:
            self.psh_count += 1
        if flags & 0x10:
            self.ack_count += 1


def _canon(src: str, dst: str, sport: int, dport: int, proto: str) -> Tuple[FlowKey, bool]:
    """Canonicalize direction (lower IP string wins) -> (key, reversed)."""
    if (src, sport) <= (dst, dport):
        return (src, dst, sport, dport, proto), False
    return (dst, src, dport, sport, proto), True


class FlowAggregator:
    """Rolling 5s bidirectional flow aggregator (in-memory, zero pcap)."""

    def __init__(self, window: float = WINDOW_SECONDS):
        self.window = window
        self.flows: Dict[FlowKey, FlowStats] = defaultdict(FlowStats)

    def feed(self, packets: Iterable[Tuple[float, str, str, int, int, str, int, int]]) -> List[dict]:
        """Fold a batch of packets into per-flow dicts, one per window."""
        out: List[dict] = []
        for ts, src, dst, sport, dport, proto, flags, size in packets:
            key, _ = _canon(src, dst, sport, dport, proto)
            self.flows[key].add(ts, flags, size)
        return out

    def tick(self) -> List[dict]:
        """Emit + clear one window of aggregated flow stats."""
        rows: List[dict] = []
        for key, st in list(self.flows.items()):
            if st.pkts == 0:
                continue
            n = max(st.pkts - 1, 1)
            iat_mean = st.iat_sum / n
            iat_var = max(st.iat_sqsum / n - iat_mean * iat_mean, 0.0)
            rows.append({
                "src": key[0], "dst": key[1],
                "sport": key[2], "dport": key[3], "proto": key[4],
                "pkts": st.pkts, "bytes": st.bytes,
                "syn": st.syn_count, "synack": st.synack_count,
                "rst": st.rst_count, "fin": st.fin_count,
                "psh": st.psh_count, "ack": st.ack_count,
                "iat_mean": iat_mean, "iat_var": iat_var,
            })
        self.flows.clear()
        return rows


def windows_from_packets(
    packets: List[Tuple[float, str, str, int, int, str, int, int]],
    window: float = WINDOW_SECONDS,
) -> List[List[dict]]:
    """Slice packet timeline into W-second windows of aggregated flow rows."""
    packets = sorted(packets, key=lambda p: p[0])
    duration = packets[-1][0] if packets else 0.0
    n_win = int(math.ceil(duration / window)) or 1
    out: List[List[dict]] = []
    idx = 0
    for w in range(n_win):
        lo, hi = w * window, (w + 1) * window
        agg = FlowAggregator(window)
        while idx < len(packets) and packets[idx][0] < hi:
            agg.feed([packets[idx]])
            idx += 1
        rows = agg.tick()
        out.append(rows)
    return out
