# SN Image Style Imitation Skill

English | [简体中文](README_CN.md)

This document introduces the `sn-image-imitate` skill and provides a Quick Start for using it end-to-end in OpenClaw / Hermes.

## Prerequisites

- **Python** 3.9 or later (3.10+ recommended).
- **SN API** credentials for image generation and LLM/VLM endpoints (`SN_IMAGE_BASE_API_KEY`, `SN_CHAT_API_KEY`; see Quick Start).
- `sn-image-base` skill installed (as a base dependency).

## Skill Overview

### sn-image-imitate (Tier 1)

Image style imitation scene skill, built on top of `sn-image-base`. See [`skills/sn-image-imitate/SKILL.md`](../sn-image-imitate/SKILL.md) for full behavior.

Given a reference image and a target content description, the skill:

1. **Image Annotation** — Uses VLM to extract a long caption and layout blueprint from the reference image
2. **Caption Rewrite** — Rewrites the caption to replace content with the user-specified target while preserving style and layout
3. **Generation & Review** — Generates a new image from the rewritten caption, reviews layout consistency via VLM, and retries with corrective hints when the threshold is not met

### Non-goals

- Pure style transfer without content change — use dedicated style-transfer tools instead
- Local editing / inpainting
- Video or animation input
- Batch generation from multiple reference images
- Pixel-level fidelity to the reference

### Dependency Graph

```
sn-image-base (Tier 0)
  ├── sn-image-recognize  → VLM calls (image annotation + layout review)
  ├── sn-text-optimize    → LLM calls (caption rewrite)
  └── sn-image-generate   → Image generation
```

## Quick Start

### 1. Register the skill

Make sure `sn-image-base` is already registered (see the registration steps in [`sn-image-generate_en.md`](../../docs/sn-image-generate_en.md)), then register `sn-image-imitate` with OpenClaw or Hermes:

| Approach | What to do |
|----------|------------|
| **Shared on this machine** | Copy or symlink `skills/sn-image-imitate` to `~/.openclaw/skills/` (OpenClaw) or `~/.hermes/skills/openclaw-imports/` (Hermes). |
| **Workspace `skills/`** | Copy or symlink `skills/sn-image-imitate` into your agent workspace. |
| **`openclaw.json`** | If you have already pointed `skills.load.extraDirs` to this repo's `skills` directory, no additional action is needed. |

### 2. Python dependencies and API keys

Dependency installation and API key configuration are for [sn-image-base](../sn-image-base/SKILL.md) skill.

The minimum environment variables to configure `sn-image-base` skill running with [SenseNova Token Plan](https://platform.sensenova.cn/token-plan):

```ini
SN_IMAGE_GEN_API_KEY="your-api-key"
SN_CHAT_API_KEY="your-api-key"
```

Please refer to the **Python dependencies and API keys** section in [`sn-image-generate_en.md`](../../docs/sn-image-generate_en.md) for more configurations.

### 3. Invoke in agent

Describe the task in chat, for example:

> "Use the style of this image to create a poster about new energy vehicles"

Or call the skill by name:

> /skill sn-image-imitate "Reference image: /path/to/ref.png, Target content: new energy vehicle poster"

## Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `reference_image` | string | **Required** | Local path or URL of the reference image |
| `target_content` | string | **Required** | Description of the desired new content |
| `output_mode` | string | `friendly` | Output mode: `friendly` (concise) or `verbose` (detailed) |
| `aspect_ratio` | string | `16:9` | Aspect ratio of the generated image |
| `image_size` | string | `2k` | Size preset of the generated image |
| `max_attempts` | int | `3` | Maximum number of generation attempts |
| `layout_threshold` | float | `0.75` | Minimum layout similarity score to accept the result |

## Workflow Overview

```
User request → Main Agent
  ├── Parameter validation + preflight message
  └── Launch Worker Agent
        ├── Step 0: Initialization (task_id, temp directory)
        ├── Step 1: VLM image annotation → short/long caption + layout blueprint
        ├── Step 2: LLM caption rewrite (preserve style & layout, replace content)
        └── Step 3: Generation + review loop
              ├── Generate candidate image
              ├── VLM layout consistency review (only when max_attempts > 1)
              ├── Pass threshold → early termination
              └── Fail → append corrective hints, continue to next attempt
```

## Output Modes

### friendly mode (default)

A concise description + the final generated image.

### verbose mode

A structured summary including:

1. Reference image short caption
2. Style and layout highlights
3. Rewritten long caption used for generation
4. Per-attempt similarity scores and major deviations
5. Timing summary
6. Final image

## FAQ

### Q: The generated image layout differs significantly from the reference. What should I do?

- Increase `max_attempts` to allow more retry rounds
- Lower `layout_threshold` to relax the acceptance criteria
- Ensure the reference image has clear visual structure and distinct regions

### Q: How to fix a missing API key error?

Run the `sn-image-doctor` skill to check environment configuration, or refer to the API key setup in [`sn-image-generate_en.md`](../../docs/sn-image-generate_en.md).

### Q: Can I change only the style without modifying content?

This skill is designed to preserve style while replacing content. If you only need style transfer without content change, use a dedicated style-transfer tool instead.
