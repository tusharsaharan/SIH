"""Full WS smoke test: sim session -> alerts -> containment, at th=0.80."""
import asyncio
import json
import sys

sys.path.insert(0, ".")

import httpx
import websockets


async def main():
    async with httpx.AsyncClient() as c:
        r = await c.post("http://127.0.0.1:8000/api/sim/start",
                         params={"recon_min": 8.0, "det_min": 12.0, "speed": 240.0})
        print("start:", r.json())

    n_tel, n_alert, n_cont = 0, 0, 0
    first_alert_min = None
    async with websockets.connect("ws://127.0.0.1:8000/ws", max_size=None) as ws:
        t0 = asyncio.get_event_loop().time()
        while asyncio.get_event_loop().time() - t0 < 60:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=10.0)
            except asyncio.TimeoutError:
                break
            msg = json.loads(raw)
            k = msg.get("type")
            if k == "telemetry":
                n_tel += 1
            elif k == "alert":
                n_alert += 1
                if first_alert_min is None:
                    first_alert_min = msg["simMinute"]
                    print(f"FIRST ALERT t+{msg['simMinute']}m "
                          f"(detonation 12.0m -> lead {12.0 - msg['simMinute']:.1f}m) "
                          f"{msg['mitre']} horizon={msg['horizonMin']}m")
            elif k == "containment":
                n_cont += 1
                print("CONTAINMENT:", msg["rule"])
            elif k == "event" and msg.get("event") == "detonation":
                print(f"DETONATION at t+{msg['simMinute']}m")
            elif k == "event" and msg.get("event") == "session_end":
                break
    print(f"telemetry={n_tel} alerts={n_alert} containment={n_cont} "
          f"first_alert={first_alert_min}")
    async with httpx.AsyncClient() as c:
        await c.post("http://127.0.0.1:8000/api/sim/stop")


asyncio.run(main())
