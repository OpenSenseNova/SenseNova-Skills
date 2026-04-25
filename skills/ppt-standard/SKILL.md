---
name: ppt-standard
description: |
  Standard-mode PPT pipeline. style_spec -> outline -> asset_plan + per-slot
  image generation + VLM QC -> per-page HTML -> per-page review (+ optional
  rewrite) -> aggregated review.md -> PPTX export. Expects task_pack.json +
  info_pack.json already written by ppt-entry.
metadata:
  project: SenseNova-Skills
  tier: 1
  category: scene
  user_visible: false
triggers:
  - "ppt-standard"
---

# ppt-standard

## Preconditions

- `<deck_dir>/task_pack.json` exists and `ppt_mode == "standard"`
- `<deck_dir>/info_pack.json` exists
- `<deck_dir>/pages/` exists
- `<deck_dir>/images/` exists

Any missing -> stop and tell user to enter via `/skill ppt-entry`.

## Resume first

Always run `scripts/resume_scan.py --deck-dir <deck_dir>` as step 1:

```bash
python <SKILL_DIR>/scripts/resume_scan.py --deck-dir <deck_dir>
```

It returns a manifest JSON with
`next_action in {style, outline, asset_plan, per_page, aggregate_review, export_pptx, finished}`.
Dispatch:

| `next_action` | Do |
|---|---|
| `style` | Run Stage 2 |
| `outline` | Run Stage 3 |
| `asset_plan` | Run Stage 4 |
| `per_page` | For every `page` where `action != "skip"`, run Stages 5 / 6 |
| `aggregate_review` | Run Stage 8 |
| `export_pptx` | Run Stage 7 |
| `finished` | Echo closing summary (Stage 9) and exit |

Within "per_page", per-page `action` further drives:
- `full` = Stage 5 (HTML) + Stage 6 (review + optional rewrite)
- `review_only` = Stage 6 only (HTML already on disk)
- `skip` = do nothing

## Conventions

- All shell examples use `<SKILL_DIR>`, `<deck_dir>`, `<deck_id>`, `<U1_IMAGE_BASE>`, `<PPT_ENTRY_DIR>`, `<NNN>` placeholders; main agent substitutes at call time. See `<PPT_ENTRY_DIR>/references/conventions.md`.
- All path-bearing fields written to `<deck_dir>` artifacts are **absolute**.
- `<<<INLINE: references/html_constraints.md>>>` placeholders inside prompt files must be expanded in-memory before calling `u1-text-optimize` (see conventions.md).

## Stage 2 — style_spec.json

Trigger: `style_spec_done == false`.

```bash
python <U1_IMAGE_BASE>/u1_image_base/openclaw_runner.py u1-text-optimize \
  --system-prompt-path <SKILL_DIR>/prompts/style_spec.md \
  --user-prompt "<JSON of task_pack.params + info_pack.query_normalized>" \
  --output-format json
```

Take `result` -> parse as JSON -> write to `<deck_dir>/style_spec.json`.

Failure (non-JSON / empty / CLI error): **abort** — structural artifact.

Timing:

```bash
python <PPT_ENTRY_DIR>/scripts/timing_helper.py record-stage \
  --path <deck_dir>/timing.json --stage style --seconds <elapsed>
```

## Stage 3 — outline.json

Trigger: `outline_done == false`.

```bash
python <U1_IMAGE_BASE>/u1_image_base/openclaw_runner.py u1-text-optimize \
  --system-prompt-path <SKILL_DIR>/prompts/outline.md \
  --user-prompt "<cat style_spec.json + JSON of query_normalized + document_digest + params.page_count>" \
  --output-format json
```

Extract `result` -> parse as JSON (page_count must match). Write to `<deck_dir>/outline.json`.

Failure -> abort.

Timing: `record-stage --stage outline --seconds <elapsed>`.

## Stage 4.1 — asset_plan.json

Trigger: `asset_plan_done == false`.

```bash
python <U1_IMAGE_BASE>/u1_image_base/openclaw_runner.py u1-text-optimize \
  --system-prompt-path <SKILL_DIR>/prompts/asset_plan.md \
  --user-prompt "<cat outline.json + cat style_spec.json>" \
  --output-format json
```

After parsing the returned JSON:

1. Walk every `pages[].slots[].local_path`. If a value is not absolute (does not start with `/`), rewrite it to `<deck_dir>/images/page_{page_no:03d}_{slot_id}.png`.
2. Force `status="pending"` and `quality_review=null` on every slot.

Write the normalized payload to `<deck_dir>/asset_plan.json`.

Failure -> abort (structural).

Timing: `record-stage --stage asset_plan --seconds <elapsed>`.

## Stage 4.2 — per-slot image generation

For each slot in `asset_plan.pages[].slots[]` where `status == "pending"` AND `local_path` does not exist on disk:

```bash
python <U1_IMAGE_BASE>/u1_image_base/openclaw_runner.py u1-image-generate \
  --prompt "<slot.image_prompt>" \
  --aspect-ratio "<slot.aspect_ratio>" \
  --image-size "<slot.image_size>" \
  --save-path "<slot.local_path>" \
  --output-format json
```

