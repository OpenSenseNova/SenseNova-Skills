---
name: ppt-creative
description: |
  Creative-mode PPT pipeline. One full-page 16:9 PNG per slide, generated via
  u1-image-generate with a per-page composed prompt. Expects task_pack.json +
  info_pack.json already written by ppt-entry.
metadata:
  project: SenseNova-Skills
  tier: 1
  category: scene
  user_visible: false
triggers:
  - "ppt-creative"
---

# ppt-creative

## Preconditions

- `<deck_dir>/task_pack.json` exists and `ppt_mode == "creative"`
- `<deck_dir>/info_pack.json` exists
- `<deck_dir>/pages/` exists

Any missing -> stop and tell user to enter via `/skill ppt-entry`.

## Resume first

Always run `scripts/resume_scan.py --deck-dir <deck_dir>` as step 1.
Read the manifest; dispatch based on what's present:

```bash
python <SKILL_DIR>/scripts/resume_scan.py --deck-dir <deck_dir>
# => {"style_spec_done": true/false, "outline_done": true/false,
#     "pages": [{"action": "skip|render_only|full"}, ...]}
```

### Dispatch table

| Manifest state | Do |
|---|---|
| `style_spec_done == false` | Run Stage 2 |
| `style_spec_done == true`, `outline_done == false` | Run Stage 3 |
| Both true | For each page: run Stage 4 per the per-page `action` |

Within "Stage 4", per-page `action` further drives:
- `full` -> run 4.1 (compose prompt) + 4.2 (generate image)
- `render_only` -> run 4.2 only (prompt.txt already on disk)
- `skip` -> do nothing

## timing.json (shared with ppt-entry)

Step 1 of entry already ran `timing_helper.py init`; this skill does NOT re-init.
After every stage completes, record wall-clock seconds via the helper; per-page
stages also record per-page fields. See
`<PPT_ENTRY_DIR>/scripts/timing_helper.py` and the contract in
`<PPT_ENTRY_DIR>/references/conventions.md`.

## Stage 2 — style_spec.md

Trigger: `style_spec_done == false`.

- Branch A (no reference images, or all ref images missing on disk):

```bash
python <U1_IMAGE_BASE>/u1_image_base/openclaw_runner.py u1-text-optimize \
  --system-prompt-path <SKILL_DIR>/prompts/style_from_query.md \
  --user-prompt "<JSON of info_pack.query_normalized + task_pack.params>" \
  --output-format json
```

- Branch B (has at least one reference image that exists on disk):

```bash
python <U1_IMAGE_BASE>/u1_image_base/openclaw_runner.py u1-image-recognize \
  --system-prompt-path <SKILL_DIR>/prompts/style_from_image.md \
  --user-prompt "PPT 主题: <topic>; 配合参考图产出风格 spec" \
  --images /abs/path/ref1.png /abs/path/ref2.png \
  --output-format json
```

Take `result` field (markdown body) -> write to `<deck_dir>/style_spec.md`.

If `info_pack.user_assets.reference_images` is non-empty but all paths missing
on disk: degrade to Branch A and record a line
`reference_images_missing: <original paths>` at the top of style_spec.md.

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
  --user-prompt "<cat style_spec.md + JSON of info_pack.query_normalized + task_pack.params>" \
  --output-format json
```

Extract `result` -> parse as JSON (the prompt enforces strict JSON; page_count
must match). Write to `<deck_dir>/outline.json`.

On failure (non-JSON / empty): **abort** (structural artifact).

Timing: `record-stage --stage outline --seconds <elapsed>`.

## Stage 4 — per-page prompt + image (sequential)

For each page where `action != "skip"`:

### 4.1 Compose prompt (skip when `action == "render_only"`)

```bash
python <U1_IMAGE_BASE>/u1_image_base/openclaw_runner.py u1-text-optimize \
  --system-prompt-path <SKILL_DIR>/prompts/page_prompt.md \
  --user-prompt "<cat style_spec.md + JSON of outline.pages[i]>" \
  --output-format json
```

Take `result` (prose) -> write to `<deck_dir>/pages/page_{NNN}.prompt.txt`
(absolute path).

### 4.2 Generate image

```bash
python <U1_IMAGE_BASE>/u1_image_base/openclaw_runner.py u1-image-generate \
  --prompt "$(cat <deck_dir>/pages/page_{NNN}.prompt.txt)" \
  --aspect-ratio 16:9 \
  --image-size 2k \
  --save-path <deck_dir>/pages/page_{NNN}.png \
  --output-format json
```

### 4.3 Failure handling

- 4.1 failure (model timeout / empty / malformed): skip this page, record `page_no` into an in-memory `failed_pages`, continue
- 4.2 failure: same — skip, record, continue
- No retries; the prompt.txt may remain on disk for later manual re-run of 4.2

Timing per page: record with `record-page` for `prompt_seconds` (4.1) and
`image_gen_seconds` (4.2); accumulate with `record-stage` for `style` /
`outline` / `image_generate`.

## Stage 5 — closing

Emit a closing summary per spec §8.2:

```
创意模式已完成。

📁 输出目录：<deck_dir>
📄 结果文件：
  - style_spec.md
  - outline.json
  - pages/page_001.png ~ page_NNN.png（失败 M 页：page_..., page_...）

⚠️ 未完成：
  - page_007：生图返回超时，已跳过；可重新调用 ppt-creative 对该页单独重试

⏱️ 耗时统计：
  - 总计：...
  - 风格：...
  - 大纲：...
  - 逐页出图：...

下一步：
  - 可直接在 pages/ 目录查看 PNG
```

Read `<deck_dir>/timing.json` for the stats.

## Progress echo

- Start: one line — mode, deck_dir, page_count
- Stage 2 / Stage 3: one line each on completion
- Stage 4: one line every 3 pages (not every page)
- Closing: the full summary above

## Does NOT

- Do not call any model endpoint directly — always via `openclaw_runner.py`
- Do not parallelize page rendering
- Do not retry on first failure
- Do not generate editable JSON from the PNG (out of scope this version)
