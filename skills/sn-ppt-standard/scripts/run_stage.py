#!/usr/bin/env python3
"""Single entry point for every sn-ppt-standard stage.

Usage:
    python run_stage.py preflight       --deck-dir <deck>
    python run_stage.py style           --deck-dir <deck>
    python run_stage.py outline         --deck-dir <deck>
    python run_stage.py asset-plan      --deck-dir <deck>
    python run_stage.py gen-image       --deck-dir <deck> --page N --slot SLOT
    python run_stage.py page-html       --deck-dir <deck> --page N
    python run_stage.py batch-gen-image --deck-dir <deck> [--concurrency 4]
    python run_stage.py batch-page-html --deck-dir <deck> [--concurrency 4]
    python run_stage.py export          --deck-dir <deck>

The main agent (in OpenClaw) is expected to call this script **once per
stage**, with page/slot iteration driven by the agent's own loop of tool_calls.
The script itself never loops over pages or slots — that guarantees the main
agent stays in control of progress echo and error handling.

Each subcommand:
- reads the artifacts it needs from deck_dir
- builds the full LLM/VLM/T2I payload (including document_digest and
  raw_documents excerpts when appropriate)
- calls model_client and writes the output artifact
- prints a single-line JSON status to stdout (`{"status": "ok", ...}` or
  `{"status": "failed", "error": ...}`)
- returns exit code 0 on success, non-zero on failure
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import re
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
LIB_DIR = SKILL_DIR / "lib"
if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))

from model_client import ModelClientError, llm, vlm  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ok(**kw) -> int:
    print(json.dumps({"status": "ok", **kw}, ensure_ascii=False))
    return 0


def _fail(msg: str, **kw) -> int:
    print(json.dumps({"status": "failed", "error": msg, **kw}, ensure_ascii=False))
    return 1


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _load_prompt(name: str) -> str:
    """Load a prompt file and expand <<<INLINE: path>>> references."""
    p = SKILL_DIR / "prompts" / name
    raw = p.read_text(encoding="utf-8")

    def expand(m: re.Match) -> str:
        rel = m.group(1).strip()
        target = SKILL_DIR / rel
        if not target.exists():
            raise FileNotFoundError(f"INLINE target missing: {target}")
        return target.read_text(encoding="utf-8")

    return re.sub(r"<<<INLINE:\s*([^>]+)>>>", expand, raw)


def _strip_code_fences(s: str) -> str:
    """Remove leading/trailing ``` fences the model sometimes adds."""
    s = s.strip()
    if s.startswith("```"):
        first_nl = s.find("\n")
        if first_nl != -1:
            s = s[first_nl + 1:]
        if s.endswith("```"):
            s = s[:-3]
    return s.strip()


def _parse_json_loose(s: str) -> dict:
    """Best-effort JSON parse — strip fences and try to find an outer {...}."""
    s = _strip_code_fences(s)
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        # try to find the first {...} block
        start = s.find("{")
        end = s.rfind("}")
        if start != -1 and end > start:
            return json.loads(s[start:end + 1])
        raise


_STYLE_DIMENSIONS_PATH = SKILL_DIR.parent.parent / "reference" / "style_dimensions.json"


def _load_style_dimensions() -> dict | None:
    """Load the curated style catalog. Returns None if the file is missing
    (e.g. external distributions that ship only the pre-rendered catalog.md)."""
    if not _STYLE_DIMENSIONS_PATH.exists():
        return None
    try:
        return _load_json(_STYLE_DIMENSIONS_PATH)
    except Exception:
        return None


