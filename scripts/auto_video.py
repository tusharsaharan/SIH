"""Auto-generate 2-min AegisForecast explainer video - zero manual editing.
Slides (Pillow) + voiceover (edge-tts) + mux (imageio-ffmpeg binary).
Output: aegisforecast_2min.mp4 in repo root.
"""
import asyncio, subprocess, sys, os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import imageio_ffmpeg

ROOT = Path(r"C:\Users\tusha\OneDrive\Desktop\SIH")
OUT = ROOT / "aegisforecast_2min.mp4"
TMP = Path(r"C:\Users\tusha\AppData\Local\Temp\opencode\aegis_video")
TMP.mkdir(parents=True, exist_ok=True)
FF = imageio_ffmpeg.get_ffmpeg_exe()
W, H = 1280, 720

# 6 segments ~20s each = 120s. Script ~270 words.
SEGMENTS = [
  {
    "title": "AEGISFORECAST",
    "subtitle": "Forecast attacks. Before detonation.",
    "body": "SIH / NTRO PS 25217  |  Team Entropy",
    "vo": "Cyberattacks detonate in seconds. Defenses react after the damage is done. What if you could forecast an attack twenty minutes before it happens? Meet AegisForecast.",
    "bg": (10, 18, 38),
  },
  {
    "title": "THE PROBLEM",
    "subtitle": "Reactive SOCs fail",
    "body": "Terabytes of pcaps  |  Alert fatigue  |  Zero lead time",
    "vo": "Today's security centers are reactive. They store gigabytes of packet captures, drown in false positives, and detect intrusions only after data is stolen. We needed a system that predicts, not just detects.",
    "bg": (38, 10, 18),
  },
  {
    "title": "HOW IT WORKS",
    "subtitle": "Zero-upload telemetry engine",
    "body": "Live traffic > eBPF probe > 5s flow stats > Bi-LSTM + Transformer\nNo pcap ever written  |  22 features x 48 windows",
    "vo": "AegisForecast folds live traffic into in-memory five second flow statistics. No pcap is ever written. A per-host Bi-LSTM with attention, challenged by a Transformer, watches forty eight windows and predicts attack probability, MITRE stage, and minutes to detonation.",
    "bg": (8, 32, 44),
  },
  {
    "title": "LIVE SOC DASHBOARD",
    "subtitle": "WEB 0.998 risk  |  benign hosts 0.013",
    "body": "Topology map  |  SHAP explain in 6ms  |  Auto-SOAR contain",
    "vo": "On the live dashboard you see lateral movement across five hosts. WEB spikes to point nine nine eight risk while benign hosts stay at point zero one three. Every alert is explained with SHAP in six milliseconds, correlated into campaigns, and auto-contained by SOAR.",
    "bg": (10, 18, 38),
    "image": ROOT / "docs" / "soc-ivory-dashboard.png",
  },
  {
    "title": "PROVEN, NOT CLAIMED",
    "subtitle": "AUC 0.985  |  20 min median lead  |  100% coverage",
    "body": "Transformer AUC 0.985  |  Horizon error 4.3 min  |  CIC-IDS2017 zero-shot\nSlow-scan + mimicry: CAUGHT",
    "vo": "And it is proven, not claimed. Transformer A U C zero point nine eight five. One hundred percent coverage with twenty minute median lead time. Validated zero shot on real CIC IDS 2017 captures. Even stealth slow scans are caught.",
    "bg": (18, 34, 20),
  },
  {
    "title": "AEGISFORECAST",
    "subtitle": "Forecast. Explain. Contain.",
    "body": "github.com/TeamEntropy  |  SIH Final 2026",
    "vo": "AegisForecast. Forecast. Explain. Contain. Thank you.",
    "bg": (10, 18, 38),
  },
]

def get_font(size, bold=False):
    for p in [r"C:\Windows\Fonts\arialbd.ttf" if bold else r"C:\Windows\Fonts\arial.ttf",
              r"C:\Windows\Fonts\segoeui.ttf"]:
        if os.path.exists(p):
            try: return ImageFont.truetype(p, size)
            except: pass
    return ImageFont.load_default()

