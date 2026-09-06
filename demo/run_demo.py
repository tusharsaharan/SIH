"""End-to-end demo orchestrator.

Runs the full AegisForecast pipeline with NO browser required:
  1. generate a live attack scenario (recon -> detonation)
  2. stream windows through the flow aggregator -> forecaster
  3. print alerts, SHAP attributions, MITRE stages, containment dispatches
  4. summarize lead-time vs detonation

Usage: python -m demo.run_demo [recon_min] [det_min] [speed]
"""

from __future__ import annotations

import io
import json
import random
import sys
import time
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, ".")

from aegis import ALERT_CONFIDENCE
from aegis.flows import FlowAggregator
from aegis.ml.inference import ForecastEngine
from aegis.simulator import AttackScenario, attack_packets, benign_packets

WIN = 5.0


def main(recon_min: float = 8.0, det_min: float = 12.0, speed: float = 200.0):
    print("=" * 74)
    print("AEGISFORECAST — LIVE DEMO (zero-upload pipeline)")
    print("=" * 74)

    sc = AttackScenario("demo-live", "203.0.113.50", "10.20.0.1",
                        recon_minutes=recon_min, detonation_minute=det_min, kind="apt")
    rng = random.Random(2026)
    packets = benign_packets(det_min + 2.0, seed=rng.randint(0, 10**6)) \
        + attack_packets(sc, seed=rng.randint(0, 10**6))
    packets.sort(key=lambda p: p[0])

    engine = ForecastEngine(threshold=ALERT_CONFIDENCE)
    agg = FlowAggregator(WIN)

    # warm up autograd/threading so measured latency excludes cold start
    import numpy as _np
    import torch as _torch
    _x = _torch.tensor(_np.random.rand(1, engine.seq_len, engine.feature_dim) * 0.3,
                       dtype=_torch.float32)
    for _ in range(3):
        engine.explain(_x)
    engine.explain_total_ms = 0.0
    engine.explain_count = 0

    total_windows = int(packets[-1][0] // WIN) + 1
    alerts, containments = [], []
    first_alert_min = None
    sustained = 0
    t_start = time.time()

    print(f"streaming {len(packets):,} packets / {total_windows} windows "
          f"(recon={recon_min}m, detonation={det_min}m, threshold={ALERT_CONFIDENCE})\n")

    # single cursor across windows: packets are time-sorted, each window
    # consumes only its own slice (O(n) total, not O(n*windows))
    idx = 0
    for w in range(total_windows):
        lo, hi = w * WIN, (w + 1) * WIN
        # slice this window's packets
        window_pkts = []
        while idx < len(packets) and packets[idx][0] < hi:
            if packets[idx][0] >= lo:
                window_pkts.append(packets[idx])
            idx += 1

        agg.feed(window_pkts)
        rows = agg.tick()
        forecast = engine.feed_window(rows)
        if forecast is None:
            continue
        sim_min = (w + 1) * WIN / 60.0

        if forecast.alert:
            alerts.append(forecast)
            sustained += 1          # total sustained alerts (cooldown enforces spacing)
            if first_alert_min is None:
                first_alert_min = sim_min
            shap_str = ", ".join(f"{s['feature']}({s['importance']:.0%})"
                                 for s in forecast.shap_top[:3])
            print(f"  t+{sim_min:6.2f}m  ⚠ ALERT  P={forecast.attack_prob:.3f} "
                  f"{forecast.stage_info['ta']} {forecast.stage_info['tactic']:<20} "
                  f"ETA {forecast.horizon_min:4.1f}m  [{shap_str}]")
            # containment: 3rd sustained alert (cooldown-gated) -> dispatch rule
            if sustained >= 3 and (
                not containments or sim_min - containments[-1][0] > 2.0):
                containments.append((sim_min, forecast))
                print(f"           └─ CONTAINMENT: iptables -I INPUT -s 203.0.113.50 -j DROP "
                      f"(3 sustained alerts, P≥{ALERT_CONFIDENCE})")

        if w and abs(sim_min - det_min) < WIN / 60.0 / 2:
            print(f"  t+{sim_min:6.2f}m  ✸ DETONATION EVENT (payload delivered)")

    elapsed = time.time() - t_start
    print("\n" + "=" * 74)
    print("DEMO SUMMARY")
    print("=" * 74)
    print(f"windows processed : {total_windows}")
    print(f"alerts fired      : {len(alerts)}")
    print(f"containment rules : {len(containments)}")
    if first_alert_min is not None:
        print(f"first alert       : t+{first_alert_min:.2f}m")
        print(f"lead time         : {det_min - first_alert_min:.2f} minutes BEFORE detonation")
    print(f"explain latency   : avg {engine.explain_total_ms / max(engine.explain_count, 1):.1f} ms "
          f"per window (budget 15ms)")
    print(f"wall time         : {elapsed:.1f}s")
    try:
        mm = json.loads((Path(__file__).resolve().parents[1]
                        / "aegis" / "ml" / "artifacts" / "metrics.json").read_text())
        model_name = mm.get("model_name", "Bi-LSTM+Attention")
        model_line = (f"{model_name}, val AUC {mm['val_auc']}, "
                      f"stage acc {mm['val_stage_acc']} (see artifacts/metrics.json)")
    except Exception:
        model_line = "Bi-LSTM+Attention (see artifacts/metrics.json)"
    print(f"model             : {model_line}")
    print(f"privacy           : zero pcap written — in-memory flow stats only")
    print("=" * 74)
    return 0 if alerts else 1


if __name__ == "__main__":
    recon = float(sys.argv[1]) if len(sys.argv) > 1 else 8.0
    det = float(sys.argv[2]) if len(sys.argv) > 2 else 12.0
    speed = float(sys.argv[3]) if len(sys.argv) > 3 else 200.0
    sys.exit(main(recon, det, speed))
