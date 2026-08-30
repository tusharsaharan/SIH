"""SQLite persistence layer (stdlib sqlite3, zero-config file DB).

Tables:
  sessions - every sim session (single or multi-host)
  alerts   - every alert fired, with host + campaign enrichment
  actions  - SOAR response actions + state transitions (auditable trail)
  intel    - IP reputation / IoCs / campaign knowledge base
  reports  - generated incident reports (markdown + html)

Threaded-use note: FastAPI runs in one event loop; all DB calls happen on
the request/task thread. A module-level connection with check_same_thread
disabled + a lock keeps writes safe with negligible contention (this is a
demo-scale DB, not a hot path).
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional

DB_PATH = Path(__file__).resolve().parents[2] / "aegis" / "data" / "aegis.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT UNIQUE NOT NULL,
    kind TEXT NOT NULL DEFAULT 'single',
    started_ts REAL NOT NULL,
    ended_ts REAL,
    scenario TEXT,
    detonation_min REAL,
    n_alerts INTEGER DEFAULT 0,
    summary TEXT
);
CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    host TEXT,
    sim_minute REAL,
    attack_prob REAL,
    mitre TEXT,
    stage TEXT,
    horizon_min REAL,
    shap TEXT,
    enrichment TEXT,
    created_ts REAL
);
CREATE TABLE IF NOT EXISTS actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    incident_key TEXT,
    host TEXT,
    action TEXT NOT NULL,
    detail TEXT,
    actor TEXT NOT NULL DEFAULT 'system',
    state TEXT,
    created_ts REAL
);
CREATE TABLE IF NOT EXISTS intel (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ip TEXT UNIQUE NOT NULL,
    reputation REAL,
    geo TEXT,
    first_seen TEXT,
    campaigns TEXT
);
CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT UNIQUE NOT NULL,
    title TEXT,
    markdown TEXT,
    html TEXT,
    created_ts REAL
);
CREATE INDEX IF NOT EXISTS idx_alerts_session ON alerts(session_id);
CREATE INDEX IF NOT EXISTS idx_actions_session ON actions(session_id);
"""

_lock = threading.Lock()
_conn: Optional[sqlite3.Connection] = None

_BUSY_RETRIES = 5
_BUSY_BACKOFF = 0.15  # seconds, linear


def get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        _conn = sqlite3.connect(str(DB_PATH), check_same_thread=False,
                                timeout=30.0)
        _conn.row_factory = sqlite3.Row
        _conn.executescript(_SCHEMA)
        _conn.execute("PRAGMA journal_mode=WAL")
        _conn.execute("PRAGMA busy_timeout=30000")
    return _conn


def _write(sql: str, params: tuple = ()) -> None:
    """Write with retry on transient lock contention (never crash a session)."""
    last: Optional[Exception] = None
    for attempt in range(_BUSY_RETRIES):
        try:
            with _lock:
                conn = get_conn()
                conn.execute(sql, params)
                conn.commit()
            return
        except sqlite3.OperationalError as e:
            last = e
            if "locked" not in str(e).lower() and "busy" not in str(e).lower():
                raise
            time.sleep(_BUSY_BACKOFF * (attempt + 1))
    raise last  # type: ignore[misc]


# ------------------------------------------------------------------ sessions
def start_session(session_id: str, kind: str = "single",
                  scenario: str = "", detonation_min: float = 0.0) -> None:
    _write(
        "INSERT OR REPLACE INTO sessions "
        "(session_id, kind, started_ts, scenario, detonation_min) "
        "VALUES (?,?,?,?,?)",
        (session_id, kind, time.time(), scenario, detonation_min))


def end_session(session_id: str, n_alerts: int, summary: str = "") -> None:
    _write(
        "UPDATE sessions SET ended_ts=?, n_alerts=?, summary=? "
        "WHERE session_id=?",
        (time.time(), n_alerts, summary, session_id))


