#!/bin/sh
# Loudness, true peak, clipping, silences and length of the audio in a video (or WAV).
# usage: sh audio_check.sh FILE [TARGET_LUFS=-14]
F=$1; TGT=${2:--14}
[ -f "$F" ] || { echo "usage: audio_check.sh FILE [TARGET_LUFS]"; exit 1; }
python3 - "$F" "$TGT" <<'EOF'
import json, re, subprocess, sys
f, tgt = sys.argv[1], float(sys.argv[2])
p = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", f], capture_output=True, text=True).stdout)
aus = [s for s in p["streams"] if s["codec_type"] == "audio"]
vs = [s for s in p["streams"] if s["codec_type"] == "video"]
if not aus:
    print("FAIL no audio stream"); sys.exit(1)
a = aus[0]; fails = []
adur = float(a.get("duration") or p["format"]["duration"])
print(f"audio   {a['codec_name']} {a.get('sample_rate')} Hz, {a.get('channels')} ch, {adur:.3f} s")
if vs:
    vdur = float(vs[0].get("duration") or p["format"]["duration"])
    if abs(vdur - adur) > 0.1: fails.append(f"audio {adur:.2f} s vs video {vdur:.2f} s")
log = subprocess.run(["ffmpeg", "-v", "info", "-i", f, "-vn", "-af", "ebur128=peak=true,astats=metadata=0,silencedetect=n=-50dB:d=1.0", "-f", "null", "-"],
                     capture_output=True, text=True).stderr
I = re.findall(r"I:\s+(-?[\d.]+) LUFS", log); TP = re.findall(r"Peak:\s+(-?[\d.inf]+) dBFS", log)
clip = re.findall(r"Number of clipped samples: (\d+)", log) or re.findall(r"Peak count: (\d+)", log)
lufs = float(I[-1]) if I else None; tp = float(TP[-1]) if TP and TP[-1] not in ("-inf", "inf") else None
print(f"loudness {lufs} LUFS (target {tgt}), true peak {tp} dBTP")
if lufs is None or abs(lufs - tgt) > 2: fails.append(f"integrated loudness {lufs} not within ±2 of {tgt}")
if tp is not None and tp > -0.5: fails.append(f"true peak {tp} dBTP above -0.5")
for st, en in zip(re.findall(r"silence_start: ([\d.]+)", log), re.findall(r"silence_end: ([\d.]+)", log) + [str(adur)]):
    print(f"warn    silence {float(st):.2f}-{float(en):.2f} s  -- fine only if deliberate")
for x in fails: print("FAIL   ", x)
print("OK" if not fails else f"{len(fails)} failure(s)")
sys.exit(1 if fails else 0)
EOF
