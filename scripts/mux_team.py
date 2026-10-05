from pathlib import Path
import subprocess, re
from PIL import Image, ImageDraw, ImageFont
import imageio_ffmpeg
FF = imageio_ffmpeg.get_ffmpeg_exe()
TMP = Path(r"C:\Users\tusha\AppData\Local\Temp\opencode\aegis_video")
ROOT = Path(r"C:\Users\tusha\OneDrive\Desktop\SIH")
OUT = ROOT / "aegisforecast_2min_team.mp4"

NAMES = ["TUSHAR", "SAHIL", "SHIVAM", "CHINMAY", "LAKSHYA GUPTA", "TUSHAR"]
AUD = [TMP/f"vo_team_00_tushar.mp3", TMP/f"vo_team_01_sahil.mp3",
       TMP/f"vo_team_02_shivam.mp3", TMP/f"vo_team_03_chinmay.mp3",
       TMP/f"vo_team_04_lakshya.mp3", TMP/f"vo_team_05_tushar_2.mp3"]

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
    if not m: return 15.0
    return int(m.group(1))*3600 + int(m.group(2))*60 + float(m.group(3))

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
    sp = TMP/f"slide_team_{i:02d}.png"
    base.save(sp)
    a = AUD[i]
    t = dur(a) + 1.2
    seg = TMP/f"segT_{i:02d}.mp4"
    subprocess.run([FF,"-y","-loop","1","-i",str(sp),"-i",str(a),
        "-c:v","libx264","-tune","stillimage","-c:a","aac",
        "-t",f"{t:.1f}","-pix_fmt","yuv420p","-shortest",str(seg)],
        check=True, capture_output=True)
    segs.append(seg)
    print(f"seg {i+1}/6 {NAMES[i]} audio {t-1.2:.1f}s ok")

lst = TMP/"listT.txt"
lst.write_text("\n".join(f"file '{s.as_posix()}'" for s in segs))
subprocess.run([FF,"-y","-f","concat","-safe","0","-i",str(lst),"-c","copy",str(OUT)], check=True)
print("WROTE", OUT, OUT.stat().st_size//1024, "KB")
r = subprocess.run([FF,"-i",str(OUT)], capture_output=True, text=True)
print([l.strip() for l in r.stderr.splitlines() if "Duration" in l][:2])
