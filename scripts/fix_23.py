"""Fix 2/3 inaudible + seek jump: loudnorm all voices, uniform re-encode concat."""
from pathlib import Path
import subprocess
import imageio_ffmpeg
FF = imageio_ffmpeg.get_ffmpeg_exe()
ROOT = Path(r"C:\Users\tusha\OneDrive\Desktop\SIH")
VIN = ROOT / "voice_input"
TMP = Path(r"C:\Users\tusha\AppData\Local\Temp\opencode\aegis_video")
OUT = ROOT / "aegisforecast_2min_real.mp4"

NAMES = ["TUSHAR", "SAHIL", "SHIVAM", "CHINMAY", "LAKSHYA GUPTA", "TUSHAR"]
KEYS = ["tushar", "sahil", "shivam", "chinmay", "lakshya", "tushar2"]

def find_voice(key):
    kn = key.replace("_", "").replace("-", "")
    cands = [p for p in VIN.iterdir() if p.is_file() and p.suffix.lower() in
             (".m4a",".mp3",".wav",".ogg",".aac",".wma",".mpeg",".mpg",".mp4",".mov",".webm")
             and kn in p.stem.lower().replace("_","").replace("-","") and p.name.lower() != "readme.md"]
    if key in ("tushar","tushar2"):
        want2 = ("2" in key)
        cands = [p for p in cands if ("2" in p.stem) == want2]
    return sorted(cands)[0]

# 1. loudnorm each voice to uniform wav (boost quiet Sahil/Shivam to match)
norms = []
for i, k in enumerate(KEYS):
    src = find_voice(k)
    nw = TMP / f"norm_{i:02d}.wav"
    subprocess.run([FF,"-y","-i",str(src),
        "-af","loudnorm=I=-12:TP=-1.0:LRA=7,volume=6dB,alimiter=limit=0.95,aresample=48000,aformat=channel_layouts=mono",
        "-ar","48000","-ac","1",str(nw)], check=True, capture_output=True)
    norms.append(nw)
    print(f"norm {i} {NAMES[i]} {src.name} ok")

# 2. build uniform segments (same codecs/params, re-encoded later)
from PIL import Image, ImageDraw, ImageFont
def font(sz, bold=False):
    import os
    for p in [r"C:\Windows\Fonts\arialbd.ttf" if bold else r"C:\Windows\Fonts\arial.ttf"]:
        if os.path.exists(p):
            try: return ImageFont.truetype(p, sz)
            except: pass
    return ImageFont.load_default()

segs = []
for i in range(6):
    base = Image.open(TMP/f"slide_{i:02d}.png").convert("RGB")
    d = ImageDraw.Draw(base)
    tag = f"VOICE: {NAMES[i]}"
    f = font(24, True)
    tw = d.textlength(tag, font=f)
    x, y = 1280-80-int(tw)-24, 720-60
    d.rounded_rectangle([x-12, y-8, x+int(tw)+12, y+32], radius=8, fill=(0,200,220))
    d.text((x, y), tag, font=f, fill=(0,0,0))
    sp = TMP/f"slide_fix_{i:02d}.png"
    base.save(sp)
    seg = TMP/f"segF_{i:02d}.mp4"
    # -t from norm wav duration + 1.0s padding; uniform 25fps + aac 48k mono
    import re
    r = subprocess.run([FF,"-i",str(norms[i])], capture_output=True, text=True)
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", r.stderr)
    t = int(m.group(1))*3600+int(m.group(2))*60+float(m.group(3))+1.0 if m else 18.0
    subprocess.run([FF,"-y","-loop","1","-framerate","25","-i",str(sp),"-i",str(norms[i]),
        "-map","0:v:0","-map","1:a:0",
        "-c:v","libx264","-preset","medium","-crf","21","-r","25",
        "-c:a","aac","-ar","48000","-ac","1","-b:a","128k",
        "-t",f"{t:.2f}","-pix_fmt","yuv420p","-shortest",str(seg)],
        check=True, capture_output=True)
    segs.append(seg)
    print(f"seg {i+1}/6 {NAMES[i]} {t-1.0:.1f}s ok")

# 3. final concat WITH re-encode (fixes seek jump / DTS issues)
inputs = []
for s in segs:
    inputs += ["-i", str(s)]
fc = "".join(f"[{i}:v:0][{i}:a:0]" for i in range(6)) + f"concat=n=6:v=1:a=1[v][a]"
cmd = [FF,"-y",*inputs,"-filter_complex",fc,
       "-map","[v]","-map","[a]",
       "-c:v","libx264","-preset","medium","-crf","21","-r","25",
       "-c:a","aac","-ar","48000","-ac","1","-b:a","128k",
       "-pix_fmt","yuv420p","-movflags","+faststart",str(OUT)]
subprocess.run(cmd, check=True, capture_output=True)
print("WROTE", OUT, OUT.stat().st_size//1024, "KB")
r = subprocess.run([FF,"-i",str(OUT)], capture_output=True, text=True)
print([l.strip() for l in r.stderr.splitlines() if "Duration" in l][:1])
