"""Multi-host enterprise segment simulation.

Segment (10.20.0.0/24):
  DC   10.20.0.5   domain controller - LDAP 389/636, DNS 53, Kerberos 88
  WEB  10.20.0.10  web/app server   - HTTPS 443, HTTP 80
  DB   10.20.0.20  database         - MySQL 3306, MSSQL 1433
  FILE 10.20.0.30   file server      - SMB 445, NFS 2049
  WS1  10.20.0.40   workstation      - HTTPS/HTTP/DNS client

Benign profiles are role-specific (rates, ports, packet sizes, iat).
Multi-stage APT scenarios traverse hosts:
  attacker -> WEB (recon+exploit) -> credentials -> FILE (SMB lateral)
  -> DB (dump) -> DC (detonation/wiper)
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Dict, List, Tuple

from aegis.simulator import Packet, benign_packets

# ---------------------------------------------------------------- topology
HOSTS = {
    "DC":   {"ip": "10.20.0.5",  "role": "domain-controller",
             "services": [(389, "tcp", 0.8, 80, 160), (88, "tcp", 0.3, 60, 90),
                         (53, "udp", 2.0, 55, 80)]},
    "WEB":  {"ip": "10.20.0.10", "role": "web-server",
             "services": [(443, "tcp", 16.0, 300, 1400), (80, "tcp", 5.0, 200, 900)]},
    "DB":   {"ip": "10.20.0.20", "role": "database",
             "services": [(3306, "tcp", 3.5, 120, 1100), (1433, "tcp", 0.6, 120, 900)]},
    "FILE": {"ip": "10.20.0.30", "role": "file-server",
             "services": [(445, "tcp", 2.2, 100, 700), (2049, "tcp", 0.4, 120, 800)]},
    "WS1":  {"ip": "10.20.0.40", "role": "workstation",
             "services": [(443, "tcp", 9.0, 350, 1300), (53, "udp", 2.5, 55, 80),
                          (80, "tcp", 2.0, 200, 800)]},
}
HOST_IPS = {h["ip"]: name for name, h in HOSTS.items()}

WORKSTATION_CLIENTS = [f"10.20.1.{i}" for i in range(2, 25)]


@dataclass
class MultiStageScenario:
    """Lateral APT: attacker -> WEB -> FILE -> DB -> DC detonation."""
    name: str
    attacker_ip: str
    recon_minutes: float          # attacker vs WEB recon ramp
    dwell_file: float              # minutes on FILE before pivoting
    dwell_db: float                # minutes on DB
    detonation_minute: float       # impact on DC
    kind: str = "multi_stage"


def multi_host_benign(duration_min: float, seed: int | None = None) -> List[Packet]:
    """Role-based benign traffic for the whole segment."""
    rng = random.Random(seed)
    packets: List[Packet] = []
    duration_s = duration_min * 60.0

    # per-host service traffic from internal clients / workstations
    for hname, h in HOSTS.items():
        ip = h["ip"]
        for port, proto, rate, lo, hi in h["services"]:
            t = rng.random() * 2.0
            while t < duration_s:
                if hname in ("WEB", "DB", "FILE", "DC"):
                    src = rng.choice(WORKSTATION_CLIENTS + [HOSTS["WS1"]["ip"]])
                else:  # WS1 talks to servers
                    src = ip
                    ip_peer = rng.choice([HOSTS["WEB"]["ip"], HOSTS["DC"]["ip"]])
                    pkt = (t, ip, ip_peer, rng.randint(49152, 65535), port, proto,
                           0x18 if proto == "tcp" else 0, rng.randint(lo, hi))
                    packets.append(pkt)
                    packets.append((t + rng.uniform(0.001, 0.02), ip_peer, ip, port,
                                    rng.randint(49152, 65535), proto, 0x10,
                                    int(rng.randint(lo, hi) * 0.7)))
                    t += rng.expovariate(rate)
                    continue
                pkt = (t, src, ip, rng.randint(49152, 65535), port, proto,
                       0x18 if proto == "tcp" else 0, rng.randint(lo, hi))
                packets.append(pkt)
                packets.append((t + rng.uniform(0.001, 0.02), ip, src, port,
                                rng.randint(49152, 65535), proto, 0x10,
                                int(rng.randint(lo, hi) * 0.7)))
                t += rng.expovariate(rate)

    # inter-server chatter: DC <-> everything (auth), WEB <-> DB (app queries)
    for a, b, port, proto, rate, lo, hi in [
        (HOSTS["WEB"]["ip"], HOSTS["DB"]["ip"], 3306, "tcp", 4.0, 200, 1200),
        (HOSTS["WS1"]["ip"], HOSTS["DC"]["ip"], 389, "tcp", 0.5, 70, 150),
        (HOSTS["FILE"]["ip"], HOSTS["DC"]["ip"], 88, "tcp", 0.3, 60, 90),
    ]:
        t = rng.random() * 2.0
        while t < duration_s:
            packets.append((t, a, b, rng.randint(49152, 65535), port, proto,
                           0x18, rng.randint(lo, hi)))
            packets.append((t + rng.uniform(0.001, 0.02), b, a, port,
                           rng.randint(49152, 65535), proto, 0x10,
                           int(rng.randint(lo, hi) * 0.75)))
            t += rng.expovariate(rate)

    packets.sort(key=lambda p: p[0])
    return packets


def multi_stage_packets(sc: MultiStageScenario,
                        seed: int | None = None) -> List[Packet]:
    """Lateral kill-chain packets.

    Timeline (minutes):
      0 .. recon            attacker recon/exploit on WEB (SYN ramp + probes)
      recon .. recon+d1     credential access on WEB (brute force)
      +d1 .. +d2            SMB lateral movement on FILE (dwell_file)
      +d2 .. +d3            DB dump on DB (dwell_db)
      .. detonation         C2 beacons + Kerberos pivot toward DC
      detonation            wiper/impact burst on DC
    """
    rng = random.Random(seed)
    s = sc
    pkts: List[Packet] = []
    WEB = HOSTS["WEB"]["ip"]; FILE = HOSTS["FILE"]["ip"]
    DB = HOSTS["DB"]["ip"]; DC = HOSTS["DC"]["ip"]
    A = s.attacker_ip

    t0 = 0.0
    recon_end = s.recon_minutes
    cred_end = recon_end + 2.5
    file_end = cred_end + s.dwell_file
    db_end = file_end + s.dwell_db
    det = s.detonation_minute

    # ---- Phase 1: recon ramp on WEB (TA0043) -----------------------------
    scan_ports = [80, 443, 22, 8080, 8443, 3306]
    t = 0.0
    while t < recon_end * 60:
        frac = t / (recon_end * 60)
        pkts.append((t, A, WEB, rng.randint(40000, 65000),
                     rng.choice(scan_ports), "tcp", 0x02, rng.randint(40, 60)))
        if rng.random() < 0.06:
            pkts.append((t + 0.002, WEB, A, 443, rng.randint(40000, 65000),
                         "tcp", 0x12, 60))
        t += rng.uniform(2.5 * (1 - frac) + 0.3, 3.5 * (1 - frac) + 0.4)

    # ---- Phase 2: credential access on WEB (TA0006) ---------------------
    t = recon_end * 60
    while t < cred_end * 60:
        for _ in range(rng.randint(3, 7)):
            pkts.append((t, A, WEB, rng.randint(40000, 65000), 443, "tcp",
                         0x18, rng.randint(90, 150)))
            t += rng.uniform(0.06, 0.2)
        t += rng.uniform(0.4, 1.0)

    # ---- Phase 3: lateral to FILE via SMB (TA0008) ----------------------
    t = cred_end * 60
    while t < file_end * 60:
        pkts.append((t, WEB, FILE, rng.randint(40000, 65000), 445, "tcp",
                     0x18, rng.randint(120, 400)))
        if rng.random() < 0.35:
            pkts.append((t + 0.004, FILE, WEB, 445, rng.randint(40000, 65000),
                         "tcp", 0x18, rng.randint(100, 300)))
        t += rng.uniform(0.5, 1.4)

    # ---- Phase 4: DB dump (TA0010 exfil prep) ---------------------------
    t = file_end * 60
    while t < db_end * 60:
        pkts.append((t, FILE, DB, rng.randint(40000, 65000), 3306, "tcp",
                     0x18, rng.randint(300, 1400)))
        pkts.append((t + 0.005, DB, FILE, 3306, rng.randint(40000, 65000),
                     "tcp", 0x18, rng.randint(200, 1200)))
        t += rng.uniform(0.8, 2.2)

    # ---- Phase 5: C2 + pivot toward DC (TA0011) --------------------------
    t = db_end * 60
    while t < det * 60:
        pkts.append((t, A, WEB, rng.randint(49152, 65535), 443, "tcp",
                     0x18, 74))                              # beacon
        pkts.append((t + 0.003, WEB, A, 443, rng.randint(49152, 65535),
                     "tcp", 0x18, 88))
        if rng.random() < 0.5:
            pkts.append((t, DB, DC, rng.randint(49152, 65535), 88, "tcp",
                         0x18, rng.randint(90, 200)))         # kerberos pivot
        t += rng.uniform(4.0, 6.0)

    # ---- Phase 6: detonation on DC (TA0042) ------------------------------
    det_s = det * 60
    for _ in range(260):
        off = rng.uniform(0, 9.0)
        pkts.append((det_s + off, DC, A, rng.randint(49152, 65535), 443,
                     "tcp", 0x18, rng.randint(1300, 1460)))   # exfil
        pkts.append((det_s + off + 0.002, A, DC, 443,
                     rng.randint(49152, 65535), "tcp", 0x18, 66))
    pkts.sort(key=lambda p: p[0])
    return pkts


def is_internal_ip(ip: str) -> bool:
    """True for segment hosts + internal client subnets (10.20.x)."""
    return ip.startswith("10.20.")


def default_multi_scenario(seed: int = 7) -> MultiStageScenario:
    """Standard demo scenario: 8m recon, 3m FILE dwell, 2.5m DB, det @ 18m."""
    rng = random.Random(seed)
    recon = rng.uniform(7.0, 9.0)
    det = recon + 2.5 + 3.0 + 2.5 + rng.uniform(1.5, 2.5)
    return MultiStageScenario(
        name="lateral-demo",
        attacker_ip="203.0.113.50",
        recon_minutes=recon,
        dwell_file=3.0,
        dwell_db=2.5,
        detonation_minute=det,
    )
