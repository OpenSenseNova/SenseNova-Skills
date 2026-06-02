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

- `<deck_dir>/task_pack.json` exists and `ppt_mode == "standard"`
- `<deck_dir>/info_pack.json` exists

Any missing → stop and tell user to enter via `/skill sn-ppt-entry`.

## 🚫 Hard rules (the main agent MUST NOT)

1. **Do NOT write Python scripts that loop over pages or slots** in a single exec. Use the batch subcommands, or per-item execs in the agent's own loop of tool_calls.
2. **Do NOT fake image generation.** If `gen-image` and its image-search fallback both fail, don't write a placeholder PNG — the HTML stage will redesign around the missing slot.
3. **Do NOT construct LLM prompts yourself.** `run_stage.py` is the only place that builds payloads.
4. **Do NOT add `timing` / logging / retry layers.** The skill is intentionally thin.
5. **Do NOT go silent between execs.** Echo a one-line Chinese progress message after each exec before issuing the next.
6. **Do NOT use python-pptx, pptxgenjs, or any alternative PPTX builder.** `run_stage.py export` is the ONLY way to produce a PPTX file. Never write Python scripts that import `pptx` or Node scripts that import `pptxgenjs`. If export fails or is skipped, the HTML pages are the final deliverable.
7. **Do NOT re-run a failing stage more than twice.** If the same `run_stage.py` subcommand fails with the same error on two consecutive attempts, treat it as a permanent failure. Echo the failure, record the skipped stage, and move on. Partial output is better than a stuck retry loop.
8. **Language integrity.** All user-visible text MUST match the user's query language. If the query is Chinese, every title, bullet, caption, label, and footnote MUST be in Chinese — even if source documents are in English. A single English title in a Chinese deck is a regression.
9. **Image integration.** All images used in slides MUST be saved under `<deck_dir>/images/` and referenced via relative paths from HTML (e.g., `../images/photo.jpg`). Never leave remote URLs in final HTML. Never use colored rectangles as image placeholders. If a searched/downloaded image exists on disk, it MUST appear in the corresponding page HTML.
10. **Do NOT fabricate data.** All numbers, statistics, and factual claims MUST come from the user's uploaded documents or from web search results. If no data source is available, use qualitative descriptions instead of invented numbers.
11. **Wait for `ask_user` responses.** When you ask the user a question (e.g., to clarify parameters or confirm style), do NOT proceed until the user replies. Never continue with assumed/default values without explicit confirmation.
12. **Multi-round edits: regenerate, do not patch.** When the user requests changes to an existing deck, re-run the affected pipeline stages from scratch. Do NOT edit files in-place with sed/perl/Python string manipulation — the artifact schemas are machine-generated and easy to corrupt.

## Visual quality standards

- The style_spec MUST NOT default to safe/bland choices (e.g., white background + blue accents + black text). Actively prefer distinctive, themed styles.
- Each page HTML MUST have visual density: use color blocks, decorative elements, background gradients, and layout variety. A page that looks like a Word document (white background, title + bullet list, no decoration) is a FAILURE.
- Avoid low-contrast text. All body text must have at least 4.5:1 contrast ratio against its background.

## Image sourcing

The user's `image_source` preference (from `task_pack.params`) determines how images are obtained:

**`web-search`**: Search the web for real images via the `sn-search-image` skill. Each result includes the image URL, source page, title, and domain — easy to trace and attribute. Save downloaded images under `<deck_dir>/images/` and reference them with relative paths in HTML.

**`ai-gen`**: Use AI image generation via `gen-image` / `sn-image-base`. Asset priority for standard image slots: **searched image first**, **generated image second**, **authored SVG/CSS illustration last**. Do not mention the image-search provider name in prompts, progress, visible slide text, or user-facing summaries.

**`none`**: No raster images — use text, tables, charts, and CSS visuals only.

### Infographic slots (U1-generated diagrams)

For flowcharts, process diagrams, organizational charts, and complex data visualizations, the pipeline creates `infographic` slots (slot_kind=`infographic`). These are **always AI-generated via U1** — web search is not used for infographics because they visualize content-specific data.

When `gen-image` processes an infographic slot, U1 generates a clean, professionally styled diagram. If U1 generation fails, fall back to ECharts, CSS, or text tables.

### Image search as fallback

When `image_source` is `ai-gen` and generation fails for a slot, use web search as a backup (if `SERPER_API_KEY` is set).

### No junk — hard constraint

Never use: grey boxes, 1×1 transparent PNGs, "image pending" labels, broken-image icons, fake thumbnails, empty reserved frames, or colored rectangles as image placeholders. If no good image turns up for a slot — from any source — rework the page completely.

## External research

- Always use the web search skills (`sn-search-web`) for facts, research, and knowledge grounding.

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

# Batch (concurrent) equivalents. Use when individual execs would exceed
# time budget. Batch commands block until ALL items complete.
# Concurrency for batch-page-html: 1 (≤4 pages), 2 (5-8 pages), 4 (9+ pages).
# Concurrency for batch-gen-image: default 4.
$R batch-gen-image  --deck-dir $D [--concurrency 4]
$R batch-page-html  --deck-dir $D --concurrency N

$R export        --deck-dir $D              # -> <deck_id>.pptx
```

`batch-gen-image` serializes writes to `asset_plan.json` under a process-local lock so concurrent workers don't clobber each other.

**Prefer individual commands for small decks.** For ≤4 pages, use individual `page-html` commands — one page per exec gives visible progress. For 5+ pages, use `batch-page-html` with the concurrency listed above.

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

### HTML content check before export

Before running `export`, verify that every `pages/page_NNN.html` has substantive content:
- File size > 1KB and contains visible text beyond empty boilerplate
- If any page HTML is suspiciously small (< 500 bytes), re-run `page-html` for that page
- Only proceed to export when all pages pass

## Export PPTX gate

`scripts/export_pptx/html_to_pptx.mjs` is invoked with `--force` — skips built-in motif / real-photo gates (this skill doesn't use the motif protocol). PPTX still produces even if some slots are missing images.

If the headless browser (Playwright/Chromium) is unavailable, the export returns `status: "skipped"` with reason `"headless_browser_unavailable"`. The PPTX file is absent — this is an expected degraded ending state. The HTML pages are the final deliverable.

🚫 **DO NOT fall back to python-pptx, libreoffice, or any other converter.** DO NOT attempt to install Chromium system dependencies manually. Simply report the skip and finish.

## Does NOT

- Does not call `sn-image-base` for LLM/VLM (only for T2I).
- Does not retry failed model calls.
- Does not write progress to disk.
- Does not do per-page visual review or rewriting (removed in this iteration).
