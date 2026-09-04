"""Parity check: same packets -> training rows vs live rows must match."""
import io
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aegis.flows import FlowAggregator
from aegis.ml.dataset import _rows_from_packets
from aegis.simulator.multistage import HOSTS, multi_host_benign

pkts = multi_host_benign(1.0, seed=1)[:2000]
pkts = sorted(pkts, key=lambda p: p[0])[:600]

# training path
train_rows = _rows_from_packets(pkts)

# live path
agg = FlowAggregator(5.0)
agg.feed(pkts)
live_rows = agg.tick()

print("training rows:", len(train_rows), "| live rows:", len(live_rows))
if train_rows and live_rows:
    tr0, lr0 = train_rows[0], live_rows[0]
    keys = ["pkts", "bytes", "syn", "ack", "iat_mean"]
    for k in keys:
        print(f"  {k:>9}: train={tr0[k]} live={lr0[k]}")
    same = all(
        len(a) == len(b) and all(
            all(x[k] == y[k] for k in ("src", "dst", "sport", "dport", "proto"))
            for x, y in zip(a, b))
        for a, b in [(train_rows, live_rows)])
    print("flows identical:", same)
