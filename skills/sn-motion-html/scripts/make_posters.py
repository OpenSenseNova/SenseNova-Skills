#!/usr/bin/env python3
"""Convert scene PNG masters to compact WebP posters."""

from __future__ import annotations

import argparse
from pathlib import Path
from PIL import Image


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_root", type=Path)
    parser.add_argument("--quality", type=int, default=84)
    parser.add_argument("--max-width", type=int, default=1800)
    args = parser.parse_args()

    root = args.project_root.expanduser().resolve()
    scenes = root / "assets" / "images" / "scenes"
    inputs = sorted(scenes.glob("*.png"))
    if not inputs:
        raise SystemExit(f"No PNG scene masters found in {scenes}")

    for source in inputs:
        target = source.with_suffix(".webp")
        with Image.open(source) as image:
            image = image.convert("RGB")
            if image.width > args.max_width:
                height = round(image.height * args.max_width / image.width)
                image = image.resize((args.max_width, height), Image.Resampling.LANCZOS)
            image.save(target, "WEBP", quality=args.quality, method=6)
        print(f"saved {target.relative_to(root)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
