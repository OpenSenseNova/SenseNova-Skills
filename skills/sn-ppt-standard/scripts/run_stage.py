#!/usr/bin/env python3
"""Single entry point for every sn-ppt-standard stage.

Usage:
    python run_stage.py preflight       --deck-dir <deck>
    python run_stage.py style           --deck-dir <deck>
    python run_stage.py outline         --deck-dir <deck>
    python run_stage.py asset-plan      --deck-dir <deck>
    python run_stage.py gen-image       --deck-dir <deck> --page N --slot SLOT
    python run_stage.py page-html       --deck-dir <deck> --page N
    python run_stage.py batch-gen-image    --deck-dir <deck> [--concurrency 4]
    python run_stage.py batch-page-html    --deck-dir <deck> [--concurrency 4]
    python run_stage.py review             --deck-dir <deck> [--concurrency 4]
    python run_stage.py review-page        --deck-dir <deck> --page N
    python run_stage.py refine-page        --deck-dir <deck> --page N
    python run_stage.py batch-refine-page  --deck-dir <deck> [--concurrency 4]
    python run_stage.py export             --deck-dir <deck>

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
import shutil
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib import error as urlerror
from urllib import request as urlrequest

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


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    return int(_env_float(name, default))


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


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
    outline_timeout = _env_float(
        "OUTLINE_SN_TEXT_TIMEOUT",
        _env_float("SN_TEXT_TIMEOUT", _env_float("SN_CHAT_TIMEOUT", 300.0)),
    )
    outline_retries = _env_int("OUTLINE_SN_TEXT_RETRIES", 1)
    try:
        raw = llm(
            system_prompt, user_prompt,
            timeout=outline_timeout, retries=outline_retries, request_name="outline",
        )
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

        intent_by_slot = {
            s.get("slot_id"): s.get("intent") or ""
            for s in (op.get("asset_slots") or [])
            if s.get("slot_id")
        }

        # Filter slots by whitelist
        filtered = []
        for slot in page.get("slots", []):
            kind = slot.get("slot_kind", "")
            if kind not in _ALLOWED_SLOT_KINDS:
                dropped_kinds.append(f"p{pno}/{slot.get('slot_id','?')}={kind!r}")
                continue
            sid = slot.get("slot_id", "slot")
            slot["local_path"] = f"images/page_{pno:03d}_{sid}.png"
            slot["search_query"] = _slot_search_query({
                **slot,
                "intent": intent_by_slot.get(sid, ""),
            })
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


def _image_search_script() -> Path | None:
    """Locate the configured image-search skill script without exposing the
    provider name in PPT progress/errors."""
    configured = os.environ.get("PPT_IMAGE_SEARCH_SCRIPT", "").strip()
    candidates: list[Path] = []
    if configured:
        candidates.append(Path(configured).expanduser())
    for skill_dir in sorted(p for p in SKILL_DIR.parent.iterdir() if p.is_dir()):
        scripts_dir = skill_dir / "scripts"
        if scripts_dir.is_dir():
            candidates.extend(sorted(scripts_dir.glob("*image_search.py")))
    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return candidate
    return None


def _slot_search_query(slot: dict) -> str:
    query = (
        slot.get("search_query")
        or slot.get("intent")
        or slot.get("image_prompt")
        or slot.get("slot_id")
        or ""
    )
    return re.sub(r"\s+", " ", str(query)).strip()


def _image_search_candidates(query: str) -> tuple[list[dict], str | None]:
    if not _env_bool("PPT_IMAGE_SEARCH_FALLBACK", True):
        return [], "image search fallback disabled"
    if not query:
        return [], "empty image search query"
    script = _image_search_script()
    if script is None:
        return [], "image search skill not found"

    num = max(1, _env_int("PPT_IMAGE_SEARCH_RESULTS", 10))
    timeout = max(5, _env_int("PPT_IMAGE_SEARCH_TIMEOUT", 45))
    cmd = [sys.executable, str(script), query, "--num", str(num), "--json"]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return [], "image search timed out"
    except OSError:
        return [], "image search could not start"
    if proc.returncode != 0:
        return [], "image search unavailable"
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return [], "image search returned invalid data"

    raw_items = data.get("images")
    if not isinstance(raw_items, list):
        raw_items = data.get("results")
    if not isinstance(raw_items, list):
        return [], "image search returned no results"

    candidates: list[dict] = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        image_url = str(item.get("imageUrl") or item.get("image_url") or "").strip()
        if not image_url:
            nested = item.get("image")
            if isinstance(nested, dict):
                image_url = str(nested.get("src") or nested.get("url") or "").strip()
        if not image_url:
            continue
        candidates.append({
            "image_url": image_url,
            "page_url": str(item.get("link") or item.get("url") or "").strip(),
            "title": str(item.get("title") or "").strip(),
            "source": str(item.get("source") or item.get("domain") or "").strip(),
        })
    if not candidates:
        return [], "image search returned no downloadable images"
    return candidates, None


def _save_downloaded_image(raw_path: Path, save_path: Path) -> bool:
    """Normalize downloaded images to the requested slot path when possible."""
    if _read_image_size(raw_path) is None:
        return False
    try:
        from PIL import Image  # noqa: WPS433 — optional dep
        with Image.open(raw_path) as im:
            im.load()
            has_alpha = "A" in im.getbands()
            target_mode = "RGBA" if has_alpha else "RGB"
            if im.mode != target_mode:
                im = im.convert(target_mode)
            save_path.parent.mkdir(parents=True, exist_ok=True)
            im.save(save_path, format="PNG")
        return save_path.exists() and save_path.stat().st_size > 0
    except Exception:
        try:
            save_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(raw_path), str(save_path))
            return save_path.exists() and save_path.stat().st_size > 0
        except OSError:
            return False


def _download_image_candidate(url: str, save_path: Path) -> tuple[bool, str | None]:
    max_bytes = max(1024 * 1024, _env_int("PPT_IMAGE_SEARCH_MAX_BYTES", 15 * 1024 * 1024))
    timeout = max(5, _env_int("PPT_IMAGE_DOWNLOAD_TIMEOUT", 30))
    req = urlrequest.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "image/*,*/*;q=0.8",
        },
    )
    tmp = save_path.with_name(save_path.name + ".download")
    try:
        with urlrequest.urlopen(req, timeout=timeout) as resp:
            content_type = (resp.headers.get("Content-Type") or "").split(";", 1)[0].lower()
            if content_type and not content_type.startswith("image/"):
                return False, "candidate was not an image"
            payload = resp.read(max_bytes + 1)
    except (urlerror.URLError, OSError, ValueError):
        return False, "candidate download failed"
    if len(payload) > max_bytes:
        return False, "candidate image too large"
    try:
        tmp.write_bytes(payload)
        if not _save_downloaded_image(tmp, save_path):
            return False, "candidate image could not be decoded"
    finally:
        try:
            if tmp.exists():
                tmp.unlink()
        except OSError:
            pass

    qc_reject = _vlm_image_qc(save_path)
    if qc_reject is not None:
        try:
            save_path.unlink()
        except OSError:
            pass
        return False, f"candidate rejected by VLM QC: {qc_reject[:120]}"
    return True, None


def _try_image_search_fallback(
    plan_path: Path,
    page_no: int,
    slot_id: str,
    slot: dict,
    save_path: Path,
    generation_error: str,
) -> tuple[bool, dict | str]:
    query = _slot_search_query(slot)
    candidates, search_error = _image_search_candidates(query)
    if search_error:
        return False, search_error

    last_error = "no usable image search result"
    for candidate in candidates:
        ok, err = _download_image_candidate(candidate["image_url"], save_path)
        if not ok:
            last_error = err or last_error
            continue
        updates = {
            "status": "ok",
            "asset_source": "image_search",
            "search_query": query,
            "source_url": candidate["image_url"],
            "source_page": candidate.get("page_url") or "",
            "source_title": candidate.get("title") or "",
            "source_domain": candidate.get("source") or "",
            "quality_review": {
                "generated_image_error": generation_error[:300],
                "fallback": "image_search",
                "rejected_by": None,
            },
        }
        _update_asset_plan_slot(plan_path, page_no, slot_id, updates)
        return True, updates
    return False, last_error


def cmd_gen_image(deck: Path, page_no: int, slot_id: str) -> int:
    """Generate a single slot's image via sn-image-base's sn_agent_runner (T2I).

    Policy: T2I must route through sn-image-base, NOT through model_client.
    model_client handles only LLM / VLM.
    """
    plan_path = deck / "asset_plan.json"
    plan = _load_json(plan_path)
    page = next((p for p in plan.get("pages", []) if int(p.get("page_no", -1)) == page_no), None)
    if page is None:
        return _fail(f"page {page_no} missing from asset_plan")
    slot = next((s for s in page.get("slots", []) if s.get("slot_id") == slot_id), None)
    if slot is None:
        return _fail(f"slot {slot_id!r} missing from page {page_no}")

    save_path = deck / slot["local_path"]
    save_path.parent.mkdir(parents=True, exist_ok=True)

    def _record_failure(err: str) -> int:
        fallback_ok, fallback = _try_image_search_fallback(
            plan_path, page_no, slot_id, slot, save_path, err,
        )
        if fallback_ok and isinstance(fallback, dict):
            return _ok(
                page_no=page_no,
                slot_id=slot_id,
                path=slot["local_path"],
                source="image_search",
                note="generated image failed; image search fallback used",
            )
        _update_asset_plan_slot(
            plan_path, page_no, slot_id,
            {
                "status": "failed",
                "quality_review": {
                    "error": err[:300],
                    "fallback_error": str(fallback)[:300],
                },
            },
        )
        return _fail(f"gen-image p{page_no} {slot_id}: {err}",
                     page_no=page_no, slot_id=slot_id)

    # Locate sn-image-base/scripts/sn_agent_runner.py
    sn_base = os.environ.get("SN_IMAGE_BASE", "").strip()
    if sn_base:
        runner = Path(sn_base) / "scripts" / "sn_agent_runner.py"
    else:
        # fallback: assume sibling dir under skills/
        runner = SKILL_DIR.parent / "sn-image-base" / "scripts" / "sn_agent_runner.py"
    if not runner.exists():
        return _record_failure(f"sn-image-base sn_agent_runner.py not found at {runner}; set $SN_IMAGE_BASE")

    cmd = [
        sys.executable, str(runner), "sn-image-generate",
        "--prompt", slot.get("image_prompt") or _slot_search_query(slot),
        "--aspect-ratio", slot.get("aspect_ratio", "16:9"),
        "--image-size", slot.get("image_size", "2k"),
        "--save-path", str(save_path),
        "--output-format", "json",
    ]

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


def _extract_css_blocks(html: str) -> str:
    return "\n".join(
        m.group(1)
        for m in re.finditer(r"<style\b[^>]*>(.*?)</style>", html, re.IGNORECASE | re.DOTALL)
    )


def _selector_block(css: str, selector: str) -> str:
    pattern = rf"(?<![\w-]){re.escape(selector)}\s*\{{([^{{}}]*)\}}"
    m = re.search(pattern, css, re.IGNORECASE | re.DOTALL)
    return m.group(1) if m else ""


def _has_decl(block: str, prop: str, value_pattern: str | None = None) -> bool:
    m = re.search(rf"(?<![\w-]){re.escape(prop)}\s*:\s*([^;]+)", block, re.IGNORECASE)
    if not m:
        return False
    if value_pattern is None:
        return True
    return re.search(value_pattern, m.group(1).strip(), re.IGNORECASE) is not None


def _html_contract_issues(html: str) -> list[str]:
    """Fast static checks for the non-negotiable HTML shell.

    These catch the common regressions seen in recent runs before export:
    missing #bg/#ct, auto-height wrappers, padding on .wrapper, malformed
    @import rules, and stray prose inside <style>.
    """
    issues: list[str] = []
    if not re.search(r"<!doctype\s+html", html, re.IGNORECASE):
        issues.append("missing <!DOCTYPE html>")
    if not re.search(r"<div\b[^>]*class=[\"'][^\"']*\bwrapper\b", html, re.IGNORECASE):
        issues.append("missing outer <div class=\"wrapper\">")
    if not re.search(r"<div\b[^>]*id=[\"']bg[\"']", html, re.IGNORECASE):
        issues.append("missing <div id=\"bg\"> background layer")
    if not re.search(r"<div\b[^>]*id=[\"']ct[\"']", html, re.IGNORECASE):
        issues.append("missing <div id=\"ct\"> content layer")

    css = _extract_css_blocks(html)
    if not css.strip():
        issues.append("missing <style> CSS")
        return issues

    if re.search(r"@import\s+url\(", css, re.IGNORECASE):
        issues.append("uses external CSS @import; use local/system fonts only")
    css_no_comments = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)
    if re.search(r"}\s*[\u4e00-\u9fff][^{}]*[.#][A-Za-z0-9_-]+\s*\{", css_no_comments):
        issues.append("style block contains stray natural-language prose outside CSS comments")

    wrapper = _selector_block(css, ".wrapper")
    if not wrapper:
        issues.append("missing .wrapper CSS rule")
    else:
        if not _has_decl(wrapper, "width", r"^1600px$"):
            issues.append(".wrapper width must be exactly 1600px")
        if not _has_decl(wrapper, "height", r"^900px$"):
            issues.append(".wrapper height must be exactly 900px")
        if not _has_decl(wrapper, "position", r"^relative$"):
            issues.append(".wrapper position must be relative")
        if not _has_decl(wrapper, "overflow", r"^hidden$"):
            issues.append(".wrapper overflow must be hidden")
        if _has_decl(wrapper, "padding") and not _has_decl(wrapper, "padding", r"^0(px)?$"):
            issues.append(".wrapper must not carry content padding; put padding on #ct")
        if re.search(r"\b(max-width|min-height|max-height)\s*:", wrapper, re.IGNORECASE):
            issues.append(".wrapper must not use max-width/min-height/max-height")
        if re.search(r"\b(width\s*:\s*100%|height\s*:\s*auto)\b", wrapper, re.IGNORECASE):
            issues.append(".wrapper must not use responsive width:100% or height:auto")

    ct = _selector_block(css, "#ct")
    if not ct:
        issues.append("missing #ct CSS rule")
    else:
        if not _has_decl(ct, "position", r"^absolute$"):
            issues.append("#ct position must be absolute")
        if not _has_decl(ct, "inset", r"^0(px)?$"):
            issues.append("#ct must use inset: 0")
        if not _has_decl(ct, "padding", r"^60px$"):
            issues.append("#ct padding must be exactly 60px safe margin")
        if not _has_decl(ct, "box-sizing", r"^border-box$"):
            issues.append("#ct must use box-sizing: border-box")
        if _has_decl(ct, "height", r"^100%$") or _has_decl(ct, "position", r"^relative$"):
            issues.append("#ct must not be a relative 100%-height wrapper")

    if re.search(r"\b(transform\s*:\s*scale|zoom\s*:)", css, re.IGNORECASE):
        issues.append("must not use transform: scale(...) or zoom to fake fitting")

    return issues[:12]


def _browser_layout_issues(html_path: Path) -> list[str]:
    """Use Playwright when available to catch actual overflow.

    Browser QC is best-effort. If node/playwright/browser binaries are missing,
    skip it rather than failing page generation on environment setup.
    """
    if os.environ.get("PPT_LAYOUT_BROWSER_QC", "1").strip() in {"0", "false", "False"}:
        return []

    import subprocess

    playwright = SKILL_DIR / "scripts" / "export_pptx" / "node_modules" / "playwright"
    if not playwright.exists():
        return []

    script = r"""
