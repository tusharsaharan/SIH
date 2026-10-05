"""Boot the app on 8011 and verify single-service serving."""
import os, subprocess, sys, time, urllib.request

os.environ["PORT"] = "8011"
ROOT = r"C:\Users\tusha\OneDrive\Desktop\SIH"
p = subprocess.Popen([sys.executable, "-m", "aegis.server"], cwd=ROOT,
                     stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
try:
    health = None
    for _ in range(40):
        time.sleep(3)
        try:
            with urllib.request.urlopen("http://127.0.0.1:8011/api/health", timeout=5) as r:
                import json
                health = json.loads(r.read())
                break
        except Exception:
            pass
    assert health, "backend never became healthy"
    print("HEALTH:", health.get("status"), "threshold:", health.get("threshold"))

    def get(path):
        with urllib.request.urlopen("http://127.0.0.1:8011" + path, timeout=10) as r:
            return r.status, r.read()

    s, body = get("/")
    print("ROOT:", s, "len:", len(body), "hasRoot:", b'id="root"' in body)
    assert s == 200 and b'id="root"' in body

    s, body = get("/assets/index-wW2f78_T.js")
    print("ASSET:", s, "len:", len(body))
    assert s == 200 and len(body) > 1000

    s, body = get("/some/spa/route")
    print("SPA-FALLBACK:", s, "hasRoot:", b'id="root"' in body)
    assert s == 200 and b'id="root"' in body

    print("VERIFY OK")
finally:
    p.terminate()
