"""Compare live WEB feature vector vs dataset attack feature vector."""
import io
import random
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np

from aegis.features import FEATURE_NAMES, SequenceFeaturizer
from aegis.ml.dataset import _rows_from_packets, build_scenario_tensor
from aegis.simulator import default_scenarios
from aegis.simulator.multistage import HOSTS, default_multi_scenario, \
    multi_host_benign, multi_stage_packets

# ---- dataset attack sequence (single-host APT, from cache) --------------
sc = default_scenarios(24, seed=7)[0]
X, ya, ys, yh = build_scenario_tensor(sc, seed=7 * 1000, use_slope=True)
mid = X[len(X) // 3]     # a mid-attack sequence
print("dataset seq shape:", mid.shape)
ds_mean = mid.mean(axis=0)
print("dataset seq mean feature vector:")
for n, v in list(zip(FEATURE_NAMES, ds_mean))[:12]:
    print(f"  {n:>18}: {v:+.3f}")

# ---- live WEB sequence (multi scenario) --------------------------------
msc = default_multi_scenario(seed=77)
rng = random.Random(5)
pkts = multi_host_benign(msc.detonation_minute + 2.0, seed=rng.randint(0, 10**6)) \
    + multi_stage_packets(msc, seed=rng.randint(0, 10**6))
pkts.sort(key=lambda p: p[0])
WEB_IP = HOSTS["WEB"]["ip"]

fz = SequenceFeaturizer(use_slope=True)
feats = []
n_win = int(pkts[-1][0] // 5.0) + 1
for w in range(n_win):
    lo, hi = w * 5.0, (w + 1) * 5.0
    hp = [p for p in pkts if lo <= p[0] < hi and (p[1] == WEB_IP or p[2] == WEB_IP)]
    feats.append(fz.feed(_rows_from_packets(hp)))

live_seq = np.asarray(feats[150:198])   # during attack mid-phase
print("\nlive WEB seq shape:", live_seq.shape)
live_mean = live_seq.mean(axis=0)
print("live WEB seq mean feature vector:")
for n, v in list(zip(FEATURE_NAMES, live_mean))[:12]:
    print(f"  {n:>18}: {v:+.3f}")

print("\ndelta (live - dataset):")
for i, n in enumerate(FEATURE_NAMES[:12]):
    d = live_mean[i] - ds_mean[i]
    print(f"  {n:>18}: {d:+.3f}")
