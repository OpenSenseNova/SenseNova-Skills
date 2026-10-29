"""Narration with edge-tts: one clip per line, measured speech extent, word timings, cached.

usage: python3 tts.py LINES.json OUT_DIR [--only id1,id2]

LINES.json:
{
  "voice": "en-US-AndrewNeural",          # default voice (e.g. zh-CN-XiaoxiaoNeural for Mandarin)
  "rate": "-6%",                           # default speaking rate
  "lines": [
    {"id": "l01", "say": "Half the Moon is always lit.", "show": "Half the Moon is always lit."},
    {"id": "l02", "say": "Fifteen percent off.", "show": "15% off", "rate": "-12%"}
  ]
}
"say" is what the voice speaks (numbers spelled out), "show" is the subtitle text (defaults to "say").

Writes OUT_DIR/<id>.wav (48 kHz mono) and OUT_DIR/timing.json with, per line: duration, speech onset/offset
inside the clip (measured from energy), and word boundaries shifted onto the measured onset.
Place each line at a film time `at`; speech then starts at at + onset.
"""
import asyncio, json, subprocess, sys, wave
from pathlib import Path
import numpy as np

SR = 48000

async def synth(text, voice, rate, mp3):
    import edge_tts
    com = edge_tts.Communicate(text, voice, rate=rate, boundary="WordBoundary")
    words = []
    with open(mp3, "wb") as f:
        async for ch in com.stream():
            if ch["type"] == "audio":
                f.write(ch["data"])
            elif ch["type"] in ("WordBoundary", "SentenceBoundary"):
                words.append({"w": ch["text"], "t0": ch["offset"] / 1e7, "t1": (ch["offset"] + ch["duration"]) / 1e7})
    return words

def load(p):
    with wave.open(str(p)) as w:
        return np.frombuffer(w.readframes(w.getnframes()), "<i2").astype(np.float32) / 32768

def main():
    if len(sys.argv) < 3: sys.exit(__doc__)
    cfg = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    out = Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
    only = set(sys.argv[sys.argv.index("--only") + 1].split(",")) if "--only" in sys.argv else set()
    res = {"voice": cfg.get("voice"), "rate": cfg.get("rate"), "lines": []}
    for ln in cfg["lines"]:
        say = ln["say"]; voice = ln.get("voice", cfg.get("voice", "en-US-AndrewNeural")); rate = ln.get("rate", cfg.get("rate", "+0%"))
        mp3, wav, meta = out / f"{ln['id']}.mp3", out / f"{ln['id']}.wav", out / f"{ln['id']}.json"
        key = {"say": say, "voice": voice, "rate": rate}
        cached = meta.exists() and wav.exists() and json.loads(meta.read_text()).get("key") == key
        if not cached or ln["id"] in only:
            for attempt in range(3):                       # the service occasionally drops a request
                try:
                    words = asyncio.run(synth(say, voice, rate, mp3)); break
                except Exception as e:
                    if attempt == 2: raise
                    print("retry", ln["id"], e)
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(mp3), "-ac", "1", "-ar", str(SR), str(wav)], check=True)
            meta.write_text(json.dumps({"key": key, "words": words}, ensure_ascii=False))
        words = json.loads(meta.read_text())["words"]
        a = load(wav)
        # speech extent: 10 ms RMS frames above (peak frame - 38 dB)
        fr = a[: len(a) // 480 * 480].reshape(-1, 480); db = 20 * np.log10(np.sqrt((fr ** 2).mean(1)) + 1e-9)
        on = np.flatnonzero(db > db.max() - 38)
        onset, offset = (on[0] * 0.01, (on[-1] + 1) * 0.01) if len(on) else (0.0, len(a) / SR)
        # edge-tts word offsets run ~40-55 ms early: shift them so the first word starts at the measured onset
        if words:
            d = onset - words[0]["t0"]
            words = [{**w, "t0": round(w["t0"] + d, 3), "t1": round(w["t1"] + d, 3)} for w in words]
        res["lines"].append({"id": ln["id"], "say": say, "show": ln.get("show", say), "voice": voice, "rate": rate,
                             "wav": str(wav), "duration": round(len(a) / SR, 3), "onset": round(onset, 3),
                             "offset": round(offset, 3), "words": words})
        print(f"{ln['id']:6s} {len(a) / SR:6.2f} s  speech {onset:5.2f}-{offset:5.2f}  {(str(len(say.split())) + ' words') if voice[:2] != 'zh' else (str(len(say)) + ' chars')}  {voice} {rate}")
    (out / "timing.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")

if __name__ == "__main__":
    main()
