---
name: sn-ppt-standard
description: |
  Standard-mode PPT pipeline. All LLM / VLM / T2I calls are wrapped in a
  single CLI entry (scripts/run_stage.py). The main agent's job is simple:
  emit ONE shell command per stage, never write loops, never write prompts.
metadata:
  project: SenseNova-Skills
  tier: 1
  category: scene
  user_visible: false
triggers:
  - "sn-ppt-standard"
---

# sn-ppt-standard

This skill is **self-contained** — no dependency on `sn-image-base` for LLM/VLM (T2I still goes through `sn-image-base`). Every call through `$SKILL_DIR/scripts/run_stage.py`. Every subcommand is deterministic: one input set → one output artifact → one-line JSON status.

## Preconditions

- `<deck_dir>/task_pack.json` exists and `ppt_mode in {"standard", "fast"}`
- `<deck_dir>/info_pack.json` exists

Any missing → stop and tell user to enter via `/skill sn-ppt-entry`.

When `ppt_mode == "fast"`: **build first, then iterate.** Jump straight into making complete slides — content and visuals included — without upfront research or planning. Skip the style preview checkpoint. Run the full pipeline including PPTX export. Once the PPT is generated, present it and explicitly invite feedback: "What would you like to change?" The cycle of feedback and adjustment continues until the user is satisfied. **Data handling**: use uploaded documents first. If no data is available, use mock/example data — label it as "[Sample Data]" in the slides AND explicitly tell the user in the chat response which data is mock so they can replace it.

When `ppt_mode == "standard"`: **plan thoroughly first, then build.** The style preview checkpoint is active — pause after style_spec.json for user confirmation. Align on colors, fonts, and tone before proceeding. Do thorough research and image search. Produce a polished, delivery-ready presentation. **Data handling**: documents first, web search second, ask user as last resort. Never fabricate numbers.

## 🚫 Hard rules (the main agent MUST NOT)

1. **Do NOT write Python scripts that loop over pages or slots** in a single exec. Use the batch subcommands, or per-item execs in the agent's own loop of tool_calls.
2. **Do NOT fake image generation.** If `gen-image` and its image-search fallback both fail, don't write a placeholder PNG — the HTML stage will redesign around the missing slot.
3. **Do NOT construct LLM prompts yourself.** `run_stage.py` is the only place that builds payloads.
4. **Do NOT add `timing` / logging / retry layers.** The skill is intentionally thin.
5. **Do NOT go silent between execs.** Echo a one-line Chinese progress message after each exec before issuing the next.
6. **Do NOT use python-pptx or any alternative PPTX builder** when export is skipped or fails. The HTML pages are complete as-is — there is no fallback renderer. An absent PPTX is an acceptable ending state.

## External research and image assets

- Always use the web search skills for facts, research and knowledge grounding.
- Always add real visual assets when a page benefits from them. Asset priority is: **searched image first**, **generated image second**, **authored SVG/CSS illustration last**. Do not mention the image-search provider name in prompts, progress, visible slide text, or user-facing summaries.
- Never use placeholder images or placeholder boxes. Do not create grey blocks, 1x1 transparent PNGs, "image pending" labels, broken-image icons, fake thumbnails, or empty reserved frames.
- If no generated/searched image exists for a slot, redesign the page without that raster image. Use an inline SVG or CSS-drawn visual only when it is an actual diagram/decoration that carries the slide's idea; otherwise use text, tables, charts, and layout.

## Pipeline

```bash
R="python3 $SKILL_DIR/scripts/run_stage.py"
D="<deck_dir>"

$R preflight     --deck-dir $D              # validate + stage assets
$R style         --deck-dir $D              # -> style_spec.json
$R outline       --deck-dir $D              # -> outline.json
$R asset-plan    --deck-dir $D              # -> asset_plan.json

# Per-item forms — one progress line per item. PREFERRED for visibility:
# each exec returns quickly with status, keeping the user informed.
$R gen-image     --deck-dir $D --page N --slot SLOT_ID
$R page-html     --deck-dir $D --page N

# Batch (concurrent) equivalents. Use only when there are many items (>10)
# AND individual execs would exceed time budget. Batch commands block until
# ALL items complete — the user sees no progress during execution.
$R batch-gen-image  --deck-dir $D [--concurrency 4]
$R batch-page-html  --deck-dir $D [--concurrency 4]

$R export        --deck-dir $D              # -> <deck_id>.pptx
```

### Style preview checkpoint (standard mode only)

When `ppt_mode == "standard"`: after `style_spec.json` is produced, **pause for user confirmation** before proceeding to outline and page generation:

1. Read `style_spec.json` and describe the visual direction to the user: primary colors, typography, and overall mood
2. Ask whether to proceed or modify (e.g., "change the primary color to blue", "make it more minimalist")
3. If the user requests changes, re-run the style stage with the updated preferences
4. Only proceed to outline after the user confirms

