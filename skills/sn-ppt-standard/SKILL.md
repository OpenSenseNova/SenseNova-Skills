---
name: sn-ppt-standard
description: |
  Standard and fast PPT pipeline. All LLM / VLM / T2I calls are wrapped in a
  single CLI entry (scripts/run_stage.py). The main agent's job is simple:
  emit ONE shell command per stage, never write loops, never write prompts.
  
  Standard mode plans thoroughly with a three-sample deck preview checkpoint
  (three concatenated deck images plus a preview URL), web research, image
  search, and user-selected final output format (PPTX or PDF) for polished,
  delivery-ready presentations. Fast mode builds
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

This skill is **self-contained** — no dependency on `sn-image-base` for LLM/VLM (T2I still goes through `sn-image-base`). Generation logic stays in `$SKILL_DIR/scripts/run_stage.py`; use `run_stage_with_progress.py` only as a WebUI progress wrapper. Every subcommand is deterministic: one input set → one output artifact → one-line JSON status.

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
- "Standard mode includes a three-sample deck preview checkpoint where you would compare three concatenated deck images and a preview URL before I built all 12 slides"
- "With image search enabled, slides 2 and 8 could use real product photos instead of the AI-generated decorative images"

**3. Suggested next actions (3-4 paths):** Offer concrete directions the user can take:
- "Replace mock data: tell me which slides need real numbers and I'll update them"
- "Adjust style: I can change the color palette, fonts, or layout density across all slides at once"
- "Add a section: if you need a financial projections or risk analysis section, I can insert new slides"
- "Promote to standard: if this draft is close to what you need, I can re-run it in standard mode with full research and image search for a delivery-ready version"

When the user responds with a change request, apply it immediately and re-present the updated suggestions.

When `ppt_mode == "standard"`: **plan thoroughly first, then build.** Do thorough research and image search. Generate three visual deck samples for the user to choose from before creating the outline. Each sample includes one concatenated deck image and one HTML preview deck; also provide a single preview URL that shows all three decks. Produce the selected final format from `task_pack.params.output_format` (`"pptx"` or `"pdf"`). **Data**: documents first, web search second, ask user as last resort. Never fabricate numbers.

## 🚫 Hard rules (the main agent MUST NOT)

1. **Do NOT write Python scripts that loop over pages or slots** in a single exec. Use the batch subcommands, or per-item execs in the agent's own loop of tool_calls.
2. **Do NOT fake image generation.** If `gen-image` and its image-search fallback both fail, don't write a placeholder PNG — the HTML stage will redesign around the missing slot.
3. **Do NOT construct LLM prompts yourself.** `run_stage.py` is the only place that builds payloads.
4. **Do NOT add `timing` / logging / retry layers.** The skill is intentionally thin.
5. **Do NOT go silent between execs.** Echo a one-line Chinese progress message after each exec before issuing the next.
6. **Do NOT use python-pptx, pptxgenjs, libreoffice, or any alternative converter.** `run_stage.py export` is the ONLY way to produce the final PPTX/PDF file. Never write Python scripts that import `pptx`, Node scripts that import `pptxgenjs`, or ad hoc PDF conversion scripts. If export fails or is skipped, the HTML pages are the final deliverable.
7. **Do NOT re-run a failing stage more than twice.** If the same `run_stage.py` subcommand fails with the same error on two consecutive attempts, treat it as a permanent failure. Echo the failure, record the skipped stage, and move on. Partial output is better than a stuck retry loop.
8. **Language integrity.** All user-visible text MUST match the user's query language. If the query is Chinese, every title, bullet, caption, label, and footnote MUST be in Chinese — even if source documents are in English. A single English title in a Chinese deck is a regression.
9. **Image integration.** All images used in slides MUST be saved under `<deck_dir>/images/` and referenced via relative paths from HTML (e.g., `../images/photo.jpg`). Never leave remote URLs in final HTML. Never use colored rectangles as image placeholders. If a searched/downloaded image exists on disk, it MUST appear in the corresponding page HTML.
10. **Do NOT fabricate data.** All numbers, statistics, and factual claims MUST come from the user's uploaded documents or from web search results. If no data source is available, use qualitative descriptions instead of invented numbers.
11. **Wait for `ask_user` responses.** When you ask the user a question (e.g., to clarify parameters, choose a style sample, or choose output format), do NOT proceed until the user replies. Never continue with assumed/default values without explicit confirmation.
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

