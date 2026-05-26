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
| `user_prompt` | string | **Required** | Original user request. UTF-8 text; may include Markdown, URLs, or structured data. Length bounded only by the underlying LLM context budget. |
| `max_rounds` | int | `1` | Maximum number of generation rounds. Valid range: `1`–`8`. When `max_rounds=1`, the Step 3 VLM review and the early-termination check are both skipped. |
| `output_mode` | string | `friendly` | `friendly`: one-line content description + rank=1 single image |
|               |        |               | `verbose`: full quality ranking + timing stats + all images (ordered by rank) |
| `prompts_expand_mode` | string | `auto` | `auto`: evaluate `user_prompt` quality first; enter Step 2 expansion only when it falls short |
|                       |        |          | `force`: skip evaluation, always execute Step 2 expansion |
|                       |        |          | `disable`: skip Step 2, use `user_prompt` directly as `expanded_prompt` |
| `aspect_ratio` | string | *inferred* (`16:9`) | Set by **Main Agent** when the user states an explicit supported ratio (e.g. `16:9` / `9:16`, optionally via `宽高比` / `画面比例` / `aspect ratio`); otherwise left unset and the **Worker** infers it in Step 0 from `user_prompt` (orientation / scene cues) per `references/runtime-parameters.md`. |
| `image_size` | string | *inferred* (`2k`) | Set by **Main Agent** when the user states an explicit size (`2k` / `4k`); otherwise the **Worker** infers it in Step 0 (currently a single option, `2k`). `4k` is forwarded to the model and may be rejected (e.g. sensenova) → surfaced as an error. |

> **Who extracts what:** Main Agent parameter extraction resolves `max_rounds`, `output_mode`, `prompts_expand_mode`, and `aspect_ratio` / `image_size` (each only when the user gives an explicit value). `aspect_ratio` and `image_size` without an explicit value are inferred by the Worker in Step 0.

## API Configuration

All API calls in this skill are executed through the `sn_agent_runner.py` of the `sn-image-base` skill, with authentication parameters using default values (CLI > environment variables > built-in defaults),无需显式传入。

| Call Type | Tool | Authentication Parameters | Description |
|-----------|------|---------------------------|-------------|
| **LLM** | sn-text-optimize (evaluation/expansion) | Default reads `SN_TEXT_API_KEY` -> `SN_CHAT_API_KEY` -> `SN_API_KEY` | Built-in default points to Sensenova internal network service |
| **VLM** | sn-image-recognize (image review) | Default reads `SN_VISION_API_KEY` -> `SN_CHAT_API_KEY` -> `SN_API_KEY` | Built-in default points to Sensenova internal network service |
| **Image Generation** | sn-image-generate | Default reads `SN_IMAGE_GEN_API_KEY` -> `SN_API_KEY`; `SN_IMAGE_GEN_API_KEY` is only needed for image-specific override | Default uses image generation configuration of `sn-image-base` |

**When encountering `MissingApiKeyError` or needing to specify a model**: pass explicitly via CLI parameters, parameter reference `$SN_IMAGE_BASE/references/api_spec.md`.

**`$SN_IMAGE_BASE` path explanation**: `$SN_IMAGE_BASE` is the installation directory of the `sn-image-base` skill (`SKILL.md` exists).
The agent can locate this path by skill name `sn-image-base` in the list of installed skills.

## Architecture: Main Agent + Worker Agent

This skill uses a two-tier agent architecture:

| Role | Responsibility |
|------|----------------|
| **Main Agent** | Receive user request, normalize parameters, send preflight, start Worker, collect results, send text and images to user |
| **Worker Agent** | Execute the generation pipeline (expand → multiple rounds of generation + review → sort), return structured JSON |

**Responsibility Boundaries**:

- Worker Agent **does not send any messages to the user directly**, only returns structured JSON
- Main Agent is responsible for sending all user-visible messages
- Worker Agent's last message **must be and only be** the JSON string defined in the Return Contract
- Worker Agent's internal VLM calls **always execute directly**, without spawning subagents

