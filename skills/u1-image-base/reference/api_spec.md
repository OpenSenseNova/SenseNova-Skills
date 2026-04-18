# u1-image-base API Specification

## Table of Contents

- [u1-image-generate](#u1-image-generate)
- [u1-image-recognize](#u1-image-recognize)
- [u1-text-optimize](#u1-text-optimize)
- [Error Handling](#error-handling)

---

## u1-image-generate

Image generation tool that calls the U1 text-to-image-no-enhance API.

### Command Format

```bash
python openclaw_runner.py u1-image-generate \
    --prompt <string> \
    [--api-key <string>] \
    [--base-url <string>] \
    [--negative-prompt <string>] \
    [--image-size 1k|2k] \
    [--aspect-ratio <string>] \
    [--seed <int>] \
    [--unet-name <string>] \
    [--poll-interval <float>] \
    [--timeout <float>] \
    [--insecure] \
    [--output-format text|json] \
    [--save-path <path>]
```

### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `--prompt` | string | **Yes** | - | Text prompt |
| `--api-key` | string | No | Reads `U1_API_KEY` env var | API Key (CLI takes precedence; raises `MissingApiKeyError` if both are empty) |
| `--negative-prompt` | string | No | `""` | Negative prompt |
| `--image-size` | string | No | `"2k"` | Image size: `1k` or `2k` |
| `--aspect-ratio` | string | No | `"16:9"` | Aspect ratio |
| `--seed` | int | No | `None` | Random seed (for reproducibility) |
| `--unet-name` | string | No | `None` | UNet model name |
| `--poll-interval` | float | No | `5.0` | Polling interval in seconds |
| `--timeout` | float | No | `300.0` | Timeout in seconds |
| `--insecure` | flag | No | `False` | Disable TLS verification |
| `--output-format` | string | No | `"text"` | Output format: `text` or `json` |
| `--save-path` | path | No | Auto-generated | Output image path |

### Aspect Ratio Options

`2:3`, `3:2`, `3:4`, `4:3`, `4:5`, `5:4`, `1:1`, `16:9`, `9:16`, `21:9`, `9:21`

### Output Path

Default output: `/tmp/openclaw-u1-image/t2i_<timestamp>.png`

### Response Examples

**text format**:

```
Image generated successfully
/tmp/openclaw-u1-image/t2i_20260414_120000.png
```

**json format**:

```json
{
  "status": "ok",
  "output": "/tmp/openclaw-u1-image/t2i_20260414_120000.png",
  "task_id": "task_xxx",
  "message": "Image generated successfully",
  "elapsed_seconds": 1.23
}
```

### API Key Notes

`--api-key` is optional. CLI parameter takes precedence; if not provided, reads from `U1_API_KEY` env var. If both are empty, raises `MissingApiKeyError`:

**text format**:

```
Error: API key is required but was not provided. Set the U1_API_KEY environment variable or pass --api-key explicitly.
```

**json format**:

```json
{"status": "failed", "error": "API key is required but was not provided. Set the U1_API_KEY environment variable or pass --api-key explicitly.", "elapsed_seconds": 0.05}
```

---

## u1-image-recognize

Image recognition tool that uses a VLM (Vision Language Model) to analyze image content.

### Command Format

```bash
python openclaw_runner.py u1-image-recognize \
    (--user-prompt <string> | --user-prompt-path <path>) \
    --images <string> [<string> ...] \
    --api-key <string> \
    --base-url <string> \
    --model <string> \
    [--system-prompt <string>] \
    [--system-prompt-path <path>] \
    [--vlm-type openai-completions|anthropic-messages] \
    [--output-format text|json]
```

### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `--user-prompt` | string | One of two | - | User instruction (mutually exclusive with `--user-prompt-path`) |
| `--user-prompt-path` | path | One of two | - | Local file path to read user instruction from (mutually exclusive with `--user-prompt`) |
| `--images` | string[] | **Yes** | - | List of image paths (supports multiple) |
| `--api-key` | string | No | No hardcoded default | CLI > `VLM_API_KEY` > `U1_LM_API_KEY`; raises `MissingApiKeyError` if all are empty |
| `--base-url` | string | No | No hardcoded default | CLI > `VLM_BASE_URL` > `U1_LM_BASE_URL`; raises error if neither is set |
| `--model` | string | No | No hardcoded default | CLI > `VLM_MODEL` env var; raises error if neither is set |
| `--system-prompt` | string | No | `""` | System instruction (mutually exclusive with `--system-prompt-path`) |
| `--system-prompt-path` | path | No | - | Local file path to read system instruction from (mutually exclusive with `--system-prompt`) |
| `--vlm-type` | string | No | `openai-completions` | CLI > `VLM_TYPE` env var > built-in default |
| `--output-format` | string | No | `"text"` | Output format: `text` or `json` |

`--vlm-type` options:

- `openai-completions`: OpenAI-compatible `/v1/chat/completions` endpoint
- `anthropic-messages`: Anthropic Messages `/v1/messages` endpoint

### Response Examples

**text format**:

```
This image shows an adorable orange cat napping in the sunlight.
```

**json format**:

```json
{
  "status": "ok",
  "result": "This image shows an adorable orange cat napping in the sunlight.",
  "model": "sensenova-122b",
  "base_url": "http://127.0.0.1:615",
  "interface_type": "openai-completions",
  "elapsed_seconds": 2.15
}
```

### Parameter Priority

`--api-key`, `--base-url`, `--model`, and `--vlm-type` all follow a two-level priority: **CLI parameter > environment variable** (no built-in defaults except `--vlm-type`; must be provided via one of the two methods).

| Parameter | Built-in Default | Environment Variable |
|-----------|-----------------|---------------------|
| `--api-key` | None (required) | `VLM_API_KEY` (primary) -> `U1_LM_API_KEY` (fallback) |
| `--base-url` | None (required) | `VLM_BASE_URL` (primary) -> `U1_LM_BASE_URL` (fallback) |
| `--model` | None (required) | `VLM_MODEL` |
| `--vlm-type` | `openai-completions` | `VLM_TYPE` |

---

## u1-text-optimize

Text optimization tool that uses an LLM (Language Model) to optimize text content.

### Command Format

```bash
python openclaw_runner.py u1-text-optimize \
    (--user-prompt <string> | --user-prompt-path <path>) \
    --api-key <string> \
    --base-url <string> \
    --model <string> \
    [--system-prompt <string>] \
    [--system-prompt-path <path>] \
    [--llm-type openai-completions|anthropic-messages] \
    [--output-format text|json]
```

### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `--user-prompt` | string | One of two | - | User instruction (mutually exclusive with `--user-prompt-path`) |
| `--user-prompt-path` | path | One of two | - | Local file path to read user instruction from (mutually exclusive with `--user-prompt`) |
| `--api-key` | string | No | No hardcoded default | CLI > `LLM_API_KEY` > `U1_LM_API_KEY`; raises `MissingApiKeyError` if all are empty |
| `--base-url` | string | No | No hardcoded default | CLI > `LLM_BASE_URL` > `U1_LM_BASE_URL`; raises error if neither is set |
| `--model` | string | No | No hardcoded default | CLI > `LLM_MODEL` env var; raises error if neither is set |
| `--system-prompt` | string | No | `""` | System instruction (mutually exclusive with `--system-prompt-path`) |
| `--system-prompt-path` | path | No | - | Local file path to read system instruction from (mutually exclusive with `--system-prompt`) |
| `--llm-type` | string | No | `openai-completions` | CLI > `LLM_TYPE` env var > built-in default |
| `--output-format` | string | No | `"text"` | Output format: `text` or `json` |

`--llm-type` options:

- `openai-completions`: OpenAI-compatible `/v1/chat/completions` endpoint
- `anthropic-messages`: Anthropic Messages `/v1/messages` endpoint

### Response Examples

**text format**:

```
Optimized text content...
```

**json format**:

```json
{
  "status": "ok",
  "result": "Optimized text content...",
  "model": "sensenova-122b",
  "base_url": "http://127.0.0.1:615",
  "interface_type": "openai-completions",
  "elapsed_seconds": 0.83
}
```

### Parameter Priority

`--api-key`, `--base-url`, `--model`, and `--llm-type` all follow a two-level priority: **CLI parameter > environment variable** (`--llm-type` has a built-in default of `openai-completions`; other parameters have no built-in defaults and must be provided via one of the two methods).

| Parameter | Built-in Default | Environment Variable |
|-----------|-----------------|---------------------|
| `--api-key` | None (required) | `LLM_API_KEY` (primary) -> `U1_LM_API_KEY` (fallback) |
| `--base-url` | None (required) | `LLM_BASE_URL` (primary) -> `U1_LM_BASE_URL` (fallback) |
| `--model` | None (required) | `LLM_MODEL` |
| `--llm-type` | `openai-completions` | `LLM_TYPE` |

---

## Error Handling

### Error Types

| Type | Source | Trigger | Output Format |
|------|--------|---------|---------------|
| `MissingApiKeyError` | Custom business exception | API Key not provided for `u1-image-generate` | text: `Error: ...` / json: `{"status": "failed", "error": "..."}` |
| `ValueError` (prompt) | `_resolve_prompt` | `--user-prompt` and `--user-prompt-path` both provided, neither provided, or file read failure | text: `Error: ...` / json: `{"status": "failed", "error": "..."}` |
| argparse missing param | argparse standard error | Missing required parameters for `u1-image-recognize`/`u1-text-optimize` | `usage: ...` + exit 2 |
| HTTP error | httpx request layer | API returns non-2xx status code | `{"status": "failed", "error": "HTTP NNN", "message": "..."}` |
| Request exception | httpx request layer | Network error, timeout, etc. | `{"status": "failed", "error": "<ExceptionType>", "message": "..."}` |

### text format

Error messages are written to stderr and do not affect stdout content.

### json format

```json
{
  "status": "failed",
  "error": "error type",
  "message": "detailed error message",
  "elapsed_seconds": 0.05
}
```

---

## API Key Environment Variables

| Tool | Environment Variables (high → low priority) | Notes |
|------|---------------------------------------------|-------|
| `u1-image-generate` | `U1_API_KEY` | CLI takes precedence; reads this var if not provided; raises `MissingApiKeyError` if both are empty |
| `u1-image-recognize` | `VLM_API_KEY` → `U1_LM_API_KEY` | CLI > `VLM_API_KEY` > `U1_LM_API_KEY`; raises `MissingApiKeyError` if all are empty |
| `u1-text-optimize` | `LLM_API_KEY` → `U1_LM_API_KEY` | CLI > `LLM_API_KEY` > `U1_LM_API_KEY`; raises `MissingApiKeyError` if all are empty |

`U1_LM_API_KEY` is the shared fallback for both VLM and LLM, suitable for configuring a unified SenseNova internal key in `.env`. `VLM_API_KEY` / `LLM_API_KEY` can independently override their respective keys when needed.