def _repair_style_triple(data: dict, dims: dict) -> tuple[dict, list[str]]:
    """Validate `data`'s (design_style, color_tone, primary_color) triple
    against the curated catalog and auto-repair incompatible picks.

    Returns the repaired data and a list of human-readable notes describing
    any fixes applied. The caller writes the notes into a `_repairs` field so
    the downstream stages (and humans debugging) can see what changed.
    """
    notes: list[str] = []
    ds_rows = {s["id"]: s for s in dims.get("design_styles", [])}
    ct_rows = {t["id"]: t for t in dims.get("color_tones", [])}
    pc_rows = {c["id"]: c for c in dims.get("primary_colors", [])}

    def _as_id(v) -> int | None:
        if isinstance(v, dict):
            v = v.get("id")
        try:
            return int(v) if v is not None else None
        except (TypeError, ValueError):
            return None

    ds_id = _as_id(data.get("design_style"))
    ct_id = _as_id(data.get("color_tone"))
    pc_id = _as_id(data.get("primary_color"))

    # design_style: must exist. If not, default to row 1 (科技感) as a last
    # resort — this should be rare; the prompt is explicit.
    if ds_id not in ds_rows:
        fallback_id = next(iter(ds_rows), 1)
        notes.append(f"design_style.id {ds_id!r} not in catalog; fell back to {fallback_id}")
        ds_id = fallback_id
    ds_row = ds_rows[ds_id]

    # color_tone: must be in design_style.compatible_tones.
    compat_tones = ds_row.get("compatible_tones") or []
    if ct_id not in compat_tones:
        fallback_id = compat_tones[0] if compat_tones else next(iter(ct_rows), 1)
        notes.append(
            f"color_tone.id {ct_id!r} not compatible with design_style {ds_id}; "
            f"fell back to {fallback_id}"
        )
        ct_id = fallback_id
    ct_row = ct_rows.get(ct_id, {})

    # primary_color: intersection of design_style.compatible_colors ∩ tone.compatible_colors
    ds_colors = set(ds_row.get("compatible_colors") or [])
    ct_colors = set(ct_row.get("compatible_colors") or [])
    intersection = [c for c in (ds_row.get("compatible_colors") or []) if c in ct_colors]
    allowed = intersection or list(ds_colors)
    if pc_id not in allowed:
        fallback_id = allowed[0] if allowed else next(iter(pc_rows), 1)
        notes.append(
            f"primary_color.id {pc_id!r} not in allowed set for (design={ds_id}, tone={ct_id}); "
            f"fell back to {fallback_id}"
        )
        pc_id = fallback_id
    pc_row = pc_rows.get(pc_id, {})

    # Overwrite the triple with canonical catalog values (ids, names, hex).
    data["design_style"] = {
        "id": ds_id,
        "name_zh": ds_row.get("name"),
        "name_en": ds_row.get("name_en"),
    }
    data["color_tone"] = {
        "id": ct_id,
        "name_zh": ct_row.get("name"),
        "name_en": ct_row.get("name_en"),
    }
    canonical_hex = (pc_row.get("hex") or "").upper()
    data["primary_color"] = {
        "id": pc_id,
        "name_zh": pc_row.get("name"),
        "name_en": pc_row.get("name_en"),
        "hex": canonical_hex,
    }

    # Force palette.primary to match the canonical hex literally.
    palette = data.get("palette")
    if not isinstance(palette, dict):
        palette = {}
        data["palette"] = palette
    if (palette.get("primary") or "").upper() != canonical_hex:
        if palette.get("primary"):
            notes.append(
                f"palette.primary {palette.get('primary')!r} overwritten to {canonical_hex}"
            )
        palette["primary"] = canonical_hex

    # Drop any stale legacy fields the LLM might still emit out of habit.
    for stale in ("css_variables", "base_styles", "mood_keywords", "layout_tendency"):
        if stale in data:
            data.pop(stale, None)
            notes.append(f"dropped legacy field {stale!r}")

    return data, notes


def _excerpt_raw_docs(info_pack: dict, max_chars: int = 4000) -> str:
    """Pull raw document text (if enabled) and clip to max_chars total."""
    rde = info_pack.get("raw_document_excerpts") or {}
    if not rde.get("enabled"):
        return ""
    path = Path(rde.get("path") or "")
    if not path.exists():
        return ""
    try:
        raw = _load_json(path)
    except Exception:
        return ""
    parts: list[str] = []
    remaining = max_chars
    for doc in raw.get("documents", []):
        chunk = doc.get("text") or ""
        if not chunk:
            continue
        clipped = chunk[:remaining]
        parts.append(f"## {doc.get('path', '?')}\n{clipped}")
        remaining -= len(clipped)
        if remaining <= 0:
            break
    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------


def cmd_preflight(deck: Path) -> int:
    tp_path = deck / "task_pack.json"
    ip_path = deck / "info_pack.json"
    if not tp_path.exists():
        return _fail("task_pack.json missing")
    if not ip_path.exists():
        return _fail("info_pack.json missing")
    tp = _load_json(tp_path)
    if tp.get("ppt_mode") != "standard":
        return _fail(f"ppt_mode is {tp.get('ppt_mode')!r}, expected 'standard'")
    (deck / "pages").mkdir(exist_ok=True)
    (deck / "images").mkdir(exist_ok=True)

    # Copy echarts.min.js into <deck_dir>/assets/echarts.min.js so pages can
    # reference it via `../assets/echarts.min.js` without a CDN.
    import shutil
    src = SKILL_DIR / "scripts" / "export_pptx" / "node_modules" / "echarts" / "dist" / "echarts.min.js"
    echarts_staged = False
    if src.exists():
        dst_dir = deck / "assets"
        dst_dir.mkdir(exist_ok=True)
        dst = dst_dir / "echarts.min.js"
        if not dst.exists() or dst.stat().st_size != src.stat().st_size:
            shutil.copyfile(src, dst)
        echarts_staged = True

    return _ok(
        deck_id=tp.get("deck_id"),
        page_count=tp.get("params", {}).get("page_count"),
        echarts_staged=echarts_staged,
    )