## Workflow

### Main Agent Workflow

1. **Parameter extraction** from the user request, in three passes:
   1. **Inline KV directives** — parse tokens of the form `key=value` where `key` ∈ {`max_rounds`, `output_mode`, `prompts_expand_mode`, `aspect_ratio`, `image_size`}; strip recognized tokens from the user message, and the remainder becomes `user_prompt`. Example: `"生成一张信息图 max_rounds=3 output_mode=verbose"` → `user_prompt="生成一张信息图"`, `max_rounds=3`, `output_mode=verbose`.
   2. **Keyword recognition** (case-insensitive, applied to the stripped text) — fill any parameter not yet set by inline KV using the table below:

      | Parameter | Trigger keywords | Resolved value |
      |-----------|------------------|----------------|
      | `output_mode` | `verbose`, `详细`, `详尽`, `完整统计` | `verbose` |
      |               | `friendly`, `简洁`, `精简` | `friendly` |
      | `max_rounds` | `N 轮`, `N rounds`, `重试 N 次` (parse `N`) | `N`, clamped to `[1, 8]` |
      | `prompts_expand_mode` | `强制扩写`, `force expand`, `force expansion` | `force` |
      |                       | `不扩写`, `跳过扩写`, `disable expansion`, `no expand` | `disable` |
      | `aspect_ratio` | an explicit supported ratio (`16:9` `9:16` `4:3` `3:4` `1:1` `2:3` `3:2` `4:5` `5:4` `21:9` `9:21`), with or without a `宽高比` / `画面比例` / `比例` / `aspect ratio` lead-in | that ratio (validated against the supported set in `runtime-parameters.md`; unsupported value → leave unset for Worker inference) |
      | `image_size` | an explicit supported size (`2k` `4k`), with or without an `image_size` / `分辨率` / `清晰度` / `image size` lead-in | that size (vague quality words like `高清` / `超清` do **not** count); unsupported value → leave unset for Worker inference |

   3. **Defaults** — any parameter still unset falls back to `max_rounds=1`, `output_mode=friendly`, `prompts_expand_mode=auto`. `aspect_ratio` and `image_size` have **no** Main-Agent default: when no explicit value is detected they are left unset for the Worker to infer in Step 0.

   Precedence: **inline KV > keyword recognition > default**. Values from inline KV are validated against the Input Specification (out-of-range `max_rounds` clamped to `[1, 8]`; unrecognized enum values fall back to default and Main Agent should log the mismatch).
2. Send uniform preflight message: `"Using sn-infographic skill to generate infographic, please wait..."`
3. Start Worker Agent (Sub-Agent), passing in complete parameters and working directory
4. When Worker Agent returns `status=ok` and `need_main_agent_send=true`:
   - **max_rounds = 1**: Generate the Text Summary (see Output Format → friendly mode for length/language rules) from `expanded_prompt` in the returned JSON (always present for `status=ok`, see Return Contract), send it, then send the rank=1 single image
   - **max_rounds > 1, friendly mode**: Generate the Text Summary based on the rank=1 round's `result` and `violations`, send it, then send the rank=1 single image
   - **max_rounds > 1, verbose mode**: Render the verbose template (see Output Format → verbose mode for substitution rules) and send it, then send all images in rank order
5. If Worker Agent returns `status=error`, report the real `error` field content to the user

### Worker Agent Workflow

Worker Agent receives `user_prompt`, `max_rounds`, `prompts_expand_mode`, an optional `aspect_ratio` and `image_size` (each set only when the user gave an explicit value), and the working directory of this skill (`SKILL_DIR`). (`output_mode` stays on the Main Agent side — Worker has no branch that depends on it.)

#### Worker Environment

Variables referenced as `$NAME` in the bash snippets below. Worker must bind each before the step that consumes it.

