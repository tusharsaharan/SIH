import json, time, urllib.request

for _ in range(30):
    time.sleep(3)
    try:
        with urllib.request.urlopen("http://127.0.0.1:8012/api/health", timeout=5) as r:
            h = json.loads(r.read())
            print("HEALTH:", h.get("status"))
            break
    except Exception as e:
        print("wait...", str(e)[:60])
else:
    raise SystemExit("container never healthy")

with urllib.request.urlopen("http://127.0.0.1:8012/", timeout=10) as r:
    body = r.read()
    print("ROOT:", r.status, "hasRoot:", b'id="root"' in body)
print("CONTAINER OK")