def cmd_style(deck: Path) -> int:
    tp = _load_json(deck / "task_pack.json")
    ip = _load_json(deck / "info_pack.json")
    system_prompt = _load_prompt("style_spec.md")
    user_prompt = json.dumps({
        "task_pack_params": tp.get("params", {}),
        "info_pack_query_normalized": ip.get("query_normalized"),
        "info_pack_user_query": ip.get("user_query"),
        "info_pack_document_digest": ip.get("document_digest"),
    }, ensure_ascii=False, indent=2)
    try:
        raw = llm(system_prompt, user_prompt)
        data = _parse_json_loose(raw)
    except (ModelClientError, json.JSONDecodeError) as e:
        return _fail(f"style: {e}")

    repair_notes: list[str] = []
    dims = _load_style_dimensions()
    if dims is not None:
        data, repair_notes = _repair_style_triple(data, dims)
    if repair_notes:
        data["_repairs"] = repair_notes

    _write_text(deck / "style_spec.json", json.dumps(data, ensure_ascii=False, indent=2))
    return _ok(
        path="style_spec.json",
        design_style=data.get("design_style"),
        color_tone=data.get("color_tone"),
        primary_color=data.get("primary_color"),
        palette=data.get("palette"),
        repairs=repair_notes or None,
    )


def cmd_outline(deck: Path) -> int:
    tp = _load_json(deck / "task_pack.json")
    ip = _load_json(deck / "info_pack.json")
    style = _load_json(deck / "style_spec.json")
    system_prompt = _load_prompt("outline.md")
    raw_docs = _excerpt_raw_docs(ip, max_chars=4000)

    # Surface standalone user-uploaded reference images as a Pool-B source for
    # `use_image`. These live in info_pack.user_assets.reference_images and
    # are otherwise ignored by the standard-mode pipeline; the outline LLM
    # uses the filename as a semantic hint to assign each to a topic page.
    ua = ip.get("user_assets") or {}
    ref_images_in = ua.get("reference_images") or []
    available_reference_images: list[dict] = []
    for i, p in enumerate(ref_images_in):
        if not p:
            continue
        if not Path(p).exists():
            continue
        available_reference_images.append({
            "reference_image_index": i,
            "basename": Path(p).name,
        })

    user_prompt = json.dumps({
        "style_spec": style,
        "task_pack_params": tp.get("params", {}),
        "info_pack_query_normalized": ip.get("query_normalized"),
        "info_pack_user_query": ip.get("user_query"),
        "info_pack_document_digest": ip.get("document_digest"),
        "raw_documents_excerpt": raw_docs or None,
        "available_reference_images": available_reference_images or None,
    }, ensure_ascii=False, indent=2)
    try:
        raw = llm(system_prompt, user_prompt)
        data = _parse_json_loose(raw)
    except (ModelClientError, json.JSONDecodeError) as e:
        return _fail(f"outline: {e}")
    pages = data.get("pages", [])
    expected = int(tp.get("params", {}).get("page_count", 0))
    if expected and len(pages) != expected:
        return _fail(f"outline page_count mismatch: got {len(pages)}, expected {expected}")
    _write_text(deck / "outline.json", json.dumps(data, ensure_ascii=False, indent=2))
    return _ok(path="outline.json", pages=len(pages))


_ALLOWED_SLOT_KINDS = {"decoration", "concept_visual"}


def cmd_asset_plan(deck: Path) -> int:
    outline = _load_json(deck / "outline.json")
    style = _load_json(deck / "style_spec.json")
    system_prompt = _load_prompt("asset_plan.md")
    user_prompt = json.dumps({
        "style_spec": style,
        "outline": outline,
    }, ensure_ascii=False, indent=2)
    try:
        raw = llm(system_prompt, user_prompt)
        data = _parse_json_loose(raw)
    except (ModelClientError, json.JSONDecodeError) as e:
        return _fail(f"asset_plan: {e}")

    # Build a lookup from outline pages for use_table / use_image checks
    outline_pages = {int(p.get("page_no", 0)): p for p in outline.get("pages", [])}
    planned_pages = {int(p.get("page_no", 0)): p for p in data.get("pages", []) if p.get("page_no") is not None}

    # Normalize to a full page list. The model sometimes emits only pages with
    # non-empty slots, but downstream stages expect every outline page to be
    # present in asset_plan.json, including pages whose slots are intentionally
    # empty because they use inherited tables/images or pure HTML rendering.
    normalized_pages = []
    for pno in sorted(outline_pages):
        page = planned_pages.get(pno) or {"page_no": pno, "slots": []}
        page["page_no"] = pno
        if not isinstance(page.get("slots"), list):
            page["slots"] = []
        normalized_pages.append(page)
    data["pages"] = normalized_pages

    dropped_kinds: list[str] = []
    dropped_for_inherited: list[int] = []

    for page in data.get("pages", []):
        pno = int(page.get("page_no", 0))
        op = outline_pages.get(pno) or {}

        # If the outline page inherits a table or image, clear all T2I slots
        if op.get("use_table") is not None or op.get("use_image") is not None:
            if page.get("slots"):
                dropped_for_inherited.append(pno)
            page["slots"] = []
            continue

        # Filter slots by whitelist
        filtered = []
        for slot in page.get("slots", []):
            kind = slot.get("slot_kind", "")
            if kind not in _ALLOWED_SLOT_KINDS:
                dropped_kinds.append(f"p{pno}/{slot.get('slot_id','?')}={kind!r}")
                continue
            sid = slot.get("slot_id", "slot")
            slot["local_path"] = f"images/page_{pno:03d}_{sid}.png"
            slot["status"] = "pending"
            slot["quality_review"] = None
            filtered.append(slot)
        page["slots"] = filtered

    _write_text(deck / "asset_plan.json", json.dumps(data, ensure_ascii=False, indent=2))
    total_slots = sum(len(p.get("slots", [])) for p in data.get("pages", []))
    extra = {"path": "asset_plan.json", "pages": len(data.get("pages", [])), "slots": total_slots}
    if dropped_kinds:
        extra["dropped_slots_bad_kind"] = dropped_kinds
    if dropped_for_inherited:
        extra["cleared_slots_due_to_inherited"] = dropped_for_inherited
    return _ok(**extra)


