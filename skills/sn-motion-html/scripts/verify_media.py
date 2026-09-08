#!/usr/bin/env python3
"""Validate normalized dive and connector files declared by a project manifest."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_root", type=Path)
    parser.add_argument("--allow-missing", action="store_true")
    args = parser.parse_args()

    if shutil.which("ffprobe") is None:
        raise SystemExit("ffprobe is required")
    root = args.project_root.expanduser().resolve()
    manifest = json.loads((root / "prompts" / "video-manifest.json").read_text(encoding="utf-8"))
    records = [*manifest.get("dives", []), *manifest.get("connectors", [])]
    paths = [root / record["output"] for record in records]
    missing = [path for path in paths if not path.exists()]
    if missing:
        print("Missing media:")
        for path in missing:
            print(f"- {path.relative_to(root)}")
        return 0 if args.allow_missing else 2

    width = int(manifest.get("target_width", 1280))
    height = int(manifest.get("target_height", 720))
    fps = int(manifest.get("fps", 24))
    duration_target = float(manifest.get("duration", 4))
    failures = []
    for path in paths:
        command = [
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=codec_name,width,height,r_frame_rate,nb_frames:format=duration",
            "-of", "json", str(path),
        ]
        data = json.loads(subprocess.check_output(command, text=True))
        stream = data["streams"][0]
        duration = float(data["format"]["duration"])
        okay = (
            stream["codec_name"] == "h264"
            and stream["width"] == width
            and stream["height"] == height
            and stream["r_frame_rate"] == f"{fps}/1"
            and abs(duration - duration_target) < 0.05
        )
        print(f"{'OK' if okay else 'FAIL'} {path.relative_to(root)} {stream['width']}x{stream['height']} {duration:.3f}s")
        if not okay:
            failures.append(path)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
