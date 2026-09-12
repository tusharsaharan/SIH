"""Inspect persisted alert stats per host (DB sanity check)."""
import io
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, ".")

from aegis.server import db

rows = db.get_conn().execute(
    "SELECT host, COUNT(*) n, AVG(attack_prob) p, MIN(sim_minute) mn "
    "FROM alerts GROUP BY host").fetchall()
for r in rows:
    print(f"{r['host'] or '—':>8}: {r['n']:>3} alerts, avg P={r['p']:.3f}, "
          f"first at {r['mn']}m")
