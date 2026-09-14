"""Per-family evasion evaluation: stream each evasion family through a
fresh engine on the WEB perimeter view; report first-alert, lead time,
and verdict per family. Honest red-team measurement.

Usage: python scripts/eval_evasion.py
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aegis import ALERT_CONFIDENCE
from aegis.flows import FlowAggregator
from aegis.ml.inference import ForecastEngine
from aegis.simulator.evasion import default_evasion_scenarios, evasion_packets
from aegis.simulator.multistage import HOSTS, multi_host_benign

WEB_IP = HOSTS["WEB"]["ip"]
WIN = 5.0


def run_family(family: str, seed: int = 11):
    evs = [e for e in default_evasion_scenarios(seed=seed)
           if e.family == family]
    assert evs, f"unknown family {family}"
    sc = evs[0]
    benign = multi_host_benign(sc.detonation_minute + 2.0, seed=seed * 31 + 7)
    atk = []
    for ev in evs:
        atk += evasion_packets(ev, seed=seed * 57 + 3)
    packets = sorted(benign + atk, key=lambda p: p[0])

    from aegis.ml.perimeter import perimeter_packets_for_host
    eng = ForecastEngine(threshold=ALERT_CONFIDENCE)
    n_win = int(packets[-1][0] // WIN) + 1
    first_alert = None
    n_alerts = 0
    max_prob = 0.0
    for w in range(n_win):
        lo, hi = w * WIN, (w + 1) * WIN
        hp = perimeter_packets_for_host(packets, lo, hi, WEB_IP)
        agg = FlowAggregator(WIN)
        agg.feed(hp)
        f = eng.feed_window(agg.tick())
        if f is None:
            continue
        max_prob = max(max_prob, f.attack_prob)
        if f.alert:
            n_alerts += 1
            if first_alert is None:
                first_alert = (w + 1) * WIN / 60.0
    lead = (sc.detonation_minute - first_alert) if first_alert else None
    return {
        "family": family,
        "detonation_min": sc.detonation_minute,
        "recon_min": sc.recon_minutes,
        "first_alert_min": round(first_alert, 2) if first_alert else None,
        "lead_min": round(lead, 2) if lead else None,
        "n_alerts": n_alerts,
        "max_prob": round(max_prob, 3),
        "verdict": "CAUGHT" if first_alert else "EVADED",
    }


def main():
    import json
    out = [run_family("slow_scan"), run_family("mimicry")]
    for r in out:
        print(f"{r['family']:>10}: {r['verdict']:<7} "
              f"first_alert={r['first_alert_min']}m det={r['detonation_min']}m "
              f"lead={r['lead_min']}m alerts={r['n_alerts']} maxP={r['max_prob']}")
    (Path("aegis/ml/artifacts") / "evasion_report.json").write_text(
        json.dumps(out, indent=2))
    print("wrote aegis/ml/artifacts/evasion_report.json")


if __name__ == "__main__":
    main()
