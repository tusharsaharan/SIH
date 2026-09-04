"""Bridge: run Bandit (and optionally Semgrep) AST scans -> Findings -> playbook.

Used by the mitigation pipeline: source code repositories are analyzed with
Semgrep & Bandit (AST analyzers), and the vulnerability facts feed the
guardrailed playbook generator.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import List

from aegis.playbooks import Finding


def bandit_scan(target: str | Path) -> List[Finding]:
    """Run bandit JSON scan over a path; map to Finding records."""
    target = str(target)
    cmd = [sys.executable, "-m", "bandit", "-r", target, "-f", "json", "-q"]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    except FileNotFoundError:
        return []
    if not out.stdout.strip():
        return []
    try:
        data = json.loads(out.stdout)
    except json.JSONDecodeError:
        return []
    findings = []
    for r in data.get("results", []):
        sev = {"HIGH": "HIGH", "MEDIUM": "MEDIUM", "LOW": "LOW"}.get(r.get("issue_severity", ""), "LOW")
        findings.append(Finding(
            scanner="bandit",
            rule_id=str(r.get("test_id", "")),
            severity=sev,
            file=str(r.get("filename", "")),
            line=int(r.get("line_number", 0) or 0),
            description=str(r.get("issue_text", "")),
            cwe=None,
        ))
    return findings


def semgrep_scan(target: str | Path) -> List[Finding]:
    """Run semgrep JSON scan if installed; else return [] gracefully."""
    try:
        out = subprocess.run(
            ["semgrep", "--config", "auto", "--json", str(target)],
            capture_output=True, text=True, timeout=300,
        )
        data = json.loads(out.stdout or "{}")
    except (FileNotFoundError, json.JSONDecodeError, subprocess.TimeoutExpired):
        return []
    findings = []
    for r in data.get("results", []):
        sev = str(r.get("extra", {}).get("severity", "INFO")).upper()
        findings.append(Finding(
            scanner="semgrep",
            rule_id=str(r.get("check_id", "")),
            severity="HIGH" if sev == "ERROR" else "MEDIUM" if sev == "WARNING" else "LOW",
            file=str(r.get("path", "")),
            line=int(r.get("start", {}).get("line", 0) or 0),
            description=str(r.get("extra", {}).get("message", ""))[:200],
            cwe=str(r.get("extra", {}).get("cwe", "")).replace("CWE-", "") or None,
        ))
    return findings


def scan_repositories(root: str | Path) -> List[Finding]:
    """Full pipeline scan: bandit + semgrep (if available)."""
    return bandit_scan(root) + semgrep_scan(root)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("target", help="path to source code to scan")
    ap.add_argument("--context-mitre", default=None, help="current ATT&CK tactic for context")
    args = ap.parse_args()

    fs = scan_repositories(args.target)
    pb = generate_playbook(fs, stage_ctx={"mitre": args.context_mitre} if args.context_mitre else {})
    from aegis.playbooks import render_markdown
    print(render_markdown(pb))
