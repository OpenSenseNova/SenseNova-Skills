"""Compare intended event times with sound onsets in the final file.

usage: python3 sync_check.py FILE EVENTS.json [--fps 30] [--window 0.15] [--thr 0.7]
EVENTS.json: [{"t": 1.20, "name": "triangle1.land"}, ...]  (or {"events": [...]});
events with "silent": true are skipped.
Prints, per event, the nearest clear onset within the window and its offset in ms; exits 1 if more than 10% are off by > 1 frame.
"""
import json, subprocess, sys
import numpy as np

args = sys.argv[1:]
if len(args) < 2: sys.exit(__doc__)
f, ev_path = args[0], args[1]
fps = float(args[args.index("--fps") + 1]) if "--fps" in args else 30.0
win = float(args[args.index("--window") + 1]) if "--window" in args else 0.15
thr = float(args[args.index("--thr") + 1]) if "--thr" in args else 0.7   # lower it for very quiet effects
SR = 48000

raw = subprocess.run(["ffmpeg", "-v", "error", "-i", f, "-vn", "-ac", "1", "-ar", str(SR), "-f", "s16le", "-"], capture_output=True).stdout
x = np.frombuffer(raw, "<i2").astype(float) / 32768
if not len(x): sys.exit("no audio decoded")

# spectral-flux onset strength, 5 ms hop; frame i is centred on sample i*hop
hop, n = 240, 1024
frames = np.lib.stride_tricks.sliding_window_view(np.pad(x, (n // 2, n)), n)[::hop] * np.hanning(n)
mag = np.abs(np.fft.rfft(frames, axis=1))
flux = np.concatenate([[0], np.maximum(np.diff(np.log1p(100 * mag), axis=0), 0).sum(1)])
rms = np.log(np.sqrt((frames ** 2).mean(1)) + 1e-5)                 # energy rise catches low thuds
rise = np.concatenate([[0], np.maximum(np.diff(rms), 0)])
p99 = lambda v: np.percentile(v, 99) + 1e-9
flux = np.maximum(flux / p99(flux), rise / p99(rise))                 # combined onset strength, ~1 = a strong onset
times = np.arange(len(flux)) * hop / SR

events = json.load(open(ev_path))
events = events.get("events", events) if isinstance(events, dict) else events
frame = 1 / fps; rows = []; bad = 0
for e in events:
    if e.get("silent"): continue
    t = float(e["t"])
    w = (times >= t - win) & (times <= t + win)
    if not w.any():
        rows.append((e.get("name", ""), t, None, None)); bad += 1; continue
    idx = np.flatnonzero(w)
    peaks = [i for i in idx if 0 < i < len(flux) - 1 and flux[i] >= flux[i - 1] and flux[i] >= flux[i + 1]
             and flux[i] >= thr]                                     # clear local onsets only
    if not peaks:
        rows.append((e.get("name", ""), t, None, None)); bad += 1; continue
    i = min(peaks, key=lambda k: abs(times[k] - t))                  # nearest clear onset
    o = times[i]; d = (o - t) * 1000
    rows.append((e.get("name", ""), t, o, d)); bad += abs(d) > frame * 1000 + 5
print(f"{'event':28s} {'t':>8s} {'onset':>8s} {'offset ms':>10s}")
for name, t, o, d in rows:
    print(f"{name[:28]:28s} {t:8.3f} {'-' if o is None else f'{o:8.3f}':>8s} {'MISSING' if d is None else f'{d:+10.0f}':>10s}")
n_ev = max(len(rows), 1)
print(f"{len(rows) - bad}/{len(rows)} within ±1 frame ({frame * 1000:.0f} ms)")
sys.exit(1 if bad > 0.1 * n_ev else 0)
