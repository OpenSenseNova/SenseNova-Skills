"""Scan a standard-mode deck_dir and emit a JSON manifest that tells the main
agent where to resume: per-deck artifact flags + per-page action + top-level
next_action.
"""
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
    deck_id = tp["deck_id"]

    style = (deck / "style_spec.json").exists()
    outline = (deck / "outline.json").exists()
    asset_plan = (deck / "asset_plan.json").exists()
    deck_review = (deck / "review.md").exists()
    pptx = (deck / f"{deck_id}.pptx").exists()

    pages = []
    for i in range(1, page_count + 1):
        html = (deck / "pages" / f"page_{i:03d}.html").exists()
        review = (deck / "pages" / f"page_{i:03d}.review.md").exists()
        if html and review:
            action = "skip"
        elif html and not review:
            action = "review_only"
        else:
            action = "full"
        pages.append(
            {"page_no": i, "html_done": html, "review_done": review, "action": action}
        )

    # Deck-level next_action
    if all(p["action"] == "skip" for p in pages) and asset_plan and outline and style:
        if deck_review and pptx:
            next_action = "finished"
        elif deck_review and not pptx:
            next_action = "export_pptx"
        else:
            next_action = "aggregate_review"
    elif style and outline and asset_plan:
        next_action = "per_page"
    elif style and outline:
        next_action = "asset_plan"
    elif style:
        next_action = "outline"
    else:
        next_action = "style"

    return {
        "style_spec_done": style,
        "outline_done": outline,
        "asset_plan_done": asset_plan,
        "review_md_done": deck_review,
        "pptx_done": pptx,
        "pages": pages,
        "next_action": next_action,
    }


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--deck-dir", type=Path, required=True)
    args = p.parse_args(argv)
    json.dump(scan(args.deck_dir.expanduser().resolve()), sys.stdout, ensure_ascii=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
