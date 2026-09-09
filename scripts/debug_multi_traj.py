"""Debug: per-host probability trajectories on the multi scenario, new model."""
import io
import random
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aegis.flows import FlowAggregator
from aegis.ml.inference import ForecastEngine
from aegis.simulator.multistage import (HOSTS, default_multi_scenario,
                                        multi_host_benign, multi_stage_packets)

sc = default_multi_scenario(seed=77)
print(f"scenario: recon={sc.recon_minutes:.1f}m det={sc.detonation_minute:.1f}m")
rng = random.Random(99)
pkts = multi_host_benign(sc.detonation_minute + 2.0, seed=rng.randint(0, 10**6)) \
    + multi_stage_packets(sc, seed=rng.randint(0, 10**6))
pkts.sort(key=lambda p: p[0])

engines = {h: ForecastEngine() for h in HOSTS}
WIN = 5.0
n_win = int(pkts[-1][0] // WIN) + 1
probs = {h: [] for h in HOSTS}

# bucket packets per (host, window) in one pass
buckets = {h: [[] for _ in range(n_win)] for h in HOSTS}
ip2host = {h["ip"]: name for name, h in HOSTS.items()}
for ts, src, dst, sp, dp, proto, flags, size in pkts:
    w = min(int(ts // WIN), n_win - 1)
    if src in ip2host:
        buckets[ip2host[src]][w].append((ts, src, dst, sp, dp, proto, flags, size))
    if dst in ip2host:
        buckets[ip2host[dst]][w].append((ts, src, dst, sp, dp, proto, flags, size))

for w in range(n_win):
    for hname, eng in engines.items():
        agg = FlowAggregator(WIN)
        agg.feed(buckets[hname][w])
        f = eng.feed_window(agg.tick())
        if f:
            probs[hname].append((w + 1, round(f.attack_prob, 3)))

print(f"\n{'win':>4} {'min':>6} | " + " | ".join(f"{h:>6}" for h in HOSTS))
step = 6
hosts_list = list(HOSTS.keys())
maxlen = max(len(v) for v in probs.values())
for i in range(0, maxlen, step):
    row = []
    for h in hosts_list:
        if i < len(probs[h]):
            widx, p = probs[h][i]
            row.append(f"{p:>6.3f}")
        else:
            row.append(f"{'—':>6}")
    ref = probs[hosts_list[0]][i][0] if i < len(probs[hosts_list[0]]) else i * 6
    print(f"{ref:>4} {ref/12:>5.1f}m | " + " | ".join(row))

print("\nmax P per host:")
for h in hosts_list:
    if probs[h]:
        mx = max(probs[h], key=lambda t: t[1])
        print(f"  {h:>5}: {mx[1]:.3f} @ window {mx[0]} ({mx[0]/12:.1f}m)")
