"""Scan a deck_dir for creative-mode artifact presence; emit a skip/full/render_only
manifest that the main agent can consume in one shot."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def scan(deck: Path) -> dict:
    tp_path = deck / "task_pack.json"
    if not tp_path.exists():
        return {"error": f"task_pack.json missing in {deck}"}
    tp = json.loads(tp_path.read_text())
    page_count = int(tp["params"]["page_count"])

    style = (deck / "style_spec.md").exists()
    outline = (deck / "outline.json").exists()

    pages = []
    for i in range(1, page_count + 1):
        prompt = (deck / "pages" / f"page_{i:03d}.prompt.txt").exists()
        png = (deck / "pages" / f"page_{i:03d}.png").exists()
        if png:
            action = "skip"
        elif prompt:
            action = "render_only"
        else:
            action = "full"
        pages.append({"page_no": i, "prompt_done": prompt, "png_done": png, "action": action})

    deck_id = tp.get("deck_id") or deck.name
    pptx_done = (deck / f"{deck_id}.pptx").exists()

    return {"style_spec_done": style, "outline_done": outline,
            "pptx_done": pptx_done, "pages": pages}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--deck-dir", type=Path, required=True)
    args = p.parse_args(argv)
    json.dump(scan(args.deck_dir.expanduser().resolve()), sys.stdout, ensure_ascii=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
