# u1-image-base

The skill for the SenseNova-Skills project, providing low-level APIs for image generation, recognition (VLM), and text optimization (LLM).

See [SKILL.md](SKILL.md) for full behavior.

## Configuration

The skill uses environment variables or `.env` file for configuration. See [configs.py](scripts/configs.py) for the list of environment variables.

For quick start, you can use the following environment variables:

```bash
# Image Generation configs
export U1_API_KEY="your-image-api-key"   # API key for image generation
# VLM/LLM configs
export U1_LM_API_KEY="your-lm-api-key"   # API key for VLM/LLM
export U1_LM_BASE_URL="lm-api-base-url"  # API base URL for VLM/LLM, e.g "https://api.anthropic.com"
```
