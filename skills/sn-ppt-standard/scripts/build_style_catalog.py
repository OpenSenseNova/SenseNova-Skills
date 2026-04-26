#!/usr/bin/env python3
"""Rebuild skills/sn-ppt-standard/references/style_catalog.md from
reference/style_dimensions.json.

Run manually any time `reference/style_dimensions.json` changes.

The catalog is an LLM-facing menu of design_style / color_tone / primary_color
triples. The style_spec stage picks one triple rather than inventing a
palette from scratch.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
SRC = REPO / "reference" / "style_dimensions.json"
DST = REPO / "skills" / "sn-ppt-standard" / "references" / "style_catalog.md"


def _join_ids(ids: list[int]) -> str:
    return ",".join(str(i) for i in ids) if ids else "—"


def build(data: dict) -> str:
    ds = data.get("design_styles", [])
    ct = data.get("color_tones", [])
    pc = data.get("primary_colors", [])

    lines: list[str] = []
    lines.append("# Style catalog")
    lines.append("")
    lines.append(
        "Pick ONE triple `{design_style, color_tone, primary_color}` from the three tables below. "
        "Do NOT invent a style that isn't in these tables. "
        "Compatibility is pre-validated: stay within the listed `compat_*` columns."
    )
    lines.append("")

    # --- design_styles ----------------------------------------------------
    lines.append(f"## design_style  ({len(ds)} options)")
    lines.append("")
    lines.append("| id | name (zh / en) | feel | compat tone_ids | compat color_ids |")
    lines.append("|----|----------------|------|-----------------|------------------|")
    for s in ds:
        name_zh = s.get("name", "")
        name_en = s.get("name_en", "")
        desc = (s.get("desc") or "").replace("\n", " ").replace("|", "/")
        tones = _join_ids(s.get("compatible_tones") or [])
        colors = _join_ids(s.get("compatible_colors") or [])
        lines.append(f"| {s['id']} | {name_zh} / {name_en} | {desc} | {tones} | {colors} |")
    lines.append("")

    # --- color_tones ------------------------------------------------------
    lines.append(f"## color_tone  ({len(ct)} options)")
    lines.append("")
    lines.append("| id | name (zh / en) | feel | compat color_ids |")
    lines.append("|----|----------------|------|------------------|")
    for t in ct:
        name_zh = t.get("name", "")
        name_en = t.get("name_en", "")
        desc = (t.get("desc") or "").replace("\n", " ").replace("|", "/")
        colors = _join_ids(t.get("compatible_colors") or [])
        lines.append(f"| {t['id']} | {name_zh} / {name_en} | {desc} | {colors} |")
    lines.append("")

    # --- primary_colors ---------------------------------------------------
    lines.append(f"## primary_color  ({len(pc)} options)")
    lines.append("")
    lines.append("| id | name (zh / en) | hex | mood |")
    lines.append("|----|----------------|-----|------|")
    for c in pc:
        name_zh = c.get("name", "")
        name_en = c.get("name_en", "")
        hex_v = c.get("hex", "")
        mood = (c.get("mood") or "").replace("\n", " ").replace("|", "/")
        lines.append(f"| {c['id']} | {name_zh} / {name_en} | {hex_v} | {mood} |")
    lines.append("")

    # --- selection rules --------------------------------------------------
    lines.append("## Selection rules")
    lines.append("")
    lines.append(
        "1. Read `user_query` + `task_pack.params.scene` + `task_pack.params.audience` + `task_pack.params.role`; "
        "scan the design_style table and pick the ONE whose `feel` best matches. "
        "Examples: 'a Q2 financial report for senior leadership' → `商务经典` or `简报/仪表盘`; "
        "'AI product launch for consumers' → `科技感` or `渐变流体`; "
        "'kids education app' → `卡通可爱` or `儿童/幼教`."
    )
    lines.append(
        "2. Within the chosen design_style's `compat tone_ids`, pick the ONE color_tone whose `feel` fits the narrative. "
        "Tone controls overall brightness (dark vs light), saturation (mute vs vivid), and thematic family."
    )
    lines.append(
        "3. Within `design_style.compat color_ids ∩ color_tone.compat color_ids`, pick the ONE primary_color whose `mood` matches. "
        "If the intersection is empty (rare), relax to `design_style.compat color_ids` only. "
        "If still empty, pick anything from primary_color whose `mood` matches."
    )
    lines.append(
        "4. Output the three IDs + names + the primary_color's hex literally; do NOT change the hex. "
        "Downstream code uses that hex as the CSS `--primary` variable, so drift breaks consistency."
    )
    lines.append(
        "5. If the user's query explicitly names a style or color (e.g., '做个赛博朋克风的'), prioritize it "
        "as long as the name matches something in the tables."
    )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    if not SRC.exists():
        print(f"source not found: {SRC}", file=sys.stderr)
        return 1
    try:
        data = json.loads(SRC.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"json parse error: {e}", file=sys.stderr)
        return 2
    out = build(data)
    DST.parent.mkdir(parents=True, exist_ok=True)
    DST.write_text(out, encoding="utf-8")
    print(f"wrote {DST} ({len(out)} chars, "
          f"{len(data.get('design_styles', []))} styles, "
          f"{len(data.get('color_tones', []))} tones, "
          f"{len(data.get('primary_colors', []))} colors)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
