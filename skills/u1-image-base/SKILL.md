---
name: u1-image-base
description: |
  Base-layer skill for the SenseNova-Skills project, providing low-level APIs for image generation, recognition (VLM), and text optimization (LLM).
  This skill does not preprocess inputs; it only calls backend services and returns results.
  This skill is not user-facing and is intended for upper-layer skills only.
triggers:
  - "u1图像基础工具"
  - "u1-image-base"
metadata:
  project: SenseNova-Skills
  tier: 0
  category: infrastructure
  user_visible: false
---

# u1-image-base

## Dependency Installation

```bash
pip install -r requirements.txt
```

## Overview

`u1-image-base` is the base-layer skill (tier 0) of the SenseNova-Skills project and provides three low-level tools:

- `u1-image-generate`: image generation (calls text-to-image-no-enhance API)
- `u1-image-recognize`: image recognition (uses VLM to analyze image content)
- `u1-text-optimize`: text optimization (uses LLM to process text)

This skill **does not perform any input preprocessing** and only calls backend services to return results.

## Tools List

### u1-image-generate

Image generation tool that calls the text-to-image-no-enhance API.

`--prompt` is required; all other parameters are optional:

| Parameter | Type | Default | Description |
|------|------|--------|------|
| `--prompt` | string | **Required** | Prompt text for image generation |
| `--negative-prompt` | string | `""` | Negative prompt |
| `--image-size` | string | `2k` | Image size preset, supports `1k` and `2k` |
| `--aspect-ratio` | string | `16:9` | Aspect ratio, e.g. `1:1`, `16:9`, `9:16` |
| `--seed` | int | `None` | Random seed for reproducible generation |
| `--unet-name` | string | `None` | Specify a UNet model name |
| `--api-key` | string | Read from `U1_API_KEY` env var | API key (CLI argument has priority; `MissingApiKeyError` is raised when both are empty) |
| `--base-url` | string | Read from `U1_IMAGE_GEN_BASE_URL` env var | API base URL (CLI argument has priority; `MissingApiKeyError` is raised when both are empty) |
| `--poll-interval` | float | `5.0` | Polling interval (seconds) |
| `--timeout` | float | `300.0` | Timeout (seconds) |
| `--insecure` | flag | `False` | Disable TLS verification |
| `--save-path` | Path | Auto-generated | Save path |

### u1-image-recognize

Image recognition tool that uses VLM (Vision Language Model) to analyze image content. Supports multiple image inputs.

`--images` and `--user-prompt` (or `--user-prompt-path`) are required. All other parameters use three-level defaults (CLI > env var > built-in default):

| Parameter | Type | Built-in Default | Env Var | Description |
|------|------|-----------|---------|------|
| `--api-key` | string | No hardcoded default | `VLM_API_KEY` → `U1_LM_API_KEY` | Priority: CLI > `VLM_API_KEY` > `U1_LM_API_KEY`; raises `MissingApiKeyError` when all are unset |
| `--base-url` | string | No hardcoded default | `VLM_BASE_URL` -> `U1_LM_BASE_URL` | API base URL; raises error when all are unset |
| `--model` | string | No hardcoded default | `VLM_MODEL` | Model name; raises error when all are unset |
| `--vlm-type` | string | `openai-completions` | `VLM_TYPE` | VLM interface type |
| `--user-prompt-path` | string | `None` | - | Local file path, mutually exclusive with `--user-prompt` |
| `--system-prompt-path` | string | `None` | - | Local file path, mutually exclusive with `--system-prompt` |

Available values for `--vlm-type`:

- `openai-completions`: OpenAI-compatible `/v1/chat/completions` interface
- `anthropic-messages`: Anthropic Messages `/v1/messages` interface

### u1-text-optimize

Text optimization tool that uses LLM (Language Model) to optimize text content. Does not accept image inputs.

`--user-prompt` (or `--user-prompt-path`) is required. All other parameters use three-level defaults (CLI > env var > built-in default):

