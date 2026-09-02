"""Guardrailed playbook generator (deterministic, zero-hallucination).

Takes scanner findings (Semgrep/Bandit AST facts) + the current ATT&CK stage
context and assembles a mitigation playbook from a **fixed template library**.
Every output is drawn from vetted fragments - the LLM never free-generates
rules, so it cannot hallucinate. This is the 'guardrailed LLM playbook
generator' from the architecture: template-constrained generation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class Finding:
    scanner: str          # semgrep | bandit | manual
    rule_id: str          # e.g. B608 (bandit) / python.lang.security.audit...
    severity: str         # HIGH | MEDIUM | LOW
    file: str
    line: int
    description: str
    cwe: Optional[str] = None


# ---------------------------------------------------------------- templates
# key: (cwe or rule family) -> containment + hardening + verification steps
PLAYBOOKS: Dict[str, Dict[str, List[str]]] = {
    "sql-injection": {
        "contain": [
            "WAF: block UNION/SELECT-stacked query signatures on affected endpoints",
            "Firewall: rate-limit 20 req/min per source IP on the affected route",
        ],
        "harden": [
            "Replace string-formatted SQL with parameterized queries (placeholders)",
            "Adopt an ORM or query builder; forbid raw string SQL in CI (semgrep rule)",
            "Least-privilege DB account; revoke WRITE on reporting services",
        ],
        "verify": [
            "Re-run semgrep on the PR; B608-equivalent findings must be zero",
            "Fuzz inputs on staging with sqlmap in audit-only mode",
        ],
    },
    "xss": {
        "contain": [
            "WAF: enforce Content-Security-Policy default-src 'self' on affected app",
        ],
        "harden": [
            "Escape untrusted output at render time (contextual auto-escaping)",
            "Validate inputs against allow-lists; reject HTML payloads",
        ],
        "verify": [
            "Re-test payload vector with browser DevTools DOM inspection",
        ],
    },
    "weak-crypto": {
        "contain": [
            "Flag affected endpoints for TLS-only enforcement at the gateway",
        ],
        "harden": [
            "Replace MD5/DES/RC4 with SHA-256/AES-GCM or Argon2 for passwords",
            "Rotate any keys issued under the weak primitive",
        ],
        "verify": [
            "bandit -r on the module must report zero weak-crypto findings",
        ],
    },
    "command-injection": {
        "contain": [
            "Firewall: block unsolicited outbound DNS/ICMP from the affected host (C2 channel)",
            "Sandbox: deny exec of /bin/sh from the service account",
        ],
        "harden": [
            "Use subprocess with shell=False and explicit argv lists",
            "Never interpolate user input into commands; use allow-listed params",
        ],
        "verify": [
            "Semgrep rule python.lang.security.audit.subprocess-shell must be clean",
        ],
    },
    "hardcoded-secret": {
        "contain": [
            "Rotate the exposed credential immediately (assume compromised)",
            "Firewall: block the source IP if the secret grants remote access",
        ],
        "harden": [
            "Move secrets to a vault/env injection; strip from repo history",
            "Enable pre-commit secret scanning",
        ],
        "verify": [
            "git-secrets / gitleaks scan returns zero findings",
        ],
    },
    "insecure-deserialization": {
        "contain": [
            "WAF: reject requests containing serialized object payloads (pickle/yaml)",
        ],
        "harden": [
            "Use JSON with strict schemas instead of native serialization",
            "If pickle is mandatory, gate behind HMAC-signed envelopes",
        ],
        "verify": [
            "Negative tests: malformed payloads must 4xx, never 500",
        ],
    },
}

# rule_id / cwe -> playbook key
FINDING_MAP = {
    "B608": "sql-injection", "B603": "command-injection",
    "B602": "command-injection", "B605": "command-injection",
    "B404": "command-injection",
    "B324": "weak-crypto", "B303": "weak-crypto", "B305": "weak-crypto",
    "B301": "insecure-deserialization",
    "B105": "hardcoded-secret", "B106": "hardcoded-secret",
    "B107": "hardcoded-secret",
    "subprocess-shell": "command-injection",
    "sql-injection": "sql-injection",
    "hardcoded-tempfile": "hardcoded-secret",
    # aegis-ast built-in scanner rules
    "sqli-001": "sql-injection",
    "cmd-001": "command-injection",
    "cmd-002": "command-injection",
    "sec-001": "insecure-deserialization",
    "sec-002": "weak-crypto",
    "sec-003": "hardcoded-secret",
    "xss-001": "xss",
}


def map_finding(f: Finding) -> str:
    rid = f.rule_id.lower()
    for key, family in FINDING_MAP.items():
        if key.lower() in rid or (f.cwe and key.lower() == f.cwe.lower()):
            return family
    # semgrep rules often carry the family in the id
    for fam in PLAYBOOKS:
        if fam.replace("-", ".") in rid or fam.replace("-", "_") in rid or fam in rid:
            return fam
    return ""


def generate_playbook(findings: List[Finding], stage_ctx: Optional[dict] = None) -> dict:
    """Assemble a deterministic playbook: contain -> harden -> verify."""
    grouped: Dict[str, List[Finding]] = {}
    for f in findings:
        fam = map_finding(f)
        if fam:
            grouped.setdefault(fam, []).append(f)

    steps = []
    for fam, fs in grouped.items():
        pb = PLAYBOOKS[fam]
        steps.append({
            "family": fam,
            "severity": max((f.severity for f in fs), key=lambda s: {"HIGH": 3, "MEDIUM": 2, "LOW": 1}.get(s, 0)),
            "evidence": [
                {"scanner": f.scanner, "rule": f.rule_id, "loc": f"{f.file}:{f.line}", "desc": f.description}
                for f in fs[:5]
            ],
            "contain": pb["contain"],
            "harden": pb["harden"],
            "verify": pb["verify"],
        })

    steps.sort(key=lambda s: -{"HIGH": 3, "MEDIUM": 2, "LOW": 1}.get(s["severity"], 0))
    return {
        "generatedBy": "guardrailed-template-engine v0.1 (zero-hallucination)",
        "attackContext": stage_ctx or {},
        "steps": steps,
        "unmapped": [
            {"rule": f.rule_id, "loc": f"{f.file}:{f.line}"} for f in findings if not map_finding(f)
        ],
    }


def render_markdown(pb: dict) -> str:
    lines = [f"# Mitigation Playbook", "",
             f"_generated by {pb['generatedBy']}_", ""]
    if pb.get("attackContext"):
        ac = pb["attackContext"]
        lines += [f"**Attack context:** {ac.get('mitre', '—')} · {ac.get('stage', '—')} · "
                  f"confidence {ac.get('confidence', '—')}", ""]
    for i, s in enumerate(pb["steps"], 1):
        lines.append(f"## {i}. {s['family']} ({s['severity']})")
        lines.append("")
        for ev in s["evidence"]:
            lines.append(f"- evidence: `{ev['loc']}` — {ev['desc']} ({ev['scanner']} {ev['rule']})")
        lines.append("")
        for sec in ("contain", "harden", "verify"):
            lines.append(f"**{sec.title()}**")
            lines += [f"- [ ] {x}" for x in s[sec]]
            lines.append("")
    if pb["unmapped"]:
        lines.append("## Unmapped findings (manual triage)")
        lines += [f"- `{u['rule']}` @ {u['loc']}" for u in pb["unmapped"]]
    return "\n".join(lines)
