"""Multi-voiceover: tushar, sahil, shivam, chinmay, lakshya, tushar_2. Tries edge-tts with retries, fallback to silence."""
import asyncio
from pathlib import Path
TMP = Path(r"C:\Users\tusha\AppData\Local\Temp\opencode\aegis_video")

SPEAKERS = [
    ("tushar",   "en-IN-PrabhatNeural",     'Cyberattacks detonate in seconds. Defenses react after the damage is done. What if you could forecast an attack twenty minutes before it happens? Meet AegisForecast.'),
    ("sahil",    "en-US-GuyNeural",         "Today's security centers are reactive. They store gigabytes of packet captures, drown in false positives, and detect intrusions only after data is stolen. We needed a system that predicts, not just detects."),
    ("shivam",   "en-US-DavisNeural",       "AegisForecast folds live traffic into in-memory five second flow statistics. No pcap is ever written. A per-host Bi-LSTM with attention, challenged by a Transformer, watches forty eight windows and predicts attack probability, MITRE stage, and minutes to detonation."),
    ("chinmay",  "en-US-TonyNeural",        "On the live dashboard you see lateral movement across five hosts. WEB spikes to point nine nine eight risk while benign hosts stay at point zero one three. Every alert is explained with SHAP in six milliseconds, correlated into campaigns, and auto-contained by SOAR."),
    ("lakshya",  "en-US-ChristopherNeural", "And it is proven, not claimed. Transformer A U C zero point nine eight five. One hundred percent coverage with twenty minute median lead time. Validated zero shot on real C I C I D S 2017 captures. Even stealth slow scans are caught."),
    ("tushar_2", "en-IN-PrabhatNeural",     "AegisForecast. Forecast. Explain. Contain. Thank you."),
]

async def gen_one(i, name, voice, text):
    import edge_tts
    out = TMP / f"vo_team_{i:02d}_{name}.mp3"
    for attempt in range(4):
        try:
            c = edge_tts.Communicate(text, voice=voice, rate="-5%")
            await c.save(str(out))
            print(f"ok {i} {name} {voice} try{attempt+1}")
            return out
        except Exception as e:
            print(f"retry {i} {name} try{attempt+1}: {e}")
            await asyncio.sleep(3)
    print(f"FAILED {i} {name}")
    return None

async def main():
    for i, (name, voice, text) in enumerate(SPEAKERS):
        await gen_one(i, name, voice, text)

import asyncio as _a
_a.run(main())
