---
name: sn-infographic
description: |
  Generates professional infographics with various layout types and visual styles.
  Analyzes content, recommends layout and style, and generates publication-ready infographics.
  Use when user asks to create "infographic", "信息图", "visual summary", or "可视化".
metadata:
  project: SenseNova-Skills
  tier: 1
  category: scene
  priority: 9
  user_visible: true
triggers:
  - "infographic"
  - "information graphic"
  - "infographics generation"
  - "visual summary"
  - "data visualization"
  - "visual explanation"
  - "diagram"
  - "生成信息图"
  - "信息图生成"
  - "生成 infographic"
  - "信息图表"
  - "图表生成"
  - "数据可视化"
  - "图解"
---

# sn-infographic

Info graphic generation scene skill (tier 1), relying on the `sn-image-generate`, `sn-image-recognize`, and `sn-text-optimize` tools provided by `sn-image-base` (tier 0).

Features:

- Evaluation of prompt quality (auto mode)
- Prompt expansion (force/auto mode)
- Multiple rounds of image generation and VLM review
- Output the best result based on quality ranking

## Input Specification

| Parameter | Type | Default Value | Description |
|-----------|------|---------------|-------------|
| `user_prompt` | string | **Required** | User original request |
| `max_rounds` | int | `1` | Maximum number of generation rounds |
| `output_mode` | string | `friendly` | Output mode: friendly / verbose |
| `prompts_expand_mode` | string | `auto` | expand strategy: auto / force / disable |

## API Configuration

All API calls in this skill are executed through the `sn_agent_runner.py` of the `sn-image-base` skill, with authentication parameters using default values (CLI > environment variables > built-in defaults),无需显式传入。

| Call Type | Tool | Authentication Parameters | Description |
|-----------|------|---------------------------|-------------|
| **LLM** | sn-text-optimize (evaluation/expansion) | Default reads `SN_TEXT_API_KEY` / `SN_CHAT_API_KEY` environment variables | Built-in default points to Sensenova internal network service |
| **VLM** | sn-image-recognize (image review) | Default reads `SN_VISION_API_KEY` / `SN_CHAT_API_KEY` environment variables | Built-in default points to Sensenova internal network service |
| **Image Generation** | sn-image-generate | Default reads `SN_IMAGE_GEN_API_KEY` environment variable | Default uses image generation configuration of `sn-image-base` |

**When encountering `MissingApiKeyError` or needing to specify a model**: pass explicitly via CLI parameters, parameter reference `$SN_IMAGE_BASE/references/api_spec.md`.

**`$SN_IMAGE_BASE` path explanation**: `$SN_IMAGE_BASE` is the installation directory of the `sn-image-base` skill (`SKILL.md` exists).
The agent can locate this path by skill name `sn-image-base` in the list of installed skills.

## Architecture: Main Agent + Worker Agent

This skill uses a two-tier agent architecture:

| Role | Responsibility |
|------|----------------|
| **Main Agent** | Receive user request, normalize parameters, send preflight, start Worker, collect results, send text and images to user |
| **Worker Agent** | Execute orchestration loop (expand → multiple rounds of generation + review → sort), return structured JSON |

**Responsibility Boundaries**:

- Worker Agent **does not send any messages to the user directly**, only returns structured JSON
- Main Agent is responsible for sending all user-visible messages
- Worker Agent's last message **must be and only be** the JSON string defined in the Return Contract
- Worker Agent's internal VLM calls **always execute directly**, without spawning subagents

## Workflow

### Main Agent Workflow

1. Extract `user_prompt`, `max_rounds` (default 1), `output_mode` (default `friendly`), and `prompts_expand_mode` (default `auto`) from user request
2. Send uniform preflight message: `"Using sn-infographic skill to generate infographic, please wait..."`
3. Start Worker Agent (Sub-Agent), passing in complete parameters and working directory
4. When Worker Agent returns `status=ok` and `need_main_agent_send=true`:
   - **max_rounds = 1**: Send a one-sentence description of the image content, then send the rank=1 single image
   - **max_rounds > 1, friendly mode**: Generate a one-sentence natural language description based on `result` and `violations`, send the evaluation text, then send the rank=1 single image
   - **max_rounds > 1, verbose mode**: Send complete text summary message, then send all images in rank order to the user
5. If Worker Agent returns `status=error`, report the real `error` field content to the user

### Worker Agent Workflow

Worker Agent receives `user_prompt`, `max_rounds`, `output_mode`, `prompts_expand_mode`, and the working directory of this skill (`SN_IMAGE_INFOG`).

#### Step 0 — Initialization