Use `python3` on Linux/macOS, `python` on Windows (where `python3` is often absent).
All commands below use `python3` — substitute `python` on Windows.

```bash
W="python3 $SKILL_DIR/scripts/run_stage_with_progress.py"
D="<deck_dir>"

$W preflight     --deck-dir $D              # validate + stage assets, publish progress

# sn-ppt-entry should already have started the generation progress WebUI after
# task_pack.json / info_pack.json were written. Run this only as an idempotent
# reuse/fallback check for resumed or direct-invocation sessions.
python3 $SKILL_DIR/scripts/launch_workbench.py --deck-dir $D --source-session-id "${HERMES_SESSION_KEY:-}" --agent-managed 1 --agent-provider "${WORKBENCH_AGENT_PROVIDER:-hermes}"

$W style-samples --deck-dir $D             # standard only -> style_samples.json + deck preview images/URL
$W style         --deck-dir $D --sample A   # standard -> style_spec.json from selected sample
$W style         --deck-dir $D              # fast -> style_spec.json (one autonomous style)
$W outline       --deck-dir $D              # -> outline.json
$W asset-plan    --deck-dir $D              # -> asset_plan.json

# Per-item forms — one progress line per item. PREFERRED for visibility:
# each exec returns quickly with status, keeping the user informed.
$W gen-image     --deck-dir $D --page N --slot SLOT_ID
$W page-html     --deck-dir $D --page N

# Batch (concurrent) equivalents. Use when individual execs would exceed
# time budget. Batch commands block until ALL items complete.
# Concurrency for batch-page-html: 1 (≤4 pages), 2 (5-8 pages), 4 (9+ pages).
# Concurrency for batch-gen-image: default 4.
$W batch-gen-image  --deck-dir $D [--concurrency 4]
$W batch-page-html  --deck-dir $D --concurrency N [--start-page S --end-page E]

# For large decks, split into ranges to stay within the 300s execution limit:
$W batch-page-html  --deck-dir $D --concurrency 4 --start-page 1 --end-page 8
$W batch-page-html  --deck-dir $D --concurrency 4 --start-page 9 --end-page 16

$W export        --deck-dir $D              # -> <deck_id>.pptx or <deck_id>.pdf from task_pack.params.output_format
```

### Three-sample deck preview checkpoint (standard mode only)

When `ppt_mode == "standard"`: after preflight, run `style-samples`, then **pause for user selection** before proceeding to `style` and `outline`:

1. Make sure the workbench has already been launched after preflight. It will show the style chooser automatically when `style_samples.json` appears.
2. Run `$W style-samples --deck-dir $D`. This writes:
   - `style_samples.json`
   - `style_samples/style_samples.html` and `style_samples/index.html` (same all-samples preview)
   - `style_samples/sample_A_deck.svg`, `sample_B_deck.svg`, `sample_C_deck.svg` (one concatenated deck image per style)
   - `style_samples/sample_A_deck.html`, `sample_B_deck.html`, `sample_C_deck.html` (one HTML preview deck per style)
3. Parse the command JSON. It includes `preview_url`, `preview_images`, and `preview_decks`.
4. Send or attach all three `preview_images` to the user before asking them to choose. Each image is a vertically concatenated mini deck, not a single style card.
5. Provide the `preview_url` or the workbench URL so the user can compare all three decks. If the client cannot attach local images, provide each image URL/path plus the `preview_url`.
6. Present samples (`A`, `B`, `C`) with their label, design style, tone, primary color, and rationale.
7. Ask the user to choose `A`, `B`, or `C`, and wait. If the user selects in the WebUI, read `$D/.workbench/style-selection.json` and use its `sampleId`.
8. Run `$W style --deck-dir $D --sample <A|B|C>` to promote the selected sample into `style_spec.json`.
9. Only proceed to outline after `style_spec.json` exists.

