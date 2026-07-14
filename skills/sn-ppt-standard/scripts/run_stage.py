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
import subprocess
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


def _configure_stdio_encoding() -> None:
    """Keep JSON/stdout stable when Windows uses a non-UTF-8 system codepage."""
    for stream in (sys.stdout, sys.stderr):
        if not hasattr(stream, "reconfigure"):
            continue
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


_configure_stdio_encoding()


def _ok(**kw) -> int:
    print(json.dumps({"status": "ok", **kw}, ensure_ascii=False))
    return 0


def _fail(msg: str, **kw) -> int:
    print(json.dumps({"status": "failed", "error": msg, **kw}, ensure_ascii=False))
    return 1


def _background_process_kwargs() -> dict[str, int]:
    if os.name != "nt":
        return {}
    return {"creationflags": subprocess.CREATE_NO_WINDOW}


def _subprocess_env() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("PYTHONUTF8", "1")
    return env


def _run_text_subprocess(
    cmd: list[str],
    *,
    timeout: float | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        env=_subprocess_env(),
        **_background_process_kwargs(),
    )


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


def _resolve_language(tp: dict, ip: dict) -> str:
    """Resolve the target language from params.language set by the entry-skill LLM.
    Falls back to 'zh-Hans' when not explicitly set."""
    lang = tp.get("params", {}).get("language", "").strip()
    if lang in ("zh-Hans", "zh-Hant", "en"):
        return lang
    if lang == "zh":
        return "zh-Hans"
    query = ip.get("user_query") or ""
    if query and all(ord(ch) < 128 for ch in query):
        return "en"
    return "zh-Hans"


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


def _normalize_style_sample(sample: dict, index: int, dims: dict | None) -> tuple[dict, list[str]]:
    sample_ids = ("A", "B", "C")
    sample_id = sample_ids[index] if index < len(sample_ids) else chr(ord("A") + index)
    if not isinstance(sample, dict):
        sample = {}
    style_spec = sample.get("style_spec")
    if not isinstance(style_spec, dict):
        style_spec = {}
    repair_notes: list[str] = []
    if dims is not None:
        style_spec, repair_notes = _repair_style_triple(style_spec, dims)
    if repair_notes:
        style_spec["_repairs"] = repair_notes
    return {
        "sample_id": sample_id,
        "label": str(sample.get("label") or f"Style {sample_id}"),
        "rationale": str(sample.get("rationale") or ""),
        "style_spec": style_spec,
    }, repair_notes


def _preview_text_context(tp: dict, ip: dict) -> dict:
    qn = ip.get("query_normalized") if isinstance(ip.get("query_normalized"), dict) else {}
    params = tp.get("params") if isinstance(tp.get("params"), dict) else {}
    topic = qn.get("topic") or ip.get("user_query") or tp.get("deck_id") or "Presentation"
    key_points = qn.get("key_points") if isinstance(qn.get("key_points"), list) else []
    if not key_points:
        digest = ip.get("document_digest") if isinstance(ip.get("document_digest"), dict) else {}
        key_points = digest.get("key_points") if isinstance(digest.get("key_points"), list) else []
    key_points = [str(p) for p in key_points[:3] if p]
    if len(key_points) < 3:
        defaults = ["Core message", "Evidence and implications", "Recommended next steps"]
        key_points.extend(defaults[len(key_points):3])
    return {
        "topic": str(topic),
        "points": key_points[:3],
        "audience": str(params.get("audience") or "Audience"),
        "scene": str(params.get("scene") or "Presentation scenario"),
        "role": str(params.get("role") or "Presenter"),
        "output_format": str(params.get("output_format") or "pptx").upper(),
    }


def _wrap_svg_text(text: str, width: int) -> list[str]:
    text = " ".join(str(text).split())
    if not text:
        return []
    if any(ord(ch) > 127 for ch in text):
        return [text[i:i + width] for i in range(0, len(text), width)]
    words = text.split(" ")
    lines: list[str] = []
    cur = ""
    for word in words:
        candidate = word if not cur else f"{cur} {word}"
        if len(candidate) <= width:
            cur = candidate
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def _svg_text_block(text: str, x: int, y: int, *, width: int, size: int,
                    fill: str, weight: str = "400", max_lines: int = 3) -> str:
    import html
    lines = _wrap_svg_text(text, width)[:max_lines]
    spans = []
    for i, line in enumerate(lines):
        dy = 0 if i == 0 else int(size * 1.25)
        spans.append(f'<tspan x="{x}" dy="{dy}">{html.escape(line)}</tspan>')
    if not spans:
        return ""
    return (
        f'<text x="{x}" y="{y}" fill="{html.escape(fill)}" '
        f'font-size="{size}" font-weight="{html.escape(weight)}" '
        f'font-family="Inter, Arial, sans-serif">{"".join(spans)}</text>'
    )