On success: set `slot.status = "ok"`; capture `elapsed_seconds` from the JSON stdout and record per-page timing:

```bash
python <PPT_ENTRY_DIR>/scripts/timing_helper.py record-page \
  --path <deck_dir>/timing.json \
  --page-no <slot.page_no> \
  --field image_gen_seconds \
  --seconds <elapsed>
```

On failure: set `slot.status = "failed"`, leave `local_path` unchanged, do NOT retry, continue to next slot.

After the loop: write back the updated `asset_plan.json`; accumulate `stages.image_generate` via a single `record-stage` at the end of 4.2.

## Stage 4.3 — per-slot QC

For each slot where `status == "ok"` AND `quality_review == null`:

```bash
python <U1_IMAGE_BASE>/u1_image_base/openclaw_runner.py u1-image-recognize \
  --system-prompt-path <SKILL_DIR>/prompts/asset_qc.md \
  --user-prompt "Evaluate the image per the rules. Return JSON only." \
  --images "<slot.local_path>" \
  --output-format json
```

Parse `result` as JSON -> write to `slot.quality_review`. On QC failure (non-JSON / CLI error): leave `quality_review = null`, do NOT regenerate the image, do NOT drop the slot. Continue.

After the loop: write back `asset_plan.json`.

Timing: `record-stage --stage asset_qc --seconds <elapsed>`.

## Stage 5 — per-page HTML

For each page where `action` includes Stage 5 (i.e., `html_done == false`):