Progress echo after samples: `[1] style_samples.json ✓ 3 个 deck 预览图 + URL，等待选择`.
Progress echo after selection: `[1] style_spec.json ✓ selected sample <A|B|C>`.

When `ppt_mode == "fast"`: **skip this checkpoint.** Proceed directly through all stages without pausing.

`batch-gen-image` serializes writes to `asset_plan.json` under a process-local lock so concurrent workers don't clobber each other.

**Split decks into small ranges.** Hermes defaults to a 180s foreground timeout. The SN API can take 60-90s per page for HTML generation, so conservative batching is essential:

- Concurrency 2: 3 pages max per batch (3×90s/2 ≈ 135s)
- Concurrency 4: 6 pages max per batch (6×90s/4 ≈ 135s)
- For 10 pages: `--start-page 1 --end-page 3`, `--start-page 4 --end-page 6`, `--start-page 7 --end-page 9`, then page 10 solo.
- If even 3-page batches time out, the SN API backend is slow — skip directly to manual fallback rather than splitting further.
- Batch commands block until ALL items complete; a single slow page stalls the whole batch.

### Generation progress WebUI launch

`sn-ppt-entry` starts the generation progress WebUI immediately after the first JSON files exist. In this skill, run the same helper only as an idempotent reuse/fallback check after `preflight` and before `style-samples`, `style`, `outline`, or HTML generation:

```bash
python3 $SKILL_DIR/scripts/launch_workbench.py --deck-dir $D --source-session-id "${HERMES_SESSION_KEY:-}" --agent-managed 1 --agent-provider "${WORKBENCH_AGENT_PROVIDER:-hermes}"
```

On native Windows Hermes installs where `python3` is unavailable, run the same helper with `python`.

**⚠️ MSYS path conversion pitfall (Windows + git-bash/MSYS):** When running under MSYS/git-bash on Windows, the shell auto-converts arguments that look like POSIX paths (e.g., `/progress`) to Windows-style paths. This breaks `--progress-route` and any other argument starting with `/`. **Fix:** prefix the command with `MSYS_NO_PATHCONV=1`:

```bash
MSYS_NO_PATHCONV=1 python $SKILL_DIR/scripts/launch_workbench.py --deck-dir $D --progress-route /progress --agent-managed 1 --host 0.0.0.0
MSYS_NO_PATHCONV=1 python $SKILL_DIR/scripts/progress_event.py --deck-dir $D --stage entry --status ok ...
```

This applies to BOTH `launch_workbench.py` and `progress_event.py` when slash-prefixed arguments are used.

Before starting the server, the helper checks NodeJS. If it returns `{"status":"skipped","reason":"nodejs_missing",...}`, ask the user whether to install NodeJS/dependencies. If they decline, say generation will continue without the WebUI and proceed. If they agree, first use any approved dependency-install skill/tool exposed by the active environment; otherwise use platform install means only after explicit dangerous-operation confirmation.

When launched from an agent, keep `--agent-managed 1`. Managed mode hides BYOK/model configuration in the PPT workbench and lets the Node server relay bottom-chat turns to a deck-scoped companion session. For Hermes, keep passing the active generation session only as `--source-session-id` so the companion can read the original generation prompt and related context; do not expose WebUI, Gateway, REST, ACP commands, or API keys to the browser.

Interactive provider configuration is structured-only:

- Hermes: `--agent-provider hermes --agent-transport webui|gateway` plus `--webui-base-url` or `--gateway-base-url`.
- OpenClaw: `--agent-provider openclaw --agent-transport rest --agent-base-url <url> --agent-api-key <key>`.
- Codex: `--agent-provider codex --agent-transport acp --acp-command <codex-acp command>`.
- Claude Code: `--agent-provider claude-code --agent-transport acp --acp-command <claude ACP command>`.
- WorkBuddy: `--agent-provider workbuddy` only marks provider identity. Tell the user that WorkBuddy has no supported API or ACP interface for use as an interactive workbench bridge, so bottom-chat modification turns cannot be sent back to WorkBuddy.

