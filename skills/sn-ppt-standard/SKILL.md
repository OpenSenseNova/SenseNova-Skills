---
name: sn-ppt-standard
description: |
  Standard and fast PPT pipeline. All LLM / VLM / T2I calls are wrapped in a
  single CLI entry (scripts/run_stage.py). The main agent's job is simple:
  emit ONE shell command per stage, never write loops, never write prompts.
  
  Standard mode plans thoroughly with a style preview checkpoint, web research,
  and image search for polished, delivery-ready presentations. Fast mode builds
  a complete draft immediately with autonomous decisions, then provides
  structured refinement suggestions so the user can iterate quickly. Supports
  AI-generated infographics (U1) for diagrams and flowcharts, web image search
  (Serper) for real photos, and ECharts for data charts.
metadata:
  project: SenseNova-Skills
  tier: 1
  category: scene
  user_visible: false
triggers:
  - "sn-ppt-standard"
---

# sn-ppt-standard

> **⚠️ This skill must be invoked through `/skill sn-ppt-entry`.** Never start here directly — the entry skill collects parameters, parses uploaded files, and writes `task_pack.json` + `info_pack.json` that this skill requires. If you arrived here without those files, stop and tell the user to enter via `/skill sn-ppt-entry` or "生成 PPT".

This skill is **self-contained** — no dependency on `sn-image-base` for LLM/VLM (T2I still goes through `sn-image-base`). Every call through `$SKILL_DIR/scripts/run_stage.py`. Every subcommand is deterministic: one input set → one output artifact → one-line JSON status.

## Preconditions

- `<deck_dir>/task_pack.json` exists and `ppt_mode in {"standard", "fast"}`
- `<deck_dir>/info_pack.json` exists

Any missing → stop and tell user to enter via `/skill sn-ppt-entry`.

When `ppt_mode == "fast"`: **build first, then iterate.** Make decisions autonomously — do not ask the user about colors, fonts, page count, or layout preferences. Infer reasonable defaults from the query and start building immediately. Skip optional web search and image search. Run the full pipeline including PPTX export. **Data**: use uploaded documents first; if none, use mock data labeled `[Sample Data]` and tell the user in chat which data needs replacement. **Images**: AI generation for decorative images, ECharts for charts — no questions asked.

### Post-generation (fast mode only)

After the PPTX is generated, do NOT just say "done, any feedback?" Instead, provide a **structured set of refinement suggestions** based on the actual content you generated. This helps the user understand what changed between your fast draft and what a polished standard-mode version would look like.

**1. Quick wins (3-5 specific suggestions):** Point to concrete things the user could improve with one-line instructions. Tie each suggestion to a specific slide or element. Examples:
- "Slide 3: replace the mock revenue numbers with your actual Q4 data"
- "Slide 5: swap the generic team photo placeholder with your real team picture"
- "Cover slide: try a darker background for more impact — I can switch it to deep navy"
- "Slide 7: the bar chart is using sample data — give me your real numbers and I'll regenerate it"

**2. Standard-mode comparison (2-3 gaps):** Explain what would have been different in standard mode, so the user knows what they're trading off. Examples:
- "In standard mode, I would have searched the web for competitor benchmarks to include on slide 4 — right now those numbers are estimates labeled [Sample Data]"
- "Standard mode includes a style preview checkpoint where you would have confirmed the coral-red accent color before I built all 12 slides"
- "With image search enabled, slides 2 and 8 could use real product photos instead of the AI-generated decorative images"

**3. Suggested next actions (3-4 paths):** Offer concrete directions the user can take:
- "Replace mock data: tell me which slides need real numbers and I'll update them"
- "Adjust style: I can change the color palette, fonts, or layout density across all slides at once"
- "Add a section: if you need a financial projections or risk analysis section, I can insert new slides"
- "Promote to standard: if this draft is close to what you need, I can re-run it in standard mode with full research and image search for a delivery-ready version"

When the user responds with a change request, apply it immediately and re-present the updated suggestions.

When `ppt_mode == "standard"`: **plan thoroughly first, then build.** Do thorough research and image search. Produce a polished, delivery-ready presentation. **Data**: documents first, web search second, ask user as last resort. Never fabricate numbers.

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
13. **Validate paths before writing.** All output goes under `<deck_dir>/` — the absolute path written in `task_pack.json`. Before writing any file, verify the parent directory exists. Never write to `/workspace/`, `/tmp/`, `~/`, `./`, or any path not rooted at `<deck_dir>`. If a command's `--output` or `--save-path` argument doesn't start with `<deck_dir>/`, it's wrong.

## Visual quality standards

- The style_spec MUST NOT default to safe/bland choices (e.g., white background + blue accents + black text). Actively prefer distinctive, themed styles.
- Each page HTML MUST have visual density: use color blocks, decorative elements, background gradients, and layout variety. A page that looks like a Word document (white background, title + bullet list, no decoration) is a FAILURE.
- Avoid low-contrast text. All body text must have at least 4.5:1 contrast ratio against its background.

## Image sourcing