| Parameter | Type | Built-in Default | Env Var | Description |
|------|------|-----------|---------|------|
| `--api-key` | string | No hardcoded default | `LLM_API_KEY` → `U1_LM_API_KEY` | Priority: CLI > `LLM_API_KEY` > `U1_LM_API_KEY`; raises `MissingApiKeyError` when all are unset |
| `--base-url` | string | No hardcoded default | `LLM_BASE_URL` -> `U1_LM_BASE_URL` | API base URL; raises error when all are unset |
| `--model` | string | No hardcoded default | `LLM_MODEL` | Model name; raises error when all are unset |
| `--llm-type` | string | `openai-completions` | `LLM_TYPE` | LLM interface type |
| `--user-prompt-path` | string | `None` | - | Local file path, mutually exclusive with `--user-prompt` |
| `--system-prompt-path` | string | `None` | - | Local file path, mutually exclusive with `--system-prompt` |

Available values for `--llm-type`:

- `openai-completions`: OpenAI-compatible `/v1/chat/completions` interface
- `anthropic-messages`: Anthropic Messages `/v1/messages` interface

## VLM vs LLM

| Tool | Model Type | Image Input | Interface Type Parameter |
|------|----------|-----------------|-------------|
| `u1-image-recognize` | VLM (Vision Language Model) | Yes, supports multiple images | `--vlm-type` |
| `u1-text-optimize` | LLM (Language Model) | No, text only | `--llm-type` |

## Usage

All tools are called through the unified `openclaw_runner.py` entrypoint:

```bash
# Image generation (only prompt required; api-key/base-url have defaults)
python u1_image_base/openclaw_runner.py u1-image-generate \
    --prompt "..."

# Image generation (override base-url)
python u1_image_base/openclaw_runner.py u1-image-generate \
    --prompt "..." \
    --base-url "https://custom-endpoint.com/u1-model"

# Image generation (explicitly override api-key)
python u1_image_base/openclaw_runner.py u1-image-generate \
    --prompt "..." \
    --api-key "sk-xxx"

# Image recognition (VLM) - minimal call (uses built-in Sensenova defaults)
python u1_image_base/openclaw_runner.py u1-image-recognize \
    --user-prompt "Describe the image" \
    --images "path/to/image.png"

# Image recognition (VLM) - override to Anthropic Claude API compatible (messages interface)
python u1_image_base/openclaw_runner.py u1-image-recognize \
    --user-prompt "Describe the image" \
    --images "path/to/image.png" \
    --api-key "sk-ant-xxx" \
    --base-url "https://api.anthropic.com" \
    --model "claude-sonnet-4-6" \
    --vlm-type "anthropic-messages"

# Text optimization (LLM) - minimal call (uses built-in Sensenova defaults)
python u1_image_base/openclaw_runner.py u1-text-optimize \
    --user-prompt "Optimize the text: ..."

# Text optimization (LLM) - override to Anthropic Claude API compatible (messages interface)
python u1_image_base/openclaw_runner.py u1-text-optimize \
    --user-prompt "Optimize the text: ..." \
    --api-key "sk-ant-xxx" \
    --base-url "https://api.anthropic.com" \
    --model "claude-sonnet-4-6" \
    --llm-type "anthropic-messages"
```

### Default Parameter Behavior

Authentication parameters for `u1-image-generate` have the following default behavior:

| Parameter | Default | Override | Description |
|------|--------|----------|------|
| `--base-url` | Read from `U1_BASE_URL` env var | `--base-url "..."` | CLI argument has priority; throws error if env var and CLI value are both missing |
| `--api-key` | Read from `U1_API_KEY` env var | `--api-key "..."` | CLI argument has priority; throws `MissingApiKeyError` if env var and CLI value are both missing |

`u1-image-recognize` (VLM) and `u1-text-optimize` (LLM) use three-level priority: **CLI argument > environment variable > built-in default**