Never parse provider CLI/TUI output for the WebUI companion bridge.

If the helper returns `{"status":"ok", ...}`, echo the returned `generation_url` to the user. The returned `generation_url` is the progress page at `/progress`; the editor remains available through `editor_url` at `/editor`.

`生成进度工作台已启动：<url>`

If the helper returns `{"status":"skipped", ...}`, echo a short skip reason and continue generating HTML. WebUI startup must never block PPT generation.

The helper locates the local `sensenova-ppt-workbench` launcher from `SENSENOVA_PPT_WORKBENCH_CLI`, `PPT_WORKBENCH_CLI`, or common `~/Repository/ppt-editor/src/ppt-editor` paths, with the legacy root layout kept as a fallback. It builds the workbench once if `dist/index.html` is missing, starts a lightweight server, and reuses an existing healthy server for the same deck.

**Bridge mode** — the workbench auto-detects its bridge type:
- **Writable companion bridge**: When a supported WebUI, Gateway/REST, or ACP bridge is configured, the workbench creates/reuses one companion session for the deck and writes bottom-chat turns there.
- **Source-only mode**: When no writable bridge is configured, the workbench still shows all pages, tools, and export, but bottom chat cannot write to an agent companion session. This does NOT block PPT preview or export.

Remote access behavior:
- Prefer Hermes/canvas/port-forward URLs from `WORKBENCH_PUBLIC_URL`, `HERMES_WORKBENCH_PUBLIC_URL`, `HERMES_CANVAS_URL`, `HERMES_PORT_FORWARD_URL`, `CANVAS_URL`, `PORT_FORWARD_URL`, `TUNNEL_URL`, Codespaces, or Gitpod.
- If a forwarded/canvas URL exists, the helper binds the WebUI to localhost and reports the forwarded generation URL.
- If no forwarded/canvas URL exists, native hosts bind to localhost by default.
- Docker/WSL bind to `0.0.0.0` by default and report a LAN URL based on the machine's non-loopback IPv4 address.
- If the reported URL is not reachable from the user's device, ask for a reachable forward/canvas URL or explicit host/IP and rerun the helper with `--public-url <url>` or `--host <host>`.

### How `page-html` works (two LLM calls per page)

1. **Rewrite** — `prompts/page_html_rewrite.md` converts the structured outline + style_spec + inherited content into a natural-language user prompt (content, layout, palette, inherited material).
2. **Generate** — `prompts/page_html.md` is a hard-contract system prompt (document shell, image path format, ECharts rules, single-layer background, `<span>` wrapping rule, language lock). Receives the rewritten query as the user message and returns the final `<!DOCTYPE html>...</html>`.

This split keeps converter-facing mechanical contracts (chart container id = `chart_N`, `{renderer:'svg'}`, `__pptxChartsReady` counter, allowed chart types, etc.) in the generator's system prompt — not buried in the natural-language query where they'd get smoothed out.

## SN API model pitfall

The default model `sensenova-6.7-flash-lite` frequently returns `reasoning_content`
but **empty `content`** in its response. This causes `run_stage.py` to fail with
`"LLM response had no usable text"` on stages that parse JSON output:
`outline`, `asset-plan`, and `page-html`.

**Preferred fix — switch the model (one-time config change):**
Set `SN_TEXT_MODEL=deepseek-v4-flash` (or another reliable non-reasoning model)
in the SenseNova `.env`. This resolves the `reasoning_content` empty-shell bug
and **greatly reduces** (but does not eliminate) the malformed-JSON
`"Expecting ',' delimiter"` errors that `sensenova-6.7-flash-lite` produces on
the `outline` stage. Even with `deepseek-v4-flash`, outline can still fail
with JSON parse errors on some runs — treat it as flaky, not fixed. After the
switch, `asset-plan` and `page-html` run more reliably, but `outline` remains
the most fragile stage across all tested models.

**Fallback (if model switch is not possible):** `preflight` and `style` are usually unaffected because they
don't require structured JSON from the model. When `outline` / `asset-plan` /
`page-html` fail with this error:

1. Run `style` through SN API if not done already.
2. Read `style_spec.json` for palette/typography.
3. Manually author `outline.json` following the schema in `prompts/outline.md`.
4. Generate each `pages/page_NNN.html` using the agent's own LLM (not SN API).
   Follow the hard contract in `prompts/page_html.md`: 1600×900 wrapper, `#bg`+`#ct`,
   ECharts rules, single-layer backgrounds, `<span>` wrapping, language lock.
5. Run `export` normally — it does not call the SN API.

## Stage failure handling

When a `run_stage.py` subcommand fails (exit code 1):

- **Echo the failure** and proceed to the next stage. A failed style stage does not block outline; a failed outline does not block export.
- **Only abort the pipeline** for unrecoverable errors: permanently invalid model name, missing or revoked API key, model returns HTTP 401/403. If the same error is clearly unrecoverable (not a timeout or transient gateway issue), stop and report.
- **Timeout, no-response, and gateway errors are transient** — treat them like the retry rules in rule #7 and move on.
- **SN API fallback:** When the SN LLM backend consistently times out (2+ consecutive failures on `outline` or `asset-plan` stages), skip those stages and use Hermes' native LLM to manually create `outline.json` and page HTMLs. The `page_html.md` contract (1600×900, `.wrapper > #bg + #ct`, ECharts rules) still applies. Then run `export` with the existing scripts — they work with any compliant HTML pages regardless of how they were generated.
- **Never fall back to python-pptx or alternative tools** when a stage fails. The remedy is to re-run that stage, skip it and continue, or work around missing artifacts — not to switch to a different PPTX builder. `run_stage.py` is the only path to generate slides.
- Stages after a failure use whichever artifacts exist from earlier stages. If `style_spec.json` is missing because the style stage failed, the remaining stages work around it — outline can use defaults, page-html can use a generic style.
- After all stages complete (some succeeded, some failed), still run `export` — it produces whatever is available.

### SN API timeout fallback (manual artifact creation)

When the SN LLM backend consistently times out on LLM-dependent stages (`outline`, `asset-plan`, `page-html`) — two consecutive timeouts per stage with `ReadTimeout` — **do not abort the pipeline**. Instead, create the intermediate artifacts manually using the agent's own capabilities:

1. **outline.json**: Write it directly using `write_file`. Use the schema from `prompts/outline.md`. Populate content from the agent's own knowledge or web research (not calling the SN API). The outline MUST match the exact JSON schema — page_kind values, bullet head/detail objects, data_points format, etc.

2. **asset_plan.json**: Skip entirely. The downstream `page-html` stage (manual HTML generation) and `export` stage do not require it. Mark the stage as cancelled in your todo list.

3. **page_NNN.html**: Generate each page directly using `write_file`. Follow the HTML contract from `prompts/page_html.md`:

   **⚠️ Before generating HTML pages, check for the `inherited_tables` pitfall:** If `info_pack.json` has `document_digest.inherited_tables` entries pointing to tables in `raw_documents.json`, but the document was a `.md` file, `parse_user_docs.py` extracted raw text without structured table data. When `use_table` fields in `outline.json` reference these tables, `_resolve_inherited_table` crashes with `JSONDecodeError: Expecting value`. **Fix:** clear `inherited_tables` to `[]` in `info_pack.json`:

   ```json
   "inherited_tables": [],
   ```

   This is safe because the manual HTML pages embed their own table data.

   Follow the HTML contract:
   - `1600×900` canvas, `.wrapper > #bg + #ct` structure
   - All `<span>` wrapping rule for pseudo-element containers
   - ECharts: `<script src="../assets/echarts.min.js">`, container id `chart_N`, `{renderer:'svg'}`, `__pptxChartsReady` counter
   - Relative image paths: `../images/...`
   - Language lock: all visible text in the user's query language
   - Single-layer backgrounds (no stacked `background: linear-gradient(...), url(...)`)
   If ECharts is needed, copy `echarts.min.js` from a previous deck's `assets/` directory (e.g., `ppt_decks/<previous_deck>/assets/echarts.min.js`) into the current deck's `assets/`.