def _update_asset_plan_slot(
    plan_path: Path, page_no: int, slot_id: str, updates: dict
) -> None:
    """Atomically re-read asset_plan.json, patch the target slot, write it back.

    Holds _PLAN_LOCK so concurrent gen-image workers can't clobber each other.
    """
    with _PLAN_LOCK:
        plan = _load_json(plan_path)
        for page in plan.get("pages", []):
            if int(page.get("page_no", -1)) != page_no:
                continue
            for slot in page.get("slots", []):
                if slot.get("slot_id") == slot_id:
                    slot.update(updates)
                    break
            break
        _write_text(plan_path, json.dumps(plan, ensure_ascii=False, indent=2))


def cmd_gen_image(deck: Path, page_no: int, slot_id: str) -> int:
    """Generate a single slot's image via sn-image-base's sn_agent_runner (T2I).

    Policy: T2I must route through sn-image-base, NOT through model_client.
    model_client handles only LLM / VLM.
    """
    import subprocess

    plan_path = deck / "asset_plan.json"
    plan = _load_json(plan_path)
    page = next((p for p in plan.get("pages", []) if int(p.get("page_no", -1)) == page_no), None)
    if page is None:
        return _fail(f"page {page_no} missing from asset_plan")
    slot = next((s for s in page.get("slots", []) if s.get("slot_id") == slot_id), None)
    if slot is None:
        return _fail(f"slot {slot_id!r} missing from page {page_no}")

    # Locate sn-image-base/scripts/sn_agent_runner.py
    sn_base = os.environ.get("SN_IMAGE_BASE", "").strip()
    if sn_base:
        runner = Path(sn_base) / "scripts" / "sn_agent_runner.py"
    else:
        # fallback: assume sibling dir under skills/
        runner = SKILL_DIR.parent / "sn-image-base" / "scripts" / "sn_agent_runner.py"
    if not runner.exists():
        return _fail(f"sn-image-base sn_agent_runner.py not found at {runner}; set $SN_IMAGE_BASE")

    save_path = deck / slot["local_path"]
    save_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable, str(runner), "sn-image-generate",
        "--prompt", slot["image_prompt"],
        "--aspect-ratio", slot.get("aspect_ratio", "16:9"),
        "--image-size", slot.get("image_size", "2k"),
        "--save-path", str(save_path),
        "--output-format", "json",
    ]

    def _record_failure(err: str) -> int:
        _update_asset_plan_slot(
            plan_path, page_no, slot_id,
            {"status": "failed", "quality_review": {"error": err[:300]}},
        )
        return _fail(f"gen-image p{page_no} {slot_id}: {err}",
                     page_no=page_no, slot_id=slot_id)

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    except subprocess.TimeoutExpired:
        return _record_failure("sn_agent_runner sn-image-generate timed out after 600s")
    except FileNotFoundError as e:
        return _record_failure(f"failed to spawn python for sn-image-base: {e}")

    if proc.returncode != 0:
        # runner failed; parse JSON error if present, else use stderr
        err = proc.stderr.strip() or proc.stdout.strip() or f"exit {proc.returncode}"
        try:
            out = json.loads(proc.stdout.strip().splitlines()[-1])
            if out.get("status") == "failed":
                err = str(out.get("error", err))
        except Exception:
            pass
        return _record_failure(err)

    # Verify the file actually landed
    if not save_path.exists() or save_path.stat().st_size == 0:
        return _record_failure(f"sn-image-generate returned ok but {save_path} is missing/empty")

    # VLM quality gate — T2I models sometimes emit images with color-hex
    # swatches as text, watermarks, UI chrome, or garbled glyphs. These look
    # broken on a slide, so reject + delete instead of shipping them.
    qc_reject = _vlm_image_qc(save_path)
    if qc_reject is not None:
        try:
            save_path.unlink()
        except OSError:
            pass
        _update_asset_plan_slot(
            plan_path, page_no, slot_id,
            {"status": "failed", "quality_review": {"rejected_by": "vlm_qc", "reason": qc_reject[:300]}},
        )
        return _fail(
            f"gen-image p{page_no} {slot_id}: rejected by VLM QC ({qc_reject[:120]})",
            page_no=page_no, slot_id=slot_id, qc_rejected=True,
        )

    _update_asset_plan_slot(
        plan_path, page_no, slot_id,
        {"status": "ok", "quality_review": {"rejected_by": None}},
    )
    return _ok(page_no=page_no, slot_id=slot_id, path=slot["local_path"])