The user's `image_source` preference (from `task_pack.params`) determines how images are obtained:

**`web-search`**: Search the web for real images via the `sn-search-image` skill. Each result includes the image URL, source page, title, and domain — easy to trace and attribute. Save downloaded images under `<deck_dir>/images/` and reference them with relative paths in HTML. Web search is ideal for real product photos, landmark shots, or anything AI can't draw accurately.

**`ai-gen`**: Use AI image generation via `gen-image` / `sn-image-base`. Asset priority for standard image slots: **searched image first**, **generated image second**, **authored SVG/CSS illustration last**. Do not mention the image-search provider name in prompts, progress, visible slide text, or user-facing summaries.

**`none`**: No raster images — use text, tables, charts, and CSS visuals only.

### Infographic slots (U1-generated diagrams)

For flowcharts, process diagrams, organizational charts, and complex data visualizations, the pipeline creates `infographic` slots (slot_kind=`infographic`). These are **always AI-generated via U1** — web search is not used for infographics because they visualize content-specific data.

When `gen-image` processes an infographic slot, U1 generates a clean, professionally styled diagram. If U1 generation fails, fall back to ECharts, CSS, or text tables.

### Image search as fallback

When `image_source` is `ai-gen` and generation fails for a slot, use web search as a backup (if `SERPER_API_KEY` is set).

### No junk — hard constraint

Never use: grey boxes, 1×1 transparent PNGs, "image pending" labels, broken-image icons, fake thumbnails, empty reserved frames, or colored rectangles as image placeholders. If no good image turns up for a slot — from any source — rework the page completely. Different layout, different approach. The user must never see that awkward hole where a picture should be.

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
$R batch-page-html  --deck-dir $D --concurrency N [--start-page S --end-page E]

# For large decks, split into ranges to stay within the 300s execution limit:
$R batch-page-html  --deck-dir $D --concurrency 4 --start-page 1 --end-page 8
$R batch-page-html  --deck-dir $D --concurrency 4 --start-page 9 --end-page 16

$R export        --deck-dir $D              # -> <deck_id>.pptx
```

### Style preview checkpoint (standard mode only)

When `ppt_mode == "standard"`: after `style_spec.json` is produced, **pause for user confirmation** before proceeding to outline:

1. Read `style_spec.json` and describe the visual direction: primary colors, typography, and overall mood
2. Ask whether to proceed or modify (e.g., "change the primary color to blue")
3. If the user requests changes, re-run the style stage with updated preferences
4. Only proceed to outline after the user confirms

Progress echo: `[1] style_spec.json ✓ — waiting for style confirmation`.

When `ppt_mode == "fast"`: **skip this checkpoint.** Proceed directly through all stages without pausing.

`batch-gen-image` serializes writes to `asset_plan.json` under a process-local lock so concurrent workers don't clobber each other.

**Split large decks into ranges.** Hermes has a 300s execution limit. For >8 pages, use `--start-page` / `--end-page` to split work across multiple execs, each with its own concurrency. For ≤8 pages, a single batch is fine. Example for 16 pages: batch 1-8 and batch 9-16 as separate execs.

### How `page-html` works (two LLM calls per page)

1. **Rewrite** — `prompts/page_html_rewrite.md` converts the structured outline + style_spec + inherited content into a natural-language user prompt (content, layout, palette, inherited material).
2. **Generate** — `prompts/page_html.md` is a hard-contract system prompt (document shell, image path format, ECharts rules, single-layer background, `<span>` wrapping rule, language lock). Receives the rewritten query as the user message and returns the final `<!DOCTYPE html>...</html>`.

This split keeps converter-facing mechanical contracts (chart container id = `chart_N`, `{renderer:'svg'}`, `__pptxChartsReady` counter, allowed chart types, etc.) in the generator's system prompt — not buried in the natural-language query where they'd get smoothed out.

## Stage failure handling

When a `run_stage.py` subcommand fails (exit code 1):

- **Echo the failure** and proceed to the next stage. A failed style stage does not block outline; a failed outline does not block export.
- **Only abort the pipeline** for unrecoverable errors: permanently invalid model name, missing or revoked API key, model returns HTTP 401/403. If the same error is clearly unrecoverable (not a timeout or transient gateway issue), stop and report.
- **Timeout, no-response, and gateway errors are transient** — treat them like the retry rules in rule #7 and move on.
- **Never fall back to python-pptx or alternative tools** when a stage fails. The remedy is to re-run that stage, skip it and continue, or work around missing artifacts — not to switch to a different PPTX builder. `run_stage.py` is the only path to generate slides.
- Stages after a failure use whichever artifacts exist from earlier stages. If `style_spec.json` is missing because the style stage failed, the remaining stages work around it — outline can use defaults, page-html can use a generic style.
- After all stages complete (some succeeded, some failed), still run `export` — it produces whatever is available.

Progress echo for failures:

| After failed style | `[1] style ✗ 模型超时，继续后续阶段` |
| After failed outline | `[2] outline ✗ JSON 解析失败，继续后续阶段` |

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
