"""Deliberately VULNERABLE training target for the AegisForecast sandbox.

This code intentionally contains weaknesses (SQLi, command injection, weak
crypto, hardcoded secret, pickle deserialization) so the sandbox can stage
realistic multi-stage attacks and the AST scanner -> playbook pipeline has
genuine findings to work with. Never deploy this anywhere.
"""

import os
import pickle
import sqlite3
import subprocess

from flask import Flask, request

app = Flask(__name__)
DB = "/tmp/app.db"

SECRET_API_KEY = "sk-live-9f8e7d6c5b4a3210987654321fedcba"   # B105 hardcoded secret


def init_db():
    con = sqlite3.connect(DB)
    con.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT)")
    con.execute("INSERT OR IGNORE INTO users VALUES (1, 'admin')")
    con.commit()
    con.close()


@app.route("/user")
def get_user():
    uid = request.args.get("id", "1")
    # VULN: string-formatted SQL -> SQL injection (bandit B608)
    con = sqlite3.connect(DB)
    rows = con.execute(f"SELECT * FROM users WHERE id = {uid}").fetchall()
    con.close()
    return {"user": rows}


@app.route("/ping")
def ping():
    host = request.args.get("host", "127.0.0.1")
    # VULN: shell=True with user input -> command injection (bandit B602/B605)
    out = subprocess.run(f"ping -c 1 {host}", shell=True, capture_output=True, text=True)
    return {"output": out.stdout}


@app.route("/load")
def load_state():
    blob = request.args.get("state", "")
    # VULN: unsafe deserialization (bandit B301)
    try:
        return {"state": pickle.loads(bytes.fromhex(blob))}
    except Exception:
        return {"error": "bad state"}, 400


@app.route("/token/<name>")
def token(name):
    # VULN: weak hash for token generation (bandit B324)
    import hashlib
    return {"token": hashlib.md5(name.encode()).hexdigest()}


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=8080)