_VLM_QC_SYSTEM = """You are a strict image QC reviewer for presentation slides.

Reject an image if it shows ANY of:
- Hex color codes or RGB values rendered as visible text inside the image
  (e.g. "#FF0000", "rgb(120, 30, 200)", a color-picker swatch with numbers)
- A color palette or swatch grid with labels / codes — this is a design tool
  leaked into the output, not a slide image
- Watermarks, website URLs, model-brand marks (e.g. "getty images", "stable diffusion")
- UI chrome from design tools (toolbars, menu bars, layer panels, rulers)
- Garbled / nonsense text that looks like text but isn't a real word
- Big empty white areas with only stray marks

If the image is a normal illustration / photo / abstract decoration with no such defects, accept it.

Output format — STRICTLY ONE of these two lines, nothing else:

  OK
  REJECT: <one short reason, under 20 words>

No explanations, no JSON, no markdown.
"""


def _vlm_image_qc(image_path: Path) -> str | None:
    """Run a fast VLM QC check on a generated image. Returns None if the
    image is acceptable, or a short rejection reason if it should be dropped.

    The QC is best-effort: any error (missing VLM, network, parse failure) is
    treated as ACCEPT so we never block the pipeline on the QC itself.
    """
    try:
        out = vlm(_VLM_QC_SYSTEM, "Review this image.", images=[image_path])
    except Exception:
        return None
    first = (out or "").strip().splitlines()[0].strip() if (out or "").strip() else ""
    if not first:
        return None
    upper = first.upper()
    if upper == "OK" or upper.startswith("OK "):
        return None
    if upper.startswith("REJECT"):
        # trim "REJECT:" prefix if present
        after = first.split(":", 1)[1].strip() if ":" in first else first
        return after or "vlm rejected without reason"
    # Unparseable — be permissive, ship it.
    return None


def _normalize_img_srcs(html: str, page_plan: dict, extra_paths: list[str] | None = None) -> tuple[str, int]:
    """Rewrite every <img src="..."> whose basename matches a known asset slot
    (or an extra allowlisted path) into the correct `../<relative>` form.

    Handles the common model mistakes:
      - "images/page_002_x.png"      (relative missing `../`)
      - "/images/page_002_x.png"     (absolute URL)
      - "/mnt/data/page_002_x.png"   (hallucinated absolute path)
      - "file:///abs/.../page_002_x.png"
    If the basename doesn't match any known asset, leave it alone.

    `extra_paths` lists additional `images/...`-style relative paths (e.g. the
    inherited image copied into images/page_XXX_inherited.png) that should be
    canonicalized the same way.

    Returns (new_html, rewrite_count).
    """
    # Build basename -> canonical relative target lookup
    wanted: dict[str, str] = {}
    for slot in page_plan.get("slots", []):
        lp = slot.get("local_path") or ""
        if not lp:
            continue
        base = lp.rsplit("/", 1)[-1]
        wanted[base] = f"../{lp}" if not lp.startswith("../") else lp

    for extra in extra_paths or []:
        if not extra:
            continue
        base = extra.rsplit("/", 1)[-1]
        wanted[base] = f"../{extra}" if not extra.startswith("../") else extra

    if not wanted:
        return html, 0

    def _fix(m: re.Match) -> str:
        raw = m.group(2)
        # keep data URIs and external http URLs untouched
        if raw.startswith(("data:", "http://", "https://")):
            return m.group(0)
        base = raw.rsplit("/", 1)[-1].split("?", 1)[0]
        target = wanted.get(base)
        if target is None:
            return m.group(0)
        return f'{m.group(1)}"{target}"'

    pattern = re.compile(r'(<img\b[^>]*\bsrc=)"([^"]*)"', re.IGNORECASE)
    count_holder = {"n": 0}

    def _count_wrapper(m: re.Match) -> str:
        new = _fix(m)
        if new != m.group(0):
            count_holder["n"] += 1
        return new

    new_html = pattern.sub(_count_wrapper, html)
    return new_html, count_holder["n"]


