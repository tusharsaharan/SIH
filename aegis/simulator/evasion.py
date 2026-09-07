"""Red-team evasion scenarios: attacks designed to defeat the forecaster.

Two families:
  slow_scan  - ultra-low-rate SYN scan: a handful of probes/hour spread over
               many hours; stays below the ramp/slope detectors that catch
               ordinary low-and-slow scans. The honest weakness we surface.
  mimicry    - attack traffic shaped to a benign profile: probe cadence,
               packet sizes, and port usage cloned from normal HTTPS traffic
               so statistical features sit inside the benign manifold.

Purpose (from the Phase 3 plan): an honest adversarial evaluation - show one
stealth case the model still catches and one that evades, then explain WHY
and what signal would close the gap. This is a strength in front of NTRO
judges, not a weakness.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import List

from aegis.simulator import Packet
from aegis.simulator.multistage import HOSTS

WEB = HOSTS["WEB"]["ip"]


@dataclass
class EvasionScenario:
    name: str
    family: str                 # slow_scan | mimicry
    attacker_ip: str
    target_ip: str
    recon_minutes: float
    detonation_minute: float


def default_evasion_scenarios(seed: int = 5) -> List[EvasionScenario]:
    """One slow_scan (likely evades) + one mimicry (often caught)."""
    return [
        EvasionScenario("evade-slowscan", "slow_scan", "203.0.113.101", WEB,
                        recon_minutes=14.0, detonation_minute=17.0),
        EvasionScenario("evade-mimicry", "mimicry", "198.51.100.77", WEB,
                        recon_minutes=8.0, detonation_minute=11.0),
    ]


def evasion_packets(sc: EvasionScenario, seed: int | None = None) -> List[Packet]:
    rng = random.Random(seed)
    pkts: List[Packet] = []
    A, T = sc.attacker_ip, sc.target_ip

    if sc.family == "slow_scan":
        # ~2-5 SYNs per minute, jittered, one port at a time - under any
        # rate-ramp signature. Dwell long. Detonate quickly when it comes.
        ports = [443, 8443, 8080, 22, 3306]
        t = 0.0
        while t < sc.recon_minutes * 60:
            pkts.append((t, A, T, rng.randint(40000, 65000),
                         rng.choice(ports), "tcp", 0x02, rng.randint(40, 60)))
            t += rng.uniform(14.0, 32.0)          # one probe / ~20s
    else:
        # mimicry: HTTPS-looking cadence (bursty page-fetch pattern), MTU-ish
        # sizes, port 443 only, plus slow probing folded into the bursts.
        t = 0.0
        while t < sc.recon_minutes * 60:
            # benign-looking page fetch burst: 8-14 pkts, realistic sizes
            for _ in range(rng.randint(8, 14)):
                pkts.append((t, A, T, rng.randint(49152, 65535), 443, "tcp",
                             0x18, rng.randint(380, 1420)))
                t += rng.uniform(0.004, 0.02)
            pkts.append((t, T, A, 443, rng.randint(49152, 65535), "tcp",
                         0x10, rng.randint(500, 1300)))   # server reply
            t += rng.uniform(1.5, 4.0)                      # think-time gap
        # subtle service probing hidden in the same shape near the end
        t = sc.recon_minutes * 60 * 0.8
        while t < sc.recon_minutes * 60:
            pkts.append((t, A, T, rng.randint(49152, 65535), 443, "tcp",
                         0x02, rng.randint(52, 58)))       # SYN hidden in flow
            t += rng.uniform(25.0, 45.0)

    # shared: small C2 + detonation (same as normal APTs)
    det_s = sc.detonation_minute * 60
    t = sc.recon_minutes * 60
    while t < det_s - 4:
        pkts.append((t, A, T, rng.randint(49152, 65535), 443, "tcp", 0x18, 74))
        pkts.append((t + 0.003, T, A, 443, rng.randint(49152, 65535),
                     "tcp", 0x18, 88))
        t += rng.uniform(5.0, 7.0)
    for _ in range(200):
        off = rng.uniform(0, 8.0)
        pkts.append((det_s + off, T, A, rng.randint(49152, 65535), 443, "tcp",
                     0x18, rng.randint(1300, 1460)))
        pkts.append((det_s + off + 0.002, A, T, 443,
                     rng.randint(49152, 65535), "tcp", 0x18, 66))
    pkts.sort(key=lambda p: p[0])
    return pkts


def evasion_analysis() -> dict:
    """Honest written analysis shipped with the evasion demo.

    Measured outcomes below are from `scripts/eval_evasion.py` against the
    current perimeter-view model at threshold 0.72 (see
    `aegis/ml/artifacts/evasion_report.json` for the machine-readable
    numbers). Update this text if the model or threshold changes.
    """
    return {
        "slow_scan": {
            "measuredOutcome": "CAUGHT — first alert t+4.0m vs detonation "
                               "t+17.0m (13.0 min lead, max P 0.996)",
            "whyCaught": "even one probe per ~20s accumulates: over the 4-min "
                         "lookback the perimeter view sees a persistent trickle "
                         "of SYNs from an unlisted external IP with zero benign "
                         "cover traffic, and the slope features pick up the "
                         "monotonic ramp once the buffer fills",
            "whyItWasDesignedToEvade": "per-window syn_ratio stays near the "
                         "benign floor, so any single-window detector misses "
                         "it — only the multi-window temporal view catches it",
            "whatWouldEvadeIt": "sub-buffer-fill dwell (rotate source IP every "
                                "< 4 minutes), or interleaving with genuine "
                                "benign flows from the same source",
        },
        "mimicry": {
            "measuredOutcome": "CAUGHT — first alert t+4.0m vs detonation "
                               "t+11.0m (7.0 min lead, max P 0.996)",
            "whyCaught": "burst cadence and sizes mimic HTTPS, but the embedded "
                         "SYN probes and the C2 heartbeat cadence (fixed 5-7s) "
                         "still perturb inter-arrival variance and small-packet "
                         "ratio enough to cross the alert threshold",
            "residualRisk": "a fully session-hijacked attack that reuses real "
                            "user TLS sessions would evade flow-statistical "
                            "detection entirely - needs payload-layer "
                            "signals (out of scope, eBPF-extendable)",
        },
    }
