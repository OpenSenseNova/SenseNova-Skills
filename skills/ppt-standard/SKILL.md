---
name: ppt-standard
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
  - "ppt-standard"
---

# ppt-standard

This skill is **self-contained** — no dependency on `u1-image-base`, no `timing.json`, no image search. Every model call goes through `$SKILL_DIR/scripts/run_stage.py`. Every subcommand is deterministic: one input set → one output artifact → one-line JSON status.

## Preconditions

- `<deck_dir>/task_pack.json` exists and `ppt_mode == "standard"`
- `<deck_dir>/info_pack.json` exists

Any missing → stop and tell user to enter via `/skill ppt-entry`.

## 🚫 Hard rules (the main agent MUST NOT)

1. **Do NOT write Python scripts that loop over pages or slots.** Every per-page / per-slot call is a separate `exec` tool_call. If you catch yourself writing `for page in outline: ...` → STOP.
2. **Do NOT fake image generation.** If `gen-image` returns `status: "failed"`, do NOT write a 1x1 PNG placeholder or mark it `ok` anyway. Let the failure propagate — the HTML page will redesign its layout around the missing slot (see `prompts/page_html.md`).
3. **Do NOT construct LLM prompts yourself.** `run_stage.py` is the only place that builds payloads. If a prompt is missing context (e.g. `document_digest`), fix it in `run_stage.py`, don't bypass.
4. **Do NOT add `timing` / logging / retry layers.** The skill is intentionally thin.
5. **Do NOT go silent between exec tool_calls.** After every exec returns (success OR failure), you MUST immediately send a short Chinese chat line summarizing the JSON status to the user, BEFORE issuing the next exec. Example: exec returns `{"status":"ok","page_no":3,"path":"..."}` → your very next message is `[页 3/10] HTML ✓` → then the next exec. Silence between exec calls is a bug; if you're tempted to batch progress into a single message at the end, that's the bug.

## Pipeline (10 subcommands, agent dispatches each)

```bash
# Substitute $SKILL_DIR with the real path; <deck_dir> from task_pack.json.
R="python3 $SKILL_DIR/scripts/run_stage.py"
D="<deck_dir>"

$R preflight     --deck-dir $D              # validate + ensure pages/ images/
$R style         --deck-dir $D              # -> style_spec.json  (1 LLM)
$R outline       --deck-dir $D              # -> outline.json     (1 LLM)
$R asset-plan    --deck-dir $D              # -> asset_plan.json  (1 LLM)

# Per-item execs — use these when you need fine-grained control, resume of a
# single failure, or the agent wants to emit one progress line per item:
$R gen-image     --deck-dir $D --page N --slot SLOT_ID
$R page-html     --deck-dir $D --page N
# page-review / page-rewrite are currently DISABLED in run_stage.py
# (PAGE_REVIEW_ENABLED=False). Invoking them returns ok+skipped=true without
# any model call. Don't dispatch them until they're re-enabled.

# Concurrent batch equivalents (PREFERRED for throughput; default 4 workers).
# Each fans the per-item work out across a thread pool so model-API waits
# overlap. The batch command still prints ONE summary JSON to stdout plus a
# per-item progress line to stderr (agent can tail stderr for live updates).
$R batch-gen-image    --deck-dir $D [--concurrency 4]
$R batch-page-html    --deck-dir $D [--concurrency 4]
# batch-page-review / batch-page-rewrite are also disabled — SKIP these.

$R deck-review   --deck-dir $D              # -> review.md (deck-level summary only)
$R export        --deck-dir $D              # -> <deck_id>.pptx (Node/Playwright)
```

**Review is currently disabled.** Recent observations showed the per-page reviewer negatively optimizing slides (stripping content, bad layout swaps). Until prompts are retuned, `cmd_page_review` / `cmd_page_rewrite` and their batch variants short-circuit with `skipped=true` — no model call, no rewrite, no `page_NNN.review.md` file produced. The agent should go directly from `batch-page-html` to `deck-review` → `export`. Re-enable by flipping `PAGE_REVIEW_ENABLED = True` in `scripts/run_stage.py`.

The per-item and batch forms are interchangeable; the batch forms are just a thread-pool wrapper around the same underlying functions. For `batch-gen-image`, asset_plan.json writes are serialized under a process-local lock so concurrent workers don't clobber each other's slot status.

### The review → rewrite chain (CURRENTLY DISABLED)

Each page's review is a VLM pass over a rendered 1600×900 screenshot. Its primary job is catching **overflow** (content clipped at the right/bottom edge), plus broken rendering / low contrast / bad image paths. Content is already fixed upstream — the reviewer does NOT touch text, charts, inherited tables, or inherited images.

The pipeline chain:

1. `page-html` / `batch-page-html` → two LLM calls per page:
   - **Step 1 (rewrite):** `prompts/page_html_rewrite.md` converts the structured outline + style_spec + inherited content into a natural-language "query_detailed"-style user prompt (saved to `pages/page_NNN.query.txt` for debugging). All global PPTX constraints (1600×900 canvas, ECharts, relative image paths, single-layer background, `<span>` around text near pseudo decorations, etc.) are folded into the natural-language query.
   - **Step 2 (generate):** `prompts/page_html.md` is a minimal 3-line system prompt ("输出完整 HTML，不加解释"). It receives the rewritten query as the user message and returns the final `<!DOCTYPE html>...</html>`.
   This replaces the previous monolithic page_html prompt (constraint-heavy schema). The rewriter owns all constraints; the generator just renders a natural-language spec.