def list_sessions(limit: int = 50) -> List[dict]:
    rows = get_conn().execute(
        "SELECT * FROM sessions ORDER BY started_ts DESC LIMIT ?",
        (limit,)).fetchall()
    return [dict(r) for r in rows]


# ------------------------------------------------------------------- alerts
def record_alert(session_id: str, host: str, sim_minute: float,
                 attack_prob: float, mitre: str, stage: str,
                 horizon_min: float, shap: List[dict],
                 enrichment: Optional[dict] = None) -> None:
    _write(
        "INSERT INTO alerts (session_id, host, sim_minute, attack_prob, "
        "mitre, stage, horizon_min, shap, enrichment, created_ts) "
        "VALUES (?,?,?,?,?,?,?,?,?,?)",
        (session_id, host, sim_minute, attack_prob, mitre, stage,
         horizon_min, json.dumps(shap),
         json.dumps(enrichment) if enrichment else None, time.time()))


def session_alerts(session_id: str) -> List[dict]:
    rows = get_conn().execute(
        "SELECT * FROM alerts WHERE session_id=? ORDER BY sim_minute",
        (session_id,)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["shap"] = json.loads(d["shap"] or "[]")
        d["enrichment"] = json.loads(d["enrichment"] or "null")
        out.append(d)
    return out


# ------------------------------------------------------------------ actions
def record_action(session_id: str, incident_key: str, host: str,
                  action: str, detail: str = "", actor: str = "system",
                  state: str = "") -> None:
    _write(
        "INSERT INTO actions (session_id, incident_key, host, action, "
        "detail, actor, state, created_ts) VALUES (?,?,?,?,?,?,?,?)",
        (session_id, incident_key, host, action, detail, actor, state,
         time.time()))


def session_actions(session_id: str) -> List[dict]:
    rows = get_conn().execute(
        "SELECT * FROM actions WHERE session_id=? ORDER BY created_ts",
        (session_id,)).fetchall()
    return [dict(r) for r in rows]


# -------------------------------------------------------------------- intel
def seed_intel_if_empty(records: List[dict]) -> None:
    with _lock:
        n = get_conn().execute("SELECT COUNT(*) c FROM intel").fetchone()["c"]
        if n:
            return
        get_conn().executemany(
            "INSERT OR IGNORE INTO intel (ip, reputation, geo, first_seen, campaigns) "
            "VALUES (?,?,?,?,?)",
            [(r["ip"], r["reputation"], r["geo"], r["first_seen"],
              json.dumps(r["campaigns"])) for r in records])
        get_conn().commit()


def lookup_intel(ip: str) -> Optional[dict]:
    row = get_conn().execute(
        "SELECT * FROM intel WHERE ip=?", (ip,)).fetchone()
    if not row:
        return None
    d = dict(row)
    d["campaigns"] = json.loads(d["campaigns"] or "[]")
    return d


def all_intel() -> List[dict]:
    rows = get_conn().execute("SELECT * FROM intel ORDER BY reputation").fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["campaigns"] = json.loads(d["campaigns"] or "[]")
        out.append(d)
    return out


# ------------------------------------------------------------------ reports
def save_report(session_id: str, title: str, markdown: str, html: str) -> None:
    _write(
        "INSERT OR REPLACE INTO reports "
        "(session_id, title, markdown, html, created_ts) VALUES (?,?,?,?,?)",
        (session_id, title, markdown, html, time.time()))


def get_report(session_id: str) -> Optional[dict]:
    row = get_conn().execute(
        "SELECT * FROM reports WHERE session_id=?",
        (session_id,)).fetchone()
    return dict(row) if row else None


def reset_db() -> None:
    """Drop all tables (used by tests)."""
    with _lock:
        conn = get_conn()
        for t in ("sessions", "alerts", "actions", "intel", "reports"):
            conn.execute(f"DROP TABLE IF EXISTS {t}")
        conn.executescript(_SCHEMA)
        conn.commit()
