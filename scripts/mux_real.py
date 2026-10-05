"""Mux REAL team voices from voice_input/ -> aegisforecast_2min_real.mp4. Any ext: m4a/mp3/wav/ogg."""
from pathlib import Path
import subprocess, re
from PIL import Image, ImageDraw, ImageFont
import imageio_ffmpeg
FF = imageio_ffmpeg.get_ffmpeg_exe()
ROOT = Path(r"C:\Users\tusha\OneDrive\Desktop\SIH")
VIN = ROOT / "voice_input"
TMP = Path(r"C:\Users\tusha\AppData\Local\Temp\opencode\aegis_video")
TMP.mkdir(parents=True, exist_ok=True)
OUT = ROOT / "aegisforecast_2min_real.mp4"

NAMES = ["TUSHAR", "SAHIL", "SHIVAM", "CHINMAY", "LAKSHYA GUPTA", "TUSHAR"]
PREFIX = ["01_tushar", "02_sahil", "03_shivam", "04_chinmay", "05_lakshya", "06_tushar2"]

def find_voice(prefix):
    # fuzzy: match any file containing the name part (case-insensitive)
    key = prefix[3:] if "_" in prefix else prefix  # 01_tushar -> tushar
    key = key.lower().replace("_","").replace("-","")
    cands = [p for p in VIN.iterdir() if p.is_file() and p.suffix.lower() in
             (".m4a",".mp3",".wav",".ogg",".aac",".wma",".mpeg",".mpg",".mp4",".mov",".webm")
             and key in p.stem.lower().replace("_","").replace("-","") and p.name.lower() != "readme.md"]
    # disambiguate tushar vs tushar2: exact 06 slot wants file with 2 in name
    if key in ("tushar", "tushar2"):
        want2 = ("2" in prefix)
        cands = [p for p in cands if ("2" in p.stem) == want2]
    if cands: return sorted(cands)[0]
    # fallback to exact prefix match (old scheme)
    for ext in ["*.m4a", "*.mp3", "*.wav", "*.ogg", "*.aac", "*.wma"]:
        hits = list(VIN.glob(prefix + ext))
        if hits: return hits[0]
    # also try without number
    return None

def font(sz, bold=False):
    import os
    for p in [r"C:\Windows\Fonts\arialbd.ttf" if bold else r"C:\Windows\Fonts\arial.ttf"]:
        if os.path.exists(p):
            try: return ImageFont.truetype(p, sz)
            except: pass
    return ImageFont.load_default()

def dur(p):
    r = subprocess.run([FF, "-i", str(p)], capture_output=True, text=True)
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", r.stderr)
    if not m: raise RuntimeError(f"cannot read duration {p}: {r.stderr[-300:]}")
    return int(m.group(1))*3600 + int(m.group(2))*60 + float(m.group(3))

missing = [p for p in PREFIX if find_voice(p) is None]
if missing:
    print("MISSING:", missing)
    print("Drop files in:", VIN)
    raise SystemExit(1)

segs = []
for i in range(6):
    aud = find_voice(PREFIX[i])
    base = Image.open(TMP/f"slide_{i:02d}.png").convert("RGB")
    d = ImageDraw.Draw(base)
    tag = f"VOICE: {NAMES[i]}"
    f = font(24, True)
    tw = d.textlength(tag, font=f)
    x, y = 1280-80-int(tw)-24, 720-60
    d.rounded_rectangle([x-12, y-8, x+int(tw)+12, y+32], radius=8, fill=(0,200,220))
    d.text((x, y), tag, font=f, fill=(0,0,0))
    sp = TMP/f"slide_real_{i:02d}.png"
    base.save(sp)
    t = dur(aud) + 1.0
    seg = TMP/f"segR_{i:02d}.mp4"
    subprocess.run([FF,"-y","-loop","1","-i",str(sp),"-i",str(aud),
        "-map","0:v:0","-map","1:a:0?",
        "-c:v","libx264","-tune","stillimage","-c:a","aac",
        "-t",f"{t:.1f}","-pix_fmt","yuv420p","-shortest",str(seg)],
        check=True, capture_output=True)
    segs.append(seg)
    print(f"seg {i+1}/6 {NAMES[i]} {aud.name} {t-1.0:.1f}s ok")

lst = TMP/"listR.txt"
lst.write_text("\n".join(f"file '{s.as_posix()}'" for s in segs))
subprocess.run([FF,"-y","-f","concat","-safe","0","-i",str(lst),"-c","copy",str(OUT)], check=True)
print("WROTE", OUT, OUT.stat().st_size//1024, "KB")
