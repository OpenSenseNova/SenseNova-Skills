#!/bin/sh
# Check a rendered video against the spec and look for black or frozen stretches.
# usage: sh check_video.sh VIDEO WIDTH HEIGHT FPS MIN_DUR MAX_DUR [audio=any|0|1]
#   audio: any = report only (default), 0 = must have no audio stream, 1 = must have one
V=$1; W=$2; H=$3; FPS=$4; DMIN=$5; DMAX=$6; AUD=${7:-any}
[ -f "$V" ] || { echo "usage: check_video.sh VIDEO W H FPS MIN_DUR MAX_DUR [audio any|0|1]"; exit 1; }
python3 - "$V" "$W" "$H" "$FPS" "$DMIN" "$DMAX" "$AUD" <<'EOF'
import json, re, subprocess, sys
v, W, H, FPS, DMIN, DMAX, AUD = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), float(sys.argv[4]), float(sys.argv[5]), float(sys.argv[6]), sys.argv[7]
p = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-count_frames", "-of", "json", v],
                              capture_output=True, text=True).stdout)
vs = [s for s in p["streams"] if s["codec_type"] == "video"]
aus = [s for s in p["streams"] if s["codec_type"] == "audio"]
fails = []
if not vs:
    print("FAIL no video stream"); sys.exit(1)
s = vs[0]
num, den = map(int, s["avg_frame_rate"].split("/"))
fps = num / den if den else 0
dur = float(p["format"]["duration"])
frames = int(s.get("nb_read_frames") or 0)
print(f"video   {s['codec_name']} {s['width']}x{s['height']} {s.get('pix_fmt')} {fps:.3f} fps, {frames} frames, {dur:.3f} s")
print(f"audio   {len(aus)} stream(s)" + (f", {aus[0]['codec_name']}, {float(aus[0].get('duration', 0)):.3f} s" if aus else ""))
if aus and abs(float(aus[0].get('duration', dur)) - dur) > 0.1:
    print(f"warn    audio length differs from video length by {abs(float(aus[0]['duration']) - dur):.2f} s")
if (s["width"], s["height"]) != (W, H): fails.append(f"resolution {s['width']}x{s['height']} != {W}x{H}")
if abs(fps - FPS) > 0.01: fails.append(f"fps {fps:.3f} != {FPS}")
if not (DMIN - 0.05 <= dur <= DMAX + 0.05): fails.append(f"duration {dur:.2f} outside {DMIN}-{DMAX}")
if s["codec_name"] != "h264": fails.append(f"codec {s['codec_name']} != h264")
if s.get("pix_fmt") != "yuv420p": fails.append(f"pix_fmt {s.get('pix_fmt')} != yuv420p")
if AUD == "1" and not aus: fails.append("expected an audio stream")
if AUD == "0" and aus: fails.append("unexpected audio stream")
log = subprocess.run(["ffmpeg", "-v", "info", "-i", v, "-vf", "blackdetect=d=0.3:pix_th=0.06,freezedetect=n=0.002:d=1.5", "-an", "-f", "null", "-"],
                     capture_output=True, text=True).stderr
for m in re.finditer(r"black_start:([\d.]+) black_end:([\d.]+)", log):
    print(f"warn    black {m.group(1)}-{m.group(2)} s");
fr = re.findall(r"freeze_start: ([\d.]+)|freeze_end: ([\d.]+)", log)
starts = [float(a) for a, b in fr if a]; ends = [float(b) for a, b in fr if b]
for i, st in enumerate(starts):
    en = ends[i] if i < len(ends) else dur
    print(f"warn    frozen {st:.2f}-{en:.2f} s ({en - st:.2f} s)  -- fine only if it is a deliberate hold")
for f in fails: print("FAIL   ", f)
print("OK" if not fails else f"{len(fails)} failure(s)")
sys.exit(1 if fails else 0)
EOF