1. Generate `task_id` (using timestamp, format `YYYYMMDD_HHMMSS`)
2. Create a uniform temporary directory: `/tmp/openclaw/sn-infographic/<task_id>/` as `TEMP_DIR`
3. Initialize an empty `rounds` list
4. Infer `aspect_ratio` (default `16:9`) and `image_size` (default `2k`) from `user_prompt` based on the rules in `$SKILL_DIR/references/runtime-parameters.md`

#### Step 1 — `prompts_expand_mode` Processing

**`disable` mode**:

- Skip expand, directly use `user_prompt` as `expanded_prompt`
- Assign variable and write to temporary directory:

  ```bash
  EXPANDED_PROMPT="$USER_PROMPT"
  echo "$EXPANDED_PROMPT" > "$TEMP_DIR/expanded-prompt.txt"
  ```

- Record `prompts_expand_skipped = true`

**`force` mode**:

- Directly execute Step 2

**`auto` mode**:

1. Call sn-text-optimize for evaluation
2. Parse JSON, extract `required_results` and `optional_results`
3. Determine logic:
   - `required_pass`: All `answer` in `required_results` are `"yes"`
   - `optional_pass`: The number of `answer="yes"` in `optional_results` / total ≥ 0.6
   - `should_expand = not (required_pass and optional_pass)`
4. If JSON parsing fails, default `should_expand = true` (conservative strategy)
5. If `should_expand = false`: Skip Step 2, assign variable and write to temporary directory, record `prompts_expand_skipped = true`:

   ```bash
   EXPANDED_PROMPT="$USER_PROMPT"
   echo "$EXPANDED_PROMPT" > "$TEMP_DIR/expanded-prompt.txt"
   ```

6. If `should_expand = true`: Execute Step 2

