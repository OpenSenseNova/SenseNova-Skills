# SenseNova-Skills

A collection of AIGC skills.

## Skills

### u1-image-base (Tier 0)

Base-layer infrastructure skill providing four low-level tools:

- **u1-image-generate** — text-to-image generation
- **u1-text-optimize** — text processing using LLM

All tools are invoked through a unified `openclaw_runner.py` entrypoint.

### u1-infographic (Tier 1)

Scene skill for generating professional infographics. Builds on `u1-image-base` to provide:

- Automatic prompt quality evaluation
- Content analysis and layout/style selection (87 layouts, 66 styles)
- Multi-round image generation with VLM review
- Quality ranking and best-result output

## Quick Start

### Install dependencies

```bash
pip install -r skills/u1-image-base/requirements.txt
```

### Configure API keys

```bash
export U1_API_KEY="your-image-api-key"
export U1_LM_API_KEY="your-lm-api-key"   # shared fallback for LLM/VLM
```

### Generate an infographic

Invoke the `u1-infographic` skill through your agent with a natural language request, e.g.:

> "Create an infographic explaining the water cycle"

With agents like [OpenClaw](https://openclaw.ai/), you can explicitly call the skill by name:

> /skill u1-infographic "The water cycle"
