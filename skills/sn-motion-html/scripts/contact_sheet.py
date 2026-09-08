#!/usr/bin/env python3
"""Create a labeled midpoint contact sheet for every declared video clip."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import shutil
import subprocess
from PIL import Image, ImageDraw


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_root", type=Path)
    parser.add_argument("--columns", type=int, default=4)
    parser.add_argument("--cell-width", type=int, default=384)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if shutil.which("ffmpeg") is None:
        raise SystemExit("ffmpeg is required")

    root = args.project_root.expanduser().resolve()
    manifest = json.loads((root / "prompts" / "video-manifest.json").read_text(encoding="utf-8"))
    records = [("dive", item) for item in manifest.get("dives", [])]
    records += [("connector", item) for item in manifest.get("connectors", [])]
    missing = [root / item["output"] for _, item in records if not (root / item["output"]).exists()]
    if missing:
        raise SystemExit("Missing media: " + ", ".join(str(path.relative_to(root)) for path in missing))

    frame_dir = root / "tmp" / "contact-sheet"
    frame_dir.mkdir(parents=True, exist_ok=True)
    duration = float(manifest.get("duration", 4))
    frames: list[tuple[str, Path]] = []
    for index, (kind, item) in enumerate(records):
        frame = frame_dir / f"{index:03d}-{kind}-{item['id']}.jpg"
        subprocess.run([
            "ffmpeg", "-v", "error", "-y", "-ss", str(duration / 2),
            "-i", str(root / item["output"]), "-frames:v", "1", str(frame),
        ], check=True)
        frames.append((f"{kind}: {item['id']}", frame))

    columns = max(1, args.columns)
    rows = math.ceil(len(frames) / columns)
    cell_width = args.cell_width
    cell_height = round(cell_width * 9 / 16)
    label_height = 30
    sheet = Image.new("RGB", (columns * cell_width, rows * (cell_height + label_height)), "#f2ebdd")
    draw = ImageDraw.Draw(sheet)
    for index, (label, frame) in enumerate(frames):
        with Image.open(frame) as image:
            image = image.convert("RGB").resize((cell_width, cell_height), Image.Resampling.LANCZOS)
        x = (index % columns) * cell_width
        y = (index // columns) * (cell_height + label_height)
        sheet.paste(image, (x, y))
        draw.text((x + 8, y + cell_height + 7), label, fill="#25231f")

    output = (args.output or (root / "tmp" / "contact-sheet.png")).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