**Evaluation Call** (using `sn-image-base`'s `sn-text-optimize` tool):

```bash
python "$SN_IMAGE_BASE/scripts/sn_agent_runner.py" sn-text-optimize \
  --system-prompt-path "$SKILL_DIR/references/evaluation-standard.md" \
  --user-prompt "$USER_PROMPT" \
  --output-format json
```

#### Step 2 — Content Analysis + Layout & Style Selection + Prompt Expansion

**2.0 Content Analysis** (using `sn-image-base`'s `sn-text-optimize` tool):

```bash
ANALYSIS=$(python "$SN_IMAGE_BASE/scripts/sn_agent_runner.py" sn-text-optimize \
  --system-prompt-path "$SKILL_DIR/references/analysis-framework.md" \
  --user-prompt "$USER_PROMPT" \
  --output-format json)
```

Save analysis result stdout to `analysis.json` in temporary directory `$TEMP_DIR/analysis.json`:

```bash
echo "$ANALYSIS" > "$TEMP_DIR/analysis.json"
```

**2.1 Layout & Style Selection**

1. Read analysis result from temporary directory `$TEMP_DIR/analysis.json`;

  ```bash
  ANALYSIS=$(cat "$TEMP_DIR/analysis.json")
  ```

2. Based on `data_type`, `tone`, `audience`, select `layout` and `style` based on the rules in `$SKILL_DIR/references/layout-style-selection.md`;
3. Read layout/style definition files:

  ```bash
  LAYOUT_DEF=$(cat "$SKILL_DIR/references/layouts/<layout>.md")
  STYLE_DEF=$(cat "$SKILL_DIR/references/styles/<style>.md")
  ```

  If file does not exist, fallback to `hub-spoke` + `corporate-memphis`.

4. Save selection result to temporary directory: `$TEMP_DIR/layout-style.json`;

Format of `layout-style.json`:

```json
{
  "layout": "<layout>",
  "style": "<style>"
}
```

**2.2 Structured Content Generation**

Read analysis result and structured content template, convert `user_prompt` into a design-ready structured content based on the template rules:

```bash
ANALYSIS=$(cat "$TEMP_DIR/analysis.json")
LAYOUT_STYLE=$(cat "$TEMP_DIR/layout-style.json")
STRUCTURED_CONTENT_TEMPLATE=$(cat "$SKILL_DIR/references/structured-content-template.md")
```

Follow the three phases defined in the template (High-Level Outline → Section Development → Data Integrity Check),
combine the learning objectives, visual opportunities, and key data in `analysis.json`, generate structured content, and save it to the temporary directory:

```bash
cat > "$TEMP_DIR/structured-content.md" << 'EOF'
<Content generated based on structured-content-template.md format>
EOF
```

**Rules**: All data must be preserved exactly. Do not rewrite. Do not add information that is not in the source.

**2.3 Prompt Expansion** (using `sn-image-base`'s `sn-text-optimize` tool):

Read structured content and layout/style selection from temporary directory, dynamically concatenate system prompt, and write to temporary file:

```bash
STRUCTURED_CONTENT=$(cat "$TEMP_DIR/structured-content.md")
LAYOUT_STYLE=$(cat "$TEMP_DIR/layout-style.json")
LAYOUT=$(echo "$LAYOUT_STYLE" | jq -r '.layout')
STYLE=$(echo "$LAYOUT_STYLE" | jq -r '.style')
LAYOUT_DEF=$(cat "$SKILL_DIR/references/layouts/${LAYOUT}.md")
STYLE_DEF=$(cat "$SKILL_DIR/references/styles/${STYLE}.md")

cat > "$TEMP_DIR/expand-system-prompt.md" << EOF
$(cat "$SKILL_DIR/references/prompts-expand-system.md")

---

## Selected Layout: $LAYOUT

$LAYOUT_DEF

---

## Selected Style: $STYLE

$STYLE_DEF

---

## Output Template Reference

$(cat "$SKILL_DIR/references/base-prompt.md")
EOF
```

Use the content of `structured-content.md` as user-prompt, read system prompt from temporary file and call sn-text-optimize:

```bash
python "$SN_IMAGE_BASE/scripts/sn_agent_runner.py" sn-text-optimize \
  --system-prompt-path "$TEMP_DIR/expand-system-prompt.md" \
  --user-prompt "$STRUCTURED_CONTENT" \
  --output-format json
```

Parse JSON stdout, extract `result` field as `expanded_prompt`, and write to temporary directory:

```bash
echo "$EXPANDED_PROMPT" > "$TEMP_DIR/expanded-prompt.txt"
```

If parsing fails or truncation is suspected (the returned content is incomplete), notify the user and terminate the workflow.

#### Step 3 — Image Generation Loop

Execute `round` from `1` to `max_rounds` sequentially:

**Generate Image** (using `sn-image-base`'s `sn-image-generate` tool):

```bash
python "$SN_IMAGE_BASE/scripts/sn_agent_runner.py" sn-image-generate \
  --prompt "$EXPANDED_PROMPT" \
  --image-size "$IMAGE_SIZE" \
  --aspect-ratio "$ASPECT_RATIO" \
  --save-path "$TEMP_DIR/round_<N>.png" \
  -o json
```

**Review Image** (only executed when `max_rounds > 1`):

VLM configuration requirements:

- When `max_rounds > 1`, call VLM for review
- Select VLM model from OpenClaw configuration as parameter for image recognition
- If no suitable VLM model exists in OpenClaw configuration:
  - Notify user that current parameter combination cannot be executed
  - Suggest adding VLM configuration or changing max_rounds to 1 to avoid VLM calls
- If VLM call times out or fails: do not fallback, report the real error directly

```bash
python "$SN_IMAGE_BASE/scripts/sn_agent_runner.py" sn-image-recognize \
  --system-prompt-path "$SN_IMAGE_INFOG/references/prompts-critic-system.md" \
  --user-prompt "Evaluate the diagram in the image against the rules. Output your assessment." \
  --images "$TEMP_DIR/round_<N>.png" \
  --output-format json
```

System prompt comes from `references/prompts-critic-system.md`, user prompt is provided directly.

**Save Round Result**：

```json
{
  "round": 1,
  "image": "$TEMP_DIR/round_1.png",
  "result": "PASS|FAIL",
  "violations_count": 0,
  "violations": [],
  "reasoning": "<Reasoning process, empty string when max_rounds=1>",
  "timing": {
    "image_generation": { "elapsed_seconds": 12.34, "model": "sn_image_model" },
    "vlm_review": { "elapsed_seconds": 5.67, "model": "sensenova-6.7-flash-lite" }
  }
}
```

Note: `elapsed_seconds` is read from the `--output-format json` return of each CLI call; `image_generation.model` is fixed to the hardcoded placeholder `"sn_image_model"` (sn-image-generate does not return the model field); `vlm_review.model` is read from the JSON return of sn-image-recognize. `timing.vlm_review` is omitted when `max_rounds=1`.

**Early Termination Check** (only executed when `max_rounds > 1`):

- If `result=PASS`, immediately exit the loop, do not continue generating
- If `result=FAIL`, continue to the next round (if there are remaining rounds)

#### Step 4 — Image Quality Ranking

Sort images by `violations_count` ascending + `round` ascending, return structured JSON to Main Agent.

### Return Contract

After Worker Agent completes, its last message must be and only be the following JSON string (bare JSON, no code fences, no preceding or trailing text).

**Normal Flow:**

```json
{
  "status": "ok",
  "need_main_agent_send": true,
  "output_mode": "friendly|verbose",
  "expanded_prompt": "<always contains when output_mode=verbose; value is original user_prompt when prompts_expand_skipped=true, otherwise is expanded result>",
  "prompts_expand_skipped": true,
  "early_terminated": true,
  "timing": {
    "total_elapsed_seconds": 35.12,
    "prompt_detection": { "elapsed_seconds": 2.11, "model": "sensenova-6.7-flash-lite" },
    "content_analysis": { "elapsed_seconds": 3.22, "model": "sensenova-6.7-flash-lite" },
    "prompt_expand": { "elapsed_seconds": 8.45, "model": "sensenova-6.7-flash-lite" }
  },
  "rounds": [
    {
      "round": 1,
      "image": "$TEMP_DIR/round_1.png",
      "result": "PASS|FAIL",
      "violations_count": 0,
      "violations": [],
      "reasoning": "<Reasoning process, empty string when max_rounds=1>",
      "timing": {
        "image_generation": { "elapsed_seconds": 12.34, "model": "sn_image_model" },
        "vlm_review": { "elapsed_seconds": 5.67, "model": "sensenova-6.7-flash-lite" }
      }
    }
  ]
}
```

**Error Flow:**

```json
{
  "status": "error",
  "error": "<Actual error information>"
}
```

**Rules:**

- `status=ok` must contain `need_main_agent_send: true`
- `expanded_prompt` must contain when `output_mode=verbose`; value is original `user_prompt` when `prompts_expand_skipped=true`
- `prompts_expand_skipped` must contain when expand is not executed (value is `true`), covering two cases: `prompts_expand_mode=disable` and `prompts_expand_mode=auto` and evaluation passes and skip expand
- `early_terminated` must contain when early termination (value is `true`), omitted when normal execution completes
- `violations` is an array of strings, from review results
- `reasoning` is an empty string when `max_rounds=1`
- Top-level `timing` contains:
  - `total_elapsed_seconds`: Worker Agent's wall time from Step 0 to returning JSON, calculated by Worker Agent itself
  - `prompt_detection`: Step 1 evaluation call, containing `elapsed_seconds` and `model` (read from sn-text-optimize JSON return); omitted when `prompts_expand_mode=disable`
  - `content_analysis`: Step 2.0 content analysis call, containing `elapsed_seconds` and `model` (read from sn-text-optimize JSON return); omitted when expand is skipped
  - `prompt_expand`: Step 2.3 prompt expansion call, containing `elapsed_seconds` and `model` (read from sn-text-optimize JSON return); omitted when expand is skipped
- `rounds[].timing.image_generation.model` is fixed to the hardcoded placeholder `"sn_image_model"`
- `rounds[].timing.vlm_review` is omitted when `max_rounds=1`

## Output Format

### friendly mode (default)

**Text Summary:**

- **when `max_rounds = 1`**: Generate a one-sentence description of the image content based on `expanded_prompt`,不超过50字
- **when `max_rounds > 1`**: Generate a one-sentence description of the image content based on `result` and `violations`,不超过50字：
  - `result=PASS`: Describe in a positive tone
  - `result=FAIL` (1-2 violations): Gently point out specific issues
  - `result=FAIL` (3 or more): Objectively summarize the main issues

**Image**: rank=1 best single image

### verbose mode

```
Quality ranking result (high -> low)
---
Expanded prompt: [expanded | not expanded, using original prompt]
<expanded_prompt>
---
#1 round=<n> result=<PASS|FAIL> violations=<n> [early terminated]
#2 round=<n> result=<PASS|FAIL> violations=<n>
...
---
Time statistics: Total <total>s | Prompt evaluation <t>s | Content analysis <t>s | Prompt expansion <t>s | Image generation <t>s×<n> rounds | VLM review <t>s×<n> rounds
---
Images (sent in rank order)
```

## Call Relationship

- Bottom-level dependency: `sn-image-base` → `sn-image-generate`, `sn-image-recognize`, `sn-text-optimize`

## References

- `references/analysis-framework.md` - Analysis methodology
- `references/base-prompt.md` - Prompt template
- `references/evaluation-standard.md` - Evaluation standard
- `references/layout-style-selection.md` - Layout and style selection rules
- `references/prompts-expand-system.md` - Prompt expansion system prompt
- `references/prompts-critic-system.md` - Prompt critic system prompt
- `references/runtime-parameters.md` - Runtime parameters
- `references/structured-content-template.md` - Structured content template
- `references/layouts/<layout>.md` - Layout definitions (87 layouts)
- `references/styles/<style>.md` - Style definitions (66 styles)