def _resolve_inherited_table(ip: dict, page_outline: dict) -> dict | None:
    ref = page_outline.get("use_table")
    if not ref:
        return None
    rde = ip.get("raw_document_excerpts") or {}
    raw_path = rde.get("path")
    if not raw_path or not Path(raw_path).exists():
        return None
    raw = _load_json(Path(raw_path))
    docs = raw.get("documents") or []
    try:
        di = int(ref["doc_index"])
        ti = int(ref["table_index"])
        rows = docs[di]["tables"][ti]
        return {"doc_index": di, "table_index": ti, "rows": rows}
    except (KeyError, IndexError, TypeError):
        return None


def _resolve_inherited_image(ip: dict, page_outline: dict, deck: Path, page_no: int) -> dict | None:
    """Resolve `page_outline.use_image` into a concrete image.

    Two variants are supported:
      - Pool A (doc-embedded): `{"doc_index": D, "image_index": I}` — looks up
        raw_documents.json → `documents[D].inherited_images[I].path`.
      - Pool B (standalone user uploads): `{"reference_image_index": N}` —
        looks up `info_pack.user_assets.reference_images[N]`.
    Either way, copy the image into `<deck_dir>/images/page_XXX_inherited.<ext>`
    and return its relative path + alt text.
    """
    ref = page_outline.get("use_image")
    if not ref:
        return None

    src = ""
    alt = ""

    # Pool B — reference_image_index
    if "reference_image_index" in ref:
        try:
            idx = int(ref["reference_image_index"])
        except (TypeError, ValueError):
            return None
        ua = ip.get("user_assets") or {}
        refs = ua.get("reference_images") or []
        if idx < 0 or idx >= len(refs):
            return None
        src = refs[idx] or ""
        # Derive a reasonable alt from the filename (fig3_dram_market_share.png → "dram market share")
        if src:
            stem = Path(src).stem
            alt = stem.replace("_", " ")
    # Pool A — doc_index / image_index
    elif "doc_index" in ref and "image_index" in ref:
        rde = ip.get("raw_document_excerpts") or {}
        raw_path = rde.get("path")
        if not raw_path or not Path(raw_path).exists():
            return None
        try:
            raw = _load_json(Path(raw_path))
        except Exception:
            return None
        docs = raw.get("documents") or []
        try:
            di = int(ref["doc_index"])
            ii = int(ref["image_index"])
            img = docs[di]["inherited_images"][ii]
        except (KeyError, IndexError, TypeError):
            return None
        # `inherited_images[i]` historically has two shapes in the wild:
        # `{path, alt}` dict (canonical, from parse_user_docs.py) or a bare
        # path string (hand-edited decks / older artifacts). Accept both
        # rather than crash with AttributeError.
        if isinstance(img, dict):
            src = img.get("path") or ""
            alt = img.get("alt", "") or ""
        elif isinstance(img, str):
            src = img
            alt = Path(img).stem.replace("_", " ") if img else ""
        else:
            return None
    else:
        # unknown shape
        return None

    if not src:
        return None
    # Remote URL: pass through as-is (page_html may embed it directly)
    if src.startswith(("http://", "https://", "data:")):
        return {"remote_url": src, "local_path": None, "alt": alt}

    src_path = Path(src)
    if not src_path.exists() or not src_path.is_file():
        return None

    # Copy into <deck_dir>/images/page_XXX_inherited.<ext> (preserve ext)
    ext = src_path.suffix.lower() or ".png"
    dst_rel = f"images/page_{page_no:03d}_inherited{ext}"
    dst_abs = deck / dst_rel
    dst_abs.parent.mkdir(parents=True, exist_ok=True)
    dst_abs.write_bytes(src_path.read_bytes())
    return {"remote_url": None, "local_path": dst_rel, "alt": alt}