4. **export**: After all HTML pages exist, run `run_stage.py export --deck-dir <D>` as normal. The export stage is independent of SN API — it reads HTML pages and produces PPTX/PDF via Playwright. It will succeed with manually-generated HTML pages just as it would with pipeline-generated ones.

**Why this works**: The `run_stage.py` stages are loosely coupled through files on disk — each stage reads its inputs from JSON/HTML files and writes its outputs as files. The export stage doesn't know or care whether the HTML was generated by an SN LLM call or written manually. This fallback preserves the pipeline's export capability while bypassing the broken SN backend.

**When to use this fallback**: After two consecutive timeouts per failing stage. A single timeout could be transient — retry once per rule #7. But if two stages both fail (e.g., `outline` times out twice AND `asset-plan` times out twice), the SN backend is clearly down and you should switch to manual mode for all remaining LLM-dependent stages rather than burning time on individual retries.

**Fast mode + Chinese content**: the `outline` stage is especially fragile with zh-Hans content — expect 2 consecutive JSON parse failures and fall through to manual outline. This is common enough to not be alarming; the manual outline + manual HTML path produces a complete deck reliably.

**Progress echoes for manual mode**:
| After manual outline | `[2] outline.json ✓ 12 页（手动编写）` |
| After manual HTML pages | `[页 1-12/12] HTML ✓（手动生成）` |

**Reference files for manual fallback**:
- `prompts/outline.md` — canonical outline.json schema and generation contract.
- `references/html_constraints.md` — non-negotiable HTML contract from `page_html.md` (skeleton, ECharts, CSS rules).

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
| After style samples | `[1] style_samples.json ✓ 3 个 deck 预览图 + URL，等待选择` |
| After style | `[1] style_spec.json ✓ 样例 A / 主色 #2D5BFF` |
| After outline | `[2] outline.json ✓ 10 页` |
| After asset-plan | `[3] asset_plan.json ✓ N 槽位` |
| After WebUI launch/reuse | `生成进度工作台已启动：http://127.0.0.1:<port>/progress` |
| Per gen-image | `[图 5/14] page_003/hero ✓` or `... ✗ 服务端 502` |
| After all gen-image | `图片生成阶段完成：成功 12，失败 2` |
| Per page-html | `[页 3/10] HTML ✓` |
| After export | `PPTX ✓ (10/10 页)` / `PDF ✓ (10/10 页)` or `导出失败: ...` |

**Silence for more than ~30 seconds = a bug.**

## Resume semantics

The script is stateless — re-run a subcommand and it'll overwrite its output artifact. Quick `ls <deck_dir>` decides what's left:

- `style_samples.json` exists but `style_spec.json` is missing in standard mode → first check `.workbench/style-selection.json`; if absent, read `preview.preview_url` and `preview.artifacts`, resend the three concatenated deck images plus the preview URL if the user has not seen them, ask the user to choose `A`, `B`, or `C`, then run `style --sample <A|B|C>`
- `style_spec.json` exists → skip `style-samples` and `style`
- `outline.json` exists → skip `outline`
- `asset_plan.json` exists → skip `asset-plan` (but any slot whose `local_path` is missing or `status != "ok"` still needs `gen-image`)
- `pages/page_NNN.html` exists → skip `page-html` for that page
- `<deck_id>.pptx` exists → skip `export`

`scripts/resume_scan.py` emits a JSON manifest summarizing all this.

## Model compatibility & reasoning-model handling

Some models are **reasoning models** that return their output in
`choices[0].message.reasoning_content` instead of `choices[0].message.content`:

| Model | Manifestation |
|-------|--------------|
| `kimi-k2.7-code` | `reasoning_content` present, `content` empty |
| `sensenova-6.7-flash-lite` (default when no `SN_TEXT_MODEL` set) | `reasoning_content` present, `content` empty; OR produces malformed JSON causing `"Expecting ',' delimiter"` errors on `outline` |

The `_coerce_message_content` function in `lib/model_client.py` must handle this field as a
fallback. If you encounter `"LLM response had no usable text"` errors, check that
`"reasoning_content"` is in the fallback key list at line ~191:

```python
for key in ("text", "output_text", "value", "reasoning_content"):
```

### Model override for JSON reliability

When a reasoning model produces malformed JSON in structured-output stages (e.g.,
`outline`, `asset-plan`), switch to a non-reasoning model. **Preferred**: export
`SN_TEXT_MODEL=deepseek-v4-flash` and `SN_CHAT_MODEL=deepseek-v4-flash` in the
SenseNova `.env` file. Tested working end-to-end: `preflight`, `style-samples`,
`style`, `outline`, `asset-plan`, and `page-html` (7/10 pages) all succeed with
this model at `localhost:8090`. Alternative: `export SN_TEXT_MODEL="gpt-4o"` for
a one-shot override.

### Batch retry for individual items

`batch-page-html` can produce transient failures on some pages while succeeding on
others. The batch returns `status: "ok"` overall, but individual `[N/10] pXXX/html failed`
lines in stderr indicate which pages need retry.

**Known pattern — pages 1-3 often fail:** The cover (page 1), section_header (page 2),
and first content page (page 3) fail more often than later pages. These page types
have richer visual prompts (large titles, decorative elements, special layouts) that
stress the model's HTML generation. When pages 1-3 fail in `batch-page-html`:

1. Do NOT retry them with `page-html --page N` through SN API — the retry typically
   fails with the same error.
2. Generate these pages manually with Hermes' native LLM (write_file). Read the
   `outline.json` for content and `style_spec.json` for palette/typography.
3. Late pages that fail individually (pages 4+) CAN be retried with `page-html --page N`
   and often succeed on the second attempt.

**⚠️ False-positive "ok" — verify file size after batch:** `batch-page-html` can report
`[N/M] pXXX/html ok` while writing a near-empty file (as small as ~178 bytes — just the
DOCTYPE + `<head>` with no body content). This happens most often on `section_header` pages.
After every batch-page-html run, spot-check file sizes with `wc -c pages/page_*.html`.
If any page is < 500 bytes, treat it as a failed page and regenerate manually. Never
trust the "ok" status alone — always verify at least one page per batch has real content.

**section_header pages anywhere in the deck are fragile:** Not just page 2 — any
`page_kind: section_header` page (e.g., page 8 in a 10-page deck) can fail or produce
incomplete output. After batch-page-html, check all section_header pages first.

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

## Export gate

`scripts/run_stage.py export` reads `task_pack.params.output_format`.

- `output_format == "pptx"` invokes `scripts/export_pptx/html_to_pptx.mjs --force`. This skips built-in motif / real-photo gates (this skill doesn't use the motif protocol). PPTX still produces even if some slots are missing images.
- `output_format == "pdf"` invokes `scripts/export_pptx/html_to_pdf.mjs --force`. The PDF path loads each page HTML in an isolated printable frame, scales oversized slide canvases down to fit the fixed 1600×900 page, then emits one combined Chromium print PDF. It is not a screenshot-backed PDF path.
- If `output_format` is missing because the deck was created by an older entry skill, ask the user to choose PPTX or PDF before export, then run `export --format <pptx|pdf>`.

If the headless browser (Playwright/Chromium) is unavailable, the export returns `status: "skipped"` with reason `"headless_browser_unavailable"`. The selected output file is absent — this is an expected degraded ending state. The HTML pages are the final deliverable.

PDF sizing constraint: because some models emit HTML canvases larger than the expected slide size, the PDF exporter must fit by measuring the rendered slide target (`.wrapper`, `.slide.canvas`, `.slide`, or `body`) and scaling down any page larger than 1600×900. Never crop oversized pages silently.

🚫 **DO NOT fall back to python-pptx, libreoffice, or any other converter.** DO NOT attempt to install Chromium system dependencies manually. Simply report the skip and finish.

## Does NOT

- Does not call `sn-image-base` for LLM/VLM (only for T2I).
- Does not retry failed model calls.
- Does not implement generation in the WebUI progress wrapper; progress metadata is written by `run_stage_with_progress.py`, while `run_stage.py` remains the only generation implementation.
- Does not do per-page visual review or rewriting (removed in this iteration).
