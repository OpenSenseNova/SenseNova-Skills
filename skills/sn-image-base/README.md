# sn-image-base

The skill for the [SenseNova-Skills](https://github.com/OpenSenseNova/SenseNova-Skills) project, providing low-level APIs for image generation, recognition (VLM), and text optimization (LLM).

See [SKILL.md](SKILL.md) for full behavior.

This document describes detailed configurations for the skill.

For installation and usage, please refer to the project's [README.md](https://github.com/OpenSenseNova/SenseNova-Skills/blob/main/README.md).

## Overview

The skill provides the following subcommands:

- `sn-image-generate`: image generation
- `sn-image-recognize`: image recognition (VLM)
- `sn-text-optimize`: text optimization (LLM)

The skill supports the following models services:

- For image generation:
  - [SenseNova](https://platform.sensenova.cn/)
  - Nano Banana API
  - OpenAI Image Generation API (e.g. GPT-Image-2)

- For LLM/VLM:
  - [SenseNova](https://platform.sensenova.cn/)
  - Models via Anthropic Messages API (e.g. Claude Sonnet 4.6)
  - Models via OpenAI Chat Completion API (e.g. GPT and Gemini/Qwen etc. in OpenAI Compatible API format)

## Configurations

### Quick Start

We recommend you to try out our [SenseNova Token Plan](https://platform.sensenova.cn/token-plan).

Go to <https://platform.sensenova.cn/token-plan/> to register a free account and get your API key for both image generation and LLM/VLM.

Set the following environment variables in `~/.openclaw/.env` (or `~/.hermes/.env` if you are using Hermes):

```ini
# Image generation
SN_API_KEY="<sensenova-token-plan-api-key>"
SN_IMAGE_GEN_MODEL="sensenova-u1-fast"   # or other image generation models available in the SenseNova Token Plan
# LLM/VLM
SN_LM_API_KEY="<sensenova-token-plan-api-key>"
SN_LM_MODEL="sensenova-6.7-flash-lite"   # or other LLM/VLM models available in the SenseNova Token Plan
```

### Detailed Configurations

With the [Quick Start](#quick-start), you can already use this skill.

If you want to configure the skill more (i.e. use different models, change the base URL, etc.), you can see the following configurations.

Multiple sources of configuration are supported, the priority is (high to low):

- (Recommended) `~/.openclaw/.env` (for OpenClaw) or `~/.hermes/.env` (for Hermes)
- current working directory `.env` (not necessarily exists, depends on how the agent runs the skill)
- process environment variables

> For experienced developers, see [configs.py](scripts/sn_image_base/configs.py) for the full list of variables and defaults.
>
> Helpful symbols for tracing behavior quickly:
>
> - `prepare_env()` for `.env` loading order
> - `Field.resolve()` for env-var fallback order ("first set value wins")
> - `Configs` for all defaults and env-name mapping

#### Image Generation

Full configuration for image generation:

| Config Key | Description | Default |
| ---------- | ----------- | ------- |
| `SN_API_KEY` | The API key for the SenseNova Token Plan | (Required) |
| `SN_IMAGE_GEN_MODEL_TYPE` | The type of image generation model to use | `"sensenova"` |
| `SN_IMAGE_GEN_MODEL` | The name of the image generation model to use | `"sensenova-u1-fast"` |
| `SN_IMAGE_GEN_BASE_URL` | The base URL for the image generation API | `"https://token.sensenova.cn/v1"` |

The default values are recommended for the [SenseNova](https://platform.sensenova.cn/).

You only need to set the `SN_API_KEY`, and optionally set `SN_IMAGE_GEN_MODEL` to the model name provided by the token plan.

To use non-default image generation models, please:

1. Set `SN_IMAGE_GEN_MODEL_TYPE` according to the model type, available values are:

    ```ini
    # (Default) For [SenseNova](https://platform.sensenova.cn/)
    SN_IMAGE_GEN_MODEL_TYPE="sensenova"
    # For Google's Nano Banana model API
    SN_IMAGE_GEN_MODEL_TYPE="nano-banana"
    # For OpenAI's image generation API
    SN_IMAGE_GEN_MODEL_TYPE="openai-image"
    ```

2. Set `SN_IMAGE_GEN_BASE_URL` to the base URL for the image generation API. For example:

    ```ini
    # (Default) For [SenseNova](https://platform.sensenova.cn/)
    SN_IMAGE_GEN_BASE_URL="https://token.sensenova.cn/v1"
    # For Google's Nano Banana model API
    SN_IMAGE_GEN_BASE_URL="https://generativelanguage.googleapis.com"
    # For OpenAI's image generation API
    SN_IMAGE_GEN_BASE_URL="https://api.openai.com/v1"
    ```

3. Set `SN_IMAGE_GEN_MODEL` to the model name provided by the model type. For example:

    ```ini
    # (Default) For [SenseNova](https://platform.sensenova.cn/)
    SN_IMAGE_GEN_MODEL="sensenova-u1-fast"
    # For Google's Nano Banana model API
    SN_IMAGE_GEN_MODEL="gemini-3.1-flash-image-preview"
    # For OpenAI's image generation API
    SN_IMAGE_GEN_MODEL="gpt-image-2"
    ```

4. (**Required**) Set `SN_API_KEY` to the API key for the image generation API.

    ```ini
    SN_API_KEY="sk-your-image-generation-api-key"
    ```

#### VLM and LLM

If you're not intended to use different models for VLM and LLM, you can use the same `SN_LM_*` variables to configure both VLM and LLM, and skip the following VLM and LLM configurations.

##### Use the same VLM and LLM models

Full configuration for VLM and LLM (with shared `SN_LM_*` environment variables):

| Config Keys | Description | Default |
| ----------- | ----------- | ------- |
| `VLM_API_KEY` & `LLM_API_KEY` (via `SN_LM_API_KEY` env var) | The API key for the VLM and LLM API | (Required) |
| `VLM_BASE_URL` & `LLM_BASE_URL` (via `SN_LM_BASE_URL` env var) | The base URL for the VLM and LLM API | `"https://token.sensenova.cn/v1"` |
| `VLM_MODEL` & `LLM_MODEL` (via `SN_LM_MODEL` env var) | The name of the VLM and LLM model to use | `"sensenova-6.7-flash-lite"` |
| `VLM_TYPE` & `LLM_TYPE` (via `SN_LM_TYPE` env var) | The type of the VLM and LLM API to use | `"openai-completions"` |

The default values are recommended for the [SenseNova](https://platform.sensenova.cn/).

You only need to set the `SN_LM_API_KEY`, and optionally set `SN_LM_MODEL` to the model name provided by the token plan.

To use non-default shared LM settings, please:

1. Set `VLM_TYPE` & `LLM_TYPE` (via `SN_LM_TYPE`) according to the shared LM API interface type. Available values are:

    ```ini
    # (Default) OpenAI-compatible `/chat/completions` interface (most widely supported)
    SN_LM_TYPE="openai-completions"
    # Anthropic Messages `/messages` interface
    SN_LM_TYPE="anthropic-messages"
    ```

2. Set `VLM_BASE_URL` & `LLM_BASE_URL` (via `SN_LM_BASE_URL`) to the shared LM endpoint base URL. For example:

    ```ini
    # (Default) For [SenseNova](https://platform.sensenova.cn/)
    SN_LM_BASE_URL="https://token.sensenova.cn/v1"
    # For Anthropic Messages API
    SN_LM_BASE_URL="https://api.anthropic.com/v1"
    # For OpenAI's chat completion API
    SN_LM_BASE_URL="https://api.openai.com/v1"
    # For Google Gemini API (OpenAI-compatible)
    SN_LM_BASE_URL="https://generativelanguage.googleapis.com/v1beta/openai/"
    ```

3. Set `VLM_MODEL` & `LLM_MODEL` (via `SN_LM_MODEL`) to the shared LM model name. For example:

    ```ini
    # (Default) SenseNova 6.7 Flash Lite
    SN_LM_MODEL="sensenova-6.7-flash-lite"
    # Anthropic Claude Sonnet 4.6
    SN_LM_MODEL="claude-sonnet-4-6"
    # Google Gemini 3 Flash Preview
    SN_LM_MODEL="gemini-3-flash-preview"
    # OpenAI GPT 5.5
    SN_LM_MODEL="gpt-5.5"
    ```

4. (**Required**) Set `VLM_API_KEY` & `LLM_API_KEY` (via `SN_LM_API_KEY`) to the API key for the shared LM endpoint.

    ```ini
    SN_LM_API_KEY="sk-your-api-key"
    ```

##### Use different VLM and LLM models

If you want to use different models for VLM and LLM, you can configure the VLM (Image Recognition) API and LLM (Text Optimization) API with different environment variables.

> **Variable precedence (explicit rule)**
>
> When multiple variables can configure the same runtime field, the first configured env var in `configs.py` wins.
>
> - For VLM model: if both `VLM_MODEL` and `SN_LM_MODEL` are set, `VLM_MODEL` wins.
> - For LLM model: if both `LLM_MODEL` and `SN_LM_MODEL` are set, `LLM_MODEL` wins.
>
> Tiny conflict example:
>
> ```ini
> SN_LM_MODEL="sensenova-6.7-flash-lite"
> VLM_MODEL="claude-sonnet-4-6"
> ```
>
> In this case, VLM uses `claude-sonnet-4-6`, while LLM still uses `sensenova-6.7-flash-lite` (unless `LLM_MODEL` is also set).

Independent environment variables for VLM:

| Config Key | Description | Default |
| ---------- | ----------- | ------- |
| `VLM_API_KEY` | The API key for the VLM API | (Required) |
| `VLM_BASE_URL` | The base URL for the VLM API | `"https://token.sensenova.cn/v1"` |
| `VLM_MODEL` | The name of the VLM model to use | `"sensenova-6.7-flash-lite"` |
| `VLM_TYPE` | The type of the VLM API to use | `"openai-completions"` |

Independent environment variables for LLM:

| Config Key | Description | Default |
| ---------- | ----------- | ------- |
| `LLM_API_KEY` | The API key for the LLM API | (Required) |
| `LLM_BASE_URL` | The base URL for the LLM API | `"https://token.sensenova.cn/v1"` |
| `LLM_MODEL` | The name of the LLM model to use | `"sensenova-6.7-flash-lite"` |
| `LLM_TYPE` | The type of the LLM API to use | `"openai-completions"` |

Use the above environment variables to override the `SN_LM_*` variables for VLM and LLM.

## Troubleshooting

### Missing API key

- Symptom: errors like "required but not set", "missing api key", or request unauthorized.
- Fix: set `SN_API_KEY` for image generation, and set either `SN_LM_API_KEY` or task-specific keys (`VLM_API_KEY` / `LLM_API_KEY`).

### Wrong base URL

- Symptom: request fails immediately, or URL validation/auth endpoint errors.
- Fix: verify `SN_IMAGE_GEN_BASE_URL`, `SN_LM_BASE_URL`, `VLM_BASE_URL`, `LLM_BASE_URL` are full base URLs (with scheme + host), for example `https://token.sensenova.cn/v1`.

### Unsupported model name

- Symptom: provider returns HTTP 404 / model-not-found / bad request.
- Fix: ensure `*_MODEL_TYPE` / `*_TYPE` and `*_MODEL` are from the same provider, and that the model is available in your account.

### Auth / permission errors

- Symptom: HTTP 401/403, "permission denied", "forbidden".
- Fix: check whether the key matches the selected provider endpoint, confirm account quotas/permissions, and retry with a known-valid model.

## Security Notes

- **Never** commit `.env` files or API keys to git.
- If a key is leaked, rotate it immediately and update local env files.
- Prefer local secret management (`~/.openclaw/.env` or `~/.hermes/.env`) over hardcoding keys in scripts or prompts.
