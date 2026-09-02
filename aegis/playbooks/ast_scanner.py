"""Built-in AST vulnerability scanner (pure stdlib - no external tools).

Provides the same Finding records as the Semgrep/Bandit bridge, using
Python's `ast` module. Detection rules are conservative and pattern-based:

  SQLI-001   string-formatted / concatenated SQL execute  -> sql-injection
  CMD-001    subprocess with shell=True                   -> command-injection
  CMD-002    os.system / os.popen with any input          -> command-injection
  SEC-001    pickle.loads on untrusted path               -> insecure-deserialization
  SEC-002    hashlib md5/sha1 usage                       -> weak-crypto
  SEC-003    hardcoded secrets (NAME/KEY/PASSWORD/SECRET = "literal") -> hardcoded-secret
  XSS-001    unescaped HTML rendering of non-literal input -> xss

Zero dependencies, deterministic, CI-friendly. In production the richer
Semgrep/Bandit rule sets run via aegis.playbooks.scanner; this module keeps
the pipeline fully demonstrable offline.
"""

from __future__ import annotations

import ast
import hashlib
from pathlib import Path
from typing import List

from aegis.playbooks import Finding


# ------------------------------------------------------------------ helpers
_SQL_EXECUTE = {"execute", "executemany", "executescript"}
_SECRET_NAMES = ("password", "secret", "api_key", "apikey", "token",
                 "access_key", "private_key", "auth")
_WEAK_HASHES = {"md5", "sha1"}
_DESERIALIZE = {"loads", "load"}


def _is_str_format_or_concat(node: ast.AST) -> bool:
    """True for f-strings, %, +, or .format(...) over non-constant exprs."""
    if isinstance(node, ast.JoinedStr):
        return any(not isinstance(v, ast.Constant) for v in node.values)
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Mod, ast.Add)):
        return not (isinstance(node.left, ast.Constant) and isinstance(node.right, ast.Constant))
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
            and node.func.attr == "format":
        return not all(isinstance(a, ast.Constant) for a in node.args)
    return False


def _literal_str(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


# ------------------------------------------------------------------- visitor
class _SecVisitor(ast.NodeVisitor):
    def __init__(self, filename: str):
        self.findings: List[Finding] = []
        self.filename = filename

    def _add(self, rule: str, sev: str, node: ast.AST, desc: str):
        self.findings.append(Finding(
            scanner="aegis-ast", rule_id=rule, severity=sev,
            file=self.filename, line=getattr(node, "lineno", 0),
            description=desc,
        ))

    # SQL injection ------------------------------------------------------
    def visit_Call(self, node: ast.Call):                     # noqa: N802
        func = node.func
        # con.execute(f"...", ...) / cursor.execute("..." + x)
        if isinstance(func, ast.Attribute) and func.attr in _SQL_EXECUTE:
            if node.args and _is_str_format_or_concat(node.args[0]):
                self._add("SQLI-001", "HIGH", node,
                          f"SQL built via string formatting in .{func.attr}() "
                          f"- parameterize the query")
        # subprocess.*(shell=True)
        if isinstance(func, ast.Attribute) and func.attr in {
                "run", "call", "check_output", "check_call", "Popen"}:
            for kw in node.keywords:
                if kw.arg == "shell" and isinstance(kw.value, ast.Constant) \
                        and kw.value.value is True:
                    self._add("CMD-001", "HIGH", node,
                              "subprocess call with shell=True - command "
                              "injection risk; use argv list + shell=False")
        # os.system / os.popen
        if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name) \
                and func.value.id == "os" and func.attr in {"system", "popen"}:
            self._add("CMD-002", "HIGH", node,
                      "shell invocation via os.system/os.popen - injectable")
        # pickle.loads(...)
        if (isinstance(func, ast.Attribute) and func.attr in _DESERIALIZE
                and isinstance(func.value, ast.Name) and func.value.id == "pickle"):
            self._add("SEC-001", "HIGH", node,
                      "pickle deserialization on untrusted data - arbitrary "
                      "code execution risk")
        # hashlib.md5(...) / sha1
        if isinstance(func, ast.Attribute) and func.attr in _WEAK_HASHES \
                and isinstance(func.value, ast.Name) and func.value.id == "hashlib":
            self._add("SEC-002", "MEDIUM", node,
                      f"weak hash primitive hashlib.{func.attr}() - use "
                      f"sha256/argon2 for anything security-relevant")
        # Markup(...).format(...) style or Flask render_template_string w/ f-string
        if isinstance(func, ast.Attribute) and func.attr == "render_template_string" \
                and node.args and _is_str_format_or_concat(node.args[0]):
            self._add("XSS-001", "MEDIUM", node,
                      "render_template_string with dynamic string - XSS risk; "
                      "pass variables via context instead")
        self.generic_visit(node)

    # hardcoded secrets ---------------------------------------------------
    def visit_Assign(self, node: ast.Assign):                 # noqa: N802
        for tgt in node.targets:
            if isinstance(tgt, ast.Name):
                low = tgt.id.lower()
                if any(s in low for s in _SECRET_NAMES):
                    if isinstance(node.value, ast.Constant) \
                            and isinstance(node.value.value, str) \
                            and len(node.value.value) >= 8:
                        self._add("SEC-003", "HIGH", node,
                                  f"hardcoded secret '{tgt.id}' - move to vault/env")
        self.generic_visit(node)


def scan_file(path: str | Path) -> List[Finding]:
    path = Path(path)
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"),
                         filename=str(path))
    except SyntaxError as e:
        return [Finding("aegis-ast", "PARSE-ERR", "LOW", str(path),
                        e.lineno or 0, f"parse error: {e.msg}")]
    v = _SecVisitor(str(path))
    v.visit(tree)
    return v.findings


def scan_tree(root: str | Path, max_files: int = 200) -> List[Finding]:
    root = Path(root)
    files = [p for p in root.rglob("*.py")
             if "node_modules" not in p.parts and ".venv" not in p.parts][:max_files]
    out: List[Finding] = []
    for f in files:
        out += scan_file(f)
    return out
