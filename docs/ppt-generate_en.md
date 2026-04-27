# PPT Generation Skills

English | [简体中文](ppt-generate.md)

This document collects the PPT generation skills (`sn-ppt-entry`, `sn-ppt-doctor`, `sn-ppt-creative`, `sn-ppt-standard`) used in OpenClaw / Hermes to produce `.pptx` decks from user prompts and reference documents.

## Prerequisites

- **Python** 3.9 or later (3.10+ recommended).
- **Node.js** runtime (used by `sn-ppt-standard` during per-page HTML processing).
- LLM/VLM and text-to-image API credentials (see below).

## Skills

| Name | Role | Description |
|------|------|-------------|
| [`sn-ppt-entry`](../skills/sn-ppt-entry/SKILL.md) | **PPT entry** | Collects role / audience / scene / page count / mode (creative or standard), parses pdf / docx / md / txt inputs, emits `task_pack.json` + `info_pack.json`, and dispatches to a downstream mode. |
| [`sn-ppt-doctor`](../skills/sn-ppt-doctor/SKILL.md) | PPT environment doctor | Validates `sn-image-base` availability, API keys, Node runtime, and optional deps; writes missing required vars into `.env`. |
| [`sn-ppt-creative`](../skills/sn-ppt-creative/SKILL.md) | PPT creative mode | One full-page 16:9 PNG per slide, generated via `sn-image-generate` from a per-page composed prompt; exports PPTX. |
| [`sn-ppt-standard`](../skills/sn-ppt-standard/SKILL.md) | PPT standard mode | `style_spec` → outline → asset plan + per-slot images + VLM QA → per-page HTML → per-page review (optional rewrite) → summary `review.md` → PPTX export. |

`sn-ppt-creative` depends on `sn-image-base` for text-to-image; `sn-ppt-standard` ships its own LLM / VLM invocation scripts (`scripts/run_stage.py`) but still routes text-to-image through `sn-image-base`.

## Quick Start

Use these skills from [OpenClaw](https://openclaw.ai/). For the generic skill registration steps (copy / symlink / `openclaw.json`), see [`sn-image-generate_en.md`](sn-image-generate_en.md#1-register-skills); they are not repeated here.

### 1. Python dependencies

```bash
# sn-ppt-entry: PDF / DOCX parsing
pip install -r skills/sn-ppt-entry/requirements.txt

# sn-ppt-creative: PPTX export
pip install -r skills/sn-ppt-creative/requirements.txt

# sn-ppt-creative also needs sn-image-base's image generation runtime
pip install -r skills/sn-image-base/requirements.txt
```

`sn-ppt-doctor` uses only the Python stdlib. `sn-ppt-standard` wraps model calls in `scripts/run_stage.py` and also requires `python-pptx` for the final PPTX export.

### 2. API keys and environment variables

Set the following in `~/.openclaw/.env` (OpenClaw) or `~/.hermes/.env` (Hermes):

```ini
# LLM (outline, style_spec, content planning, image caption, page review)
SN_CHAT_API_KEY="your-api-key"
SN_CHAT_BASE_URL="https://token.sensenova.cn"
SN_CHAT_MODEL="sensenova-6.7-flash-lite"
SN_VISION_API_KEY="your-api-key"
SN_VISION_BASE_URL="https://token.sensenova.cn"
SN_VISION_MODEL="sensenova-6.7-flash-lite"

# Text-to-image (required for creative mode, on-demand for standard mode)
SN_IMAGE_GEN_API_KEY="your-api-key"
SN_IMAGE_GEN_MODEL_TYPE="sensenova"
SN_IMAGE_GEN_MODEL="sensenova-u1-fast"
```

Optional variables `SN_IMAGE_GEN_*`, `SN_TEXT_*`, and `SN_VISION_*` override default models and timeouts. Full list: [`skills/sn-image-base/README.md`](../skills/sn-image-base/README.md).

Run environment doctor before invoking:

> Run the `sn-ppt-doctor` skill

### 3. Invoke in Agent

`sn-ppt-entry` is the unified entry point and dispatches to creative or standard mode automatically:

> "Make a 10-page deck on team OKRs for an executive audience, minimalist style"

Or call by name:

> /skill sn-ppt-entry "Team OKR review"

## Outputs

Decks are written to `$(pwd)/ppt_decks/<topic>_<timestamp>/`, containing:

- `task_pack.json` / `info_pack.json` — parsed task parameters from `sn-ppt-entry`
- `style_spec.json` (standard mode) / `style_spec.md` (creative mode), `outline.json` — style and outline
- `pages/page_*.png` — full-page images (creative) or HTML-rendered slides (standard)
- `review.md` — per-page review summary (standard mode)
- `<deck_id>.pptx` — final PPTX

_See the "Sample Outputs" section in the top-level [`README.md`](../README.md#sample-outputs) for end-to-end examples._
