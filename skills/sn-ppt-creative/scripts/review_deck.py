#!/usr/bin/env python3
"""Write review.md and review.json for creative-mode PNG decks.

Creative mode produces one full-slide PNG per page. The review step is
deterministic: it verifies expected PNG presence, records basic dimensions when
Pillow is available, and flags missing/empty/non-16:9 pages before PPTX
packaging. It does not call a model and does not block packaging by default.
"""
from __future__ import annotations

import argparse
import json
import struct
import sys
from pathlib import Path


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _image_size(path: Path) -> tuple[int | None, int | None, str | None]:
    try:
        with path.open("rb") as handle:
            header = handle.read(24)
        if header[:8] == b"\x89PNG\r\n\x1a\n" and header[12:16] == b"IHDR":
            width, height = struct.unpack(">II", header[16:24])
            if width > 0 and height > 0:
                return int(width), int(height), None
            return None, None, "PNG has invalid zero width or height."
        if path.suffix.lower() == ".png":
            return None, None, "File has .png extension but no valid PNG header."
    except Exception as exc:
        return None, None, f"PNG header could not be read: {exc}"

    try:
        from PIL import Image  # noqa: WPS433 - optional dependency

        with Image.open(path) as im:
            im.verify()
            return int(im.size[0]), int(im.size[1]), None
    except ImportError:
        return None, None, "Image dimensions could not be verified without Pillow."
    except Exception as exc:
        return None, None, f"PNG could not be opened for dimension verification: {exc}"


def review(deck: Path) -> dict:
    tp = _load_json(deck / "task_pack.json")
    page_count = int(tp.get("params", {}).get("page_count") or 0)
    if page_count <= 0:
        outline_path = deck / "outline.json"
        if outline_path.exists():
            outline = _load_json(outline_path)
            page_count = len(outline.get("pages") or [])

    pages: list[dict] = []
    for page_no in range(1, page_count + 1):
        rel = Path("pages") / f"page_{page_no:03d}.png"
        path = deck / rel
        exists = path.exists()
        size_bytes = path.stat().st_size if exists else 0
        item = {
            "page_no": page_no,
            "path": str(rel),
            "present": exists and size_bytes > 0,
            "size_bytes": size_bytes,
            "width": None,
            "height": None,
            "aspect": None,
            "issues": [],
        }
        if not exists:
            item["issues"].append("PNG page is missing; build_pptx will insert a blank slide.")
        elif size_bytes <= 0:
            item["issues"].append("PNG page is empty; build_pptx will insert a blank slide.")
        else:
            w, h, image_error = _image_size(path)
            item["width"] = w
            item["height"] = h
            if image_error:
                item["issues"].append(image_error)
            if w and h:
                aspect = round(w / h, 3)
                item["aspect"] = aspect
                if abs(aspect - (16 / 9)) > 0.03:
                    item["issues"].append(f"PNG aspect ratio is {aspect}, expected approximately 1.778.")
        pages.append(item)

    needs = [p for p in pages if p["issues"]]
    return {
        "status": "needs_attention" if needs else "clean",
        "mode": "creative",
        "total_pages": page_count,
        "present_pages": sum(1 for p in pages if p["present"]),
        "needs_attention_pages": len(needs),
        "pages": pages,
    }


def write_review(deck: Path, data: dict) -> None:
    (deck / "review.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    lines = [
        "# Review",
        "",
        "## Summary",
        "",
        f"- Mode: creative",
        f"- Total pages expected: {data['total_pages']}",
        f"- PNG pages present: {data['present_pages']}",
        f"- Pages needing attention: {data['needs_attention_pages']}",
        "",
        "## Pages",
        "",
    ]
    for page in data["pages"]:
        status = "needs_attention" if page["issues"] else "clean"
        suffix = ""
        if page.get("width") and page.get("height"):
            suffix = f" ({page['width']}x{page['height']})"
        lines.append(f"- page_{int(page['page_no']):03d}: {status}{suffix}")
        for issue in page["issues"]:
            lines.append(f"  - {issue}")
    (deck / "review.md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--deck-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    deck = args.deck_dir.expanduser().resolve()
    data = review(deck)
    write_review(deck, data)
    print(json.dumps({
        "status": "ok",
        "review_status": data["status"],
        "total_pages": data["total_pages"],
        "needs_attention_pages": data["needs_attention_pages"],
        "review_md": "review.md",
        "review_json": "review.json",
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