| Parameter | Built-in Default | VLM Env Var | LLM Env Var |
|------|-----------|-------------|-------------|
| `--api-key` | None (must be provided) | `VLM_API_KEY` → `U1_LM_API_KEY` | `LLM_API_KEY` → `U1_LM_API_KEY` |
| `--base-url` | None (must be provided) | `VLM_BASE_URL` -> `U1_LM_BASE_URL` | `LLM_BASE_URL` -> `U1_LM_BASE_URL` |
| `--model` | None (must be provided) | `VLM_MODEL` | `LLM_MODEL` |
| `--vlm-type` / `--llm-type` | `openai-completions` | `VLM_TYPE` | `LLM_TYPE` |

`api_key` resolution order (high to low): CLI `--api-key` > `VLM_API_KEY`/`LLM_API_KEY` (independent) > `U1_LM_API_KEY` (shared fallback). If all are unset, `MissingApiKeyError` is raised.

All parameters except `--vlm-type`/`--llm-type` must be provided via CLI arguments or environment variables.

## Agent Configuration Integration

The agent can automatically read parameters from `openclaw.json` without manual input:

| CLI Parameter | openclaw.json Field | Example |
|-----------|-------------------|--------|
| `--base-url` | `providers.<name>.baseUrl` | `https://api.anthropic.com` |
| `--llm-type` | `providers.<name>.api` | `anthropic-messages` / `openai-completions` |
| `--vlm-type` | `providers.<name>.api` | `anthropic-messages` / `openai-completions` |
| `--model` | `providers.<name>.models[].id` | `claude-sonnet-4-6` |
| `--api-key` | `providers.<name>.apiKey` or env var | `sk-cp-...` |

Note: `--llm-type` and `--vlm-type` share the same `providers.<name>.api` field and are used by LLM and VLM tools respectively.

Mapping between `provider.api` and interface type:

| api Value | Corresponding `--llm-type` / `--vlm-type` | Endpoint Path |
|--------|----------------------------------|---------------|
| `anthropic-messages` | `anthropic-messages` | `/v1/messages` |
| `openai-completions` | `openai-completions` | `/v1/chat/completions` |
| `openai-responses` | (future extension) | `/responses` |

## Mapping Between base-url and Interface Type

Different API types have different requirements for base-url format:

| Type | `--llm-type` / `--vlm-type` | base-url Example | Code Appended Path | Final URL Example |
|------|------------------------------|---------------|--------------|---------------|
| LLM | `openai-completions` | `http://127.0.0.1:615` | `/v1/chat/completions` | `http://127.0.0.1:615/v1/chat/completions` |
| LLM | `anthropic-messages` | `https://api.anthropic.com` | `/v1/messages` | `https://api.anthropic.com/v1/messages` |
| VLM | `openai-completions` | `http://127.0.0.1:615` | `/v1/chat/completions` | `http://127.0.0.1:615/v1/chat/completions` |
| VLM | `anthropic-messages` | `https://api.anthropic.com` | `/v1/messages` | `https://api.anthropic.com/v1/messages` |

**Note**:

- `openai-completions` interface: code automatically appends `/v1/chat/completions`
- `anthropic-messages` interface: code automatically appends `/v1/messages`
- Some providers require base-url with `/v1`, while others do not, depending on provider implementation
- If unsure, prefer not adding `/v1` because the code appends it automatically

## Output Format

All tools support two output formats:

- `--output-format text` (default): outputs plain text result
- `--output-format json`: outputs JSON, including `status` and `elapsed_seconds` (runtime in seconds, rounded to 2 decimals)

JSON output for `u1-image-recognize` and `u1-text-optimize` also includes `model`, `base_url`, and `interface_type` to verify the effective runtime configuration:

```json
{
  "status": "ok",
  "result": "...",
  "model": "sensenova-122b",
  "base_url": "http://127.0.0.1:615",
  "interface_type": "openai-completions",
  "elapsed_seconds": 1.23
}
```

On failure:

```json
{
  "status": "failed",
  "error": "error message",
  "elapsed_seconds": 0.05
}
```

## Input/Output Specification

See `reference/api_spec.md` for details.