Build the user prompt by concatenating:
- `<SKILL_DIR>/references/html_constraints.md` content (this is the `<<<INLINE: references/html_constraints.md>>>` substitution inside `page_html.md`)
- `style_spec.json` content
- `outline.pages[i]` JSON
- `asset_plan.pages[i]` JSON (slots with absolute local_path + quality_review)
- Optional: relevant excerpts from `raw_documents.json` (only if `info_pack.raw_document_excerpts.enabled == true` AND this page's outline notes a data-heavy kind)

```bash
python <U1_IMAGE_BASE>/u1_image_base/openclaw_runner.py u1-text-optimize \
  --system-prompt-path <SKILL_DIR>/prompts/page_html.md \
  --user-prompt "<assembled prompt>" \
  --output-format json
```

Take `result` (HTML string) -> write to `<deck_dir>/pages/page_<NNN>.html`.

Failure: skip this page, append `page_no` to in-memory `failed_pages`, continue.

Timing (per page): `record-page --field html_seconds --seconds <elapsed>`; accumulate `record-stage --stage page_html`.

## Stage 6.1 — per-page review

For each page where `html_done == true` AND `review_done == false`:

```bash
python <U1_IMAGE_BASE>/u1_image_base/openclaw_runner.py u1-text-optimize \
  --system-prompt-path <SKILL_DIR>/prompts/page_review.md \
  --user-prompt "<cat style_spec.json + JSON of outline.pages[i] + cat pages/page_<NNN>.html>" \
  --output-format json
```

Take `result` (markdown) -> write to `<deck_dir>/pages/page_<NNN>.review.md`.

**Parsing contract**: after writing, read back the FIRST line (strip). If it is exactly `VERDICT: NEEDS_REWRITE`, proceed to Stage 6.2 for this page. Otherwise (including parse failure / first-line absent / `VERDICT: CLEAN`) -> CLEAN, skip 6.2.

Timing: `record-page --field review_seconds`; accumulate `record-stage --stage review`.

## Stage 6.2 — per-page rewrite (when NEEDS_REWRITE)

Only when 6.1's VERDICT is NEEDS_REWRITE, run at most ONE rewrite:

```bash
python <U1_IMAGE_BASE>/u1_image_base/openclaw_runner.py u1-text-optimize \
  --system-prompt-path <SKILL_DIR>/prompts/page_rewrite.md \
  --user-prompt "<cat pages/page_<NNN>.html + cat pages/page_<NNN>.review.md>" \
  --output-format json
```

Take `result` (HTML) -> overwrite `<deck_dir>/pages/page_<NNN>.html`.

On failure: keep the original HTML; append to `<deck_dir>/pages/page_<NNN>.review.md`:

```
## Rewrite attempt failed: <reason>
```

Do NOT touch the first-line VERDICT.

Timing: `record-page --field rewrite_seconds`; accumulate `record-stage --stage rewrite`.

## Stage 8 — aggregated review.md (runs BEFORE Stage 7)

Trigger: all per-page `.review.md` files exist (or skipped due to failed_pages).

```bash
python <U1_IMAGE_BASE>/u1_image_base/openclaw_runner.py u1-text-optimize \
  --system-prompt-path <SKILL_DIR>/prompts/deck_review.md \
  --user-prompt "<for each page: '## page_<NNN>\n' + review.md content; then a 'failed_pages: [...]' tail>" \
  --output-format json
```

Take `result` (markdown) -> write to `<deck_dir>/review.md`.

Timing: `record-stage --stage review_summary`.

## Stage 7 — export PPTX

Runs **AFTER** Stage 8 (so `review.md` exists for the converter gate to read).

Default invocation (gates on, **do NOT** pass `--force` unless the user asks):

```bash
node <SKILL_DIR>/scripts/export_pptx/html_to_pptx.mjs --deck-dir <deck_dir>
```

Output: `<deck_dir>/<deck_id>.pptx` (the converter names the file after `basename(deck_dir)` — ppt-entry already names `deck_dir` to equal `deck_id`).

### Converter gates (all enforced by default)

1. `<deck_dir>/review.md` exists and is not marked as blocking
2. motif `data-layer` tags present when declared by `style_spec.json` (HTML must render them — see `references/html_constraints.md` §4)
3. `real-photo` asset slots must reference actual local PNGs, not placeholders (see `references/html_constraints.md` §5)

On gate failure: converter exits non-zero. **Do NOT auto-retry with `--force`.**
Read the stderr; append the reason to the top of `<deck_dir>/review.md` (or write `<deck_dir>/export_error.md` if `review.md` somehow doesn't exist); surface the blocker to the user.

### Optional flags (for user / debugging)

| Flag | Purpose |
|---|---|
| `--output <filename>` | Output PPTX filename (default: basename(deck_dir) + `.pptx`) |
| `--output-dir <dir>` | Output directory (default: `<deck_dir>`) |
| `--pages-dir <dir>` | HTML pages directory (default: `<deck_dir>/pages/`) |
| `--force` | Downgrade gate failures to warnings, continue export |
| `--batch` | Skip gates + skip remote image downloads; implies `--force` |

### Converter built-in behavior (do NOT re-implement)

The Node converter in `scripts/export_pptx/` already handles:
- First-time self-install of `npm` deps and chromium (if not pre-installed)
- Auto-normalizing a flat `deck_dir/page_*.html` layout into `deck_dir/pages/`
- Reading `style_spec.json` / `storyboard.json` to enrich PPTX defaults (fonts, title)
- Per-page conversion failure tolerance — generates a blank slide to preserve page numbering
- Remote `http(s)` image downloads into `<deck_dir>/images/` (no-op in external-release flow where all images are already local)

### Success output (stdout JSON)

```json
{"success": true, "output": "/abs/.../<deck_id>.pptx", "pages": 10, "converted": 10, "failed": 0, "fileSize": 1234567}
```

Main agent parses this JSON and echoes `converted / failed` in the closing summary (Stage 9).

### First-time setup

If `scripts/export_pptx/node_modules/` is missing (Phase 0's `ppt-doctor` will WARN about this), run once:

```bash
cd <SKILL_DIR>/scripts/export_pptx
npm install
npx playwright install chromium
```

The converter also self-installs on first call if you skip this, at the cost of warm-up latency on that run.

### Failure modes

| Case | Handling |
|---|---|
| Gate failure (review / motif / real-photo) | Do NOT retry with `--force`. Append reason to `review.md` top; surface to user; Stage 9 reports PPTX missing |
| Converter crash after gate pass (Playwright error, pptxgenjs error, etc.) | Same: append to `review.md`; Stage 9 reports PPTX missing |
| `node` not on PATH / `npm install` not run | `ppt-doctor` should have caught this; if we get here anyway, surface the error; suggest `/skill ppt-doctor` |

Timing:

```bash
python <PPT_ENTRY_DIR>/scripts/timing_helper.py record-stage \
  --path <deck_dir>/timing.json --stage pptx_export --seconds <elapsed>
```

## Stage 9 — closing summary

Read `<deck_dir>/timing.json` and emit the closing message per spec §8.3:
deliverables / concerns / 耗时统计 / next steps.

If `<deck_id>.pptx` does NOT exist (Phase 5 not yet shipped, or Stage 7 failed), say so explicitly; do NOT pretend it exists.

## Stage ordering note

The stage numbers (2, 3, 4.1, 4.2, 4.3, 5, 6.1, 6.2, 7, 8, 9) express semantic
dependency order. Actual execution order is

```
2 -> 3 -> 4.1 -> 4.2 -> 4.3 -> 5 -> 6 -> 8 -> 7 -> 9
```

(Stage 8 before Stage 7 so the PPTX export gate can read `review.md`.)

## Progress echo

- Start: one line — mode, deck_dir, page_count, whether document digest is present
- After each of Stages 2, 3, 4.1: one line
- During Stages 4.2 / 4.3: one line every 5 slots
- During Stage 5: one line every 3 pages
- After Stage 6: one line with the count of pages that triggered rewrite
- After Stage 7 (Phase 5): one line with the PPTX path
- After Stage 8: one line
- Closing (Stage 9): the full summary from spec §8.3

## Does NOT

- Do not call any model endpoint directly — always via `openclaw_runner.py`
- Do not parallelize page / slot work
- Do not retry on first failure
- Do not write to files outside `<deck_dir>` (except calling the timing helper and the exporter, which live inside the skills tree)
