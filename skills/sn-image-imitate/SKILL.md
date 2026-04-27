---
name: sn-image-imitate
description: |
  Generates a new image that imitates the style of a reference image while updating content based on user intent.
  Uses a three-stage pipeline: image annotation (long caption), caption rewriting, and image generation.
  Use when user asks to "imitate style", "保持这个风格重画", "按这张图风格生成", or "style transfer with new content".
metadata:
  project: SenseNova-Skills
  tier: 1
  category: scene
  priority: 8
  user_visible: true
triggers:
  - "style imitation"
  - "style transfer"
  - "imitate this image style"
  - "use this style with new content"
  - "reference style image"
  - "风格模仿"
  - "风格迁移"
  - "模仿这张图风格"
  - "按参考图风格生成"
---

# sn-image-imitate

Image style imitation scene skill (tier 1), relying on the `sn-image-recognize`, `sn-text-optimize`, and `sn-image-generate` tools provided by `sn-image-base` (tier 0).

Features:

- Extracts high-fidelity long caption from a reference image
- Rewrites caption according to user requested content change while preserving style and layout
- Enforces layout-lock constraints during caption rewrite
- Performs post-generation layout consistency review and bounded retries
- Returns structured process artifacts for debugging and reproducibility

## Non-goals

- Pure neural style transfer without content change (use dedicated style-transfer tools instead)
- Local editing / inpainting of specific regions within the reference image
- Processing video or animation input (only single static images are supported)
- Batch generation from multiple reference images in one invocation
- Guaranteeing pixel-level fidelity to the reference; the skill targets layout and style consistency, not exact reproduction

## Input Specification

- `reference_image` (string, required): local path or URL of the style reference image
- `target_content` (string, required): new content user wants in the generated image
- `output_mode` (string, default `friendly`): output mode, `friendly` or `verbose`
- `aspect_ratio` (string, default `16:9`): output aspect ratio for generation
- `image_size` (string, default `2k`): output image size preset
- `max_attempts` (int, default `3`): maximum generation attempts for meeting layout consistency
- `layout_threshold` (float, default `0.75`): minimum layout similarity score to accept result

## Environment Variable

Dependency installation and API key configuration are for [sn-image-base](../sn-image-base/SKILL.md) skill.

