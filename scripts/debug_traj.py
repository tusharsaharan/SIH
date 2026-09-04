"""Debug: probability trajectory on the exact demo scenario."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import random

from aegis import ALERT_CONFIDENCE
from aegis.flows import windows_from_packets
from aegis.ml.inference import ForecastEngine
from aegis.simulator import AttackScenario, attack_packets, benign_packets

sc = AttackScenario("demo-live", "203.0.113.50", "10.20.0.1",
                    recon_minutes=8.0, detonation_minute=12.0, kind="apt")
rng = random.Random(2026)
packets = benign_packets(14.0, seed=rng.randint(0, 10**6)) \
    + attack_packets(sc, seed=rng.randint(0, 10**6))
packets.sort(key=lambda p: p[0])

eng = ForecastEngine(threshold=ALERT_CONFIDENCE)
probs = []
for i, rows in enumerate(windows_from_packets(packets)):
    f = eng.feed_window(rows)
    if f:
        probs.append((i + 1, round(f.attack_prob, 3), f.stage_info["ta"]))

print("threshold:", ALERT_CONFIDENCE)
print("n forecasts:", len(probs))
mx = max(probs, key=lambda t: t[1])
print("max prob:", mx)
# print trajectory every 6th window
for w, p, ta in probs[::6]:
    print(f"  win {w:>3} ({w/12:>5.1f}m)  P={p:.3f}  {ta}")