def wrap(draw, text, font, max_w):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if draw.textlength(t, font=font) <= max_w: cur = t
        else: lines.append(cur); cur = w
    if cur: lines.append(cur)
    return lines

def make_slide(seg, idx):
    img = Image.new("RGB", (W, H), seg["bg"])
    d = ImageDraw.Draw(img)
    # accent bar
    d.rectangle([0, 0, W, 10], fill=(0, 200, 220))
    d.rectangle([0, H-10, W, H], fill=(0, 200, 220))
    fT, fS, fB = get_font(64, True), get_font(34), get_font(26)
    y = 70
    d.text((80, y), seg["title"], font=fT, fill=(255, 255, 255)); y += 95
    d.text((80, y), seg["subtitle"], font=fS, fill=(120, 220, 255)); y += 65
    for line in seg["body"].split("\n"):
        for wl in wrap(d, line, fB, W-200):
            d.text((80, y), wl, font=fB, fill=(225, 235, 245)); y += 38
        y += 6
    # dashboard screenshot inset on slide 4
    if "image" in seg and seg["image"].exists():
        try:
            shot = Image.open(seg["image"]).convert("RGB")
            shot.thumbnail((1120, 340), Image.LANCZOS)
            img.paste(shot, (80, 400))
            d.rectangle([80, 400, 80+shot.width, 400+shot.height], outline=(0,200,220), width=2)
        except Exception as e:
            print("shot fail:", e)
    # slide number + progress bar
    d.text((80, H-60), f"{idx+1} / {len(SEGMENTS)}  |  AegisForecast 2-min explainer", font=get_font(20), fill=(150,170,190))
    pw = int(W * (idx+1) / len(SEGMENTS))
    d.rectangle([0, H-10, pw, H], fill=(255,255,255))
    p = TMP / f"slide_{idx:02d}.png"
    img.save(p)
    return p

async def make_audio(text, out):
    import edge_tts
    c = edge_tts.Communicate(text, voice="en-IN-PrabhatNeural", rate="-5%")
    await c.save(str(out))
    return out

def probe_dur(mp3):
    r = subprocess.run([FF, "-i", str(mp3)], capture_output=True, text=True)
    import re
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", r.stderr)
    if not m: return 0
    return int(m.group(1))*3600 + int(m.group(2))*60 + float(m.group(3))

async def main():
    slides = [make_slide(s, i) for i, s in enumerate(SEGMENTS)]
    print("slides done")
    segs = []
    # TTS
    audios = []
    try:
        for i, s in enumerate(SEGMENTS):
            mp3 = TMP / f"vo_{i:02d}.mp3"
            await make_audio(s["vo"], mp3)
            audios.append(mp3)
        print("tts ok")
    except Exception as e:
        print("TTS failed, silent fallback:", e)
        audios = []
    # Build per-segment mp4s
    for i, slide in enumerate(slides):
        seg = TMP / f"seg_{i:02d}.mp4"
        if i < len(audios) and audios[i].exists():
            dur = max(probe_dur(audios[i]) + 1.0, 6.0)
            cmd = [FF, "-y", "-loop", "1", "-i", str(slide), "-i", str(audios[i]),
                   "-c:v", "libx264", "-tune", "stillimage", "-c:a", "aac",
                   "-t", f"{dur:.1f}", "-pix_fmt", "yuv420p", "-shortest", str(seg)]
        else:
            cmd = [FF, "-y", "-loop", "1", "-i", str(slide),
                   "-c:v", "libx264", "-t", "20", "-pix_fmt", "yuv420p", str(seg)]
        subprocess.run(cmd, check=True, capture_output=True)
        segs.append(seg)
        print(f"seg {i+1}/{len(slides)} done")
    # concat
    lst = TMP / "list.txt"
    lst.write_text("\n".join(f"file '{s.as_posix()}'" for s in segs))
    subprocess.run([FF, "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(OUT)], check=True)
    print("WROTE", OUT, OUT.stat().st_size // 1024, "KB")

asyncio.run(main())
