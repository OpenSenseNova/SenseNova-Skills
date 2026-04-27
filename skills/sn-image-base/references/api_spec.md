# sn-image-base API Specification

## Table of Contents

- [sn-image-generate](#sn-image-generate)
- [sn-image-recognize](#sn-image-recognize)
- [sn-text-optimize](#sn-text-optimize)
- [Error Handling](#error-handling)

---

## sn-image-generate

Image generation tool that calls the configured image generation backend.

### Command Format

```bash
python sn_agent_runner.py sn-image-generate \
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
| `--api-key` | string | No | Reads `SN_IMAGE_GEN_API_KEY` env var | API Key (CLI takes precedence; raises `MissingApiKeyError` if both are empty) |
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

Default output: `/tmp/openclaw-sn-image/t2i_<timestamp>.png`

### Response Examples

**text format**:

```
Image generated successfully
/tmp/openclaw-sn-image/t2i_20260414_120000.png
```

**json format**:

```json
{
  "status": "ok",
  "output": "/tmp/openclaw-sn-image/t2i_20260414_120000.png",
  "task_id": "task_xxx",
  "message": "Image generated successfully",
  "elapsed_seconds": 1.23
}
```

### API Key Notes

`--api-key` is optional. CLI parameter takes precedence; if not provided, reads from `SN_IMAGE_GEN_API_KEY` env var. If both are empty, raises `MissingApiKeyError`:

**text format**:

```
Error: API key is required but was not provided. Set the SN_IMAGE_GEN_API_KEY environment variable or pass --api-key explicitly.
```

**json format**:

```json
{"status": "failed", "error": "API key is required but was not provided. Set the SN_IMAGE_GEN_API_KEY environment variable or pass --api-key explicitly.", "elapsed_seconds": 0.05}
```

---

## sn-image-recognize

Image recognition tool that uses a VLM (Vision Language Model) to analyze image content.

### Command Format

```bash
python sn_agent_runner.py sn-image-recognize \
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
| `--api-key` | string | No | No hardcoded default | CLI > `SN_VISION_API_KEY` > `SN_CHAT_API_KEY`; raises `MissingApiKeyError` if all are empty |
| `--base-url` | string | No | `https://token.sensenova.cn/v1` | CLI > `SN_VISION_BASE_URL` > `SN_CHAT_BASE_URL` |
| `--model` | string | No | `sensenova-6.7-flash-lite` | CLI > `SN_VISION_MODEL` > `SN_CHAT_MODEL` |
| `--system-prompt` | string | No | `""` | System instruction (mutually exclusive with `--system-prompt-path`) |
| `--system-prompt-path` | path | No | - | Local file path to read system instruction from (mutually exclusive with `--system-prompt`) |
| `--vlm-type` | string | No | `openai-completions` | CLI > `SN_VISION_TYPE` > `SN_CHAT_TYPE` |
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
  "model": "sensenova-6.7-flash-lite",
  "base_url": "https://token.sensenova.cn/v1",
  "interface_type": "openai-completions",
  "elapsed_seconds": 2.15
}
```

### Parameter Priority

`--api-key`, `--base-url`, `--model`, and `--vlm-type` use priority: **CLI parameter > command-specific environment variable > shared `SN_CHAT_*` environment variable > built-in default**.

| Parameter | Built-in Default | Environment Variable |
|-----------|-----------------|---------------------|
| `--api-key` | None (required) | `SN_VISION_API_KEY` -> `SN_CHAT_API_KEY` |
| `--base-url` | `https://token.sensenova.cn/v1` | `SN_VISION_BASE_URL` -> `SN_CHAT_BASE_URL` |
| `--model` | `sensenova-6.7-flash-lite` | `SN_VISION_MODEL` -> `SN_CHAT_MODEL` |
| `--vlm-type` | `openai-completions` | `SN_VISION_TYPE` -> `SN_CHAT_TYPE` |

Compatibility note: host-only chat base URLs such as `https://token.sensenova.cn`
are also accepted. If the base URL has no path, the runner inserts `/v1` before
the interface endpoint; if it already has a path such as `/v1`, the runner
appends only the interface endpoint path.

---

## sn-text-optimize

Text optimization tool that uses an LLM (Language Model) to optimize text content.

### Command Format

```bash
python sn_agent_runner.py sn-text-optimize \
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
| `--api-key` | string | No | No hardcoded default | CLI > `SN_TEXT_API_KEY` > `SN_CHAT_API_KEY`; raises `MissingApiKeyError` if all are empty |
| `--base-url` | string | No | `https://token.sensenova.cn/v1` | CLI > `SN_TEXT_BASE_URL` > `SN_CHAT_BASE_URL` |
| `--model` | string | No | `sensenova-6.7-flash-lite` | CLI > `SN_TEXT_MODEL` > `SN_CHAT_MODEL` |
| `--system-prompt` | string | No | `""` | System instruction (mutually exclusive with `--system-prompt-path`) |
| `--system-prompt-path` | path | No | - | Local file path to read system instruction from (mutually exclusive with `--system-prompt`) |
| `--llm-type` | string | No | `openai-completions` | CLI > `SN_TEXT_TYPE` > `SN_CHAT_TYPE` |
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
  "model": "sensenova-6.7-flash-lite",
  "base_url": "https://token.sensenova.cn/v1",
  "interface_type": "openai-completions",
  "elapsed_seconds": 0.83
}
```

### Parameter Priority

`--api-key`, `--base-url`, `--model`, and `--llm-type` use priority: **CLI parameter > command-specific environment variable > shared `SN_CHAT_*` environment variable > built-in default**.

| Parameter | Built-in Default | Environment Variable |
|-----------|-----------------|---------------------|
| `--api-key` | None (required) | `SN_TEXT_API_KEY` -> `SN_CHAT_API_KEY` |
| `--base-url` | `https://token.sensenova.cn/v1` | `SN_TEXT_BASE_URL` -> `SN_CHAT_BASE_URL` |
| `--model` | `sensenova-6.7-flash-lite` | `SN_TEXT_MODEL` -> `SN_CHAT_MODEL` |
| `--llm-type` | `openai-completions` | `SN_TEXT_TYPE` -> `SN_CHAT_TYPE` |

Compatibility note: host-only chat base URLs such as `https://token.sensenova.cn`
are also accepted. If the base URL has no path, the runner inserts `/v1` before
the interface endpoint; if it already has a path such as `/v1`, the runner
appends only the interface endpoint path.

---

## Error Handling

### Error Types

| Type | Source | Trigger | Output Format |
|------|--------|---------|---------------|
| `MissingApiKeyError` | Custom business exception | API Key not provided for `sn-image-generate` | text: `Error: ...` / json: `{"status": "failed", "error": "..."}` |
| `ValueError` (prompt) | `_resolve_prompt` | `--user-prompt` and `--user-prompt-path` both provided, neither provided, or file read failure | text: `Error: ...` / json: `{"status": "failed", "error": "..."}` |
| argparse missing param | argparse standard error | Missing required parameters for `sn-image-recognize`/`sn-text-optimize` | `usage: ...` + exit 2 |
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
| `sn-image-generate` | `SN_IMAGE_GEN_API_KEY` | CLI takes precedence; reads this var if not provided; raises `MissingApiKeyError` if both are empty |
| `sn-image-recognize` | `SN_VISION_API_KEY` -> `SN_CHAT_API_KEY` | CLI > command-specific key > shared chat key; raises `MissingApiKeyError` if all are empty |
| `sn-text-optimize` | `SN_TEXT_API_KEY` -> `SN_CHAT_API_KEY` | CLI > command-specific key > shared chat key; raises `MissingApiKeyError` if all are empty |

`SN_CHAT_API_KEY` is the shared key for both text and vision chat calls. Use `SN_TEXT_API_KEY` or `SN_VISION_API_KEY` when a command needs a different provider.
