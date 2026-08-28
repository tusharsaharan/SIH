"""MITRE ATT&CK stage taxonomy and mapping.

Stages tracked (simplified enterprise kill-chain):
  0 BENIGN        - normal enterprise traffic
  1 RECON         - TA0043 Reconnaissance (scans, service probes)
  2 ENUM          - TA0007 Discovery / credential access (TA0006)
  3 C2            - TA0011 Command & Control (beaconing, lateral movement)
  4 IMPACT        - TA0042 Impact (detonation, exfiltration)
"""

from __future__ import annotations

from typing import Dict, List

STAGES: List[Dict] = [
    {"id": 0, "key": "benign",  "tactic": "Benign",           "ta": None,    "name": "Normal Traffic"},
    {"id": 1, "key": "recon",   "tactic": "Reconnaissance",   "ta": "TA0043", "name": "Network Scan / Probe"},
    {"id": 2, "key": "enum",    "tactic": "Credential Access","ta": "TA0006", "name": "Enumeration / Brute Force"},
    {"id": 3, "key": "c2",      "tactic": "Command & Control","ta": "TA0011", "name": "C2 Beaconing / Lateral"},
    {"id": 4, "key": "impact",  "tactic": "Impact",           "ta": "TA0042", "name": "Detonation / Exfiltration"},
]
NUM_STAGES = len(STAGES)
STAGE_NAMES = [s["name"] for s in STAGES]
STAGE_TACTICS = [s["tactic"] for s in STAGES]


def stage_info(stage_id: int) -> Dict:
    return STAGES[max(0, min(stage_id, NUM_STAGES - 1))]
