"""Shared window cache: packet simulation -> window rows memoization.

Packet generation + window slicing dominates eval time (minutes per
battery). The pipelines are deterministic per (session, seed), so we cache
the window rows on disk (parquet-like pickle) and reuse them across
training runs, eval batteries, and ablation configs.

Cache key: sha1(name|kind|dur|recon|det|seed) -> windows pickle under
aegis/ml/artifacts/wincache/.
"""

from __future__ import annotations

import hashlib
import pickle
import random
from pathlib import Path
from typing import List, Optional

from aegis.flows import windows_from_packets
from aegis.simulator import AttackScenario, attack_packets, benign_packets

CACHE_DIR = Path(__file__).resolve().parent / "artifacts" / "wincache"


def _cache_path(key: str) -> Path:
    return CACHE_DIR / f"{key}.pkl"


def _key_for(sc: AttackScenario, seed: int, with_benign: bool = True) -> str:
    raw = f"{sc.name}|{sc.kind}|{sc.attacker_ip}|{sc.target_ip}|" \
          f"{sc.recon_minutes:.3f}|{sc.detonation_minute:.3f}|{seed}|{with_benign}"
    return hashlib.sha1(raw.encode()).hexdigest()[:16]


def scenario_windows(
    sc: AttackScenario,
    seed: int,
    with_benign: bool = True,
    use_cache: bool = True,
) -> List[List[dict]]:
    """Windows (list of flow-row lists) for one scenario, memoized."""
    key = _key_for(sc, seed, with_benign)
    cp = _cache_path(key)
    if use_cache and cp.exists():
        try:
            return pickle.loads(cp.read_bytes())
        except Exception:
            pass  # corrupt entry -> rebuild

    rng = random.Random(seed)
    benign = benign_packets(sc.detonation_minute + 2.0, seed=rng.randint(0, 10**6))
    attack = attack_packets(sc, seed=rng.randint(0, 10**6)) \
        if sc.kind != "benign" else []
    packets = sorted(benign + attack, key=lambda p: p[0]) if with_benign else attack
    windows = windows_from_packets(packets)

    if use_cache:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        try:
            cp.write_bytes(pickle.dumps(windows, protocol=pickle.HIGHEST_PROTOCOL))
        except Exception:
            pass
    return windows


def benign_windows(duration_min: float, seed: int, use_cache: bool = True) -> List[List[dict]]:
    """Windows for a pure-benign session, memoized."""
    raw = f"benign|{duration_min:.3f}|{seed}"
    key = hashlib.sha1(raw.encode()).hexdigest()[:16]
    cp = _cache_path(key)
    if use_cache and cp.exists():
        try:
            return pickle.loads(cp.read_bytes())
        except Exception:
            pass
    packets = benign_packets(duration_min, seed=seed)
    windows = windows_from_packets(packets)
    if use_cache:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        try:
            cp.write_bytes(pickle.dumps(windows, protocol=pickle.HIGHEST_PROTOCOL))
        except Exception:
            pass
    return windows


def clear_cache() -> None:
    if CACHE_DIR.exists():
        for p in CACHE_DIR.glob("*.pkl"):
            p.unlink(missing_ok=True)