def cmd_page_html(deck: Path, page_no: int) -> int:
    """Two-step HTML generation:

    Step 1 (REWRITE): convert the structured outline + style + inherited
      content into a single natural-language "query_detailed"-style user
      prompt.
    Step 2 (GENERATE): call the HTML generator LLM with a minimal system
      prompt ("you output complete HTML, no explanations") + the rewritten
      natural-language user prompt → final HTML.

    This replaces the previous monolithic prompt loaded with schema fields,
    CSS rules, and hard constraints. The rewriter is responsible for
    folding all constraints into a natural-language description, matching
    the `query_detailed` training-data style.
    """
    style = _load_json(deck / "style_spec.json")
    outline = _load_json(deck / "outline.json")
    plan = _load_json(deck / "asset_plan.json")
    ip = _load_json(deck / "info_pack.json")
    tp = _load_json(deck / "task_pack.json")

    page_outline = next((p for p in outline["pages"] if int(p["page_no"]) == page_no), None)
    if page_outline is None:
        return _fail(f"outline missing page {page_no}")
    page_plan = next((p for p in plan["pages"] if int(p["page_no"]) == page_no), None)
    if page_plan is None:
        return _fail(f"asset_plan missing page {page_no}")

    inherited_table = _resolve_inherited_table(ip, page_outline)
    inherited_image = _resolve_inherited_image(ip, page_outline, deck, page_no)

    # Only expose slots the rewriter should actually mention in the query —
    # failed slots are hidden so the rewriter describes a text-first layout.
    available_slot_images: list[str] = []
    for slot in page_plan.get("slots") or []:
        if slot.get("status") != "failed" and slot.get("local_path"):
            # Relative to <deck_dir>, which pages/ HTML references as "../<path>"
            available_slot_images.append(slot["local_path"])

    # --- Step 1: rewrite structured data → natural-language user prompt ---
    rewrite_system = _load_prompt("page_html_rewrite.md")
    rewrite_user_payload = {
        "style_spec": style,
        "page_outline": page_outline,
        "page_no": page_no,
        "inherited_table": inherited_table,
        "inherited_image_local_path": (inherited_image or {}).get("local_path"),
        "available_slot_images": available_slot_images,
        "language": tp.get("params", {}).get("language", "zh"),
    }
    try:
        rewritten_query = llm(
            rewrite_system,
            json.dumps(rewrite_user_payload, ensure_ascii=False, indent=2),
        )
    except ModelClientError as e:
        return _fail(f"page-html rewrite p{page_no}: {e}", page_no=page_no)
    rewritten_query = _strip_code_fences(rewritten_query) if rewritten_query.lstrip().startswith("```") else rewritten_query
    rewritten_query = rewritten_query.strip()
    if not rewritten_query:
        return _fail(f"page-html rewrite p{page_no}: empty rewrite output", page_no=page_no)

    # --- Step 2: generate HTML from the rewritten query ---
    gen_system = _load_prompt("page_html.md")
    try:
        html = llm(gen_system, rewritten_query)
    except ModelClientError as e:
        return _fail(f"page-html p{page_no}: {e}", page_no=page_no)

    html = _strip_code_fences(html) if html.lstrip().startswith("```") else html

    # Defensive: rewrite any malformed <img src> paths back to the canonical
    # relative form. The rewriter + generator usually get this right, but
    # models still occasionally emit absolute paths / leading slashes.
    extra_paths: list[str] = []
    if inherited_image and inherited_image.get("local_path"):
        extra_paths.append(inherited_image["local_path"])
    html, fixed = _normalize_img_srcs(html, page_plan, extra_paths=extra_paths)

    out_path = deck / "pages" / f"page_{page_no:03d}.html"
    _write_text(out_path, html)
    return _ok(
        page_no=page_no,
        path=str(out_path.relative_to(deck)),
        img_srcs_fixed=fixed,
    )


def cmd_export(deck: Path) -> int:
    import subprocess
    converter = SKILL_DIR / "scripts" / "export_pptx" / "html_to_pptx.mjs"
    if not converter.exists():
        return _fail("export_pptx/html_to_pptx.mjs missing — run npm install in scripts/export_pptx")
    cmd = ["node", str(converter), "--deck-dir", str(deck), "--force"]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        return _fail(f"export failed: {proc.stderr.strip()[:500]}")
    # Try to parse the converter's stdout json
    stdout = proc.stdout.strip()
    converted = pages = failed = None
    try:
        last = [l for l in stdout.splitlines() if l.strip().startswith("{")]
        if last:
            info = json.loads(last[-1])
            converted = info.get("converted")
            pages = info.get("pages")
            failed = info.get("failed")
    except Exception:
        pass
    return _ok(pages=pages, converted=converted, failed=failed)


# ---------------------------------------------------------------------------
# Batch helpers (concurrent fan-out)
# ---------------------------------------------------------------------------

# Serializes the read-modify-write cycle on asset_plan.json so concurrent
# gen-image workers don't clobber each other's slot updates.
_PLAN_LOCK = threading.Lock()
_STDOUT_LOCK = threading.Lock()


