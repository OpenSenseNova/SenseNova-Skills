#!/usr/bin/env python3
"""Generate VLM-derived captions for every image referenced by a deck.

Two image pools are processed:
  - Pool A: documents[*].inherited_images[*]  — embedded in user docs
            (read from <deck_dir>/raw_documents.json; caption written back
             into the same JSON, into a `vlm_caption` field per image).
  - Pool B: info_pack.user_assets.reference_images — standalone uploads
            (caption written into a sister field
             info_pack.user_assets.reference_image_captions: {abs_path: caption}).

**Idempotent**: an image that already carries a non-empty caption is skipped
on subsequent runs, so this can be invoked multiple times safely.

Single source of truth: this script is the ONLY place that calls VLM for
image content description. Downstream consumers (ppt-standard's page_html
stage) read the cached field and never re-caption.

Usage:
    python caption_images.py --deck-dir <deck>

Reads `$PPT_STANDARD_DIR/lib/model_client.py` for the `vlm()` helper. Set
`$PPT_STANDARD_DIR` if the layout differs from `<this-skill>/../ppt-standard`.
Prints one JSON status line; exit 0 even if some images fail (failures are
reported in the JSON).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ENTRY_SKILL_DIR = Path(__file__).resolve().parent.parent


def _resolve_model_client() -> tuple:
    """Locate ppt-standard/lib/model_client.py and import its vlm()."""
    candidates = []
    env_dir = os.environ.get("PPT_STANDARD_DIR", "").strip()
    if env_dir:
        candidates.append(Path(env_dir) / "lib")
    candidates.append(ENTRY_SKILL_DIR.parent / "ppt-standard" / "lib")
    for cand in candidates:
        if (cand / "model_client.py").exists():
            sys.path.insert(0, str(cand))
            from model_client import vlm, ModelClientError  # noqa: E402
            return vlm, ModelClientError
    raise FileNotFoundError(
        f"ppt-standard/lib/model_client.py not found; "
        f"checked {[str(c) for c in candidates]}. Set $PPT_STANDARD_DIR."
    )


CAPTION_SYSTEM = (
    "你是图像内容描述助手。请用一句简洁的中文描述这张图片画的是什么内容、"
    "关键视觉元素和数据要点（数字 / 类别 / 趋势）。直接输出描述，"
    "不要前后缀、不要 JSON、不要列表、不要 markdown 标记。控制在 30-80 字。"
)
CAPTION_USER = "<image>\n请描述这张图片。"


def _caption_one(vlm, image_path: Path) -> tuple[str | None, str | None]:
    """Return (caption, error). caption is non-empty on success."""
    try:
        out = vlm(CAPTION_SYSTEM, CAPTION_USER, images=[image_path])
    except Exception as e:  # noqa: BLE001
        return None, f"{type(e).__name__}: {e}"
    out = (out or "").strip()
    if not out:
        return None, "empty caption"
    # Strip accidental markdown / fence wrappers
    if out.startswith("```"):
        nl = out.find("\n")
        if nl != -1:
            out = out[nl + 1:]
        if out.endswith("```"):
            out = out[:-3]
    return out.strip(), None


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--deck-dir", type=Path, required=True)
    p.add_argument("--concurrency", type=int, default=4,
                   help="max parallel VLM workers (default 4, clamped to 1-16)")
    args = p.parse_args(argv)
    deck = args.deck_dir.expanduser().resolve()
    concurrency = max(1, min(int(args.concurrency), 16))

    raw_path = deck / "raw_documents.json"
    info_path = deck / "info_pack.json"

    raw = json.loads(raw_path.read_text(encoding="utf-8")) if raw_path.exists() else None
    info = json.loads(info_path.read_text(encoding="utf-8")) if info_path.exists() else None

    if raw is None and info is None:
        print(json.dumps({"status": "failed", "error": "neither raw_documents.json nor info_pack.json found"},
                         ensure_ascii=False))
        return 1

    vlm, _err_cls = _resolve_model_client()

    # ----- Phase 1: scan in main thread, build the "needs work" task list -----
    # Sequential planning is cheap and lets us count totals + skip cached
    # entries without locking. Pool A side promotes str-shape entries to dict
    # in-place so the worker can attach `vlm_caption` to a stable target.
    pool_a_total = pool_a_done = pool_a_failed = 0
    pool_b_total = pool_b_done = pool_b_failed = 0
    failures: list[dict] = []

    # Each task carries enough context for the result aggregator to know
    # where to write the caption back. We never mutate shared state from
    # workers — all writes happen in the main thread after join.
    tasks: list[dict] = []

    if raw is not None:
        for di, doc in enumerate(raw.get("documents") or []):
            inh_list = doc.get("inherited_images") or []
            for ii, img in enumerate(inh_list):
                pool_a_total += 1
                if isinstance(img, str):
                    img = {"path": img}
                    inh_list[ii] = img  # promote in place (main thread, safe)
                if not isinstance(img, dict):
                    pool_a_failed += 1
                    failures.append({"pool": "A", "doc": di, "i": ii, "error": "unrecognized shape"})
                    continue
                if (img.get("vlm_caption") or "").strip():
                    pool_a_done += 1
                    continue
                src = img.get("path") or ""
                src_p = Path(src)
                if not src or not src_p.exists() or not src_p.is_file():
                    pool_a_failed += 1
                    failures.append({"pool": "A", "doc": di, "i": ii,
                                     "path": src, "error": "image file not found"})
                    continue
                tasks.append({"pool": "A", "doc": di, "i": ii, "path": str(src_p),
                              "label": f"A/d{di}/i{ii}/{src_p.name}"})

    if info is not None:
        ua = info.setdefault("user_assets", {})
        ref_imgs = ua.get("reference_images") or []
        captions: dict = ua.setdefault("reference_image_captions", {})
        for src in ref_imgs:
            if not src:
                continue
            pool_b_total += 1
            if (captions.get(src) or "").strip():
                pool_b_done += 1
                continue
            src_p = Path(src)
            if not src_p.exists() or not src_p.is_file():
                pool_b_failed += 1
                failures.append({"pool": "B", "path": src, "error": "image file not found"})
                continue
            tasks.append({"pool": "B", "path": str(src_p), "ref_path": src,
                          "label": f"B/{src_p.name}"})

    # ----- Phase 2: parallel VLM calls (only if there's any work to do) -----
    # Each worker is pure: read its image path, call vlm(), return text. No
    # shared mutable state. Idempotency was already enforced in Phase 1.
    if tasks:
        with ThreadPoolExecutor(max_workers=concurrency) as ex:
            future_to_task = {
                ex.submit(_caption_one, vlm, Path(t["path"])): t
                for t in tasks
            }
            for fut in as_completed(future_to_task):
                t = future_to_task[fut]
                try:
                    cap, err = fut.result()
                except Exception as e:  # noqa: BLE001
                    cap, err = None, f"{type(e).__name__}: {e}"
                if cap is None:
                    fail = {"pool": t["pool"], "path": t["path"], "error": err}
                    if t["pool"] == "A":
                        fail.update({"doc": t["doc"], "i": t["i"]})
                        pool_a_failed += 1
                    else:
                        pool_b_failed += 1
                    failures.append(fail)
                    continue
                # Write result back into the in-memory structures (main thread).
                if t["pool"] == "A":
                    raw["documents"][t["doc"]]["inherited_images"][t["i"]]["vlm_caption"] = cap
                    pool_a_done += 1
                else:
                    info["user_assets"]["reference_image_captions"][t["ref_path"]] = cap
                    pool_b_done += 1

    # ----- Phase 3: write back once -----
    if raw is not None:
        raw_path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    if info is not None:
        info_path.write_text(json.dumps(info, ensure_ascii=False), encoding="utf-8")

    payload = {
        "status": "ok",
        "deck": str(deck),
        "concurrency": concurrency,
        "submitted": len(tasks),
        "pool_a": {"total": pool_a_total, "captioned_or_cached": pool_a_done, "failed": pool_a_failed},
        "pool_b": {"total": pool_b_total, "captioned_or_cached": pool_b_done, "failed": pool_b_failed},
    }
    if failures:
        payload["failures"] = failures[:20]  # cap so stdout doesn't blow up
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