| Variable | Source | Used by |
|----------|--------|---------|
| `USER_PROMPT` | Main Agent input — original user request | Step 1 evaluation; Step 2.0 content analysis |
| `MAX_ROUNDS` | Main Agent input (default `1`) | Step 3 loop bound; early-termination gate |
| `PROMPTS_EXPAND_MODE` | Main Agent input (default `auto`) | branches Step 1 |
| `SKILL_DIR` | Agent runtime resolves the current skill's install path (e.g. `~/.openclaw/skills/sn-infographic`, `~/.hermes/skills/sn-infographic`) | reads `references/*` |
| `SN_IMAGE_BASE` | Agent runtime resolves by skill name `sn-image-base` in the installed-skill registry | runs `scripts/sn_agent_runner.py` |
| `TASK_ID` | Step 0 (`date +%Y%m%d_%H%M%S`) | uniqueness token |
| `TEMP_DIR` | Step 0 (`/tmp/openclaw/sn-infographic/${TASK_ID}`) | scratch dir for all intermediate artifacts |
| `IMAGE_SIZE` | Main Agent input when the user stated an explicit size, else Step 0 inference from `USER_PROMPT` (single option, `2k`) | `sn-image-generate --image-size` |
| `ASPECT_RATIO` | Main Agent input when the user stated an explicit ratio, else Step 0 inference from `USER_PROMPT` (default `16:9`) | `sn-image-generate --aspect-ratio` |
| `EXPANDED_PROMPT` | Step 1 (copy of `USER_PROMPT` when Step 2 is skipped) or Step 2.3 (expanded result) | `sn-image-generate --prompt` |
| `LAYOUT`, `STYLE` | Step 2.1 selection result (with fallback to `hub-spoke` / `corporate-memphis`) | Step 2.3 system-prompt assembly |
| `ROUND` | Step 3 loop counter (`for ROUND in $(seq 1 "$MAX_ROUNDS")`) | per-round file naming (`round_${ROUND}.png`) |

**Naming**: `$SKILL_DIR` for own files; `$SN_<SKILL_NAME>` (e.g. `$SN_IMAGE_BASE`) for cross-skill references.

**JSON parsing**: every `sn_agent_runner.py ... -o json` call prints a JSON *envelope* on stdout (`{"status", "result", "model", ...}`; diagnostics go to stderr). A failed call sets `status` to a non-`ok` value (e.g. `failed`) and omits `result`, so **always confirm `.status == ok` on the envelope before reading `.result`** — otherwise a missing `.result` surfaces as the literal `null`, which is itself valid JSON and slips past both `jq -r` and `extract_json.py` (no error raised). The LLM's own JSON (evaluation / analysis steps) lives inside the `result` string and may carry stray prose or ` ```json ` fences. Before any `jq`, pipe the runner output through `$SN_IMAGE_BASE/scripts/extract_json.py` (reads stdin, prints the recovered JSON, exits non-zero when none is found); for steps that parse the inner LLM/VLM JSON, pipe `.result` through it as well. A non-`ok` status or a non-zero `extract_json.py` exit means the response is unusable → return the Error Flow JSON.

#### Step 0 — Initialization

1. Generate `task_id` (timestamp, format `YYYYMMDD_HHMMSS`) and create the uniform temporary directory `/tmp/openclaw/sn-infographic/<task_id>/` as `TEMP_DIR`. `TEMP_DIR` must exist before any subsequent step writes to it:

   ```bash
   TASK_ID=$(date +%Y%m%d_%H%M%S)
   TEMP_DIR="/tmp/openclaw/sn-infographic/${TASK_ID}"
   mkdir -p "$TEMP_DIR"
   ```

2. Initialize an empty `rounds` list
3. Resolve `aspect_ratio` and `image_size` (bind to `ASPECT_RATIO` / `IMAGE_SIZE`): use the explicit Main Agent value when present, else infer from `user_prompt` per `$SKILL_DIR/references/runtime-parameters.md`. Defaults: `aspect_ratio` → `16:9`; `image_size` inference currently has a single option, `2k`.

#### Step 1 — Decide whether to rewrite the image prompt (always runs)