def _capture_cmd(func, *args, **kwargs) -> tuple[int, dict]:
    """Run a cmd_* function that prints a single JSON status line to stdout,
    capture that line, and return (exit_code, parsed_dict)."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = func(*args, **kwargs)
    raw = buf.getvalue().strip()
    last = raw.splitlines()[-1] if raw else ""
    try:
        payload = json.loads(last) if last else {}
    except json.JSONDecodeError:
        payload = {"status": "failed", "raw": last[:300]}
    return code, payload


def _progress(msg: str) -> None:
    """Human-readable progress line to stderr so the agent can tail it."""
    with _STDOUT_LOCK:
        print(msg, file=sys.stderr, flush=True)


def _run_concurrent(tasks: list[tuple], concurrency: int) -> list[dict]:
    """Run a list of (func, args, kwargs, label) tuples in a ThreadPoolExecutor.

    Returns a list of result dicts in submission order, each with keys:
      label, exit_code, payload
    """
    results: list[dict | None] = [None] * len(tasks)
    concurrency = max(1, min(int(concurrency), 16))
    with ThreadPoolExecutor(max_workers=concurrency) as ex:
        future_to_i = {}
        for i, (fn, args, kwargs, label) in enumerate(tasks):
            fut = ex.submit(_capture_cmd, fn, *args, **kwargs)
            future_to_i[fut] = (i, label)
        for fut in as_completed(future_to_i):
            i, label = future_to_i[fut]
            try:
                code, payload = fut.result()
            except Exception as e:  # noqa: BLE001
                code, payload = 1, {"status": "failed", "error": f"{type(e).__name__}: {e}"[:300]}
            status = payload.get("status", "failed")
            _progress(f"[{label}] {status}")
            results[i] = {"label": label, "exit_code": code, "payload": payload}
    return [r for r in results if r is not None]


def cmd_batch_gen_image(deck: Path, concurrency: int) -> int:
    """Fan out gen-image over every pending slot in asset_plan.json."""
    plan_path = deck / "asset_plan.json"
    if not plan_path.exists():
        return _fail("asset_plan.json missing")
    plan = _load_json(plan_path)
    tasks: list[tuple] = []
    for page in plan.get("pages", []):
        pno = int(page.get("page_no", 0))
        for slot in page.get("slots", []):
            if slot.get("status") == "ok":
                continue
            sid = slot.get("slot_id", "slot")
            tasks.append((cmd_gen_image, (deck, pno, sid), {}, f"p{pno:03d}/{sid}"))
    if not tasks:
        return _ok(stage="gen-image", submitted=0, note="nothing pending")
    results = _run_concurrent(tasks, concurrency)
    ok = [r["label"] for r in results if r["exit_code"] == 0]
    failed = [
        {"label": r["label"], "error": r["payload"].get("error", "")}
        for r in results if r["exit_code"] != 0
    ]
    return _ok(
        stage="gen-image",
        concurrency=concurrency,
        submitted=len(tasks),
        ok=len(ok),
        failed=len(failed),
        failed_detail=failed or None,
    )


def cmd_batch_page_html(deck: Path, concurrency: int) -> int:
    outline_path = deck / "outline.json"
    if not outline_path.exists():
        return _fail("outline.json missing")
    outline = _load_json(outline_path)
    tasks: list[tuple] = []
    for page in outline.get("pages", []):
        pno = int(page.get("page_no", 0))
        if pno <= 0:
            continue
        tasks.append((cmd_page_html, (deck, pno), {}, f"p{pno:03d}/html"))
    if not tasks:
        return _fail("no pages in outline")
    results = _run_concurrent(tasks, concurrency)
    ok = sum(1 for r in results if r["exit_code"] == 0)
    failed = [
        {"label": r["label"], "error": r["payload"].get("error", "")}
        for r in results if r["exit_code"] != 0
    ]
    return _ok(
        stage="page-html",
        concurrency=concurrency,
        submitted=len(tasks),
        ok=ok,
        failed=len(failed),
        failed_detail=failed or None,
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="run_stage")
    sub = p.add_subparsers(dest="cmd", required=True)

    for name in ("preflight", "style", "outline", "asset-plan", "export"):
        sp = sub.add_parser(name)
        sp.add_argument("--deck-dir", type=Path, required=True)

    sp = sub.add_parser("gen-image")
    sp.add_argument("--deck-dir", type=Path, required=True)
    sp.add_argument("--page", type=int, required=True)
    sp.add_argument("--slot", type=str, required=True)

    sp = sub.add_parser("page-html")
    sp.add_argument("--deck-dir", type=Path, required=True)
    sp.add_argument("--page", type=int, required=True)

    # Batch / concurrent variants (default concurrency=4). Each fans out its
    # per-item work across a thread pool so LLM / VLM / T2I wait times overlap.
    for name in ("batch-gen-image", "batch-page-html"):
        sp = sub.add_parser(name)
        sp.add_argument("--deck-dir", type=Path, required=True)
        sp.add_argument("--concurrency", type=int, default=4,
                        help="max parallel workers (default 4, clamped to 1-16)")

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    deck = args.deck_dir.expanduser().resolve()
    if args.cmd == "preflight":
        return cmd_preflight(deck)
    if args.cmd == "style":
        return cmd_style(deck)
    if args.cmd == "outline":
        return cmd_outline(deck)
    if args.cmd == "asset-plan":
        return cmd_asset_plan(deck)
    if args.cmd == "gen-image":
        return cmd_gen_image(deck, args.page, args.slot)
    if args.cmd == "page-html":
        return cmd_page_html(deck, args.page)
    if args.cmd == "export":
        return cmd_export(deck)
    if args.cmd == "batch-gen-image":
        return cmd_batch_gen_image(deck, args.concurrency)
    if args.cmd == "batch-page-html":
        return cmd_batch_page_html(deck, args.concurrency)
    return _fail(f"unknown command {args.cmd!r}")


if __name__ == "__main__":
    sys.exit(main())
