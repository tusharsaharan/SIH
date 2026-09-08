"""Auto-generated incident reports (markdown + standalone styled HTML).

Built from persisted session data (alerts, actions, intel enrichment).
Deterministic template assembly - consistent with the guardrails posture.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Dict, List

from aegis.server import db
from aegis.server.intel import campaign_rollup

_CSS = """
body{font-family:'Segoe UI',system-ui,sans-serif;background:#0f172a;color:#e2e8f0;margin:0;padding:40px}
.wrap{max-width:900px;margin:0 auto}
h1{color:#38bdf8;font-size:26px;border-bottom:1px solid #334155;padding-bottom:12px}
h2{color:#94a3b8;font-size:16px;text-transform:uppercase;letter-spacing:.12em;margin-top:36px}
table{width:100%;border-collapse:collapse;margin-top:10px;font-size:13px}
th{background:#1e293b;color:#94a3b8;text-align:left;padding:8px 10px;text-transform:uppercase;font-size:11px;letter-spacing:.08em}
td{border-bottom:1px solid #1e293b;padding:8px 10px}
.badge{display:inline-block;padding:2px 10px;border-radius:999px;font-size:11px;font-weight:600}
.badge.crit{background:#7f1d1d;color:#fecaca}
.badge.warn{background:#78350f;color:#fde68a}
.badge.ok{background:#14532d;color:#bbf7d0}
.meta{color:#64748b;font-size:12px}
.kv{display:grid;grid-template-columns:200px 1fr;gap:6px 18px;font-size:13px}
.kv b{color:#94a3b8;font-weight:600}
.mitre{color:#38bdf8;font-family:Consolas,monospace}
.footer{margin-top:48px;color:#475569;font-size:11px;border-top:1px solid #1e293b;padding-top:12px}
"""


def generate_incident_report(session_id: str) -> Dict[str, str]:
    """Assemble the report for a persisted session; saves + returns it."""
    sess_rows = [s for s in db.list_sessions(500)
                 if s["session_id"] == session_id]
    sess = sess_rows[0] if sess_rows else {"session_id": session_id,
                                           "kind": "unknown",
                                           "scenario": "unknown",
                                           "detonation_min": 0,
                                           "n_alerts": 0,
                                           "summary": ""}
    alerts = db.session_alerts(session_id)
    actions = db.session_actions(session_id)
    campaigns = campaign_rollup(alerts)

    # timeline buckets: first alert per host, detonation, containments
    hosts_hit = sorted({a["host"] for a in alerts})
    first_alert = alerts[0] if alerts else None
    lead = round(sess["detonation_min"] - first_alert["sim_minute"], 2) \
        if first_alert and sess.get("detonation_min") else None

    md = _markdown(sess, alerts, actions, campaigns, hosts_hit, lead)
    html = _html(sess, alerts, actions, campaigns, hosts_hit, lead)
    title = f"Incident Report — {session_id}"
    db.save_report(session_id, title, md, html)
    return {"title": title, "markdown": md, "html": html}


def _fmt_ts(ts: float) -> str:
    return time.strftime("%H:%M:%S", time.localtime(ts)) if ts else "—"


def _markdown(sess, alerts, actions, campaigns, hosts_hit, lead) -> str:
    lines = [
        "# Incident Report", "",
        f"**Session:** `{sess['session_id']}` · **Kind:** {sess.get('kind', '—')} "
        f"· **Scenario:** {sess.get('scenario', '—')}", "",
        "## Executive summary", "",
    ]
    if alerts:
        verdict = "critical" if hosts_hit else "informational"
        lines.append(
            f"The forecasting engine identified an **{verdict}** multi-stage "
            f"attack campaign across **{len(hosts_hit)} host(s): "
            f"{', '.join(hosts_hit) if hosts_hit else 'single-segment'}**. "
            + (f"First alert preceded detonation by **{lead} minutes**, giving "
               f"the SOC a proactive containment window. " if lead else "") +
            f"{len(alerts)} alerts fired; **{len(campaigns)}** correlated "
            f"campaign(s); {len(actions)} response actions "
            f"({len([a for a in actions if a['action'] == 'isolate'])} "
            f"host isolation(s)).")
    else:
        lines.append(
            "No alerts were raised during this session. Either the traffic "
            "remained within the benign manifold, or an evasive adversary "
            "stayed below the detection thresholds (see evasion analysis).")
    lines += ["", "## Timeline", "",
              "| sim-minute | host | P(attack) | MITRE | stage | horizon |",
              "|---|---|---|---|---|---|"]
    for a in alerts[:40]:
        lines.append(f"| {a['sim_minute']} | {a['host']} | "
                     f"{a['attack_prob']:.2f} | {a['mitre']} | "
                     f"{a['stage']} | {a['horizon_min']}m |")
    lines += ["", "## Campaign attribution", ""]
    if campaigns:
        lines += ["| campaign | verdict | hosts | alerts | max P |",
                  "|---|---|---|---|---|"]
        for c in campaigns:
            lines.append(f"| {c['campaign']} | {c.get('verdict', '—')} | "
                         f"{', '.join(c['hosts']) or '—'} | {c['nAlerts']} | "
                         f"{c['maxProb']:.2f} |")
    else:
        lines.append("_No correlated campaigns._")
    lines += ["", "## Response actions", ""]
    if actions:
        lines += ["| time | host | action | actor | state |", "|---|---|---|---|---|"]
        for a in actions:
            lines.append(f"| {_fmt_ts(a['created_ts'])} | {a['host']} | "
                         f"{a['action']} | {a['actor']} | {a['state']} |")
    else:
        lines.append("_No response actions recorded._")
    lines += ["", "## Top SHAP drivers (first alert)", ""]
    if alerts:
        for s in (alerts[0]["shap"] or [])[:6]:
            lines.append(f"- `{s['feature']}` — {s['importance']:.1%}")
    lines += ["", "---", f"_Generated by AegisForecast · {time.strftime('%Y-%m-%d %H:%M')}_"]
    return "\n".join(lines)


def _html(sess, alerts, actions, campaigns, hosts_hit, lead) -> str:
    sev = "crit" if alerts else "ok"
    badge = {"crit": "CRITICAL", "ok": "NO ALERTS"}[sev]
    rows_a = "".join(
        f"<tr><td>{a['sim_minute']}m</td><td>{a['host']}</td>"
        f"<td>{a['attack_prob']:.2f}</td><td class='mitre'>{a['mitre']}</td>"
        f"<td>{a['stage']}</td><td>{a['horizon_min']}m</td></tr>"
        for a in alerts[:40]) or "<tr><td colspan=6>—</td></tr>"
    rows_c = "".join(
        f"<tr><td>{c['campaign']}</td><td>{c.get('verdict', '—')}</td>"
        f"<td>{', '.join(c['hosts']) or '—'}</td><td>{c['nAlerts']}</td>"
        f"<td>{c['maxProb']:.2f}</td></tr>"
        for c in campaigns) or "<tr><td colspan=5>—</td></tr>"
    rows_act = "".join(
        f"<tr><td>{_fmt_ts(a['created_ts'])}</td><td>{a['host']}</td>"
        f"<td>{a['action']}</td><td>{a['actor']}</td><td>{a['state']}</td></tr>"
        for a in actions) or "<tr><td colspan=5>—</td></tr>"
    shap_html = ""
    if alerts:
        items = "".join(
            f"<li><code>{s['feature']}</code> — {s['importance']:.1%}</li>"
            for s in (alerts[0]["shap"] or [])[:6])
        shap_html = f"<h2>Top SHAP drivers (first alert)</h2><ul>{items}</ul>"
    lead_html = (f"<div class='kv'><b>Lead time</b><span>{lead} min before "
                 f"detonation</span></div>") if lead is not None else ""
    return f"""<!doctype html><html><head><meta charset="utf-8">
<title>Incident Report {sess['session_id']}</title><style>{_CSS}</style></head>
<body><div class="wrap">
<h1>Incident Report <span class="badge {sev}">{badge}</span></h1>
<p class="meta">Session <code>{sess['session_id']}</code> · {sess.get('kind','—')} ·
scenario <code>{sess.get('scenario','—')}</code> · generated {time.strftime('%Y-%m-%d %H:%M')}</p>
<h2>Executive summary</h2>
<div class="kv">
<b>Hosts implicated</b><span>{', '.join(hosts_hit) if hosts_hit else 'single-segment / none'}</span>
<b>Alerts</b><span>{len(alerts)}</span>
<b>Campaigns</b><span>{len(campaigns) or 0}</span>
<b>Response actions</b><span>{len(actions)}</span>
</div>
{lead_html}
<h2>Timeline</h2>
<table><tr><th>sim-min</th><th>host</th><th>P(attack)</th><th>MITRE</th><th>stage</th><th>horizon</th></tr>
{rows_a}</table>
<h2>Campaign attribution</h2>
<table><tr><th>campaign</th><th>verdict</th><th>hosts</th><th>alerts</th><th>max P</th></tr>
{rows_c}</table>
<h2>Response actions</h2>
<table><tr><th>time</th><th>host</th><th>action</th><th>actor</th><th>state</th></tr>
{rows_act}</table>
{shap_html}
<div class="footer">AegisForecast — AI-based Network Attack Forecasting ·
zero-upload eBPF telemetry · Bi-LSTM+Attention · SHAP explainability · MITRE ATT&CK</div>
</div></body></html>"""
