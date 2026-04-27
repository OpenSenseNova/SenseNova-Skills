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

- For text and vision chat:
  - [SenseNova](https://platform.sensenova.cn/)
  - Models via Anthropic Messages API (e.g. Claude Sonnet 4.6)
  - Models via OpenAI Chat Completion API (e.g. GPT and Gemini/Qwen etc. in OpenAI Compatible API format)

## Configurations

### Quick Start

We recommend you to try out our [SenseNova Token Plan](https://platform.sensenova.cn/token-plan).

Go to <https://platform.sensenova.cn/token-plan/> to register a free account and get your API key for image generation and chat calls.

Set the following environment variables in `~/.openclaw/.env` (or `~/.hermes/.env` if you are using Hermes):

```ini
# Image generation
SN_IMAGE_GEN_API_KEY="<sensenova-token-plan-api-key>"
SN_IMAGE_GEN_MODEL="sensenova-u1-fast"   # or other image generation models available in the SenseNova Token Plan
# Text and vision chat runtime
SN_CHAT_API_KEY="<sensenova-token-plan-api-key>"
SN_CHAT_MODEL="sensenova-6.7-flash-lite"
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
| `SN_IMAGE_GEN_API_KEY` | The API key for the SenseNova Token Plan | (Required) |
| `SN_IMAGE_GEN_MODEL_TYPE` | The type of image generation model to use | `"sensenova"` |
| `SN_IMAGE_GEN_MODEL` | The name of the image generation model to use | `"sensenova-u1-fast"` |
| `SN_IMAGE_GEN_BASE_URL` | The base URL for the image generation API | `"https://token.sensenova.cn/v1"` |

The default values are recommended for the [SenseNova](https://platform.sensenova.cn/).

You only need to set the `SN_IMAGE_GEN_API_KEY`, and optionally set `SN_IMAGE_GEN_MODEL` to the model name provided by the token plan.

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

4. (**Required**) Set `SN_IMAGE_GEN_API_KEY` to the API key for the image generation API.

    ```ini
    SN_IMAGE_GEN_API_KEY="sk-your-image-generation-api-key"
    ```

#### Text and Vision Chat

##### Configure the shared chat runtime

Text optimization and image recognition now share one chat runtime. Configure the
protocol, endpoint, API key, and default model once, then override text or vision
models only when needed:

| Config Keys | Description | Default |
| ----------- | ----------- | ------- |
| `SN_CHAT_API_KEY` | API key for text and vision chat calls | (Required) |
| `SN_CHAT_BASE_URL` | Shared base URL for the chat API | `"https://token.sensenova.cn/v1"` |
| `SN_CHAT_TYPE` | Shared chat protocol type | `"openai-completions"` |
| `SN_CHAT_MODEL` | Shared default model for text and vision chat calls | `"sensenova-6.7-flash-lite"` |
| `SN_TEXT_API_KEY` | Optional text-only provider API key | `SN_CHAT_API_KEY` |
| `SN_TEXT_BASE_URL` | Optional text-only provider base URL | `SN_CHAT_BASE_URL` |
| `SN_TEXT_TYPE` | Optional text-only protocol type | `SN_CHAT_TYPE` |
| `SN_TEXT_MODEL` | Optional model override for `sn-text-optimize` | `SN_CHAT_MODEL` |
| `SN_VISION_API_KEY` | Optional vision provider API key | `SN_CHAT_API_KEY` |
| `SN_VISION_BASE_URL` | Optional vision provider base URL | `SN_CHAT_BASE_URL` |
| `SN_VISION_TYPE` | Optional vision protocol type | `SN_CHAT_TYPE` |
| `SN_VISION_MODEL` | Optional vision-capable model override for `sn-image-recognize` | `SN_CHAT_MODEL` |

The default values are recommended for the [SenseNova](https://platform.sensenova.cn/).

Configure `SN_TEXT_*` or `SN_VISION_*` only when a command needs a different provider than the shared `SN_CHAT_*` provider.

For chat calls, the runner also accepts host-only base URLs such as
`https://token.sensenova.cn`: if no URL path is present, it appends the API
version path before the interface endpoint. Prefer the documented versioned
base URL, for example `https://token.sensenova.cn/v1`, for consistency with the
built-in defaults.

To use non-default shared chat settings, please:

1. Set `SN_CHAT_TYPE` according to the chat API protocol. Available values are:

    ```ini
    # (Default) OpenAI-compatible `/chat/completions` interface (most widely supported)
    SN_CHAT_TYPE="openai-completions"
    # Anthropic Messages `/messages` interface
    SN_CHAT_TYPE="anthropic-messages"
    ```

2. Set `SN_CHAT_BASE_URL` to the shared chat endpoint base URL. For example:

    ```ini
    # (Default) For [SenseNova](https://platform.sensenova.cn/)
    SN_CHAT_BASE_URL="https://token.sensenova.cn/v1"
    # For Anthropic Messages API
    SN_CHAT_BASE_URL="https://api.anthropic.com/v1"
    # For OpenAI's chat completion API
    SN_CHAT_BASE_URL="https://api.openai.com/v1"
    # For Google Gemini API (OpenAI-compatible)
    SN_CHAT_BASE_URL="https://generativelanguage.googleapis.com/v1beta/openai/"
    ```

3. Set `SN_CHAT_MODEL`, or set `SN_TEXT_MODEL` / `SN_VISION_MODEL` only when a command needs a different model:

    ```ini
    # (Default) SenseNova 6.7 Flash Lite
    SN_CHAT_MODEL="sensenova-6.7-flash-lite"
    # Anthropic Claude Sonnet 4.6
    SN_VISION_MODEL="claude-sonnet-4-6"
    # Google Gemini 3 Flash Preview
    SN_VISION_MODEL="gemini-3-flash-preview"
    # OpenAI GPT 5.5
    SN_TEXT_MODEL="gpt-5.5"
    ```

4. (**Required**) Set `SN_CHAT_API_KEY` to the API key for the shared chat endpoint.

    ```ini
    SN_CHAT_API_KEY="sk-your-api-key"
    ```

## Troubleshooting

### Missing API key

- Symptom: errors like "required but not set", "missing api key", or request unauthorized.
- Fix: set `SN_IMAGE_GEN_API_KEY` for image generation, and set `SN_CHAT_API_KEY` for chat calls. Use `SN_TEXT_API_KEY` or `SN_VISION_API_KEY` when text and vision use different providers.

### Wrong base URL

- Symptom: request fails immediately, or URL validation/auth endpoint errors.
- Fix: verify `SN_IMAGE_GEN_BASE_URL`, `SN_CHAT_BASE_URL`, `SN_TEXT_BASE_URL`, and `SN_VISION_BASE_URL` are full base URLs (with scheme + host), for example `https://token.sensenova.cn/v1`.

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