const { pathToFileURL } = require('url');
const playwrightPath = process.argv[1];
const file = process.argv[2];
let chromium;
try {
  chromium = require(playwrightPath).chromium;
} catch (e) {
  console.log(JSON.stringify({skipped: 'playwright require failed'}));
  process.exit(0);
}

(async () => {
  const browser = await chromium.launch({headless: true});
  const page = await browser.newPage({viewport: {width: 1600, height: 900}, deviceScaleFactor: 1});
  await page.goto(pathToFileURL(file).href, {waitUntil: 'load'});
  await page.waitForTimeout(200);
  const issues = await page.evaluate(() => {
    const out = [];
    const wrapper = document.querySelector('.wrapper');
    const bg = document.querySelector('#bg');
    const ct = document.querySelector('#ct');
    if (!wrapper) return ['browser: missing .wrapper'];
    const wr = wrapper.getBoundingClientRect();
    if (Math.abs(wr.width - 1600) > 1 || Math.abs(wr.height - 900) > 1) {
      out.push(`browser: .wrapper rendered ${Math.round(wr.width)}x${Math.round(wr.height)}, expected 1600x900`);
    }
    if (document.body.scrollWidth > 1601 || document.body.scrollHeight > 901) {
      out.push(`browser: body scroll area ${document.body.scrollWidth}x${document.body.scrollHeight}, expected <=1600x900`);
    }
    if (ct && (ct.scrollWidth > ct.clientWidth + 1 || ct.scrollHeight > ct.clientHeight + 1)) {
      out.push(`browser: #ct scroll area ${ct.scrollWidth}x${ct.scrollHeight}, client ${ct.clientWidth}x${ct.clientHeight}`);
    }

    const safe = {left: wr.left + 60, top: wr.top + 60, right: wr.right - 60, bottom: wr.bottom - 60};
    const roots = new Set([document.documentElement, document.body, wrapper, bg, ct].filter(Boolean));
    const decoRe = /(bg|backdrop|decor|deco|glow|orb|ring|particle|nebula|grid|line|wave|noise|halo)/i;
    for (const el of Array.from(document.body.querySelectorAll('*'))) {
      if (roots.has(el)) continue;
      if (bg && bg.contains(el)) continue;
      const cs = getComputedStyle(el);
      if (cs.display === 'none' || cs.visibility === 'hidden' || Number(cs.opacity || '1') === 0) continue;
      const r = el.getBoundingClientRect();
      if (r.width < 2 || r.height < 2) continue;
      const tag = el.tagName.toLowerCase();
      const cls = typeof el.className === 'string' ? el.className : '';
      const text = (el.innerText || el.alt || '').trim().replace(/\s+/g, ' ');
      const isNonContentDecoration = !text && !['img', 'svg', 'canvas', 'table'].includes(tag) && decoRe.test(cls);
      if (isNonContentDecoration) continue;
      const outsideSlide = r.left < wr.left - 1 || r.top < wr.top - 1 || r.right > wr.right + 1 || r.bottom > wr.bottom + 1;
      const outsideSafe = r.left < safe.left - 1 || r.top < safe.top - 1 || r.right > safe.right + 1 || r.bottom > safe.bottom + 1;
      if (!outsideSlide && !outsideSafe) continue;
      const id = el.id ? '#' + el.id : '';
      const classPart = cls ? '.' + cls.trim().split(/\s+/).slice(0, 3).join('.') : '';
      const label = `${tag}${id}${classPart}`.slice(0, 80);
      const box = `${Math.round(r.left)},${Math.round(r.top)} ${Math.round(r.width)}x${Math.round(r.height)} bottom=${Math.round(r.bottom)} right=${Math.round(r.right)}`;
      out.push(`browser: content outside safe area: ${label} [${box}] ${text.slice(0, 80)}`);
      if (out.length >= 10) break;
    }
    return out;
  });
  await browser.close();
  console.log(JSON.stringify({issues}));
})().catch(err => {
  console.log(JSON.stringify({skipped: String(err && err.message || err).split('\n')[0]}));
});
"""

    env = os.environ.copy()
    if not env.get("PLAYWRIGHT_BROWSERS_PATH"):
        # Common locations in OpenClaw workspaces / Docker images. The check
        # is intentionally best-effort; browser QC is skipped if none exist.
        candidates: list[Path | None] = []
        for parent in html_path.parents:
            candidates.extend([parent / ".playwright", parent / "_playwright"])
        candidates.extend([Path("/ms-playwright"), Path.home() / ".cache" / "ms-playwright"])
        for candidate in candidates:
            if candidate and candidate.exists():
                env["PLAYWRIGHT_BROWSERS_PATH"] = str(candidate)
                break
    try:
        proc = subprocess.run(
            ["node", "-e", script, str(playwright), str(html_path)],
            capture_output=True,
            text=True,
            timeout=30,
            env=env,
        )
    except Exception:
        return []
    try:
        payload = json.loads((proc.stdout or "").strip().splitlines()[-1])
    except Exception:
        return []
    issues = payload.get("issues")
    return [str(i) for i in issues[:12]] if isinstance(issues, list) else []


def _page_html_retry_query(original_query: str, issues: list[str]) -> str:
    issue_lines = "\n".join(f"- {i}" for i in issues[:10])
    return (
        f"{original_query}\n\n"
        "【必须修复的上一版 HTML 问题】\n"
        "上一版 HTML 没有通过布局校验。请重新输出一份完整 HTML，不要解释，不要 markdown。\n"
        f"{issue_lines}\n\n"
        "修复要求：保持原有页面主题、语言、数据和图片路径，但必须使用固定 1600×900 外壳、"
        "#bg/#ct 分层、#ct 60px 安全边距；所有可见标题、正文、卡片、图片、图表和表格都必须"
        "落在 x=60..1540、y=60..840 内。空间不够时，缩短文案、减小字号、减少装饰、压缩 gap，"
        "不要增加画布高度，不要让内容越过底部或右侧。"
    )


def _read_image_size(path: Path) -> dict | None:
    """Return `{w, h, aspect}` for a local image file, or None if unreadable.

    Decodes only the dimensions (no full pixel buffer), so it's fine to call
    on every image once per page. Supports PNG / JPEG / GIF / WebP / BMP /
    SVG (with a width/height attribute). aspect is rounded to 3 decimals.

    Used by `cmd_page_html` to feed the rewriter accurate intrinsic dimensions
    for the inherited-image and asset-slot images, so the generator can size
    container width/height to match each image's natural aspect ratio.
    """
    try:
        if not path.exists() or not path.is_file():
            return None
        head = path.read_bytes()[:64]  # generous header for SVG
    except OSError:
        return None

    w = h = 0

    # PNG: 8-byte sig + 4-byte length + 'IHDR' + 4-byte width + 4-byte height
    if head[:8] == b"\x89PNG\r\n\x1a\n" and head[12:16] == b"IHDR":
        w = int.from_bytes(head[16:20], "big")
        h = int.from_bytes(head[20:24], "big")

    # GIF: 'GIF8' + version + 2-byte width LE + 2-byte height LE
    elif head[:4] == b"GIF8":
        w = int.from_bytes(head[6:8], "little")
        h = int.from_bytes(head[8:10], "little")

    # BMP: 'BM' + 18..22 width LE + 22..26 height LE
    elif head[:2] == b"BM":
        w = int.from_bytes(head[18:22], "little")
        h = int.from_bytes(head[22:26], "little")

    # WebP: 'RIFF' .... 'WEBP' 'VP8 ' / 'VP8L' / 'VP8X' — only handle VP8X for size
    elif head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        if head[12:16] == b"VP8X":
            # 24..27 width-1 LE, 27..30 height-1 LE
            w = int.from_bytes(head[24:27], "little") + 1
            h = int.from_bytes(head[27:30], "little") + 1

    # JPEG / SVG / etc — fall back to a Pillow read if available; otherwise we
    # just don't return a size (the rewriter will work without it).
    if w <= 0 or h <= 0:
        try:
            from PIL import Image  # noqa: WPS433 — optional dep
            with Image.open(path) as im:
                w, h = im.size
        except Exception:
            return None

    if w <= 0 or h <= 0:
        return None
    return {"w": int(w), "h": int(h), "aspect": round(w / h, 3)}


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

    # Inherited image: collect every textual hint the upstream pipeline
    # already produced. Resolution order (best → worst):
    #   1. ppt-entry's `caption_images.py` (VLM, actual image content)
    #      Pool A → raw_documents.json[doc_index].inherited_images[image_index].vlm_caption
    #      Pool B → info_pack.user_assets.reference_image_captions[abs_path]
    #   2. document_digest LLM's caption_hint (text-only guess; legacy)
    #   3. alt text from doc parser / filename
    # Cached fields are read directly — we never re-caption here ("single source
    # of truth": ppt-entry/scripts/caption_images.py owns image captioning).
    inherited_image_size = None
    inherited_image_caption_hint = None
    if inherited_image and inherited_image.get("local_path"):
        inherited_image_size = _read_image_size(deck / inherited_image["local_path"])
        ref = page_outline.get("use_image") or {}
        digest = ip.get("document_digest") or {}
        ua = ip.get("user_assets") or {}

        # Pool B (reference_image_index): look up the absolute upload path,
        # then check the `reference_image_captions` map.
        if "reference_image_index" in ref:
            try:
                idx = int(ref["reference_image_index"])
                ref_imgs = ua.get("reference_images") or []
                if 0 <= idx < len(ref_imgs):
                    abs_path = ref_imgs[idx]
                    captions = ua.get("reference_image_captions") or {}
                    cap = (captions.get(abs_path) or "").strip()
                    if cap:
                        inherited_image_caption_hint = cap
            except (TypeError, ValueError):
                pass

        # Pool A (doc_index / image_index): prefer raw_documents.json's
        # `vlm_caption` over the digest's `caption_hint`.
        if inherited_image_caption_hint is None and "doc_index" in ref and "image_index" in ref:
            rde = ip.get("raw_document_excerpts") or {}
            raw_path = rde.get("path")
            if raw_path and Path(raw_path).exists():
                try:
                    raw = _load_json(Path(raw_path))
                    di = int(ref["doc_index"])
                    ii = int(ref["image_index"])
                    img_entry = raw["documents"][di]["inherited_images"][ii]
                    if isinstance(img_entry, dict):
                        cap = (img_entry.get("vlm_caption") or "").strip()
                        if cap:
                            inherited_image_caption_hint = cap
                except (KeyError, IndexError, TypeError, json.JSONDecodeError):
                    pass

        # Fallback: digest's caption_hint (LLM guess based on doc text only).
        if inherited_image_caption_hint is None:
            for entry in digest.get("inherited_images") or []:
                if not isinstance(entry, dict):
                    continue
                if "reference_image_index" in ref and "reference_image_index" in entry:
                    if entry["reference_image_index"] == ref["reference_image_index"]:
                        inherited_image_caption_hint = entry.get("caption_hint")
                        break
                elif "doc_index" in ref and "image_index" in ref:
                    if (entry.get("doc_index") == ref["doc_index"]
                            and entry.get("image_index") == ref["image_index"]):
                        inherited_image_caption_hint = entry.get("caption_hint")
                        break

    # Only expose slots the rewriter should actually mention in the query —
    # failed slots are hidden so the rewriter describes a text-first layout.
    # Each slot carries its real pixel dimensions PLUS the upstream textual
    # context (intent from outline + image_prompt that produced it) so the
    # rewriter / generator can write captions that match the image content.
    intent_by_slot: dict[str, str] = {
        s.get("slot_id"): s.get("intent") or ""
        for s in (page_outline.get("asset_slots") or [])
        if s.get("slot_id")
    }
    available_slot_images: list[dict] = []
    for slot in page_plan.get("slots") or []:
        if slot.get("status") == "failed" or not slot.get("local_path"):
            continue
        local_path = slot["local_path"]
        size = _read_image_size(deck / local_path)
        entry: dict = {
            "path": local_path,
            "slot_id": slot.get("slot_id"),
            "intent": intent_by_slot.get(slot.get("slot_id")) or "",
            "image_prompt": slot.get("image_prompt") or "",
            "search_query": slot.get("search_query") or "",
            "asset_source": slot.get("asset_source") or "image_generation",
            "source_title": slot.get("source_title") or "",
            "source_page": slot.get("source_page") or "",
        }
        if size:
            entry.update(size)  # adds w / h / aspect
        available_slot_images.append(entry)

    # --- Step 1: rewrite structured data → natural-language user prompt ---
    rewrite_system = _load_prompt("page_html_rewrite.md")
    rewrite_user_payload = {
        "style_spec": style,
        "page_outline": page_outline,
        "page_no": page_no,
        "inherited_table": inherited_table,
        "inherited_image_local_path": (inherited_image or {}).get("local_path"),
        "inherited_image_size": inherited_image_size,
        "inherited_image_alt": (inherited_image or {}).get("alt") or None,
        "inherited_image_caption_hint": inherited_image_caption_hint,
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

    # Persist the rewritten query for debugging / manual re-run.
    query_path = deck / "pages" / f"page_{page_no:03d}.query.txt"
    _write_text(query_path, rewritten_query)

    # --- Step 2: generate HTML from the rewritten query ---
    gen_system = _load_prompt("page_html.md")

    out_path = deck / "pages" / f"page_{page_no:03d}.html"
    extra_paths: list[str] = []
    if inherited_image and inherited_image.get("local_path"):
        extra_paths.append(inherited_image["local_path"])

    max_attempts = max(1, _env_int("PPT_PAGE_HTML_MAX_ATTEMPTS", 3))
    generation_query = rewritten_query
    last_html = ""
    last_fixed = 0
    last_issues: list[str] = []

    for attempt in range(1, max_attempts + 1):
        try:
            html = llm(gen_system, generation_query)
        except ModelClientError as e:
            return _fail(f"page-html p{page_no}: {e}", page_no=page_no, attempt=attempt)

        html = _strip_code_fences(html) if html.lstrip().startswith("```") else html

        # Defensive: rewrite any malformed <img src> paths back to the canonical
        # relative form. The rewriter + generator usually get this right, but
        # models still occasionally emit absolute paths / leading slashes.
        html, fixed = _normalize_img_srcs(html, page_plan, extra_paths=extra_paths)
        last_html = html
        last_fixed = fixed

        issues = _html_contract_issues(html)
        if not issues:
            _write_text(out_path, html)
            issues = _browser_layout_issues(out_path)

        if not issues:
            return _ok(
                page_no=page_no,
                path=str(out_path.relative_to(deck)),
                query_path=str(query_path.relative_to(deck)),
                img_srcs_fixed=fixed,
                attempts=attempt,
                layout_qc="passed",
            )

        last_issues = issues
        if attempt < max_attempts:
            generation_query = _page_html_retry_query(rewritten_query, issues)

    _write_text(out_path, last_html)
    issues_path = deck / "pages" / f"page_{page_no:03d}.layout_issues.json"
    _write_text(
        issues_path,
        json.dumps({"page_no": page_no, "issues": last_issues}, ensure_ascii=False, indent=2),
    )
    return _fail(
        f"page-html p{page_no}: layout validation failed after {max_attempts} attempts: "
        + "; ".join(last_issues[:3]),
        page_no=page_no,
        path=str(out_path.relative_to(deck)),
        query_path=str(query_path.relative_to(deck)),
        issues_path=str(issues_path.relative_to(deck)),
        img_srcs_fixed=last_fixed,
    )


def _dedupe_issues(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        text = str(item).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def _review_page_numbers(deck: Path) -> list[int]:
    outline_path = deck / "outline.json"
    if outline_path.exists():
        try:
            outline = _load_json(outline_path)
            nums = sorted(
                int(p.get("page_no", 0))
                for p in outline.get("pages", [])
                if int(p.get("page_no", 0)) > 0
            )
            if nums:
                return nums
        except Exception:
            pass

    tp_path = deck / "task_pack.json"
    if tp_path.exists():
        try:
            tp = _load_json(tp_path)
            n = int(tp.get("params", {}).get("page_count", 0))
            if n > 0:
                return list(range(1, n + 1))
        except Exception:
            pass

    pages_dir = deck / "pages"
    nums: list[int] = []
    for hp in sorted(pages_dir.glob("page_*.html")) if pages_dir.exists() else []:
        if hp.name.endswith(".refined.html") or hp.name.endswith(".review_candidate.html"):
            continue
        try:
            nums.append(int(hp.stem.split("_")[1]))
        except (IndexError, ValueError):
            continue
    return sorted(set(nums))


def _load_page_outline(deck: Path, page_no: int) -> dict:
    try:
        outline = _load_json(deck / "outline.json")
    except Exception:
        return {}
    for page in outline.get("pages", []):
        try:
            if int(page.get("page_no", -1)) == page_no:
                return page
        except (TypeError, ValueError):
            continue
    return {}


def _load_page_plan(deck: Path, page_no: int) -> dict:
    try:
        plan = _load_json(deck / "asset_plan.json")
    except Exception:
        return {"page_no": page_no, "slots": []}
    for page in plan.get("pages", []):
        try:
            if int(page.get("page_no", -1)) == page_no:
                return page
        except (TypeError, ValueError):
            continue
    return {"page_no": page_no, "slots": []}


def _review_html_issues(html_path: Path) -> list[str]:
    try:
        html = html_path.read_text(encoding="utf-8")
    except OSError as e:
        return [f"could not read HTML: {e}"]
    issues = _html_contract_issues(html)
    if not issues:
        issues.extend(_browser_layout_issues(html_path))
    return _dedupe_issues(issues)


def _parse_review_verdict(review: str) -> str:
    first = (review or "").strip().splitlines()[0].strip() if (review or "").strip() else ""
    if first == "VERDICT: CLEAN":
        return "clean"
    if first == "VERDICT: NEEDS_REWRITE":
        return "needs_rewrite"
    if first == "VERDICT: FIXED":
        return "fixed"
    if first == "VERDICT: MISSING":
        return "missing"
    return "unknown"


def _format_review_markdown(
    page_no: int,
    *,
    title: str,
    mechanical_issues: list[str],
    model_review: str | None = None,
    fixed: bool = False,
    warnings: list[str] | None = None,
) -> str:
    if fixed:
        first = "VERDICT: FIXED"
    elif mechanical_issues:
        first = "VERDICT: NEEDS_REWRITE"
    elif model_review and _parse_review_verdict(model_review) == "needs_rewrite":
        first = "VERDICT: NEEDS_REWRITE"
    else:
        first = "VERDICT: CLEAN"

    lines = [first, ""]
    lines.append(f"Page: page_{page_no:03d}" + (f" — {title}" if title else ""))
    if mechanical_issues:
        lines.append("")
        lines.append("Mechanical issues:")
        lines.extend(f"- {issue}" for issue in mechanical_issues)
    if model_review:
        lines.append("")
        lines.append("Model review:")
        lines.append(model_review.strip())
    if fixed:
        lines.append("")
        lines.append("Automated review rewrite was applied and passed mechanical validation.")
    if warnings:
        lines.append("")
        lines.append("Warnings:")
        lines.extend(f"- {w}" for w in warnings)
    if len(lines) == 3:
        lines.extend(["", "No mechanical layout issues detected."])
    return "\n".join(lines).rstrip() + "\n"


def _run_model_page_review(
    deck: Path,
    page_no: int,
    html_source: str,
    mechanical_issues: list[str],
) -> tuple[str | None, str | None]:
    """Return (review_markdown, warning). Model review is best-effort."""
    try:
        style = _load_json(deck / "style_spec.json")
    except Exception:
        style = {}
    payload = {
        "style_spec": style,
        "page_outline": _load_page_outline(deck, page_no),
        "mechanical_issues": mechanical_issues,
        "html_source": html_source,
    }
    try:
        review = llm(
            _load_prompt("page_review.md"),
            json.dumps(payload, ensure_ascii=False, indent=2),
            request_name=f"page_review_{page_no:03d}",
        )
    except ModelClientError as e:
        return None, f"model page review failed: {e}"
    review = (review or "").strip()
    verdict = _parse_review_verdict(review)
    if verdict not in {"clean", "needs_rewrite"}:
        return review or None, "model page review returned an invalid verdict"
    return review, None


def _rewrite_reviewed_page(
    deck: Path,
    page_no: int,
    review_markdown: str,
    html_source: str,
) -> tuple[bool, list[str], str | None]:
    """Try to rewrite page_NNN.html from review findings.

    Returns (applied, remaining_issues, warning). The candidate is only adopted
    if it passes static + browser mechanical validation.
    """
    html_path = deck / "pages" / f"page_{page_no:03d}.html"
    page_plan = _load_page_plan(deck, page_no)
    extra_paths = [
        str(p.relative_to(deck))
        for p in sorted((deck / "images").glob(f"page_{page_no:03d}_inherited.*"))
        if p.is_file()
    ]
    user_payload = {
        "page_no": page_no,
        "review_markdown": review_markdown,
        "html_source": html_source,
    }
    try:
        rewritten = llm(
            _load_prompt("page_rewrite.md"),
            json.dumps(user_payload, ensure_ascii=False, indent=2),
            request_name=f"page_rewrite_{page_no:03d}",
        )
    except ModelClientError as e:
        return False, [], f"model page rewrite failed: {e}"

    rewritten = _strip_code_fences(rewritten) if rewritten.lstrip().startswith("```") else rewritten
    rewritten = rewritten.strip()
    if not rewritten or "<html" not in rewritten.lower() or "</html>" not in rewritten.lower():
        return False, [], "model page rewrite returned non-HTML"

    rewritten, _ = _normalize_img_srcs(rewritten, page_plan, extra_paths=extra_paths)
    candidate_path = deck / "pages" / f"page_{page_no:03d}.review_candidate.html"
    _write_text(candidate_path, rewritten)
    remaining = _review_html_issues(candidate_path)
    if remaining:
        _write_text(
            deck / "pages" / f"page_{page_no:03d}.review_candidate_issues.json",
            json.dumps({"page_no": page_no, "issues": remaining}, ensure_ascii=False, indent=2),
        )
        return False, remaining, "model page rewrite candidate did not pass mechanical validation"

    backup_path = deck / "pages" / f"page_{page_no:03d}.before_review.html"
    if not backup_path.exists():
        try:
            backup_path.write_text(html_source, encoding="utf-8")
        except OSError:
            pass
    _write_text(html_path, rewritten)
    return True, [], None


def _review_page_payload(deck: Path, page_no: int) -> dict:
    """Review one generated HTML page and optionally rewrite it.

    Default is deterministic mechanical review only. Enable model review and
    rewrite with `PPT_REVIEW_USE_LLM=1`; `PPT_REVIEW_FIX=1` adopts a validated
    rewrite candidate when the review finds issues.
    """
    html_path = deck / "pages" / f"page_{page_no:03d}.html"
    review_path = deck / "pages" / f"page_{page_no:03d}.review.md"
    if not html_path.exists():
        review = f"VERDICT: MISSING\n\nPage: page_{page_no:03d}\n\n- page HTML file is missing.\n"
        _write_text(review_path, review)
        return {
            "status": "ok",
            "page_no": page_no,
            "verdict": "missing",
            "needs_attention": True,
            "review_path": str(review_path.relative_to(deck)),
        }

    html_source = html_path.read_text(encoding="utf-8")
    page_outline = _load_page_outline(deck, page_no)
    title = str(page_outline.get("title") or "")
    mechanical_issues = _review_html_issues(html_path)
    warnings: list[str] = []
    model_review: str | None = None

    use_llm = _env_bool("PPT_REVIEW_USE_LLM", False)
    fix_enabled = _env_bool("PPT_REVIEW_FIX", use_llm)
    if use_llm:
        model_review, warning = _run_model_page_review(deck, page_no, html_source, mechanical_issues)
        if warning:
            warnings.append(warning)

    review = _format_review_markdown(
        page_no,
        title=title,
        mechanical_issues=mechanical_issues,
        model_review=model_review,
        warnings=warnings,
    )
    verdict = _parse_review_verdict(review)
    fixed = False
    remaining_after_fix: list[str] = []

    if fix_enabled and verdict == "needs_rewrite":
        applied, remaining_after_fix, warning = _rewrite_reviewed_page(
            deck, page_no, review, html_source
        )
        if warning:
            warnings.append(warning)
        if applied:
            fixed = True
            mechanical_issues = []
            verdict = "fixed"
            review = _format_review_markdown(
                page_no,
                title=title,
                mechanical_issues=[],
                model_review=model_review,
                fixed=True,
                warnings=warnings,
            )

    if remaining_after_fix:
        mechanical_issues = remaining_after_fix
        verdict = "needs_rewrite"
        review = _format_review_markdown(
            page_no,
            title=title,
            mechanical_issues=mechanical_issues,
            model_review=model_review,
            warnings=warnings,
        )

    _write_text(review_path, review)
    return {
        "status": "ok",
        "page_no": page_no,
        "verdict": verdict,
        "needs_attention": verdict in {"missing", "needs_rewrite", "unknown"},
        "fixed": fixed,
        "mechanical_issues": len(mechanical_issues),
        "warnings": warnings or None,
        "review_path": str(review_path.relative_to(deck)),
    }


def cmd_review_page(deck: Path, page_no: int) -> int:
    payload = _review_page_payload(deck, page_no)
    print(json.dumps(payload, ensure_ascii=False))
    return 0


def _write_deck_review(deck: Path, page_payloads: list[dict], *, strict: bool) -> tuple[Path, Path]:
    total = len(page_payloads)
    clean = sum(1 for p in page_payloads if p.get("verdict") == "clean")
    fixed = sum(1 for p in page_payloads if p.get("fixed"))
    needs = [p for p in page_payloads if p.get("needs_attention")]

    report = {
        "status": "needs_attention" if needs else "clean",
        "strict": strict,
        "total_pages": total,
        "clean_pages": clean,
        "fixed_pages": fixed,
        "needs_attention_pages": len(needs),
        "pages": page_payloads,
    }
    json_path = deck / "review.json"
    md_path = deck / "review.md"
    _write_text(json_path, json.dumps(report, ensure_ascii=False, indent=2))

    lines = [
        "# Review",
        "",
        "## Summary",
        "",
        f"- Total pages reviewed: {total}",
        f"- Clean pages: {clean}",
        f"- Fixed during review: {fixed}",
        f"- Pages needing attention: {len(needs)}",
        "",
        "## Pages",
        "",
    ]
    for p in page_payloads:
        try:
            pno = int(p.get("page_no", 0) or 0)
        except (TypeError, ValueError):
            pno = 0
        verdict = p.get("verdict", "unknown")
        suffix = " (fixed)" if p.get("fixed") else ""
        warnings = p.get("warnings") or []
        warn_text = f"; warnings: {len(warnings)}" if warnings else ""
        lines.append(f"- page_{pno:03d}: {verdict}{suffix}{warn_text}")

    if needs:
        lines.extend(["", "## Attention Required", ""])
        for p in needs:
            try:
                pno = int(p.get("page_no", 0) or 0)
            except (TypeError, ValueError):
                pno = 0
            lines.append(f"- page_{pno:03d}: see `{p.get('review_path', '')}`")

    lines.extend(["", "## Per-Page Review Files", ""])
    for p in page_payloads:
        if p.get("review_path"):
            lines.append(f"- `{p['review_path']}`")

    _write_text(md_path, "\n".join(lines).rstrip() + "\n")
    return md_path, json_path


def cmd_review(deck: Path, concurrency: int) -> int:
    page_nos = _review_page_numbers(deck)
    if not page_nos:
        return _fail("review: no pages found to review")
    page_payloads: list[dict] = []
    concurrency = max(1, min(int(concurrency), 16))
    with ThreadPoolExecutor(max_workers=concurrency) as ex:
        future_to_page = {
            ex.submit(_review_page_payload, deck, pno): pno
            for pno in page_nos
        }
        for fut in as_completed(future_to_page):
            pno = future_to_page[fut]
            try:
                payload = fut.result()
            except Exception as e:  # noqa: BLE001
                payload = {
                    "status": "failed",
                    "page_no": pno,
                    "verdict": "failed",
                    "needs_attention": True,
                    "error": f"{type(e).__name__}: {e}"[:300],
                }
            page_payloads.append(payload)
            _progress(f"[p{pno:03d}/review] {payload.get('verdict', payload.get('status', 'unknown'))}")

    def _payload_page_no(payload: dict) -> int:
        try:
            return int(payload.get("page_no", 0) or 0)
        except (TypeError, ValueError):
            return 0

    page_payloads.sort(key=_payload_page_no)
    strict = _env_bool("PPT_REVIEW_STRICT", True)
    md_path, json_path = _write_deck_review(deck, page_payloads, strict=strict)
    needs = [p for p in page_payloads if p.get("needs_attention")]
    if strict and needs:
        return _fail(
            f"review: {len(needs)} page(s) need attention",
            stage="review",
            pages=len(page_payloads),
            needs_attention=len(needs),
            review_md=str(md_path.relative_to(deck)),
            review_json=str(json_path.relative_to(deck)),
        )
    return _ok(
        stage="review",
        pages=len(page_payloads),
        needs_attention=len(needs),
        review_md=str(md_path.relative_to(deck)),
        review_json=str(json_path.relative_to(deck)),
    )


def cmd_export(deck: Path) -> int:
    converter = SKILL_DIR / "scripts" / "export_pptx" / "html_to_pptx.mjs"
    if not converter.exists():
        return _fail("export_pptx/html_to_pptx.mjs missing — run npm install in scripts/export_pptx")
    if not (deck / "review.md").exists() and not (deck / "review.json").exists():
        _write_text(deck / "review.md", "# Review\n\nAuto-generated review stub for PPTX export.\n")
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
# Refine pipeline (screenshot → critique → apply revisions)
# ---------------------------------------------------------------------------
#
# Standalone, NOT wired into the main pipeline. Invoke via the `refine-page`
# subcommand on a page whose HTML already exists. Three steps:
#
#   1. Screenshot the rendered HTML at 1600×900 via export_pptx/screenshot.mjs.
#   2. Send (image + HTML source) to a VLM with the `refine_review.md` system
#      prompt → produces a numbered Chinese critique list. Saved to
#      `pages/page_NNN.review.md`.
#   3. Send (HTML + critique) to an LLM with the `refine_apply.md` system
#      prompt → produces a refined HTML. Saved as `pages/page_NNN.refined.html`
#      so it's easy to diff against the original.
#
# The original `page_NNN.html` is preserved untouched; nothing in the export
# pipeline picks up the .refined.html automatically. To adopt the refined
# version, manually overwrite `page_NNN.html` with `page_NNN.refined.html`.

_SCREENSHOT_MJS = SKILL_DIR / "scripts" / "export_pptx" / "screenshot.mjs"


def _screenshot_page(deck: Path, page_no: int, *, viewport: str = "1600x900") -> Path | None:
    """Render `pages/page_NNN.html` to `screenshots/page_NNN.png` via the
    co-located screenshot.mjs (Playwright + chromium).

    Returns the screenshot path on success, None on failure (caller decides
    whether to error out). screenshot.mjs is element-aware — it captures the
    first matching `.wrapper` / `.slide.canvas` / `.slide` / body element by
    boundingBox, so even if the rendered slide is smaller than the viewport,
    the PNG is cropped to the slide canvas.
    """
    import subprocess
    if not _SCREENSHOT_MJS.exists():
        return None
    html_path = deck / "pages" / f"page_{page_no:03d}.html"
    if not html_path.exists():
        return None
    out_path = deck / "screenshots" / f"page_{page_no:03d}.png"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        proc = subprocess.run(
            ["node", str(_SCREENSHOT_MJS),
             "--html", str(html_path),
             "--out", str(out_path),
             "--viewport", viewport,
             "--wait", "800"],  # extra slack for ECharts setOption
            capture_output=True, text=True, timeout=60,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0 or not out_path.exists() or out_path.stat().st_size == 0:
        return None
    return out_path


def cmd_refine_page(deck: Path, page_no: int) -> int:
    """Three-step page refinement (screenshot → VLM critique → LLM apply).

    Outputs (per page):
      - `screenshots/page_NNN.png`  (rendered slide image)
      - `pages/page_NNN.review.md`  (numbered Chinese critique list)
      - `pages/page_NNN.refined.html`  (refined HTML, kept side-by-side with
        the original — does NOT overwrite `page_NNN.html`)
    """
    html_path = deck / "pages" / f"page_{page_no:03d}.html"
    if not html_path.exists():
        return _fail(f"page_{page_no:03d}.html missing", page_no=page_no)

    # --- Step 1: screenshot ---
    screenshot = _screenshot_page(deck, page_no)
    if screenshot is None:
        return _fail(f"refine p{page_no}: screenshot failed", page_no=page_no)

    html_source = html_path.read_text(encoding="utf-8")

    # --- Step 2: visual critique (VLM) ---
    # User-message format mirrors the training-data sample:
    #   "<image>\n请根据这页 PPT 的真实渲染图和下方 HTML 初稿..."
    # The literal "<image>" token is a placeholder; the real image goes via
    # the `images=` kwarg as an OpenAI image_url part.
    review_system = _load_prompt("refine_review.md")
    review_user = (
        "<image>\n"
        "请根据这页 PPT 的真实渲染图和下方 HTML 初稿，给出视觉审稿意见。"
        "请只输出 3 到 6 条中文编号列表，每条一句话，"
        "直接包含问题判断和修改建议，不要输出 JSON、标题、解释或额外说明。\n\n"
        "HTML 初稿如下：\n"
        "<draft_html>\n"
        f"{html_source}\n"
        "</draft_html>"
    )
    try:
        review = vlm(review_system, review_user, images=[screenshot])
    except ModelClientError as e:
        return _fail(f"refine p{page_no} review: {e}", page_no=page_no)
    review = (review or "").strip()
    if not review:
        return _fail(f"refine p{page_no}: empty review output", page_no=page_no)

    review_path = deck / "pages" / f"page_{page_no:03d}.review.md"
    _write_text(review_path, review)

    # --- Step 3: apply revisions (LLM) ---
    apply_system = _load_prompt("refine_apply.md")
    apply_user = (
        "下方是当前 HTML 初稿和审稿意见。请按审稿意见修改 HTML，"
        "只输出修改后的完整 HTML 文档。\n\n"
        "<draft_html>\n"
        f"{html_source}\n"
        "</draft_html>\n\n"
        "审稿意见：\n"
        f"{review}"
    )
    try:
        refined = llm(apply_system, apply_user)
    except ModelClientError as e:
        return _fail(f"refine p{page_no} apply: {e}", page_no=page_no)

    refined = _strip_code_fences(refined) if refined.lstrip().startswith("```") else refined
    refined = refined.strip()
    if not refined or "<html" not in refined.lower() or "</html>" not in refined.lower():
        return _fail(
            f"refine p{page_no}: model returned non-HTML; review still saved",
            page_no=page_no, review_path=str(review_path.relative_to(deck)),
        )

    refined_path = deck / "pages" / f"page_{page_no:03d}.refined.html"
    _write_text(refined_path, refined)

    return _ok(
        page_no=page_no,
        screenshot=str(screenshot.relative_to(deck)),
        review_path=str(review_path.relative_to(deck)),
        refined_path=str(refined_path.relative_to(deck)),
        review_chars=len(review),
        refined_chars=len(refined),
    )


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


def cmd_batch_refine_page(deck: Path, concurrency: int) -> int:
    """Fan out the standalone `refine-page` workflow over every page that has
    a built HTML file. Each per-page task does its own screenshot → VLM
    critique → LLM apply, three calls in series per worker. Workers run in
    parallel up to `concurrency`.

    Like `refine-page`, this NEVER overwrites `page_NNN.html` — only emits
    `page_NNN.review.md` + `page_NNN.refined.html` side-by-side, so the agent
    can A/B compare before adopting.
    """
    pages_dir = deck / "pages"
    if not pages_dir.exists():
        return _fail("pages/ missing")
    tasks: list[tuple] = []
    for hp in sorted(pages_dir.glob("page_*.html")):
        # Skip ".refined.html" outputs from prior runs.
        if hp.name.endswith(".refined.html"):
            continue
        try:
            pno = int(hp.stem.split("_")[1])
        except (IndexError, ValueError):
            continue
        tasks.append((cmd_refine_page, (deck, pno), {}, f"p{pno:03d}/refine"))
    if not tasks:
        return _fail("no page_*.html files to refine")
    results = _run_concurrent(tasks, concurrency)
    ok = sum(1 for r in results if r["exit_code"] == 0)
    failed = [
        {"label": r["label"], "error": r["payload"].get("error", "")}
        for r in results if r["exit_code"] != 0
    ]
    return _ok(
        stage="refine-page",
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

    sp = sub.add_parser("review-page")
    sp.add_argument("--deck-dir", type=Path, required=True)
    sp.add_argument("--page", type=int, required=True)

    sp = sub.add_parser("review")
    sp.add_argument("--deck-dir", type=Path, required=True)
    sp.add_argument("--concurrency", type=int, default=4,
                    help="max parallel workers (default 4, clamped to 1-16)")

    # `refine-page` is a STANDALONE per-page tool: screenshot → VLM critique →
    # LLM apply. NOT wired into the main pipeline; the agent only runs it on
    # demand. Outputs page_NNN.review.md + page_NNN.refined.html (alongside
    # the original page_NNN.html, which is preserved untouched).
    sp = sub.add_parser("refine-page")
    sp.add_argument("--deck-dir", type=Path, required=True)
    sp.add_argument("--page", type=int, required=True)

    # Batch / concurrent variants (default concurrency=4). Each fans out its
    # per-item work across a thread pool so LLM / VLM / T2I wait times overlap.
    for name in ("batch-gen-image", "batch-page-html", "batch-refine-page"):
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
    if args.cmd == "review-page":
        return cmd_review_page(deck, args.page)
    if args.cmd == "review":
        return cmd_review(deck, args.concurrency)
    if args.cmd == "refine-page":
        return cmd_refine_page(deck, args.page)
    if args.cmd == "export":
        return cmd_export(deck)
    if args.cmd == "batch-gen-image":
        return cmd_batch_gen_image(deck, args.concurrency)
    if args.cmd == "batch-page-html":
        return cmd_batch_page_html(deck, args.concurrency)
    if args.cmd == "batch-refine-page":
        return cmd_batch_refine_page(deck, args.concurrency)
    return _fail(f"unknown command {args.cmd!r}")


if __name__ == "__main__":
    sys.exit(main())