2. `page-review` / `batch-page-review` → renders the page, calls VLM with the screenshot, writes `pages/page_NNN.review.md` starting with `VERDICT: NEEDS_REWRITE` or `VERDICT: CLEAN`. For NEEDS_REWRITE, the bullets name the offending selector + the defect.
3. `page-rewrite` / `batch-page-rewrite` → **runs only on pages whose review is NEEDS_REWRITE**. `batch-page-rewrite` filters by verdict automatically; the per-item `page-rewrite` short-circuits with `skipped=true` if the review is CLEAN. The rewriter ALSO gets the screenshot + outline + style_spec, so it can visually match each review bullet to a CSS change. After rewrite, the page is re-screenshotted so `screenshots/page_NNN.png` reflects the AFTER state.
4. There is **no second review pass** — one rewrite per page max (spec rule).

If you want to rerun the review/rewrite on a specific page, delete its `pages/page_NNN.review.md` and re-invoke `page-review` (then `page-rewrite` if needed).

## Output on each exec

Every subcommand prints ONE json line to stdout on success:

```json
{"status": "ok", "page_no": 3, "slot_id": "hero", "path": "images/page_003_hero.png"}
```

Or on failure (exit code 1):

```json
{"status": "failed", "error": "<reason>", "page_no": 3, "slot_id": "hero"}
```

Agent: parse this, echo a one-line Chinese progress message to the user, move on. For `gen-image` failure specifically: **don't retry**, don't substitute, just echo the failure — the HTML stage will redesign around it.

## Progress echo — MANDATORY

Between tool_calls, emit short Chinese progress lines to keep the user informed. Minimum cadence:

| Stage | Example |
|---|---|
| After preflight | `已进入 ppt-standard，共 N 页` |
| After style | `[1/10] style_spec.json ✓ 主色 #2D5BFF` |
| After outline | `[2/10] outline.json ✓ 10 页` |
| After asset-plan | `[3/10] asset_plan.json ✓ 14 槽位` |
| Per gen-image | `[图 5/14] page_003/hero ✓` or `[图 5/14] page_003/hero ✗ 服务端 502` |
| After all gen-image | `图片生成阶段完成：成功 12，失败 2` |
| Per page-html | `[页 3/10] HTML ✓` |
| Per page-review | `[页 3/10] review: NEEDS_REWRITE` or `CLEAN` |
| Per page-rewrite | `[页 3/10] rewrite ✓` |
| After deck-review | `review.md ✓` |
| After export | `PPTX ✓ (10/10 页)` or `PPTX 失败: ...` |

No page / slot iteration happens INSIDE a single tool_call — so every message is the agent's own turn, and the user sees steady progress. **Silence for more than ~30 seconds = a bug.**

## Resume semantics

The script is stateless w.r.t. resume — re-run a subcommand and it'll overwrite its output artifact. The agent decides what to skip by listing files in `<deck_dir>`:

- `style_spec.json` exists → skip `style`
- `outline.json` exists → skip `outline`
- `asset_plan.json` exists → skip `asset-plan` (but any slot whose `local_path` file doesn't exist or `status != "ok"` still needs `gen-image`)
- `pages/page_NNN.html` exists → skip `page-html` for that page
- `pages/page_NNN.review.md` exists → skip `page-review` for that page
- `review.md` exists → skip `deck-review`
- `<deck_id>.pptx` exists → skip `export`

Users can force a rerun of any stage by deleting the corresponding artifact. The agent should start every session with a quick `ls <deck_dir>` to decide what's left.

## Env

Configured via `.env` at the repo root (or `<repo>/skills/.env`). `model_client.py` auto-loads both locations. Required:

- `U1_LM_API_KEY`, `U1_LM_BASE_URL`, `U1_LM_MODEL` (or per-kind overrides `LLM_*` / `VLM_*`)
- `U1_API_KEY`, `U1_IMAGE_GEN_BASE_URL` (or `U1_BASE_URL`), `U1_IMAGE_GEN_MODEL`

Optional `LLM_TIMEOUT` / `VLM_TIMEOUT` / `U1_IMAGE_GEN_TIMEOUT` override default timeouts.

Run `python $SKILL_DIR/lib/model_client.py health` to verify env and ping LLM once before running the pipeline.

## Export PPTX gate

The Node converter (`scripts/export_pptx/html_to_pptx.mjs`) is invoked with `--force` — we skip its built-in motif / real-photo gates because (a) this skill doesn't use the motif protocol, (b) failed image slots are handled at the page-html stage via layout redesign. PPTX still produces even if some slots are missing images.

If the converter crashes (Playwright error, corrupted HTML, etc.) `run_stage.py export` returns `status: "failed"` and the skill ends with `review.md` as the only deliverable. That's acceptable — review.md still summarizes the deck.

## Does NOT

- Does not call `u1-image-base`. At all.
- Does not call any external search API.
- Does not retry failed LLM / VLM / T2I calls.
- Does not write progress to disk (no `timing.json`).
- Does not hide failures behind placeholder artifacts.
