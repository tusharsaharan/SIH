"""Threat intel knowledge base + alert enrichment + campaign correlation.

Synthetic but realistic seed data: known bad actors, prior campaigns, IoC
linkage. Enrichment runs on every alert: IP reputation, geo, first-seen,
campaign correlation (same actor IP seen before -> link to prior incidents).
"""

from __future__ import annotations

from typing import Dict, List, Optional

from aegis.server import db

# reputation: 0.0 = worst (known APT), 1.0 = clean
SEED_INTEL: List[dict] = [
    {"ip": "203.0.113.50", "reputation": 0.08, "geo": "Eastern Europe",
     "first_seen": "2026-06-14",
     "campaigns": ["SILENT-MONGOOSE"],
     "notes": "Known scanner node; low-and-slow recon, no payload"},
    {"ip": "198.51.100.77", "reputation": 0.04, "geo": "Southeast Asia",
     "first_seen": "2026-04-02",
     "campaigns": ["SILENT-MONGOOSE", "IRON-TALON"],
     "notes": "Dual-campaign pivot host; brute-force specialist"},
    {"ip": "203.0.113.99", "reputation": 0.15, "geo": "Eastern Europe",
     "first_seen": "2026-07-30",
     "campaigns": ["IRON-TALON"],
     "notes": "C2 beacon infrastructure, 4-6s heartbeat"},
    {"ip": "192.0.2.200", "reputation": 0.31, "geo": "South America",
     "first_seen": "2026-08-11",
     "campaigns": ["COBALT-DREAM"],
     "notes": "Opportunistic exploitation, noisy tooling"},
    {"ip": "203.0.113.101", "reputation": 0.02, "geo": "Unattributed",
     "first_seen": "2026-05-19",
     "campaigns": ["SILENT-MONGOOSE", "VELVET-SHADOW"],
     "notes": "Stealth actor; evasive scan shaping, protocol mimicry"},
]


def seed() -> None:
    db.seed_intel_if_empty(SEED_INTEL)


def enrich_alert(ip: str, attack_prob: float, mitre: str,
                 session_history: Optional[List[dict]] = None) -> Dict:
    """Build the enrichment block attached to every alert."""
    rec = db.lookup_intel(ip)
    if not rec:
        return {"ip": ip, "reputation": 0.7, "geo": "Unknown",
                "firstSeen": None, "campaigns": [],
                "verdict": "unlisted", "note": "no intel match"}
    campaigns = rec["campaigns"]
    verdict = "known-bad" if rec["reputation"] <= 0.2 else "suspicious"
    # campaign correlation: has this actor hit us in prior sessions?
    linked = []
    for s in session_history or []:
        if s.get("actor_ip") == ip and s.get("session_id"):
            linked.append(s["session_id"])
    return {
        "ip": ip,
        "reputation": rec["reputation"],
        "geo": rec["geo"],
        "firstSeen": rec["first_seen"],
        "campaigns": campaigns,
        "primaryCampaign": campaigns[0] if campaigns else None,
        "verdict": verdict,
        "note": rec.get("notes", ""),
        "linkedSessions": linked[:5],
    }


def campaign_rollup(alerts: List[dict]) -> List[dict]:
    """Group enriched alerts into campaigns (for the campaign view)."""
    by_camp: Dict[str, dict] = {}
    for a in alerts:
        e = a.get("enrichment") or {}
        camp = e.get("primaryCampaign") or "UNCORRELATED"
        entry = by_camp.setdefault(camp, {
            "campaign": camp, "hosts": set(), "nAlerts": 0,
            "maxProb": 0.0, "geo": e.get("geo"), "verdict": e.get("verdict"),
        })
        entry["nAlerts"] += 1
        entry["maxProb"] = max(entry["maxProb"], a.get("attack_prob", 0.0))
        if a.get("host"):
            entry["hosts"].add(a["host"])
    out = []
    for c in sorted(by_camp.values(), key=lambda x: -x["nAlerts"]):
        c["hosts"] = sorted(c["hosts"])
        out.append(c)
    return out