The minimum environment variables to configure `sn-image-base` skill running with [SenseNova Token Plan](https://platform.sensenova.cn/token-plan):

```ini
SN_IMAGE_GEN_API_KEY="your-api-key"
SN_CHAT_API_KEY="your-api-key"
```

Please refer to the **Python dependencies and API keys** section in [`sn-image-generate_en.md`](../../docs/sn-image-generate_en.md) for more configurations.

## API Configuration

All API calls in this skill are executed through the `sn_agent_runner.py` of the `sn-image-base` skill,
please refer to the `sn-image-base` skill ([README.md](../sn-image-base/README.md)) for more details.

- **VLM call**: `sn-image-recognize` (Step 1 & 3)
- **LLM call**: `sn-text-optimize` (Step 2)
- **Image generation call**: `sn-image-generate` (Step 3)

**When encountering `MissingApiKeyError` or needing explicit model control**: pass model and auth params explicitly via CLI arguments. See `$SN_IMAGE_BASE/references/api_spec.md`.

**`$SN_IMAGE_BASE` path explanation**: `$SN_IMAGE_BASE` is the installation directory of the `sn-image-base` skill (`SKILL.md` exists). The agent can locate this path by skill name `sn-image-base`.

## Architecture: Main Agent + Worker Agent

This skill uses a two-tier agent architecture:

- **Main Agent**: receives user request, normalizes parameters, sends preflight, invokes Worker Agent, and sends final text/image to user
- **Worker Agent**: executes fixed 3-step pipeline and returns structured JSON

**Responsibility Boundaries**:

- Worker Agent does not send any user-visible message directly
- Main Agent sends all user-facing responses
- Worker Agent last message must be and only be the JSON string defined in Return Contract
- Worker Agent executes VLM/LLM/image calls directly; no nested subagent for these low-level calls

## Workflow

### Main Agent Workflow

1. Extract `reference_image`, `target_content`, `output_mode` (default `friendly`), `aspect_ratio` (default `16:9`), `image_size` (default `2k`), `max_attempts` (default `3`), and `layout_threshold` (default `0.75`)
2. Validate required inputs:
   - `reference_image` is provided and resolvable
   - `target_content` is non-empty
3. Send preflight message: `"Using sn-image-imitate skill to generate a style-consistent image, please wait..."`
4. Start Worker Agent with full normalized parameters and working directory
5. On Worker result:
   - `status=ok`: send final summary and generated image
   - `status=error`: report the actual error

### Worker Agent Workflow

Worker Agent receives `reference_image`, `target_content`, `output_mode`, `aspect_ratio`, `image_size`, `max_attempts`, `layout_threshold`, and the working directory of this skill (`$SKILL_DIR`).

**Error Handling Strategy**:

All `sn_agent_runner.py` calls share the same error handling rules:

- If the subprocess exits with non-zero code, crashes, or times out: do not fallback, return `status=error` with the actual error message from stderr or the system error string
- If the subprocess returns invalid JSON or the JSON lacks an expected `result` field: return `status=error`, do not silently continue with empty or default values
- If the VLM review call fails during Step 3, treat the attempt as incomplete: do not record a score, and either retry the review once or skip to the next attempt depending on remaining budget

#### Step 0 — Initialization

1. Generate `task_id` with format `YYYYMMDD_HHMMSS`
2. Create temp directory: `/tmp/openclaw/sn-image-imitate/<task_id>/` as `TEMP_DIR`
3. Resolve and normalize `REFERENCE_IMAGE`
4. Persist user request:

```bash
echo "$TARGET_CONTENT" > "$TEMP_DIR/target-content.txt"
```

#### Step 1 — Image Annotation (long caption + layout blueprint)

Use `prompts/image_annotate.md` as system prompt and call `sn-image-recognize` on reference image.

```bash
python "$SN_IMAGE_BASE/scripts/sn_agent_runner.py" sn-image-recognize \
  --system-prompt-path "$SKILL_DIR/prompts/image_annotate.md" \
  --user-prompt "Please annotate this reference image and follow the required output format." \
  --images "$REFERENCE_IMAGE" \
  --output-format json
```

Parse JSON `result`, then parse three blocks:

- `SHORT_CAPTION: ...`
- `LONG_CAPTION: ...`
- `LAYOUT_BLUEPRINT_JSON: { ... }`

If parsing fails, `LONG_CAPTION` is empty, or `LAYOUT_BLUEPRINT_JSON` is invalid JSON, return `status=error`.

Persist outputs:

```bash
echo "$SHORT_CAPTION" > "$TEMP_DIR/reference-short-caption.txt"
echo "$LONG_CAPTION" > "$TEMP_DIR/reference-long-caption.txt"
echo "$LAYOUT_BLUEPRINT_JSON" > "$TEMP_DIR/layout-blueprint.json"
```

#### Step 2 — New long caption generation (content rewrite with layout lock)

Goal: preserve style/layout/visual language from reference long caption while replacing core content by `target_content`.

Hard constraints to preserve (guided by `layout-blueprint.json`):

- visual hierarchy (title/subtitle/body emphasis order)
- region topology (number of major blocks and their relative positions)
- reading flow (left-to-right / top-to-bottom / radial / timeline direction)
- chart type and data encoding form (if present)
- spacing rhythm and alignment pattern
- major region bounding boxes and topological relations from blueprint

**Preferred system prompt**: `prompts/caption_rewrite.md` (recommended to add).
If missing, use inline fallback system prompt:

`Rewrite the long caption by preserving style and layout constraints while replacing semantic content according to user target. Do not change block topology, reading order, or visual hierarchy. Keep the caption detailed and directly usable for image generation.`

Call `sn-text-optimize`:

```bash
python "$SN_IMAGE_BASE/scripts/sn_agent_runner.py" sn-text-optimize \
  --system-prompt-path "$SKILL_DIR/prompts/caption_rewrite.md" \
  --user-prompt "Reference long caption:\n$LONG_CAPTION\n\nLayout blueprint JSON:\n$LAYOUT_BLUEPRINT_JSON\n\nTarget content:\n$TARGET_CONTENT\n\nReturn only the rewritten long caption." \
  --output-format json
```

Parse JSON `result` as `NEW_LONG_CAPTION`. If empty, return `status=error`.

Persist output:

```bash
echo "$NEW_LONG_CAPTION" > "$TEMP_DIR/new-long-caption.txt"
```

#### Step 3 — Image Generation and Layout Review Loop

Execute `attempt` from `1` to `max_attempts` sequentially:

**Generate Image** (using `sn-image-base`'s `sn-image-generate` tool):

```bash
python "$SN_IMAGE_BASE/scripts/sn_agent_runner.py" sn-image-generate \
  --prompt "$CURRENT_PROMPT" \
  --aspect-ratio "$ASPECT_RATIO" \
  --image-size "$IMAGE_SIZE" \
  --save-path "$TEMP_DIR/attempt_<N>.png" \
  --output-format json
```

VLM configuration requirements:

- When `max_attempts > 1`, VLM review is required for each attempt
- Select VLM model from OpenClaw configuration as parameter for image recognition
- If no suitable VLM model exists in OpenClaw configuration:
  - Notify user that current parameter combination cannot be executed
  - Suggest adding VLM configuration or setting `max_attempts` to `1` to skip review
- If VLM call times out or fails: do not fallback, report the real error directly

**Layout Consistency Review** (only executed when `max_attempts > 1`):

Review candidate vs reference using `prompts/layout_review.md` (with blueprint as structural oracle):

```bash
python "$SN_IMAGE_BASE/scripts/sn_agent_runner.py" sn-image-recognize \
  --system-prompt-path "$SKILL_DIR/prompts/layout_review.md" \
  --user-prompt "Reference is image[0], candidate is image[1]. Layout blueprint JSON:\n$LAYOUT_BLUEPRINT_JSON\n\nEvaluate layout similarity and return JSON only." \
  --images "$REFERENCE_IMAGE" "$TEMP_DIR/attempt_<N>.png" \
  --output-format json
```

Expected review JSON (inside `result`):

```json
{
  "layout_similarity_score": 0.0,
  "style_similarity_score": 0.0,
  "pass": false,
  "major_deviations": [],
  "fix_hints": []
}
```

**Save Attempt Result**:

```json
{
  "attempt": 1,
  "image": "$TEMP_DIR/attempt_1.png",
  "layout_similarity_score": 0.0,
  "style_similarity_score": 0.0,
  "pass": false,
  "major_deviations": [],
  "timing": {
    "image_generation": { "elapsed_seconds": 12.34, "model": "sn_image_model" },
    "vlm_review": { "elapsed_seconds": 5.67, "model": "sensenova-122b" }
  }
}
```

Note: `elapsed_seconds` is read from the `--output-format json` return of each CLI call; `image_generation.model` is fixed to the hardcoded placeholder `"sn_image_model"` (sn-image-generate does not return the model field); `vlm_review.model` is read from the JSON return of sn-image-recognize. `timing.vlm_review` is omitted when `max_attempts=1`.

**Early Termination Check** (only executed when `max_attempts > 1`):

Pass criteria:

- `layout_similarity_score >= layout_threshold`
- `pass = true`

- If pass: immediately exit the loop, do not continue generating
- If fail and attempts remain, append correction hints to prompt:

```text
Layout correction requirements:
- <fix_hint_1>
- <fix_hint_2>
...
```

- If all attempts fail to pass threshold, return highest-score candidate and mark `layout_passed=false`

## Return Contract

Worker Agent final response must be bare JSON (no extra text, no code fence).

### Normal Flow

```json
{
  "status": "ok",
  "need_main_agent_send": true,
  "output_mode": "friendly|verbose",
  "result": {
    "image": "/tmp/openclaw/sn-image-imitate/<task_id>/attempt_2.png",
    "reference_image": "<resolved_reference_image>",
    "reference_short_caption": "<short caption from step 1>",
    "reference_long_caption": "<long caption from step 1>",
    "layout_blueprint": { "...": "..." },
    "new_long_caption": "<rewritten long caption from step 2>",
    "layout_passed": true,
    "selected_attempt": 2
  },
  "attempts": [
    {
      "attempt": 1,
      "image": "/tmp/openclaw/sn-image-imitate/<task_id>/attempt_1.png",
      "layout_similarity_score": 0.62,
      "style_similarity_score": 0.79,
      "pass": false,
      "major_deviations": ["center panel too narrow", "title block moved to top-right"]
    },
    {
      "attempt": 2,
      "image": "/tmp/openclaw/sn-image-imitate/<task_id>/attempt_2.png",
      "layout_similarity_score": 0.81,
      "style_similarity_score": 0.84,
      "pass": true,
      "major_deviations": []
    }
  ],
  "review": {
    "threshold": 0.75
  },
  "timing": {
    "total_elapsed_seconds": 24.56,
    "annotate": { "elapsed_seconds": 3.21, "model": "sensenova-122b" },
    "rewrite": { "elapsed_seconds": 2.45, "model": "sensenova-122b" },
    "generation_total": { "elapsed_seconds": 11.90, "model": "sn_image_model" },
    "review_total": { "elapsed_seconds": 7.00, "model": "sensenova-122b" }
  }
}
```

### Error Flow

```json
{
  "status": "error",
  "error": "<actual_error_message>"
}
```

Rules:

- `status=ok` must include `need_main_agent_send: true`
- `result.image` must be an existing generated image path
- `timing.total_elapsed_seconds` covers full worker execution
- If parsing of Step 1 format fails (including invalid blueprint JSON), return `status=error` (do not silently continue)
- `attempts` must record each generation + review attempt
- If no attempt passes threshold, return highest-score candidate and set `result.layout_passed=false`

## Output Format

### friendly mode (default)

- One concise sentence: generated image follows reference style and updates to requested content
- Mention whether layout consistency passed threshold and attempt count
- Send single image: `result.image`

### verbose mode

```
Style imitation result
---
Reference short caption: <reference_short_caption>
---
Style/layout cues:
<brief extraction from reference_long_caption + layout_blueprint>
---
New long caption:
<new_long_caption>
---
#1 attempt=<n> layout_score=<0.00> style_score=<0.00> pass=<true|false> [selected]
  deviations: <major_deviations or none>
#2 attempt=<n> layout_score=<0.00> style_score=<0.00> pass=<true|false>
  deviations: <major_deviations or none>
...
---
Layout threshold: <0.75> | Passed: <true|false> | Selected: attempt <n>
Time statistics: Total <total>s | Annotation <t>s | Rewrite <t>s | Generation <t>s×<n> attempts | Review <t>s×<n> attempts
---
Images (selected image)
```

## Call Relationship

- Bottom-level dependency: `sn-image-base` → `sn-image-recognize`, `sn-text-optimize`, `sn-image-generate`

## References

- `prompts/image_annotate.md` - Image annotation + layout blueprint system prompt (Step 1, required)
- `prompts/caption_rewrite.md` - Caption rewrite system prompt with layout-lock constraints (Step 2, required)
- `prompts/layout_review.md` - Candidate-vs-reference layout/style review prompt (Step 3, required)
- `../sn-image-base/SKILL.md` - Base tool behavior and parameter defaults
