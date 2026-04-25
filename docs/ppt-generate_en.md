# PPT Generation Skills

English | [简体中文](ppt-generate.md)

This document collects the PPT generation skills (`ppt-entry`, `ppt-doctor`, `ppt-creative`, `ppt-standard`) used in OpenClaw / Hermes to produce `.pptx` decks from user prompts and reference documents.

## Prerequisites

- **Python** 3.9 or later (3.10+ recommended).
- **Node.js** runtime (used by `ppt-standard` during per-page HTML processing).
- LLM/VLM and text-to-image API credentials (see below).

## Skills

| Name | Role | Description |
|------|------|-------------|
| [`ppt-entry`](../skills/ppt-entry/SKILL.md) | **PPT entry** | Collects role / audience / scene / page count / mode (creative or standard), parses pdf / docx / md / txt inputs, emits `task_pack.json` + `info_pack.json`, and dispatches to a downstream mode. |
| [`ppt-doctor`](../skills/ppt-doctor/SKILL.md) | PPT environment doctor | Validates `u1-image-base` availability, API keys, Node runtime, and optional deps; writes missing required vars into `.env`. |
| [`ppt-creative`](../skills/ppt-creative/SKILL.md) | PPT creative mode | One full-page 16:9 PNG per slide, generated via `u1-image-generate` from a per-page composed prompt; exports PPTX. |
| [`ppt-standard`](../skills/ppt-standard/SKILL.md) | PPT standard mode | `style_spec` → outline → asset plan + per-slot images + VLM QA → per-page HTML → per-page review (optional rewrite) → summary `review.md` → PPTX export. |

`ppt-creative` depends on `u1-image-base` for text-to-image; `ppt-standard` ships its own model invocation scripts (`scripts/run_stage.py`).

## Quick Start

Use these skills from [OpenClaw](https://openclaw.ai/). For the generic skill registration steps (copy / symlink / `openclaw.json`), see [`u1-image-generate_en.md`](u1-image-generate_en.md#1-register-skills); they are not repeated here.

### 1. Python dependencies

```bash
# ppt-entry: PDF / DOCX parsing
pip install -r skills/ppt-entry/requirements.txt

# ppt-creative: PPTX export
pip install -r skills/ppt-creative/requirements.txt

# ppt-creative also needs u1-image-base's image generation runtime
pip install -r skills/u1-image-base/requirements.txt
```

`ppt-doctor` uses only the Python stdlib. `ppt-standard` wraps model calls in `scripts/run_stage.py` and also requires `python-pptx` for the final PPTX export.

### 2. API keys and environment variables

Set the following in `~/.openclaw/.env` (OpenClaw) or `~/.hermes/.env` (Hermes):

```ini
# LLM (outline, style_spec, content planning)
U1_LM_API_KEY="your-api-key"
U1_LM_BASE_URL="https://token.sensenova.cn/v1"

# Text-to-image (required for creative mode, on-demand for standard mode)
U1_API_KEY="your-api-key"
```

Optional variables `U1_IMAGE_GEN_*`, `VLM_*`, `LLM_*` override default models and timeouts. Full list: [`skills/u1-image-base/README.md`](../skills/u1-image-base/README.md).

Run environment doctor before invoking:

> Run the `ppt-doctor` skill

### 3. Invoke in Agent

`ppt-entry` is the unified entry point and dispatches to creative or standard mode automatically:

> "Make a 10-page deck on team OKRs for an executive audience, minimalist style"

Or call by name:

> /skill ppt-entry "Team OKR review"

## Outputs

Decks are written to `$(pwd)/ppt_decks/<topic>_<timestamp>/`, containing:

- `task_pack.json` / `info_pack.json` — parsed task parameters from `ppt-entry`
- `style_spec.md`, `outline.json` — style and outline (standard mode)
- `pages/page_*.png` — full-page images (creative) or HTML-rendered slides (standard)
- `review.md` — per-page review summary (standard mode)
- `<deck_id>.pptx` — final PPTX

More samples: [`docs/ppt-examples.md`](ppt-examples.md) (TBD).