def _style_preview_palette(sample: dict) -> dict:
    spec = sample.get("style_spec") if isinstance(sample.get("style_spec"), dict) else {}
    palette = spec.get("palette") if isinstance(spec.get("palette"), dict) else {}
    primary_color = spec.get("primary_color") if isinstance(spec.get("primary_color"), dict) else {}
    return {
        "primary": str(palette.get("primary") or primary_color.get("hex") or "#2D5BFF").upper(),
        "accent": str(palette.get("accent") or "#FFB000").upper(),
        "neutral": str(palette.get("neutral") or "#F6F7FB").upper(),
        "ink": "#F8FAFC",
        "muted": "#D8DEE9",
        "surface": "#111827",
    }


def _render_sample_deck_svg(sample: dict, ctx: dict) -> str:
    import html
    sample_id = html.escape(str(sample.get("sample_id") or "A"))
    label = html.escape(str(sample.get("label") or sample_id))
    spec = sample.get("style_spec") if isinstance(sample.get("style_spec"), dict) else {}
    design = spec.get("design_style") if isinstance(spec.get("design_style"), dict) else {}
    tone = spec.get("color_tone") if isinstance(spec.get("color_tone"), dict) else {}
    colors = _style_preview_palette(sample)
    w, h, gap = 1280, 720, 34
    total_h = h * 3 + gap * 2

    def esc(value: object) -> str:
        return html.escape(str(value))

    def slide_bg(y: int, idx: int) -> str:
        return f"""
        <g transform="translate(0,{y})">
          <rect width="{w}" height="{h}" fill="{esc(colors['surface'])}"/>
          <rect width="{w}" height="{h}" fill="url(#grad{sample_id}{idx})"/>
          <polygon points="{w - 430},0 {w},0 {w},{h} {w - 220},{h}" fill="{esc(colors['primary'])}" opacity="0.26"/>
          <polygon points="0,{h - 210} 390,{h} 0,{h}" fill="{esc(colors['accent'])}" opacity="0.34"/>
          <rect x="72" y="62" width="136" height="40" rx="20" fill="#FFFFFF" fill-opacity="0.16" stroke="#FFFFFF" stroke-opacity="0.25"/>
          <text x="100" y="88" fill="{esc(colors['ink'])}" font-size="22" font-weight="700" font-family="Inter, Arial, sans-serif">{sample_id}</text>
        """

    title = _svg_text_block(ctx["topic"], 92, 260, width=34, size=58, fill=colors["ink"], weight="800", max_lines=2)
    subtitle = _svg_text_block(label, 96, 355, width=44, size=26, fill=colors["muted"], weight="500", max_lines=2)
    style_meta = (
        esc(design.get("name_zh") or design.get("name_en") or "")
        + " / "
        + esc(tone.get("name_zh") or tone.get("name_en") or "")
    )

    bullets = []
    for i, point in enumerate(ctx["points"], start=1):
        y = 210 + (i - 1) * 118
        bullets.append(f'<circle cx="118" cy="{y - 7}" r="24" fill="{esc(colors["accent"])}" opacity="0.9"/>')
        bullets.append(f'<text x="110" y="{y + 2}" fill="{esc(colors["surface"])}" font-size="22" font-weight="800" font-family="Inter, Arial, sans-serif">{i}</text>')
        bullets.append(_svg_text_block(point, 168, y, width=58, size=32, fill=colors["ink"], weight="650", max_lines=2))

    chips = [
        ("Role", ctx["role"]),
        ("Audience", ctx["audience"]),
        ("Scene", ctx["scene"]),
        ("Format", ctx["output_format"]),
    ]
    chip_parts = []
    for i, (key, value) in enumerate(chips):
        x = 96 + (i % 2) * 520
        y = 220 + (i // 2) * 155
        chip_parts.append(f'<rect x="{x}" y="{y}" width="430" height="92" rx="16" fill="#FFFFFF" fill-opacity="0.13" stroke="#FFFFFF" stroke-opacity="0.20"/>')
        chip_parts.append(f'<text x="{x + 28}" y="{y + 36}" fill="{esc(colors["accent"])}" font-size="20" font-weight="800" font-family="Inter, Arial, sans-serif">{esc(key)}</text>')
        chip_parts.append(_svg_text_block(value, x + 28, y + 70, width=26, size=27, fill=colors["ink"], weight="650", max_lines=1))

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{total_h}" viewBox="0 0 {w} {total_h}">
  <defs>
    <linearGradient id="grad{sample_id}1" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="{esc(colors['primary'])}" stop-opacity="0.92"/>
      <stop offset="100%" stop-color="{esc(colors['surface'])}" stop-opacity="1"/>
    </linearGradient>
    <linearGradient id="grad{sample_id}2" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="{esc(colors['surface'])}" stop-opacity="1"/>
      <stop offset="100%" stop-color="{esc(colors['primary'])}" stop-opacity="0.65"/>
    </linearGradient>
    <linearGradient id="grad{sample_id}3" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="{esc(colors['primary'])}" stop-opacity="0.72"/>
      <stop offset="100%" stop-color="{esc(colors['surface'])}" stop-opacity="1"/>
    </linearGradient>
  </defs>
  {slide_bg(0, 1)}
    <text x="96" y="156" fill="{esc(colors['accent'])}" font-size="24" font-weight="800" font-family="Inter, Arial, sans-serif">STYLE SAMPLE {sample_id}</text>
    {title}
    {subtitle}
    <text x="96" y="614" fill="{esc(colors['muted'])}" font-size="22" font-family="Inter, Arial, sans-serif">{style_meta}</text>
  </g>
  {slide_bg(h + gap, 2)}
    <text x="96" y="150" fill="{esc(colors['accent'])}" font-size="28" font-weight="800" font-family="Inter, Arial, sans-serif">Key messages</text>
    {"".join(bullets)}
  </g>
  {slide_bg((h + gap) * 2, 3)}
    <text x="96" y="150" fill="{esc(colors['accent'])}" font-size="28" font-weight="800" font-family="Inter, Arial, sans-serif">Delivery direction</text>
    {"".join(chip_parts)}
    <text x="96" y="614" fill="{esc(colors['muted'])}" font-size="24" font-family="Inter, Arial, sans-serif">{esc(sample.get("rationale") or "")}</text>
  </g>
</svg>
"""


def _render_style_samples_html(deck: Path, samples: list[dict], tp: dict, ip: dict) -> dict:
    import html

    def as_dict(value) -> dict:
        return value if isinstance(value, dict) else {}

    ctx = _preview_text_context(tp, ip)
    out_dir = deck / "style_samples"
    out_dir.mkdir(parents=True, exist_ok=True)
    cards: list[str] = []
    artifacts: list[dict] = []
    for sample in samples:
        spec = as_dict(sample.get("style_spec"))
        palette = as_dict(spec.get("palette"))
        primary_color = as_dict(spec.get("primary_color"))
        primary = (palette.get("primary") or primary_color.get("hex") or "#2D5BFF").upper()
        accent = (palette.get("accent") or "#FFB000").upper()
        neutral = (palette.get("neutral") or "#F6F7FB").upper()
        design = as_dict(spec.get("design_style"))
        tone = as_dict(spec.get("color_tone"))
        sample_id = sample.get("sample_id")
        svg_name = f"sample_{sample_id}_deck.svg"
        deck_name = f"sample_{sample_id}_deck.html"
        svg_path = out_dir / svg_name
        deck_path = out_dir / deck_name
        _write_text(svg_path, _render_sample_deck_svg(sample, ctx))
        _write_text(deck_path, f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Style Sample {html.escape(str(sample_id))}</title>
  <style>
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; background: #12151c; color: #f7f8fb; font-family: Inter, Arial, sans-serif; }}
    main {{ width: min(100vw, 1280px); margin: 0 auto; }}
    img {{ display: block; width: 100%; height: auto; }}
  </style>
</head>
<body><main><img src="{html.escape(svg_name)}" alt="Style sample {html.escape(str(sample_id))} concatenated deck"></main></body>
</html>
""")
        artifacts.append({
            "sample_id": sample_id,
            "image": str(svg_path.relative_to(deck)),
            "image_url": svg_path.resolve().as_uri(),
            "deck_html": str(deck_path.relative_to(deck)),
            "deck_url": deck_path.resolve().as_uri(),
        })
        cards.append(f"""
        <section class="sample-card" style="--primary:{html.escape(primary)};--accent:{html.escape(accent)};--neutral:{html.escape(neutral)}">
          <a class="deck-image" href="{html.escape(deck_name)}"><img src="{html.escape(svg_name)}" alt="Style sample {html.escape(str(sample_id))} concatenated deck"></a>
          <div class="sample-meta">
            <h3>{html.escape(str(sample_id))}. {html.escape(str(sample.get("label") or sample_id))}</h3>
            <div class="style-line">{html.escape(str(design.get("name_zh") or design.get("name_en") or ""))} / {html.escape(str(tone.get("name_zh") or tone.get("name_en") or ""))}</div>
            <p>{html.escape(str(sample.get("rationale") or ""))}</p>
            <div class="swatches"><i style="background:{html.escape(primary)}"></i><i style="background:{html.escape(accent)}"></i><i style="background:{html.escape(neutral)}"></i></div>
            <strong>Select {html.escape(str(sample_id))}</strong>
            <a class="open-deck" href="{html.escape(deck_name)}">Open preview deck</a>
          </div>
        </section>
        """)

    out = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Style Samples</title>
  <style>
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; padding: 28px; background: #101216; color: #f7f8fb; font-family: Inter, Arial, sans-serif; }}
    .grid {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 18px; max-width: 1440px; margin: 0 auto; }}
    .sample-card {{ background: #191d24; border: 1px solid rgba(255,255,255,.12); border-radius: 8px; overflow: hidden; box-shadow: 0 18px 42px rgba(0,0,0,.22); }}
    .deck-image {{ display: block; height: 520px; overflow: auto; background: #0b0f16; border-bottom: 1px solid rgba(255,255,255,.12); }}
    .deck-image img {{ display: block; width: 100%; height: auto; }}
    .sample-meta {{ padding: 16px 16px 18px; min-height: 172px; }}
    .sample-meta h3 {{ margin: 0 0 8px; font-size: 18px; line-height: 1.25; letter-spacing: 0; }}
    .style-line {{ color: var(--accent); font-size: 12px; line-height: 1.35; margin-bottom: 8px; }}
    .sample-meta p {{ min-height: 42px; margin: 0 0 12px; color: rgba(247,248,251,.72); font-size: 13px; line-height: 1.45; }}
    .swatches {{ display: flex; gap: 8px; margin-bottom: 12px; }}
    .swatches i {{ width: 30px; height: 18px; display: block; border-radius: 4px; border: 1px solid rgba(255,255,255,.2); }}
    strong {{ color: var(--accent); font-size: 13px; }}
    .open-deck {{ float: right; color: rgba(247,248,251,.78); font-size: 13px; text-decoration: none; }}
    @media (max-width: 980px) {{ body {{ padding: 18px; }} .grid {{ grid-template-columns: 1fr; }} }}
  </style>
</head>
<body><main class="grid">{''.join(cards)}</main></body>
</html>
"""
    out_path = out_dir / "style_samples.html"
    index_path = out_dir / "index.html"
    _write_text(out_path, out)
    _write_text(index_path, out)
    return {
        "html": out_path,
        "index": index_path,
        "url": out_path.resolve().as_uri(),
        "artifacts": artifacts,
    }


def _select_style_sample(deck: Path, sample_id: str) -> int:
    samples_path = deck / "style_samples.json"
    if not samples_path.exists():
        return _fail("style_samples.json missing; run style-samples first")
    data = _load_json(samples_path)
    wanted = sample_id.strip().upper()
    selected = None
    for sample in data.get("samples", []):
        if str(sample.get("sample_id", "")).upper() == wanted:
            selected = sample
            break
    if selected is None:
        return _fail(f"style sample {sample_id!r} not found")
    style_spec = selected.get("style_spec") or {}
    style_spec["_selected_sample"] = {
        "sample_id": selected.get("sample_id"),
        "label": selected.get("label"),
        "rationale": selected.get("rationale"),
    }
    _write_text(deck / "style_spec.json", json.dumps(style_spec, ensure_ascii=False, indent=2))
    return _ok(
        path="style_spec.json",
        sample_id=selected.get("sample_id"),
        label=selected.get("label"),
        design_style=style_spec.get("design_style"),
        color_tone=style_spec.get("color_tone"),
        primary_color=style_spec.get("primary_color"),
        palette=style_spec.get("palette"),
    )


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
    if tp.get("ppt_mode") not in {"standard", "fast"}:
        return _fail(f"ppt_mode is {tp.get('ppt_mode')!r}, expected 'standard' or 'fast'")
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


def cmd_style(deck: Path, sample_id: str | None = None) -> int:
    tp = _load_json(deck / "task_pack.json")
    if tp.get("ppt_mode") == "standard":
        selected = sample_id or tp.get("params", {}).get("style_sample")
        if selected:
            return _select_style_sample(deck, str(selected))
        if (deck / "style_samples.json").exists():
            return _fail("style sample required; pass --sample A, B, or C")
        return _fail("standard mode requires style-samples before style")
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


def cmd_style_samples(deck: Path) -> int:
    tp = _load_json(deck / "task_pack.json")
    if tp.get("ppt_mode") != "standard":
        return _fail("style-samples is only valid when ppt_mode == 'standard'")
    ip = _load_json(deck / "info_pack.json")
    system_prompt = _load_prompt("style_samples.md")
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
        return _fail(f"style-samples: {e}")

    raw_samples = data.get("samples")
    if not isinstance(raw_samples, list) or len(raw_samples) < 3:
        return _fail("style-samples: expected at least three samples")

    dims = _load_style_dimensions()
    samples: list[dict] = []
    all_repairs: list[str] = []
    used_triples: set[tuple[int | None, int | None, int | None]] = set()
    for i, sample in enumerate(raw_samples[:3]):
        normalized, repair_notes = _normalize_style_sample(sample, i, dims)
        spec = normalized.get("style_spec") or {}
        triple = (
            (spec.get("design_style") or {}).get("id"),
            (spec.get("color_tone") or {}).get("id"),
            (spec.get("primary_color") or {}).get("id"),
        )
        if triple in used_triples:
            normalized.setdefault("style_spec", {})["_duplicate_warning"] = "LLM returned a repeated style triple; review before selection."
        used_triples.add(triple)
        all_repairs.extend([f"{normalized['sample_id']}: {note}" for note in repair_notes])
        samples.append(normalized)

    result = {"samples": samples}
    if all_repairs:
        result["_repairs"] = all_repairs
    preview = _render_style_samples_html(deck, samples, tp, ip)
    result["preview"] = {
        "url": preview["url"],
        "html": str(preview["html"].relative_to(deck)),
        "index": str(preview["index"].relative_to(deck)),
        "artifacts": preview["artifacts"],
    }
    _write_text(deck / "style_samples.json", json.dumps(result, ensure_ascii=False, indent=2))
    return _ok(
        path="style_samples.json",
        preview_html=str(preview["html"].relative_to(deck)),
        preview_url=preview["url"],
        preview_images=[
            {"sample_id": a["sample_id"], "path": a["image"], "url": a["image_url"]}
            for a in preview["artifacts"]
        ],
        preview_decks=[
            {"sample_id": a["sample_id"], "path": a["deck_html"], "url": a["deck_url"]}
            for a in preview["artifacts"]
        ],
        samples=[
            {
                "sample_id": s.get("sample_id"),
                "label": s.get("label"),
                "design_style": (s.get("style_spec") or {}).get("design_style"),
                "color_tone": (s.get("style_spec") or {}).get("color_tone"),
                "primary_color": (s.get("style_spec") or {}).get("primary_color"),
            }
            for s in samples
        ],
        repairs=all_repairs or None,
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


_ALLOWED_SLOT_KINDS = {"decoration", "concept_visual", "infographic"}


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

        # Filter slots by whitelist. Missing or empty slot_kind defaults to
        # "decoration" instead of being silently dropped — a bare intent string
        # from the outline should still produce an image slot.
        filtered = []
        for slot in page.get("slots", []):
            kind = slot.get("slot_kind", "").strip()
            if not kind:
                kind = "decoration"
                slot["slot_kind"] = kind
                dropped_kinds.append(f"p{pno}/{slot.get('slot_id','?')}=<empty>→decoration")
            elif kind not in _ALLOWED_SLOT_KINDS:
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

    prompt = slot["image_prompt"]
    if slot.get("slot_kind") == "infographic":
        prompt = (
            "Infographic-style diagram with clean layout, clear labels, and professional design. "
            "Use icons, arrows, and structured data visualization where appropriate. "
            "No UI chrome, no watermarks, no garbled text.\n\n"
            f"{prompt}"
        )

    cmd = [
        sys.executable, str(runner), "sn-image-generate",
        "--prompt", prompt,
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
        proc = _run_text_subprocess(cmd, timeout=600)
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
        if slot.get("status") != "ok" or not slot.get("local_path"):
            continue
        local_path = slot["local_path"]
        image_file = deck / local_path
        if not image_file.is_file():
            continue
        size = _read_image_size(image_file)
        entry: dict = {
            "path": local_path,
            "slot_id": slot.get("slot_id"),
            "intent": intent_by_slot.get(slot.get("slot_id")) or "",
            "image_prompt": slot.get("image_prompt") or "",
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
        "language": _resolve_language(tp, ip),
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

    # Prepend an explicit language hint so the HTML generator never defaults to
    # the wrong language, even if the rewrite output is ambiguous.
    lang = _resolve_language(tp, ip)
    if lang == "zh-Hant":
        lang_hint = "Target language for all visible text: Traditional Chinese (zh-Hant). Use traditional characters (繁體中文) throughout."
    elif lang == "zh-Hans":
        lang_hint = "Target language for all visible text: Simplified Chinese (zh-Hans). Use simplified characters (简体中文) throughout."
    else:
        lang_hint = "Target language for all visible text: English (en)."
    rewritten_query = f"{lang_hint}\n\n{rewritten_query}"

    # Persist the rewritten query for debugging / manual re-run.
    query_path = deck / "pages" / f"page_{page_no:03d}.query.txt"
    _write_text(query_path, rewritten_query)

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
        query_path=str(query_path.relative_to(deck)),
        img_srcs_fixed=fixed,
    )


def _resolve_output_format(deck: Path, requested: str | None = None) -> str:
    fmt = (requested or "").strip().lower()
    if not fmt:
        try:
            tp = _load_json(deck / "task_pack.json")
            fmt = str(tp.get("params", {}).get("output_format") or "").strip().lower()
        except Exception:
            fmt = ""
    if fmt in {"pdf", "pptx"}:
        return fmt
    return "pptx"


def cmd_export(deck: Path, output_format: str | None = None) -> int:
    fmt = _resolve_output_format(deck, output_format)
    converter_name = "html_to_pdf.mjs" if fmt == "pdf" else "html_to_pptx.mjs"
    converter = SKILL_DIR / "scripts" / "export_pptx" / converter_name
    if not converter.exists():
        return _fail(f"export_pptx/{converter_name} missing — run npm install in scripts/export_pptx")
    cmd = ["node", str(converter), "--deck-dir", str(deck), "--force"]
    proc = _run_text_subprocess(cmd)
    if proc.returncode != 0:
        return _fail(f"export failed: {proc.stderr.strip()[:500]}")
    # Try to parse the converter's stdout json
    stdout = proc.stdout.strip()
    converted = pages = failed = None
    try:
        last = [l for l in stdout.splitlines() if l.strip().startswith("{")]
        if last:
            info = json.loads(last[-1])
            # Graceful skip: headless browser unavailable → not a failure
            if info.get("status") == "skipped":
                print(json.dumps({
                    "status": "skipped",
                    "stage": "export",
                    "format": fmt,
                    "reason": info.get("reason"),
                    "detail": info.get("detail"),
                }, ensure_ascii=False))
                return 0
            converted = info.get("converted")
            pages = info.get("pages")
            failed = info.get("failed")
    except Exception:
        pass
    return _ok(format=fmt, pages=pages, converted=converted, failed=failed)


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
    if not _SCREENSHOT_MJS.exists():
        return None
    html_path = deck / "pages" / f"page_{page_no:03d}.html"
    if not html_path.exists():
        return None
    out_path = deck / "screenshots" / f"page_{page_no:03d}.png"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        proc = _run_text_subprocess(
            [
                "node", str(_SCREENSHOT_MJS),
                "--html", str(html_path),
                "--out", str(out_path),
                "--viewport", viewport,
                "--wait", "800",
            ],
            timeout=60,
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
    _progress(f"Starting {len(tasks)} items with {concurrency} workers...")
    completed_count = 0
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
            completed_count += 1
            _progress(f"[{completed_count}/{len(tasks)}] {label} {status}")
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


def cmd_batch_page_html(deck: Path, concurrency: int,
                        start_page: int | None = None,
                        end_page: int | None = None) -> int:
    outline_path = deck / "outline.json"
    if not outline_path.exists():
        return _fail("outline.json missing")
    outline = _load_json(outline_path)
    tasks: list[tuple] = []
    for page in outline.get("pages", []):
        pno = int(page.get("page_no", 0))
        if pno <= 0:
            continue
        if start_page is not None and pno < start_page:
            continue
        if end_page is not None and pno > end_page:
            continue
        tasks.append((cmd_page_html, (deck, pno), {}, f"p{pno:03d}/html"))
    if not tasks:
        return _fail("no pages in outline matching range")
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

    for name in ("preflight", "style-samples", "outline", "asset-plan"):
        sp = sub.add_parser(name)
        sp.add_argument("--deck-dir", type=Path, required=True)

    sp = sub.add_parser("style")
    sp.add_argument("--deck-dir", type=Path, required=True)
    sp.add_argument("--sample", choices=("A", "B", "C", "a", "b", "c"), default=None,
                    help="promote a selected standard-mode style sample")

    sp = sub.add_parser("export")
    sp.add_argument("--deck-dir", type=Path, required=True)
    sp.add_argument("--format", choices=("pptx", "pdf"), default=None,
                    help="override task_pack.params.output_format")

    sp = sub.add_parser("gen-image")
    sp.add_argument("--deck-dir", type=Path, required=True)
    sp.add_argument("--page", type=int, required=True)
    sp.add_argument("--slot", type=str, required=True)

    sp = sub.add_parser("page-html")
    sp.add_argument("--deck-dir", type=Path, required=True)
    sp.add_argument("--page", type=int, required=True)

    # `refine-page` is a STANDALONE per-page tool: screenshot → VLM critique →
    # LLM apply. NOT wired into the main pipeline; the agent only runs it on
    # demand. Outputs page_NNN.review.md + page_NNN.refined.html (alongside
    # the original page_NNN.html, which is preserved untouched).
    sp = sub.add_parser("refine-page")
    sp.add_argument("--deck-dir", type=Path, required=True)
    sp.add_argument("--page", type=int, required=True)

    # Batch / concurrent variants (default concurrency=4). Each fans out its
    # per-item work across a thread pool so LLM / VLM / T2I wait times overlap.
    for name in ("batch-gen-image", "batch-refine-page"):
        sp = sub.add_parser(name)
        sp.add_argument("--deck-dir", type=Path, required=True)
        sp.add_argument("--concurrency", type=int, default=4,
                        help="max parallel workers (default 4, clamped to 1-16)")

    sp = sub.add_parser("batch-page-html")
    sp.add_argument("--deck-dir", type=Path, required=True)
    sp.add_argument("--concurrency", type=int, default=4,
                    help="max parallel workers (default 4, clamped to 1-16)")
    sp.add_argument("--start-page", type=int, default=None,
                    help="first page to process (1-based, inclusive)")
    sp.add_argument("--end-page", type=int, default=None,
                    help="last page to process (1-based, inclusive)")

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    deck = args.deck_dir.expanduser().resolve()
    if args.cmd == "preflight":
        return cmd_preflight(deck)
    if args.cmd == "style":
        return cmd_style(deck, getattr(args, "sample", None))
    if args.cmd == "style-samples":
        return cmd_style_samples(deck)
    if args.cmd == "outline":
        return cmd_outline(deck)
    if args.cmd == "asset-plan":
        return cmd_asset_plan(deck)
    if args.cmd == "gen-image":
        return cmd_gen_image(deck, args.page, args.slot)
    if args.cmd == "page-html":
        return cmd_page_html(deck, args.page)
    if args.cmd == "refine-page":
        return cmd_refine_page(deck, args.page)
    if args.cmd == "export":
        return cmd_export(deck, getattr(args, "format", None))
    if args.cmd == "batch-gen-image":
        return cmd_batch_gen_image(deck, args.concurrency)
    if args.cmd == "batch-page-html":
        return cmd_batch_page_html(deck, args.concurrency,
                                   getattr(args, "start_page", None),
                                   getattr(args, "end_page", None))
    if args.cmd == "batch-refine-page":
        return cmd_batch_refine_page(deck, args.concurrency)
    return _fail(f"unknown command {args.cmd!r}")


if __name__ == "__main__":
    sys.exit(main())
