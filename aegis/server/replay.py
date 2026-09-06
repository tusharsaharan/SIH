"""Session recorder + replay engine for model A/B comparison.

Recorder: on session end, persist the packet timeline + metadata to
aegis/data/replays/{session_id}.json (compact lists, rounded floats).

Replay: rerun a recording through two checkpoints (A=current default,
B=challenger, e.g. the seq-24 baseline) with identical featurization per
model config, producing aligned probability trajectories + first-alert
comparison for the dashboard A/B overlay.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Dict, List

REPLAY_DIR = Path(__file__).resolve().parents[2] / "aegis" / "data" / "replays"


def save_recording(session_id: str, kind: str, packets: List[tuple],
                   detonation_min: float, attacker_ip: str,
                   scenario: str = "") -> Path:
    """Persist a session packet timeline (compact JSON)."""
    REPLAY_DIR.mkdir(parents=True, exist_ok=True)
    path = REPLAY_DIR / f"{session_id}.json"
    data = {
        "session_id": session_id,
        "kind": kind,
        "scenario": scenario,
        "detonation_min": detonation_min,
        "attacker_ip": attacker_ip,
        "recorded_ts": time.time(),
        "n_packets": len(packets),
        # compact rows: [ts, src, dst, sport, dport, proto, flags, size]
        "packets": [[round(p[0], 3), p[1], p[2], p[3], p[4], p[5], p[6], p[7]]
                    for p in packets],
    }
    path.write_text(json.dumps(data))
    return path


def list_recordings() -> List[dict]:
    if not REPLAY_DIR.exists():
        return []
    out = []
    for p in sorted(REPLAY_DIR.glob("*.json")):
        try:
            d = json.loads(p.read_text())
            out.append({k: d.get(k) for k in
                        ("session_id", "kind", "scenario", "detonation_min",
                         "attacker_ip", "recorded_ts", "n_packets")})
        except Exception:
            continue
    return out


def load_recording(session_id: str) -> dict:
    path = REPLAY_DIR / f"{session_id}.json"
    d = json.loads(path.read_text())
    d["packets"] = [tuple(p) for p in d["packets"]]
    return d


def replay_ab(packets: List[tuple], model_a, model_b,
              win_sec: float = 5.0,
              per_host_ip: str | None = None) -> Dict:
    """Run packets through two engines; return aligned trajectories.

    per_host_ip: if set, use the perimeter view for that host (multi);
    else aggregate the full segment (single).
    """
    from aegis.flows import FlowAggregator
    from aegis.ml.perimeter import perimeter_packets_for_host

    n_win = int(max(p[0] for p in packets) // win_sec) + 1
    traj_a, traj_b = [], []
    for w in range(n_win):
        lo, hi = w * win_sec, (w + 1) * win_sec
        if per_host_ip:
            hp = perimeter_packets_for_host(packets, lo, hi, per_host_ip)
        else:
            hp = [p for p in packets if lo <= p[0] < hi]
        agg = FlowAggregator(win_sec)
        agg.feed(hp)
        rows = agg.tick()
        sim_min = round((w + 1) * win_sec / 60.0, 2)
        for eng, traj in ((model_a, traj_a), (model_b, traj_b)):
            f = eng.feed_window(rows)
            if f:
                traj.append({"simMinute": sim_min, "prob": round(f.attack_prob, 4),
                             "stage": f.stage_info["name"]})
    return {"trajectoryA": traj_a, "trajectoryB": traj_b}


def first_alert_min(traj: List[dict], threshold: float) -> float | None:
    for t in traj:
        if t["prob"] >= threshold:
            return t["simMinute"]
    return None
