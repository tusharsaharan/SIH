# eBPF Kernel Telemetry (Production Reference)

`aegis_flow_kern.c` is the production XDP probe that replaces the lab Python
simulator in deployment. Design contract (identical output schema):

| Concern | Design |
|---|---|
| Capture | eBPF XDP hook on SPAN/TAP or host NIC — zero-copy, in-kernel |
| Aggregation | LRU hash map keyed by canonical bidirectional 5-tuple |
| Output | Rolling flow stats (pkts, bytes, SYN/SYN-ACK/RST/FIN/PSH/ACK, last-seen) |
| Memory | Bounded LRU (65,536 flows) — kernel-verified, no leaks |
| Privacy | **Zero-upload**: raw packets never leave the kernel, no pcap storage |
| Overhead | Per-packet cost is a handful of atomic adds — **design target** < 2% CPU at 10Gbps (Cilium-class workloads; not yet measured on hardware — see `BENCH.md` when lab NIC testing lands) |

## User-space reader (concept)

```python
# every 5s (aegis.flows tick equivalent):
#   iterate aegis_flow_map
#   emit rows -> aegis.features.window_to_features
#   clear window counters (rollover)
```

Attach (Linux >= 5.15):

```bash
clang -O2 -target bpf -c aegis_flow_kern.c -o aegis_flow_kern.o
ip link set dev eth0 xdp obj aegis_flow_kern.o sec xdp
bpftool map dump pinned /sys/fs/bpf/aegis_flow_map
```

The demo uses the pure-Python simulator (`aegis/simulator`) which produces
bit-identical flow-row schemas, so the model, backend, and dashboard are
unchanged between lab and production.
