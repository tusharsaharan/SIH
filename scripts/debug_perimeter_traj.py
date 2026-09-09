"""WEB perimeter-view trajectory through the live engine (train/serve parity)."""
import io
import random
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aegis.flows import FlowAggregator
from aegis.ml.inference import ForecastEngine
from aegis.ml.perimeter import perimeter_packets_for_host
from aegis.simulator.multistage import (HOSTS, default_multi_scenario,
                                        multi_host_benign, multi_stage_packets)

sc = default_multi_scenario(seed=77)
print(f"scenario: recon={sc.recon_minutes:.1f}m det={sc.detonation_minute:.1f}m")
rng = random.Random(5)
pkts = multi_host_benign(sc.detonation_minute + 2.0, seed=rng.randint(0, 10**6)) \
    + multi_stage_packets(sc, seed=rng.randint(0, 10**6))
pkts.sort(key=lambda p: p[0])

WEB_IP = HOSTS["WEB"]["ip"]
WIN = 5.0
n_win = int(pkts[-1][0] // WIN) + 1
eng = ForecastEngine()

probs = []
for w in range(n_win):
    lo, hi = w * WIN, (w + 1) * WIN
    hp = perimeter_packets_for_host(pkts, lo, hi, WEB_IP)
    agg = FlowAggregator(WIN)
    agg.feed(hp)
    f = eng.feed_window(agg.tick())
    if f:
        probs.append((w + 1, f.attack_prob, f.stage_info["ta"]))

print(f"forecasts: {len(probs)}")
mx = max(probs, key=lambda t: t[1]) if probs else None
print("max P:", round(mx[1], 3) if mx else None, "at win", mx[0] if mx else None)
for w, p, ta in probs[::8]:
    phase = "recon" if w / 12 < sc.recon_minutes else ("det" if w / 12 >= sc.detonation_minute else "mid")
    print(f"  win {w:>3} ({w/12:>4.1f}m {phase:>5}) P={p:.3f} {ta}")
