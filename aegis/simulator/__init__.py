"""Network traffic simulator.

Generates realistic packet-level timelines:
- Benign enterprise background traffic (web, dns, ssh, file transfer)
- Multi-stage APT attack timelines (recon -> escalation -> detonation)

Packets are (ts, src_ip, dst_ip, src_port, dst_port, protocol, tcp_flags,
payload_bytes) tuples. In production these come from an eBPF kernel probe
(aegis/ebpf); here they are simulated for lab validation, mirroring how the
Docker sandbox injects Scapy vectors.
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from typing import List, Tuple

Packet = Tuple[float, str, str, int, int, str, int, int]


@dataclass
class AttackScenario:
    """One scripted multi-stage attack timeline (MITRE ATT&CK stages)."""

    name: str
    attacker_ip: str
    target_ip: str
    recon_minutes: float          # duration of recon phase (the 10-30 min ramp)
    detonation_minute: float      # when the payload lands
    kind: str = "apt"             # apt | portscan | bruteforce | ddos | benign


# ---------------------------------------------------------------- benign base
BENIGN_SERVICES = [
    # (port, protocol, pkt_rate_per_s, bytes_lo, bytes_hi)
    (443, "tcp", 14.0, 400, 1600),    # HTTPS browsing
    (53, "udp", 3.0, 60, 90),         # DNS
    (80, "tcp", 4.0, 200, 900),       # HTTP
    (22, "tcp", 0.4, 60, 120),        # SSH (ops)
    (445, "tcp", 1.2, 100, 300),      # SMB
]

BENIGN_CLIENTS = [f"10.20.{i}.{j}" for i in range(1, 6) for j in range(2, 30)]


def _exp_gap(rate: float, rng: random.Random) -> float:
    """Exponential inter-arrival time for a Poisson process."""
    return rng.expovariate(rate) if rate > 0 else 0.0


def benign_packets(
    duration_min: float,
    server_ip: str = "10.20.0.1",
    seed: int | None = None,
    clients: List[str] | None = None,
) -> List[Packet]:
    """Poisson background traffic for `duration_min` minutes."""
    rng = random.Random(seed)
    clients = clients or BENIGN_CLIENTS
    packets: List[Packet] = []
    duration_s = duration_min * 60.0

    for port, proto, rate, lo, hi in BENIGN_SERVICES:
        t = rng.random() * 2.0
        while t < duration_s:
            src = rng.choice(clients)
            pkt = (t, src, server_ip, rng.randint(49152, 65535), port, proto,
                   0x18 if proto == "tcp" else 0, rng.randint(lo, hi))
            packets.append(pkt)
            # server response (bidirectional)
            resp = (t + rng.uniform(0.001, 0.02), server_ip, src, port,
                    rng.randint(49152, 65535), proto,
                    0x10 if proto == "tcp" else 0, int(rng.randint(lo, hi) * 0.8))
            packets.append(resp)
            t += _exp_gap(rate, rng)
    packets.sort(key=lambda p: p[0])
    return packets


# ---------------------------------------------------------------- attack arcs
def attack_packets(scenario: AttackScenario, seed: int | None = None) -> List[Packet]:
    """Scripted APT timeline matching a MITRE ATT&CK kill chain.

    Phases (minutes from start):
      0 .. recon          : recon ramp - SYN scan + service probing that grows
                            slowly ("low and slow") - TA0043 Reconnaissance
      recon .. recon+e    : enumeration + credential fuzzing - TA0006/TA0007
      then                : lateral movement + C2 beaconing - TA0008/TA0011
      detonation          : payload detonation - TA0042 Impact
    """
    rng = random.Random(seed)
    s = scenario
    packets: List[Packet] = []
    recon_end = s.recon_minutes
    enum_end = recon_end + max(2.0, s.recon_minutes * 0.2)
    c2_end = enum_end + max(2.0, s.recon_minutes * 0.15)
    det = s.detonation_minute

    # ---- Phase 1: low-and-slow SYN scan ramping up ------------------------- (TA0043)
    scan_ports = [21, 22, 23, 25, 53, 80, 110, 135, 139, 443, 445, 1433,
                  1521, 3306, 3389, 5432, 5900, 6379, 8080, 8443, 9000]
    t = 0.0
    while t < recon_end * 60.0:
        frac = t / (recon_end * 60.0)              # 0 -> 1 ramp
        port = rng.choice(scan_ports)
        packets.append((t, s.attacker_ip, s.target_ip, rng.randint(40000, 65000),
                        port, "tcp", 0x02, rng.randint(40, 60)))   # SYN
        # rare SYN-ACK responses (closed ports send nothing / RST)
        if rng.random() < 0.04:
            packets.append((t + 0.002, s.target_ip, s.attacker_ip, port,
                            rng.randint(40000, 65000), "tcp", 0x12, 60))  # SYN-ACK
        # low-and-slow: gap shrinks as the scan accelerates (2.5s -> 0.3s)
        t += rng.uniform(2.5 * (1 - frac) + 0.3, 3.5 * (1 - frac) + 0.4)

    # ---- Phase 2: service enumeration + credential fuzzing ---------------- (TA0006/7)
    t = recon_end * 60.0
    enum_rate = 6.0
    while t < enum_end * 60.0:
        port = rng.choice([22, 80, 443, 3306, 3389])
        if port in (22, 3389):
            # brute force bursts: rapid SYN + data to auth service
            for _ in range(rng.randint(4, 9)):
                packets.append((t, s.attacker_ip, s.target_ip,
                                rng.randint(40000, 65000), port, "tcp",
                                0x02, rng.randint(40, 60)))
                packets.append((t + 0.004, s.attacker_ip, s.target_ip,
                                rng.randint(40000, 65000), port, "tcp",
                                0x18, rng.randint(80, 140)))   # PSH|ACK creds
                t += rng.uniform(0.05, 0.15)
        else:
            packets.append((t, s.attacker_ip, s.target_ip,
                            rng.randint(40000, 65000), port, "tcp", 0x18,
                            rng.randint(120, 400)))
            t += _exp_gap(enum_rate, rng)
        t += rng.uniform(0.2, 0.8)

    # ---- Phase 3: C2 beaconing + lateral movement -------------------------- (TA0011/8)
    t = enum_end * 60.0
    while t < min(c2_end * 60.0, det * 60.0):
        # periodic beacon - small packets, fixed cadence
        packets.append((t, s.attacker_ip, s.target_ip,
                        rng.randint(49152, 65535), 443, "tcp", 0x18, 74))
        packets.append((t + 0.003, s.target_ip, s.attacker_ip, 443,
                        rng.randint(49152, 65535), "tcp", 0x18, 88))
        t += rng.uniform(4.0, 6.0)
        # occasional lateral hop inside the "subnet"
        if rng.random() < 0.3:
            hop = f"10.20.0.{rng.randint(2, 12)}"
            packets.append((t, s.attacker_ip, hop, rng.randint(40000, 65000),
                            445, "tcp", 0x18, rng.randint(120, 260)))
            t += rng.uniform(1.0, 2.0)

    # ---- Phase 4: detonation ---------------------------------------------- (TA0042 Impact)
    det_s = det * 60.0
    for _ in range(220):
        off = rng.uniform(0, 8.0)
        # exfiltration / destructive burst
        packets.append((det_s + off, s.target_ip, s.attacker_ip,
                        rng.randint(49152, 65535), 443, "tcp", 0x18,
                        rng.randint(1300, 1460)))
        packets.append((det_s + off + 0.002, s.attacker_ip, s.target_ip,
                        443, rng.randint(49152, 65535), "tcp", 0x18, 66))
    packets.sort(key=lambda p: p[0])
    return packets


# ------------------------------------------------------------------ scenarios
def default_scenarios(n: int = 60, seed: int = 7) -> List[AttackScenario]:
    """Randomized attack scenarios for dataset generation."""
    rng = random.Random(seed)
    out: List[AttackScenario] = []
    kinds = ["apt"] * 5 + ["portscan", "bruteforce", "ddos"]
    for i in range(n):
        kind = rng.choice(kinds)
        recon = rng.uniform(10.0, 30.0) if kind == "apt" else rng.uniform(2.0, 8.0)
        det = recon + max(4.0, recon * rng.uniform(0.25, 0.5))
        out.append(AttackScenario(
            name=f"{kind}-{i}",
            attacker_ip=f"203.0.113.{rng.randint(2, 254)}",
            target_ip="10.20.0.1",
            recon_minutes=recon,
            detonation_minute=det,
            kind=kind,
        ))
    return out
