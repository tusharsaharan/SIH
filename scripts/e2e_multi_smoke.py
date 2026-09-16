"""E2E smoke test: multi-host session -> alerts -> SOAR -> report."""
import asyncio
import json
import sys

sys.path.insert(0, ".")

import httpx
import websockets


async def main():
    async with httpx.AsyncClient() as c:
        r = await c.post("http://127.0.0.1:8000/api/sim/start",
                         params={"kind": "multi", "speed": 200.0})
        data = r.json()
        print("start:", data)
        sid = data["sessionId"]

    n = {"telemetry": 0, "alert": 0, "containment": 0, "soar": 0, "edge": 0}
    hosts_alerted = set()
    first_alert = None
    async with websockets.connect("ws://127.0.0.1:8000/ws", max_size=None) as ws:
        t0 = asyncio.get_event_loop().time()
        while asyncio.get_event_loop().time() - t0 < 75:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=10.0)
            except asyncio.TimeoutError:
                break
            msg = json.loads(raw)
            k = msg.get("type", msg.get("event", ""))
            if k == "telemetry":
                n["telemetry"] += 1
            elif k == "alert":
                n["alert"] += 1
                hosts_alerted.add(msg.get("host"))
                if first_alert is None:
                    first_alert = msg
                    print(f"FIRST ALERT t+{msg['simMinute']}m on {msg['host']} "
                          f"{msg['mitre']} P={msg['attackProb']:.2f} "
                          f"horizon={msg['horizonMin']}m")
                    e = msg.get("enrichment") or {}
                    print(f"  enrichment: {e.get('verdict')} / {e.get('geo')} "
                          f"/ campaigns={e.get('campaigns')}")
            elif k == "containment":
                n["containment"] += 1
            elif k == "soar":
                n["soar"] += 1
                if n["soar"] <= 3:
                    print(f"SOAR: {msg['host']} {msg['fromState']}->{msg['toState']} "
                          f"by {msg['actor']}")
            elif k == "topology_edge":
                n["edge"] += 1
            elif k == "event" and msg.get("event") == "detonation":
                print(f"DETONATION t+{msg['simMinute']}m on {msg.get('detonatedHost')}")
            elif k == "event" and msg.get("event") == "session_end":
                break

    print("counts:", n, "| hosts alerted:", sorted(hosts_alerted))

    async with httpx.AsyncClient() as c:
        topo = (await c.get("http://127.0.0.1:8000/api/topology")).json()
        print("host risks:", {h["name"]: h["risk"] for h in topo["hosts"]})
        camps = (await c.get("http://127.0.0.1:8000/api/campaigns")).json()
        print("campaigns:", [(x["campaign"], x["nAlerts"], x["hosts"]) for x in camps["campaigns"]])
        # manual SOAR on an incident (WEB is the attacked host in multi mode)
        r = (await c.post("http://127.0.0.1:8000/api/respond",
                          params={"host": "WEB", "action": "triage"})).json()
        print("respond:", r.get("ok"), r.get("incident", {}).get("toState"))
        # report
        rep = (await c.get(f"http://127.0.0.1:8000/api/report/{sid}.md")).text
        print("report first line:", rep.splitlines()[0])
        print("report has timeline:", "## Timeline" in rep,
              "| campaigns:", "## Campaign attribution" in rep)
        await c.post("http://127.0.0.1:8000/api/sim/stop")


asyncio.run(main())
