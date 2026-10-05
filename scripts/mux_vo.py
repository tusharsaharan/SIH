from pathlib import Path
import subprocess, re
import imageio_ffmpeg
FF = imageio_ffmpeg.get_ffmpeg_exe()
TMP = Path(r"C:\Users\tusha\AppData\Local\Temp\opencode\aegis_video")
ROOT = Path(r"C:\Users\tusha\OneDrive\Desktop\SIH")
OUT = ROOT / "aegisforecast_2min_voiced.mp4"

def dur(p):
    r = subprocess.run([FF, "-i", str(p)], capture_output=True, text=True)
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", r.stderr)
    if not m: return 20.0
    return int(m.group(1))*3600 + int(m.group(2))*60 + float(m.group(3))

segs = []
for i in range(6):
    slide = TMP / f"slide_{i:02d}.png"
    wav = TMP / f"vo_offline_{i}.wav"
    seg = TMP / f"segA_{i:02d}.mp4"
    d = dur(wav) + 1.2
    print(i, "audio", round(d-1.2,1), "s")
    cmd = [FF, "-y", "-loop", "1", "-i", str(slide), "-i", str(wav),
           "-c:v", "libx264", "-tune", "stillimage", "-c:a", "aac",
           "-t", f"{d:.1f}", "-pix_fmt", "yuv420p", "-shortest", str(seg)]
    subprocess.run(cmd, check=True, capture_output=True)
    segs.append(seg)

lst = TMP / "lista.txt"
lst.write_text("\n".join(f"file '{s.as_posix()}'" for s in segs))
subprocess.run([FF, "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(OUT)], check=True)
print("WROTE", OUT, OUT.stat().st_size//1024, "KB")
r = subprocess.run([FF, "-i", str(OUT)], capture_output=True, text=True)
print([l.strip() for l in r.stderr.splitlines() if "Duration" in l or "Stream" in l][:4])
