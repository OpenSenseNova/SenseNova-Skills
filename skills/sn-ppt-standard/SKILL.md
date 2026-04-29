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

## External research and image assets

- Always use the web search skills for facts, research and knowledge grounding.
- Always add real visual assets when a page benefits from them. Asset priority is: **generated image first**, **searched image second**, **authored SVG/CSS illustration last**. Do not mention the image-search provider name in prompts, progress, visible slide text, or user-facing summaries.
- Never use placeholder images or placeholder boxes. Do not create grey blocks, 1x1 transparent PNGs, "image pending" labels, broken-image icons, fake thumbnails, or empty reserved frames.
- Generated images are produced by `gen-image`. When generation fails or is rejected, `run_stage.py` may automatically try image search and save a real image to the same slot path. Treat either result as a real local asset.
- Before final HTML is accepted, any chosen remote image and user-uploaded image must be saved under `<deck_dir>/images/` and referenced via deck-local relative paths. Do not leave remote image URLs in the final HTML.
- If no generated/searched image exists for a slot, redesign the page without that raster image. Use an inline SVG or CSS-drawn visual only when it is an actual diagram/decoration that carries the slide's idea; otherwise use text, tables, charts, and layout.

## Pipeline

```bash
R="python3 $SKILL_DIR/scripts/run_stage.py"
D="<deck_dir>"

$R preflight     --deck-dir $D              # validate + stage assets
$R style         --deck-dir $D              # -> style_spec.json
$R outline       --deck-dir $D              # -> outline.json
$R asset-plan    --deck-dir $D              # -> asset_plan.json

# Per-item forms — one progress line per item:
$R gen-image     --deck-dir $D --page N --slot SLOT_ID
$R page-html     --deck-dir $D --page N

# Batch (concurrent) equivalents — default 4 workers. Each prints one summary
# JSON to stdout plus per-item status lines to stderr.
$R batch-gen-image  --deck-dir $D [--concurrency 4]
$R batch-page-html  --deck-dir $D [--concurrency 4]

$R review       --deck-dir $D [--concurrency 4]  # -> review.md + review.json
$R export        --deck-dir $D              # -> <deck_id>.pptx
```

`batch-gen-image` serializes writes to `asset_plan.json` under a process-local lock so concurrent workers don't clobber each other.

### How `page-html` works (two LLM calls per page)

1. **Rewrite** — `prompts/page_html_rewrite.md` converts the structured outline + style_spec + inherited content into a natural-language user prompt (content, layout, palette, inherited material).
2. **Generate** — `prompts/page_html.md` is a hard-contract system prompt (document shell, image path format, ECharts rules, single-layer background, `<span>` wrapping rule, language lock). Receives the rewritten query as the user message and returns the final `<!DOCTYPE html>...</html>`.
3. **Layout QC** — `run_stage.py` statically verifies the required `.wrapper/#bg/#ct` shell and, when Playwright is available, renders the page at 1600×900 to reject content outside the 60px safe area. Invalid HTML is regenerated with the concrete QC findings, up to `PPT_PAGE_HTML_MAX_ATTEMPTS` (default 3).

This split keeps converter-facing mechanical contracts (chart container id = `chart_N`, `{renderer:'svg'}`, `__pptxChartsReady` counter, allowed chart types, etc.) in the generator's system prompt — not buried in the natural-language query where they'd get smoothed out.

### Review stage

`$R review --deck-dir $D` is mandatory before export. It reviews every `pages/page_NNN.html` and writes:

- `pages/page_NNN.review.md` per page
- `review.md` deck summary
- `review.json` machine-readable summary

Default behavior is deterministic and low-risk: static shell checks plus Playwright overflow checks when the browser is available. It fails in strict mode (`PPT_REVIEW_STRICT=1`, default) if any page is missing or mechanically unsafe, so the deck is not exported with clipped or broken slides.

Optional model review/rewrite is available but off by default:

- `PPT_REVIEW_USE_LLM=1` enables `prompts/page_review.md` semantic/spec review.
- `PPT_REVIEW_FIX=1` lets `prompts/page_rewrite.md` rewrite a flagged page. The rewrite is adopted only after it passes the mechanical checks; the original is kept as `page_NNN.before_review.html`.

## Output on each exec

One JSON line to stdout:

```json
{"status": "ok", "page_no": 3, "path": "images/page_003_hero.png"}
```

or on failure (exit code 1):

```json
{"status": "failed", "error": "<reason>", "page_no": 3}
```

For `gen-image` failures: **don't retry T2I**. The command already attempts the configured image-search fallback when possible. If it still fails, don't substitute a placeholder — the HTML stage will redesign around the missing asset and use SVG/CSS only as the last resort.

## Progress echo — MANDATORY

| Stage | Example |
|---|---|
| After preflight | `已进入 sn-ppt-standard，共 N 页` |
| After style | `[1] style_spec.json ✓ 主色 #2D5BFF` |
| After outline | `[2] outline.json ✓ 10 页` |
| After asset-plan | `[3] asset_plan.json ✓ N 槽位` |
| Per gen-image | `[图 5/14] page_003/hero ✓` or `[图 5/14] page_003/hero ✓ 搜索兜底` or `... ✗ 服务端 502` |
| After all gen-image | `图片生成阶段完成：成功 12，失败 2` |
| Per page-html | `[页 3/10] HTML ✓` |
| After review | `[4] review.md ✓ 通过` or `[4] review.md ✗ 2 页需处理` |
| After export | `PPTX ✓ (10/10 页)` or `PPTX 失败: ...` |

**Silence for more than ~30 seconds = a bug.**

## Resume semantics

The script is stateless — re-run a subcommand and it'll overwrite its output artifact. Quick `ls <deck_dir>` decides what's left:

- `style_spec.json` exists → skip `style`
- `outline.json` exists → skip `outline`
- `asset_plan.json` exists → skip `asset-plan` (but any slot whose `local_path` is missing or `status != "ok"` still needs `gen-image`)
- `pages/page_NNN.html` exists → skip `page-html` for that page
- `review.md` and `review.json` exist → skip `review`
- `<deck_id>.pptx` exists → skip `export`

`scripts/resume_scan.py` emits a JSON manifest summarizing all this.

## Env

Configured via `.env` at the repo root (or `<repo>/skills/.env`). `model_client.py` auto-loads both. Required:

- `SN_CHAT_API_KEY` for shared text/vision chat auth, or per-kind overrides `SN_TEXT_API_KEY` / `SN_VISION_API_KEY`
- `SN_IMAGE_GEN_API_KEY`, `SN_IMAGE_GEN_BASE_URL`, `SN_IMAGE_GEN_MODEL`

Optional `SN_CHAT_BASE_URL` / `SN_TEXT_BASE_URL` / `SN_VISION_BASE_URL`, `SN_CHAT_MODEL` / `SN_TEXT_MODEL` / `SN_VISION_MODEL`, and `SN_CHAT_TIMEOUT` / `SN_TEXT_TIMEOUT` / `SN_VISION_TIMEOUT` override defaults.

Run `python $SKILL_DIR/lib/model_client.py health` to verify env before running the pipeline.

## Export PPTX gate

`scripts/export_pptx/html_to_pptx.mjs` is invoked with `--force` — skips built-in motif / real-photo gates (this skill doesn't use the motif protocol). PPTX still produces even if some slots are missing images.

If the converter crashes, `run_stage.py export` returns `status: "failed"`. That's the deck's ending state; PPTX is simply absent.

## Does NOT

- Does not call `sn-image-base` for LLM/VLM (only for T2I).
- Does not retry failed model calls.
- Does not write progress to disk.
- Does not do subjective per-page visual review by default; page-html only performs mechanical shell / overflow QC and regeneration.