This step decides whether to **rewrite/expand the user's image-generation `prompt` text** before Step 3 generates the image, and produces the boolean `should_expand`. When Step 2 is skipped it also sets `EXPANDED_PROMPT` and records `prompts_expand_skipped = true`.

**Scope (do not over-read the step name).** "Expand" here means *rewriting the text prompt for image generation*, nothing more. This is **not** task decomposition, plan generation, or a plan-review gate, and Step 1 starts no agents of its own — it is a single `sn-text-optimize` call made by the Worker itself. Do not map it onto any `subagent-driven-development` / `delegate_task`-style workflow, and write no plan files. (The Worker is the only sub-agent this skill uses, started once by the Main Agent; the Worker spawns none of its own — see Responsibility Boundaries.)

`PROMPTS_EXPAND_MODE` is the **already-resolved input** handed over by the Main Agent — Step 1 *acts on* it, it does **not** re-parse the user request. Resolving the mode value (Main Agent parameter extraction) and running this decision are two different jobs: completing the former does **not** complete Step 1. **Do not skip this step**; in `auto` mode the evaluation call below is mandatory — never infer `should_expand` from the prompt's apparent quality.

Only **Step 2 (prompt expansion)** is ever skipped, and only when this step decides so. The branch depends on `PROMPTS_EXPAND_MODE`:

**`auto` mode** (default):

1. Run the evaluation call (mandatory). The inner evaluation JSON lives inside `.result`; its schema is `$SKILL_DIR/references/evaluation-standard.md` (`required_results`, `optional_results`).

   ```bash
   EVAL_ENVELOPE=$(python "$SN_IMAGE_BASE/scripts/sn_agent_runner.py" sn-text-optimize \
     --system-prompt-path "$SKILL_DIR/references/evaluation-standard.md" \
     --user-prompt "$USER_PROMPT" \
     --output-format json | python "$SN_IMAGE_BASE/scripts/extract_json.py")

   # A failed runner envelope (status != ok) carries no .result.
   EVAL_STATUS=$(printf '%s' "$EVAL_ENVELOPE" | jq -r '.status')

   EVAL=$(printf '%s' "$EVAL_ENVELOPE" | jq -r '.result' \
     | python "$SN_IMAGE_BASE/scripts/extract_json.py")
   ```

2. Decide `should_expand`:
   - `required_pass`: all `answer` in `required_results` are `"yes"`
   - `optional_pass`: count of `answer="yes"` in `optional_results` / total ≥ 0.6
   - `should_expand = not (required_pass and optional_pass)`
3. **Conservative fallback**: if `EVAL_STATUS` is not `ok` (the evaluation call itself failed) or `extract_json.py` exits non-zero, default `should_expand = true`. Unlike Steps 2.0 / 2.3, a failed evaluation does **not** abort the Worker — `auto` falls back to expanding.
4. If `should_expand = true`: execute Step 2.
5. If `should_expand = false`: skip Step 2, set `EXPANDED_PROMPT` to the original prompt, record `prompts_expand_skipped = true`:

   ```bash
   EXPANDED_PROMPT="$USER_PROMPT"
   echo "$EXPANDED_PROMPT" > "$TEMP_DIR/expanded-prompt.txt"
   ```

**`force` mode**:

- Skip the evaluation, always execute Step 2 (expansion is mandatory).
- `prompts_expand_skipped` is **not** recorded — the field appears in the Return JSON only when Step 2 is skipped (see Return Contract rules).

**`disable` mode**:

- Skip both the evaluation and Step 2; use `user_prompt` directly as `expanded_prompt`:

  ```bash
  EXPANDED_PROMPT="$USER_PROMPT"
  echo "$EXPANDED_PROMPT" > "$TEMP_DIR/expanded-prompt.txt"
  ```

- Record `prompts_expand_skipped = true`.

#### Step 2 — Content Analysis + Layout & Style Selection + Prompt Expansion

