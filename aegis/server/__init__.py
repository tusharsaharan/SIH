"""AegisForecast FastAPI backend — SOC platform edition.

Endpoints:
  GET  /api/health              - liveness + config
  GET  /api/state               - current snapshot (HTTP fallback)
  GET  /api/alerts              - live-session alert history
  GET  /api/containment         - dispatched containment rules
  GET  /api/playbook(.md)       - guardrailed playbook (AST scan pipeline)
  GET  /api/topology            - hosts, edges, live risk scores
  GET  /api/campaigns           - intel campaign rollup for this session
  GET  /api/history             - persisted sessions (SQLite)
  GET  /api/history/{sid}       - one session: alerts + actions
  GET  /api/report/{sid}(.md|.html) - incident report (generated on demand)
  POST /api/sim/start           - start session: kind=single|multi|evasion
  POST /api/sim/stop|pause|resume
  POST /api/respond             - SOAR manual response (analyst action)
  POST /api/soar/auto           - toggle auto-SOAR mode
  WS   /ws                      - real-time telemetry stream (<500ms cadence)

Pipeline per tick (5s simulated):
  packets -> per-host flow aggregation -> per-host forecast engines ->
  campaign aggregation -> {telemetry, alert?, enrichment, containment?,
  SOAR transitions} broadcast + persisted to SQLite.
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, PlainTextResponse

from aegis import ALERT_CONFIDENCE
from aegis.flows import FlowAggregator
from aegis.ml.inference import ForecastEngine
from aegis.ml.perimeter import perimeter_packets_for_host
from aegis.playbooks import generate_playbook, render_markdown
from aegis.playbooks.ast_scanner import scan_tree
from aegis.server import db, intel
from aegis.server.replay import (first_alert_min, list_recordings,
                                 load_recording, replay_ab, save_recording)
from aegis.simulator import AttackScenario, attack_packets, benign_packets
from aegis.simulator.multistage import (HOSTS, HOST_IPS, MultiStageScenario,
                                        default_multi_scenario,
                                        multi_host_benign, multi_stage_packets)

app = FastAPI(title="AegisForecast", version="0.3.0")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SANDBOX_TARGET = REPO_ROOT / "sandbox" / "vulnerable-app"

intel.seed()   # populate threat-intel KB on boot


# ------------------------------------------------------------------ session
@dataclass
class SimSession:
    kind: str                        # single | multi | evasion
    packets: List[tuple]
    detonation_min: float
    speed: float
    attacker_ip: str
    session_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    running: bool = False
    paused: bool = False
    idx: int = 0
    scenario: str = ""


# ------------------------------------------------------------------- SOAR
INCIDENT_STATES = ["detected", "triaged", "contained", "verified", "closed"]


class Incident:
    """SOAR incident: per host, one open incident at a time."""

    def __init__(self, host: str, session_id: str):
        self.host = host
        self.session_id = session_id
        self.key = f"{session_id}:{host}"
        self.state = "detected"
        self.actions: List[dict] = []

    def advance(self, action: str, actor: str) -> dict:
        """Apply an action; returns the transition record."""
        nxt = {
            "triage": "triaged",
            "isolate": "contained",
            "verify": "verified",
            "close": "closed",
        }.get(action)
        rec = {
            "type": "soar", "incident": self.key, "host": self.host,
            "action": action, "actor": actor,
            "fromState": self.state, "toState": nxt or self.state,
            "ts": time.time(),
        }
        if nxt:
            self.state = nxt
        self.actions.append(rec)
        return rec


class Hub:
    def __init__(self):
        self.clients: Set[WebSocket] = set()
        self.session: Optional[SimSession] = None
        self.alerts: List[dict] = []
        self.containment: List[dict] = []
        self.telemetry_tail: List[dict] = []
        self.last_forecast: Optional[dict] = None
        # per-host state
        self.engines: Dict[str, ForecastEngine] = {}      # host -> engine
        self.host_risk: Dict[str, float] = {}              # host -> live prob
        self.attack_edges: List[dict] = []
        self.incidents: Dict[str, Incident] = {}           # host -> incident
        self.alerts_last_win: Dict[str, int] = {}           # host -> last alert win
        self.auto_soar: bool = True
        self.sustained: int = 0
        self.session_alert_rows: List[dict] = []            # persisted rows

    async def broadcast(self, msg: dict):
        dead = set()
        for ws in self.clients:
            try:
                await ws.send_json(msg)
            except Exception:
                dead.add(ws)
        self.clients -= dead

    def reset(self, kind: str, packets, det_min, speed, attacker, scenario):
        self.alerts, self.containment = [], []
        self.telemetry_tail = []
        self.last_forecast = None
        self.host_risk = {h: 0.0 for h in HOSTS} if kind == "multi" else {}
        self.attack_edges = []
        self.incidents = {}
        self.alerts_last_win = {}
        self.sustained = 0
        self.session_alert_rows = []
        if kind in ("multi", "evasion"):
            self.engines = {h: ForecastEngine(threshold=ALERT_CONFIDENCE)
                            for h in HOSTS}
        else:
            self.engines = {"segment": ForecastEngine(threshold=ALERT_CONFIDENCE)}
        self.session = SimSession(kind=kind, packets=packets,
                                   detonation_min=det_min, speed=speed,
                                   attacker_ip=attacker, scenario=scenario)


hub = Hub()


# ------------------------------------------------------------------ REST API
@app.get("/api/health")
def health():
    return {"status": "ok", "model": "forecast_model.pt",
            "threshold": ALERT_CONFIDENCE,
            "autoSoar": hub.auto_soar,
            "session": hub.session.session_id if hub.session else None,
            "kind": hub.session.kind if hub.session else None}


@app.get("/api/state")
def state():
    return {
        "running": hub.session.running if hub.session else False,
        "kind": hub.session.kind if hub.session else None,
        "lastForecast": hub.last_forecast,
        "telemetry": hub.telemetry_tail[-60:],
        "alertCount": len(hub.alerts),
        "hostRisk": hub.host_risk,
        "autoSoar": hub.auto_soar,
    }


@app.get("/api/alerts")
def alerts():
    return {"alerts": hub.alerts[-50:]}


@app.get("/api/containment")
def containment():
    return {"rules": hub.containment}


@app.get("/api/topology")
def topology():
    hosts = [
        {"name": name, "ip": h["ip"], "role": h["role"],
         "risk": round(hub.host_risk.get(name, 0.0), 3),
         "incident": hub.incidents[name].state if name in hub.incidents else None}
        for name, h in HOSTS.items()
    ]
    return {
        "hosts": hosts,
        "edges": hub.attack_edges,
        "campaignRisk": round(max(hub.host_risk.values()), 3) if hub.host_risk else 0.0,
        "attackerIp": hub.session.attacker_ip if hub.session else None,
    }


@app.get("/api/campaigns")
def campaigns():
    return {"campaigns": intel.campaign_rollup(hub.session_alert_rows)}


@app.get("/api/history")
def history():
    return {"sessions": db.list_sessions()}


@app.get("/api/history/{sid}")
def history_one(sid: str):
    return {"session": {"sessionId": sid},
            "alerts": db.session_alerts(sid),
            "actions": db.session_actions(sid)}


# ------------------------------------------------------- replay + model A/B
# Challenger checkpoints for replay comparison (see docs/metrics.md for
# current val numbers; labels here are short display names only).
TRANSFORMER_CKPT = REPO_ROOT / "aegis" / "ml" / "artifacts" / "transformer" / "forecast_model.pt"
BASELINE_CKPT = TRANSFORMER_CKPT if TRANSFORMER_CKPT.exists() else (
    REPO_ROOT / "aegis" / "ml" / "artifacts" / "ablation" / "D-seq24-base" / "forecast_model.pt")
ENSEMBLE_CKPT = REPO_ROOT / "aegis" / "ml" / "artifacts" / "ensemble" / "forecast_model.pt"
# NOTE: "current" is deliberately absent — it is engine A by construction
# (replaying A-vs-A is meaningless); the listing below adds it display-only.
NAMED_MODELS = {
    "transformer": (TRANSFORMER_CKPT, "transformer"),
    "ensemble": (ENSEMBLE_CKPT, "ensemble BiLSTM+Transformer"),
    "baseline": (REPO_ROOT / "aegis" / "ml" / "artifacts" / "ablation" /
                 "D-seq24-base" / "forecast_model.pt", "seq24 baseline"),
}


@app.get("/api/replays")
def replays():
    return {"replays": list_recordings()}


@app.get("/api/replay/{sid}")
def replay(sid: str, host: str = "WEB", model_b: str = ""):
    """A/B: replay a recording through current model (A) vs challenger (B).

    Returns aligned probability trajectories + first-alert comparison.
    """
    from aegis.ml.inference import ForecastEngine
    rec = load_recording(sid)
    eng_a = ForecastEngine(threshold=ALERT_CONFIDENCE)
    if model_b in NAMED_MODELS:
        b_path, b_label = NAMED_MODELS[model_b]
    else:
        b_path = Path(model_b) if model_b else BASELINE_CKPT
        b_label = (b_path.name if b_path.name != "forecast_model.pt"
                   else "seq24 baseline")
    eng_b = ForecastEngine(threshold=ALERT_CONFIDENCE, model_path=b_path)
    per_host = rec["packets"][0] and rec["kind"] in ("multi", "evasion")
    host_ip = None
    if per_host:
        host_ip = next((h["ip"] for n, h in HOSTS.items() if n == host), None)
    out = replay_ab(rec["packets"], eng_a, eng_b, per_host_ip=host_ip)
    out.update({
        "sessionId": sid,
        "modelA": "current (seq48+slope)",
        "modelB": b_label,
        "host": host if per_host else "segment",
        "firstAlertA": first_alert_min(out["trajectoryA"], ALERT_CONFIDENCE),
        "firstAlertB": first_alert_min(out["trajectoryB"], ALERT_CONFIDENCE),
        "detonationMin": rec["detonation_min"],
    })
    return out


@app.get("/api/models")
def models():
    """Available model checkpoints for replay comparison."""
    import json as _json
    out = []
    for name, (path, label) in NAMED_MODELS.items():
        entry = {"name": name, "label": label, "available": path.exists()}
        mp = path.parent / "metrics.json"
        if mp.exists():
            try:
                m = _json.loads(mp.read_text())
                entry["val_auc"] = m.get("val_auc")
            except Exception:
                pass
        out.append(entry)
    cur = {"name": "current", "label": "current (seq48+slope)",
           "available": True}
    try:
        m = _json.loads((REPO_ROOT / "aegis" / "ml" / "artifacts" /
                         "metrics.json").read_text())
        cur["val_auc"] = m.get("val_auc")
    except Exception:
        pass
    out.append(cur)
    return {"models": out}


# ------------------------------------------------------- playbook pipeline
def _current_playbook() -> dict:
    findings = scan_tree(SANDBOX_TARGET)
    ctx = {}
    lf = hub.last_forecast
    if lf:
        ctx = {"mitre": lf.get("mitre"), "stage": lf.get("stageName"),
               "confidence": lf.get("attackProb")}
    return generate_playbook(findings, stage_ctx=ctx)


@app.get("/api/playbook")
def playbook():
    return _current_playbook()


@app.get("/api/playbook.md", response_class=PlainTextResponse)
def playbook_md():
    return render_markdown(_current_playbook())


# --------------------------------------------------------------- SOAR API
@app.post("/api/respond")
async def respond(host: str, action: str, actor: str = "analyst"):
    """Manual SOAR response from the analyst console."""
    if host not in hub.incidents:
        return {"ok": False, "reason": "no open incident on host"}
    inc = hub.incidents[host]
    rec = inc.advance(action, actor)
    db.record_action(hub.session.session_id, inc.key, host, action,
                     detail=json.dumps(rec), actor=actor, state=inc.state)
    await hub.broadcast(rec)
    return {"ok": True, "incident": rec}


@app.post("/api/soar/auto")
def soar_auto(enabled: bool = True):
    hub.auto_soar = enabled
    return {"autoSoar": hub.auto_soar}


# ------------------------------------------------------------- sim control
@app.post("/api/sim/start")
async def sim_start(kind: str = "single", recon_min: float = 8.0,
                    det_min: float = 12.0, speed: float = 120.0,
                    attacker: str = "203.0.113.50"):
    """Start a live session: kind=single | multi | evasion."""
    if hub.session and hub.session.running:
        return {"started": False, "reason": "session already running"}

    import random
    rng = random.Random(int(time.time()))

    if kind == "multi":
        sc = default_multi_scenario(seed=rng.randint(0, 10**6))
        benign = multi_host_benign(sc.detonation_minute + 2.0,
                                   seed=rng.randint(0, 10**6))
        attack = multi_stage_packets(sc, seed=rng.randint(0, 10**6))
        packets = sorted(benign + attack, key=lambda p: p[0])
        hub.reset("multi", packets, sc.detonation_minute, speed,
                  sc.attacker_ip, sc.name)
        det_min = sc.detonation_minute
        recon_min = sc.recon_minutes
    elif kind == "evasion":
        from aegis.simulator.evasion import (default_evasion_scenarios,
                                             evasion_packets)
        evs = default_evasion_scenarios(seed=rng.randint(0, 10**6))
        benign = multi_host_benign(evs[-1].detonation_minute + 2.0,
                                   seed=rng.randint(0, 10**6))
        atk = []
        for ev in evs:
            atk += evasion_packets(ev, seed=rng.randint(0, 10**6))
        packets = sorted(benign + atk, key=lambda p: p[0])
        hub.reset("evasion", packets, evs[-1].detonation_minute, speed,
                  evs[0].attacker_ip, "+".join(e.name for e in evs))
        det_min = evs[-1].detonation_minute
        recon_min = evs[0].recon_minutes
    else:
        sc = AttackScenario(f"single-{uuid.uuid4().hex[:6]}", attacker,
                            "10.20.0.1", recon_minutes=recon_min,
                            detonation_minute=det_min, kind="apt")
        benign = benign_packets(det_min + 2.0, seed=rng.randint(0, 10**6))
        attack = attack_packets(sc, seed=rng.randint(0, 10**6))
        packets = sorted(benign + attack, key=lambda p: p[0])
        hub.reset("single", packets, det_min, speed, attacker, sc.name)

    db.start_session(hub.session.session_id, kind, hub.session.scenario, det_min)
    hub.session.running = True
    asyncio.create_task(run_session())
    return {"started": True, "sessionId": hub.session.session_id,
            "kind": kind, "reconMin": recon_min, "detonationMin": det_min,
            "speed": speed, "attacker": hub.session.attacker_ip}


@app.post("/api/sim/stop")
def sim_stop():
    if hub.session:
        hub.session.running = False
    return {"stopped": True}


@app.post("/api/sim/pause")
def sim_pause():
    if hub.session:
        hub.session.paused = True
    return {"paused": True}


@app.post("/api/sim/resume")
def sim_resume():
    if hub.session:
        hub.session.paused = False
    return {"paused": False}


# ------------------------------------------------------------------ pipeline
async def run_session():
    """Consume the packet timeline window-by-window, broadcast everything."""
    s = hub.session
    WIN = 5.0
    total_windows = int((s.packets[-1][0] // WIN) + 1)
    multi = s.kind == "multi" or s.kind == "evasion"

    for w in range(total_windows):
        if not s.running:
            break
        lo, hi = w * WIN, (w + 1) * WIN
        sim_min = round((w + 1) * WIN / 60.0, 2)

        t_emit = time.perf_counter()
        host_forecasts: Dict[str, dict] = {}
        if multi:
            # PERIMETER view per host (train/serve parity with dataset):
            # only traffic with non-internal peers; internal chatter is
            # the learned benign baseline, attacks live at the perimeter
            for hname, h in HOSTS.items():
                hpkts = perimeter_packets_for_host(s.packets, lo, hi, h["ip"])
                agg = FlowAggregator(WIN)
                agg.feed(hpkts)
                rows = agg.tick()
                f = hub.engines[hname].feed_window(rows)
                if f:
                    host_forecasts[hname] = f
        else:
            agg = FlowAggregator(WIN)
            idx = s.idx
            while idx < len(s.packets) and s.packets[idx][0] < hi:
                agg.feed([s.packets[idx]])
                idx += 1
            s.idx = idx
            f = hub.engines["segment"].feed_window(agg.tick())
            if f:
                host_forecasts["segment"] = f
        emit_ms = (time.perf_counter() - t_emit) * 1000

        if not host_forecasts:
            await asyncio.sleep(WIN / s.speed)
            continue

        # aggregate: campaign view = max host risk
        for hname, f in host_forecasts.items():
            hub.host_risk[hname] = f.attack_prob
        top_host = max(host_forecasts.items(), key=lambda kv: kv[1].attack_prob)
        top_name, top_f = top_host

        fdict = top_f.to_dict()
        fdict["simMinute"] = sim_min
        fdict["host"] = top_name
        fdict["hostRisks"] = {h: round(f.attack_prob, 3)
                              for h, f in host_forecasts.items()}
        hub.last_forecast = fdict

        telemetry = {"type": "telemetry", "simMinute": sim_min,
                     "windowIdx": w, "emitMs": round(emit_ms, 2),
                     "forecast": fdict}
        hub.telemetry_tail.append(telemetry)
        if len(hub.telemetry_tail) > 400:
            hub.telemetry_tail.pop(0)
        await hub.broadcast(telemetry)

        # ---- alerts on any host that crosses threshold --------------------
        # pacing: a host may alert once per 3 windows (15s sim time)
        for hname, f in host_forecasts.items():
            if not f.alert:
                continue
            if w - hub.alerts_last_win.get(hname, -100) < 3:
                continue
            hub.alerts_last_win[hname] = w
            enr = intel.enrich_alert(s.attacker_ip, f.attack_prob,
                                     f.stage_info["ta"],
                                     db.list_sessions(20))
            alert = {
                "type": "alert",
                "id": len(hub.alerts) + 1,
                "ts": f.ts,
                "host": hname,
                "simMinute": sim_min,
                "attackProb": f.attack_prob,
                "stage": f.stage_info["name"],
                "mitre": f.stage_info["ta"],
                "horizonMin": f.horizon_min,
                "shap": f.shap_top,
                "enrichment": enr,
            }
            hub.alerts.append(alert)
            row = {"session_id": s.session_id, "host": hname,
                   "sim_minute": sim_min, "attack_prob": f.attack_prob,
                   "mitre": f.stage_info["ta"], "stage": f.stage_info["name"],
                   "horizon_min": f.horizon_min, "shap": f.shap_top,
                   "enrichment": enr}
            hub.session_alert_rows.append(row)
            db.record_alert(s.session_id, hname, sim_min, f.attack_prob,
                            f.stage_info["ta"], f.stage_info["name"],
                            f.horizon_min, f.shap_top, enr)
            await hub.broadcast(alert)

            # open/incident-track per host
            if hname not in hub.incidents:
                inc = Incident(hname, s.session_id)
                hub.incidents[hname] = inc
                db.record_action(s.session_id, inc.key, hname, "detect",
                                 detail=f"P={f.attack_prob:.2f} {f.stage_info['ta']}",
                                 actor="system", state="detected")

            # attack edge visualization for topology
            if hname != "segment":
                edge = {"from": "ATTACKER", "to": hname,
                        "simMinute": sim_min, "prob": f.attack_prob}
                if edge not in hub.attack_edges:
                    hub.attack_edges.append(edge)
                    await hub.broadcast({"type": "topology_edge", **edge})

        # ---- containment + auto-SOAR (sustained raw confidence) -----------
        # NOTE: keyed off raw P>=threshold, not the cooldown-gated alert
        # flag - cooldown paces alert broadcasts; containment needs the
        # underlying sustained confidence signal
        any_alert = any(f.attack_prob >= ALERT_CONFIDENCE
                        for f in host_forecasts.values())
        if any_alert:
            hub.sustained += 1
            if hub.sustained >= 3 and (
                not hub.containment or sim_min - hub.containment[-1]["simMinute"] > 2.0):
                rule = {
                    "type": "containment",
                    "id": len(hub.containment) + 1,
                    "simMinute": sim_min,
                    "action": "FIREWALL DROP",
                    "target": f"src host {s.attacker_ip}",
                    "confidence": fdict["attackProb"],
                    "stage": fdict["stageName"],
                    "mitre": fdict["mitre"],
                    "rule": f"iptables -I INPUT -s {s.attacker_ip} -j DROP",
                }
                hub.containment.append(rule)
                await hub.broadcast(rule)
                if hub.auto_soar:
                    for hname, inc in list(hub.incidents.items()):
                        if inc.state in ("detected", "triaged"):
                            for action in ("triage", "isolate"):
                                rec = inc.advance(action, "auto-soar")
                                db.record_action(s.session_id, inc.key, hname,
                                                 action, detail=json.dumps(rec),
                                                 actor="auto-soar", state=inc.state)
                                await hub.broadcast(rec)
        else:
            hub.sustained = 0

        # detonation marker
        if (w + 1) * WIN / 60.0 >= s.detonation_min and w * WIN / 60.0 < s.detonation_min:
            await hub.broadcast({"type": "event", "event": "detonation",
                                 "simMinute": sim_min,
                                 "detonatedHost": "DC" if multi else None})

        # pause support
        if s.paused:
            await hub.broadcast({"type": "event", "event": "paused"})
            while s.paused and s.running:
                await asyncio.sleep(0.25)
            if s.running:
                await hub.broadcast({"type": "event", "event": "resumed"})
        await asyncio.sleep(WIN / s.speed)

    if hub.session:
        hub.session.running = False
    n_alerts = len(hub.alerts)
    if s:
        db.end_session(s.session_id, n_alerts,
                       summary=f"{len(hub.incidents)} incidents, "
                               f"{len(hub.containment)} containments")
        try:
            save_recording(s.session_id, s.kind, s.packets,
                           s.detonation_min, s.attacker_ip, s.scenario)
        except Exception:
            pass  # recording is best-effort; never break the session
    await hub.broadcast({"type": "event", "event": "session_end",
                         "sessionId": s.session_id if s else None})


# ------------------------------------------------------------------ websocket
@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    hub.clients.add(ws)
    try:
        if hub.last_forecast:
            await ws.send_json({"type": "telemetry", "forecast": hub.last_forecast,
                                "telemetry": hub.telemetry_tail[-30:]})
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        hub.clients.discard(ws)


# --------------------------------------------------------- evasion analysis
@app.get("/api/evasion/analysis")
def evasion_analysis():
    from aegis.simulator.evasion import evasion_analysis as _ea
    return _ea()


# --------------------------------------------------------- incident report
def _build_report(session_id: str) -> dict:
    from aegis.server.reports import generate_incident_report
    return generate_incident_report(session_id)


def _get_report_or_503(sid: str) -> dict:
    """Fetch cached report or build one; 503 (not 500) on transient failure."""
    try:
        r = db.get_report(sid)
        if r:
            return r
        return _build_report(sid)
    except Exception as e:
        raise HTTPException(status_code=503,
                            detail=f"report temporarily unavailable: {e}")


def _clean_sid(sid: str) -> tuple[str, str]:
    """Split 'abc.md' -> ('abc', 'md'); bare id -> (id, '')."""
    if sid.endswith(".md"):
        return sid[:-3], "md"
    if sid.endswith(".html"):
        return sid[:-5], "html"
    return sid, ""


@app.get("/api/report/{sid}")
def report(sid: str):
    sid, _ = _clean_sid(sid)
    r = _get_report_or_503(sid)
    return {"sessionId": sid, "title": r["title"], "markdown": r["markdown"]}


@app.get("/api/report/{sid}.md", response_class=PlainTextResponse)
def report_md(sid: str):
    sid, _ = _clean_sid(sid)
    r = _get_report_or_503(sid)
    return r["markdown"]


@app.get("/api/report/{sid}.html", response_class=HTMLResponse)
def report_html(sid: str):
    sid, _ = _clean_sid(sid)
    r = _get_report_or_503(sid)
    return r["html"]


# ------------------------------------------------- frontend dist (single-service deploy)
# Serves frontend/dist so one URL handles dashboard + /api + /ws.
# Mounted LAST so /api/* routes above always win.
try:
    from fastapi.responses import FileResponse as _FileResponse
    from fastapi.staticfiles import StaticFiles as _StaticFiles

    _DIST = REPO_ROOT / "frontend" / "dist"
    if _DIST.is_dir():
        _ASSETS = _DIST / "assets"
        if _ASSETS.is_dir():
            app.mount("/assets", _StaticFiles(directory=_ASSETS), name="assets")

        @app.get("/{full_path:path}")
        def _spa(full_path: str):
            if full_path.startswith(("api", "ws", "docs", "openapi.json", "redoc")):
                raise HTTPException(status_code=404)
            if full_path:
                _f = _DIST / full_path
                if _f.is_file():
                    return _FileResponse(_f)
            return _FileResponse(_DIST / "index.html")
except Exception:
    pass  # dev mode without dist/ still works via vite proxy
