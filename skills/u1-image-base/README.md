# u1-image-base

The skill for the SenseNova-Skills project, providing low-level APIs for image generation, recognition (VLM), and text optimization (LLM).

See [SKILL.md](SKILL.md) for full behavior.

## Configuration

See [configs.py](u1_image_base/configs.py) for the full list of variables and defaults.

**Required** - image generation will not work without this:

```bash
export U1_API_KEY="your-image-api-key"
```

**Recommended** - shared prefix `U1_LM_*` sets both LLM and VLM; use the specific prefixes (`LLM_*` / `VLM_*`) to override individually:

```bash
export U1_LM_API_KEY="your-lm-api-key"      # LLM_API_KEY / VLM_API_KEY
export U1_LM_BASE_URL="your-lm-base-url"    # LLM_BASE_URL / VLM_BASE_URL, e.g. "https://api.anthropic.com" (Not including "/v1" path)
export U1_LM_MODEL="your-model-name"        # LLM_MODEL / VLM_MODEL
export U1_LM_TYPE="openai-completions"      # LLM_TYPE / VLM_TYPE — "openai-completions" or "anthropic-messages"
```

**Optional** - To use Nano Banana models for image generation:

```bash
export U1_API_KEY="your-api-key-for-nano-banana"                            # Your API key for Nano Banana models
export U1_IMAGE_GEN_BASE_URL="https://generativelanguage.googleapis.com"    # The base URL for Nano Banana models API
export U1_IMAGE_GEN_MODEL_TYPE="nano-banana"
export U1_IMAGE_GEN_MODEL="gemini-3.1-flash-image-preview"  # Nano Banana model name, e.g. "gemini-3.1-flash-image-preview", "gemini-3-pro-image-preview"
```

Configuration precedence in `configs.py` is: `~/.openclaw/.env` (or `~/.hermes/.env`) > current working directory `.env` > process environment variables.

Do not commit secrets.