Progress echo: `[1] style_spec.json ✓ — waiting for style confirmation`. Do not run outline until the user confirms.

When `ppt_mode == "fast"`: **skip this checkpoint.** Proceed directly from style to outline and all subsequent stages without pausing. The user will iterate on the finished PPT.

`batch-gen-image` serializes writes to `asset_plan.json` under a process-local lock so concurrent workers don't clobber each other.

**Prefer individual commands over batch.** Running `gen-image` and `page-html` one page at a time gives the user visible progress on every page. Batch commands are faster but opaque — use them sparingly and only for large decks.

### How `page-html` works (two LLM calls per page)

1. **Rewrite** — `prompts/page_html_rewrite.md` converts the structured outline + style_spec + inherited content into a natural-language user prompt (content, layout, palette, inherited material).
2. **Generate** — `prompts/page_html.md` is a hard-contract system prompt (document shell, image path format, ECharts rules, single-layer background, `<span>` wrapping rule, language lock). Receives the rewritten query as the user message and returns the final `<!DOCTYPE html>...</html>`.

This split keeps converter-facing mechanical contracts (chart container id = `chart_N`, `{renderer:'svg'}`, `__pptxChartsReady` counter, allowed chart types, etc.) in the generator's system prompt — not buried in the natural-language query where they'd get smoothed out.

## Output on each exec

One JSON line to stdout:

```json
{"status": "ok", "page_no": 3, "path": "images/page_003_hero.png"}
```

or on failure (exit code 1):

```json
{"status": "failed", "error": "<reason>", "page_no": 3}
```

For `gen-image` failures: **don't retry**, don't substitute — the HTML stage will redesign around it.

## Progress echo — MANDATORY

| Stage | Example |
|---|---|
| After preflight | `已进入 sn-ppt-standard，共 N 页` |
| After style | `[1] style_spec.json ✓ 主色 #2D5BFF` |
| After outline | `[2] outline.json ✓ 10 页` |
| After asset-plan | `[3] asset_plan.json ✓ N 槽位` |
| Per gen-image | `[图 5/14] page_003/hero ✓` or `... ✗ 服务端 502` |
| After all gen-image | `图片生成阶段完成：成功 12，失败 2` |
| Per page-html | `[页 3/10] HTML ✓` |
| After export | `PPTX ✓ (10/10 页)` or `PPTX 失败: ...` |

**Silence for more than ~30 seconds = a bug.**

## Resume semantics

The script is stateless — re-run a subcommand and it'll overwrite its output artifact. Quick `ls <deck_dir>` decides what's left:

- `style_spec.json` exists → skip `style`
- `outline.json` exists → skip `outline`
- `asset_plan.json` exists → skip `asset-plan` (but any slot whose `local_path` is missing or `status != "ok"` still needs `gen-image`)
- `pages/page_NNN.html` exists → skip `page-html` for that page
- `<deck_id>.pptx` exists → skip `export`

`scripts/resume_scan.py` emits a JSON manifest summarizing all this.

## Env

Configured via `.env` at the repo root (or `<repo>/skills/.env`). `model_client.py` auto-loads both. Required:

- `SN_API_KEY` for shared text/vision/image-generation auth, or per-kind overrides `SN_CHAT_API_KEY` / `SN_TEXT_API_KEY` / `SN_VISION_API_KEY` / `SN_IMAGE_GEN_API_KEY`
- `SN_BASE_URL`, `SN_IMAGE_GEN_MODEL`

Optional `SN_CHAT_BASE_URL` / `SN_TEXT_BASE_URL` / `SN_VISION_BASE_URL`, `SN_CHAT_MODEL` / `SN_TEXT_MODEL` / `SN_VISION_MODEL`, and `SN_CHAT_TIMEOUT` / `SN_TEXT_TIMEOUT` / `SN_VISION_TIMEOUT` override defaults.

Run `python $SKILL_DIR/lib/model_client.py health` to verify env before running the pipeline.

## Export PPTX gate

`scripts/export_pptx/html_to_pptx.mjs` is invoked with `--force` — skips built-in motif / real-photo gates (this skill doesn't use the motif protocol). PPTX still produces even if some slots are missing images.

If the headless browser (Playwright/Chromium) is unavailable, the export returns `status: "skipped"` with reason `"headless_browser_unavailable"`. The PPTX file is absent — this is an expected degraded ending state. The HTML pages are the final deliverable.

🚫 **DO NOT fall back to python-pptx, libreoffice, or any other converter.** DO NOT attempt to install Chromium system dependencies manually. Simply report the skip and finish.

## Does NOT

- Does not call `sn-image-base` for LLM/VLM (only for T2I).
- Does not retry failed model calls.
- Does not write progress to disk.
- Does not do per-page visual review or rewriting (removed in this iteration).