**2.0 Content Analysis** (using `sn-image-base`'s `sn-text-optimize` tool):

```bash
ANALYSIS_ENVELOPE=$(python "$SN_IMAGE_BASE/scripts/sn_agent_runner.py" sn-text-optimize \
  --system-prompt-path "$SKILL_DIR/references/analysis-framework.md" \
  --user-prompt "$USER_PROMPT" \
  --output-format json | python "$SN_IMAGE_BASE/scripts/extract_json.py")
```

Save the **inner** analysis JSON from `.result` (not the envelope, so Step 2.1 can `jq` `data_type` / `tone` / `audience` directly) to `$TEMP_DIR/analysis.json`. The guard below rejects a failed envelope first (status not `ok` or `extract_json.py` non-zero → Error Flow with `.error`):

```bash
# A failed runner envelope (status != ok) has no .result → return Error Flow.
if [ "$(printf '%s' "$ANALYSIS_ENVELOPE" | jq -r '.status')" != "ok" ]; then
  ANALYSIS_ERROR=$(printf '%s' "$ANALYSIS_ENVELOPE" | jq -r '.error')
  # return Error Flow JSON {"status":"error","error":"$ANALYSIS_ERROR"} to Main Agent and stop
fi

printf '%s' "$ANALYSIS_ENVELOPE" | jq -r '.result' \
  | python "$SN_IMAGE_BASE/scripts/extract_json.py" > "$TEMP_DIR/analysis.json"
```

Schema: `$SKILL_DIR/references/analysis-framework.md` (defines `data_type`, `tone`, `audience`, and the other fields consumed by Step 2.1 / 2.2).

**2.1 Layout & Style Selection**

This is a **name-level, weighted-random pick** from the candidate tables in `$SKILL_DIR/references/layout-style-selection.md`; it operates purely on layout/style **names**. **Do NOT open any file under `references/layouts/` or `references/styles/` here**, and do not "compare options" to choose a best fit — the pick is random, not reasoned over file contents. The one selected layout file and one selected style file are read exactly once, later, in Step 2.3.

1. Read analysis result from temporary directory `$TEMP_DIR/analysis.json`;

  ```bash
  ANALYSIS=$(cat "$TEMP_DIR/analysis.json")
  ```

2. From `data_type` / `tone` / `audience`, run the candidate lookup + weighted-random sampling defined in `$SKILL_DIR/references/layout-style-selection.md` to obtain one `LAYOUT` name and one `STYLE` name (names only — no file reads);
3. Validate the selection by checking the definition files exist (existence only via `[ -f ]`, still no reading); fall back to `hub-spoke` + `corporate-memphis` if missing:

  ```bash
  [ -f "$SKILL_DIR/references/layouts/${LAYOUT}.md" ] || LAYOUT=hub-spoke
  [ -f "$SKILL_DIR/references/styles/${STYLE}.md" ] || STYLE=corporate-memphis
  ```

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

Structure: `$SKILL_DIR/references/structured-content-template.md`.

**Rules**: All data must be preserved exactly. Do not rewrite. Do not add information that is not in the source.

**2.3 Prompt Expansion** (using `sn-image-base`'s `sn-text-optimize` tool):

Read layout/style selection, then assemble the system prompt by **direct file concatenation** (do not use heredocs — layout/style files contain backticks and `$(...)` that an unquoted heredoc body would execute):

```bash
LAYOUT=$(jq -r '.layout' "$TEMP_DIR/layout-style.json")
STYLE=$(jq -r '.style' "$TEMP_DIR/layout-style.json")

{
  cat "$SKILL_DIR/references/prompts-expand-system.md"
  printf '\n\n---\n\n## Selected Layout: %s\n\n' "$LAYOUT"
  cat "$SKILL_DIR/references/layouts/${LAYOUT}.md"
  printf '\n\n---\n\n## Selected Style: %s\n\n' "$STYLE"
  cat "$SKILL_DIR/references/styles/${STYLE}.md"
  printf '\n\n---\n\n## Output Template Reference\n\n'
  cat "$SKILL_DIR/references/base-prompt.md"
} > "$TEMP_DIR/expand-system-prompt.md"
```

Use the content of `structured-content.md` as user-prompt (passed via `--user-prompt-path` to avoid argv-length and quoting issues), read system prompt from temporary file and call sn-text-optimize:

```bash
EXPAND_ENVELOPE=$(python "$SN_IMAGE_BASE/scripts/sn_agent_runner.py" sn-text-optimize \
  --system-prompt-path "$TEMP_DIR/expand-system-prompt.md" \
  --user-prompt-path "$TEMP_DIR/structured-content.md" \
  --output-format json | python "$SN_IMAGE_BASE/scripts/extract_json.py")
```

Extract the `result` field as `expanded_prompt` and write to temporary directory. Here `.result` is the expanded prompt **text** (not JSON), so only the envelope is parsed via `extract_json.py`. Confirm `.status == ok` first: a failed envelope has no `.result`, so `jq -r '.result'` would yield the literal string `null` and write `"null"` as the image prompt:

```bash
# A failed runner envelope (status != ok) has no .result → return Error Flow.
if [ "$(printf '%s' "$EXPAND_ENVELOPE" | jq -r '.status')" != "ok" ]; then
  EXPAND_ERROR=$(printf '%s' "$EXPAND_ENVELOPE" | jq -r '.error')
  # return Error Flow JSON {"status":"error","error":"$EXPAND_ERROR"} to Main Agent and stop
fi

EXPANDED_PROMPT=$(printf '%s' "$EXPAND_ENVELOPE" | jq -r '.result')
echo "$EXPANDED_PROMPT" > "$TEMP_DIR/expanded-prompt.txt"
```

`expanded-prompt.txt`: single UTF-8 string, passed verbatim to `sn-image-generate --prompt` in Step 3.

Beyond the status guard above, if parsing fails or truncation is suspected (the returned content is incomplete), the Worker must likewise return the Error Flow JSON (`status=error`, real message) and terminate — it must not message the user directly (see Responsibility Boundaries).

#### Step 3 — Image Generation Loop

Execute round `ROUND` from `1` to `max_rounds` sequentially. Inside each iteration set the shell variable `ROUND` to the current round number, and use `${ROUND}` in every path so successive rounds do not overwrite each other:

```bash
for ROUND in $(seq 1 "$MAX_ROUNDS"); do
  # the Generate Image / Review Image / Save Round Result blocks below run inside this loop body
  :
done
```

**Generate Image** (using `sn-image-base`'s `sn-image-generate` tool):

```bash
python "$SN_IMAGE_BASE/scripts/sn_agent_runner.py" sn-image-generate \
  --prompt "$EXPANDED_PROMPT" \
  --image-size "$IMAGE_SIZE" \
  --aspect-ratio "$ASPECT_RATIO" \
  --save-path "$TEMP_DIR/round_${ROUND}.png" \
  -o json
```

**Review Image** (only executed when `max_rounds > 1`):

- If no VLM model is configured: return Error Flow JSON suggesting the user add a VLM configuration or set `max_rounds=1`.
- If the VLM call fails/times out: no fallback; return Error Flow JSON with the real error.

```bash
python "$SN_IMAGE_BASE/scripts/sn_agent_runner.py" sn-image-recognize \
  --system-prompt-path "$SKILL_DIR/references/prompts-critic-system.md" \
  --user-prompt "Evaluate the diagram in the image against the rules. Output your assessment." \
  --images "$TEMP_DIR/round_${ROUND}.png" \
  --output-format json
```

**Map VLM response into the per-round record** (the VLM response schema is defined in `$SKILL_DIR/references/prompts-critic-system.md`; each violation is a four-field object):

- `vlm.result` → `rounds[i].result` (verbatim — `"PASS"` or `"FAIL"`)
- `vlm.violations` → `rounds[i].violations` (passthrough verbatim — array of `{ rule_id, rule_name, detail, revised_description }` objects)
- `len(vlm.violations)` → `rounds[i].violations_count`
- `vlm.reasoning` → `rounds[i].reasoning` (verbatim string passthrough)

When `max_rounds=1` (no VLM call), default the round record to `result="PASS"`, `violations=[]`, `violations_count=0`, `reasoning=""`.

**Save Round Result**：

```json
{
  "round": 1,
  "image": "$TEMP_DIR/round_1.png",
  "result": "PASS|FAIL",
  "violations_count": 1,
  "violations": [
    {
      "rule_id": "5",
      "rule_name": "Illegible Text",
      "detail": "<offending element description>",
      "revised_description": "<suggested fix per the prompts-critic-system.md standards>"
    }
  ],
  "reasoning": "<VLM reasoning, or \"\" when max_rounds=1>",
  "timing": {
    "image_generation": { "elapsed_seconds": 12.34, "model": "sn_image_model" },
    "vlm_review": { "elapsed_seconds": 5.67, "model": "sensenova-6.7-flash-lite" }
  }
}
```

**Early Termination Check** (only executed when `max_rounds > 1`):

- If `result=PASS`, immediately exit the loop, do not continue generating
- If `result=FAIL`, continue to the next round (if there are remaining rounds)

#### Step 4 — Image Quality Ranking

Sort images by `violations_count` ascending + `round` ascending, return structured JSON to Main Agent.

### Return Contract

After Worker Agent completes, its last message must be and only be the following JSON string (bare JSON, no code fences, no preceding or trailing text).

**Notation in the examples below:**

- `<...>` — documentation placeholder; replace with the real value at runtime.
- `A|B` — one of the listed literals; the returned JSON must contain exactly one of them (e.g. `"result": "PASS"` or `"result": "FAIL"`, never the literal string `"PASS|FAIL"`).
- `$VAR` — must be expanded to the resolved value before serialization. For example, `"image": "$TEMP_DIR/round_1.png"` in the schema must be returned as the absolute path actually written by Step 3 (e.g. `"/tmp/openclaw/sn-infographic/20260521_120000/round_1.png"`), never the literal `"$TEMP_DIR/round_1.png"`.
- Conditional fields — every field whose Rules entry says "omitted when …" must be physically absent from the JSON in that case, not present-with-`null`.

**Normal Flow:**

```json
{
  "status": "ok",
  "need_main_agent_send": true,
  "expanded_prompt": "<original user_prompt if prompts_expand_skipped, else expanded result from Step 2.3>",
  "prompts_expand_skipped": true,
  "early_terminated": true,
  "timing": {
    "total_elapsed_seconds": 35.12,
    "prompt_evaluation": { "elapsed_seconds": 2.11, "model": "sensenova-6.7-flash-lite" },
    "content_analysis": { "elapsed_seconds": 3.22, "model": "sensenova-6.7-flash-lite" },
    "prompt_expand": { "elapsed_seconds": 8.45, "model": "sensenova-6.7-flash-lite" }
  },
  "rounds": [
    {
      "round": 1,
      "image": "$TEMP_DIR/round_1.png",
      "result": "PASS|FAIL",
      "violations_count": 1,
      "violations": [
        {
          "rule_id": "5",
          "rule_name": "Illegible Text",
          "detail": "<offending element description>",
          "revised_description": "<suggested fix>"
        }
      ],
      "reasoning": "<VLM reasoning, or \"\" when max_rounds=1>",
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

- `status=ok` must contain `need_main_agent_send: true`.
- `expanded_prompt`: always present in `status=ok`; value is original `user_prompt` when `prompts_expand_skipped=true`, else the Step 2.3 result.
- `prompts_expand_skipped`: present (`true`) only when Step 2 is skipped (`prompts_expand_mode=disable`, or `auto` with passing evaluation); omitted otherwise.
- `early_terminated`: present (`true`) only when Step 3 exited the loop early via a `PASS`; omitted otherwise (including all `max_rounds=1` runs).
- `violations`: array of objects from the VLM response, schema `$SKILL_DIR/references/prompts-critic-system.md` (`rule_id`, `rule_name`, `detail`, `revised_description`). `[]` when `result=PASS` or `max_rounds=1`.
- `violations_count`: `len(violations)`; `0` when `max_rounds=1`.
- `reasoning`: VLM `reasoning` field verbatim; `""` when `max_rounds=1`.
- When `max_rounds=1`, the single round's `result` defaults to `"PASS"` (image delivered without VLM check).
- Top-level `timing`:
  - `total_elapsed_seconds`: Worker wall time from Step 0 to JSON return.
  - `prompt_evaluation`: `{elapsed_seconds, model}` from Step 1 evaluation. Present only when `prompts_expand_mode=auto`.
  - `content_analysis`: `{elapsed_seconds, model}` from Step 2.0. Omitted when `prompts_expand_skipped=true`.
  - `prompt_expand`: `{elapsed_seconds, model}` from Step 2.3. Omitted when `prompts_expand_skipped=true`.
- `rounds[].timing.image_generation.model`: hardcoded `"sn_image_model"` (sn-image-generate returns no model field).
- `rounds[].timing.vlm_review`: omitted when `max_rounds=1`.

## Output Format

### friendly mode (default)

**Text Summary** — a one-sentence description generated by Main Agent. Length: **≤ 50 chars/字** regardless of language (1 Chinese character = 1 unit, 1 ASCII character = 1 unit). Language: follow the dominant language of `user_prompt` (predominantly Chinese → output Chinese; otherwise → output English).

- **when `max_rounds = 1`**: derive the description from `expanded_prompt` (focus on what the infographic depicts).
- **when `max_rounds > 1`**: derive the description from the rank=1 round's `result` and `violations`:
  - `result=PASS`: positive tone.
  - `result=FAIL` (1–2 violations): briefly point out the specific issues.
  - `result=FAIL` (≥ 3 violations): objectively summarize the main issues.

**Image**: rank=1 single image.

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

**Substitution rules:**

| Placeholder | Rule |
|-------------|------|
| `[expanded \| not expanded, using original prompt]` | `not expanded, using original prompt` when `prompts_expand_skipped=true` is present in the Return JSON; otherwise `expanded`. |
| `<expanded_prompt>` | The `expanded_prompt` field from the Return JSON, verbatim. |
| `#k round=<n> result=… violations=…` | One line per entry in `rounds[]`, in rank order (`k = 1..len(rounds)`); `<n>` is `rounds[i].round`. |
| `[early terminated]` | Append **only** to the round that actually triggered early termination (i.e. the `result=PASS` round that cut the loop). Omit on all other lines. If `early_terminated` is absent from the Return JSON, the tag never appears. |
| `Total <total>s` | `timing.total_elapsed_seconds`. Always present. |
| `Prompt evaluation <t>s` | `timing.prompt_evaluation.elapsed_seconds`. **Omit this `\| Prompt evaluation …` segment entirely** when `prompt_evaluation` is absent from the Return JSON. |
| `Content analysis <t>s` | `timing.content_analysis.elapsed_seconds`. Omit the segment entirely when absent. |
| `Prompt expansion <t>s` | `timing.prompt_expand.elapsed_seconds`. Omit the segment entirely when absent. |
| `Image generation <t>s×<n> rounds` | `<t>` = sum of `rounds[].timing.image_generation.elapsed_seconds`; `<n>` = `len(rounds)`. |
| `VLM review <t>s×<n> rounds` | `<t>` = sum of `rounds[].timing.vlm_review.elapsed_seconds` (only over rounds where the field exists); `<n>` = number of rounds with VLM review. Omit the segment entirely when `max_rounds=1` (no VLM review occurred). |
| `Images (sent in rank order)` | Section header; image delivery itself follows the channel conventions of the host runtime. |

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

Read **only the selected** layout/style file (in Step 2.3); never bulk-read these two directories to choose — selection is name-level and random (Step 2.1).
