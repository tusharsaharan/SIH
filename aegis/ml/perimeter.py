"""Per-host perimeter views: traffic between a host and NON-internal peers.

Attacks live at the perimeter (attacker IPs are external), while the bulk
of per-host benign volume is internal (clients, inter-server chatter).
Featurizing the perimeter view keeps attack signal visible instead of
drowned by internal traffic. Used identically by dataset building AND the
live server pipeline (train/serve parity).
"""

from __future__ import annotations

from typing import Dict, List

from aegis.simulator.multistage import HOSTS, is_internal_ip


def perimeter_packets_for_host(packets, lo: float, hi: float,
                               host_ip: str) -> List[tuple]:
    """Window packets touching `host_ip` where the peer is NOT internal."""
    out = []
    for ts, src, dst, sp, dp, proto, flags, size in packets:
        if not (lo <= ts < hi):
            continue
        if src == host_ip and not is_internal_ip(dst):
            out.append((ts, src, dst, sp, dp, proto, flags, size))
        elif dst == host_ip and not is_internal_ip(src):
            out.append((ts, src, dst, sp, dp, proto, flags, size))
    return out


def bucket_perimeter_windows(packets, n_win: int, win_sec: float = 5.0
                             ) -> Dict[str, List[List[tuple]]]:
    """Single pass: per-host, per-window perimeter packet buckets."""
    ip2host = {h["ip"]: name for name, h in HOSTS.items()}
    buckets = {h: [[] for _ in range(n_win)] for h in HOSTS}
    for ts, src, dst, sp, dp, proto, flags, size in packets:
        w = min(int(ts // win_sec), n_win - 1)
        if src in ip2host:
            peer = dst
            hname = ip2host[src]
            if not is_internal_ip(peer):
                buckets[hname][w].append((ts, src, dst, sp, dp, proto, flags, size))
        if dst in ip2host:
            peer = src
            hname = ip2host[dst]
            if not is_internal_ip(peer):
                buckets[hname][w].append((ts, src, dst, sp, dp, proto, flags, size))
    return buckets
