# PPT Generation Skills

English | [简体中文](sn-ppt-generate_cn.md)

This document collects the PPT generation skills (`sn-ppt-entry`, `sn-ppt-story`, `sn-ppt-standard`, `sn-ppt-dazzle`, `sn-ppt-creative`, `sn-ppt-doctor`, `sn-ppt-tools`, `sn-ppt-workbench`) used in Hermes / OpenClaw to produce decks (Static HTML, Dynamic HTML, Creative) and export `.pptx` from user prompts and reference documents.

## Prerequisites

- **Python** 3.9 or later (3.10+ recommended).
- **Node.js** runtime (used by `sn-ppt-standard` during per-page HTML processing).
- LLM/VLM and text-to-image API credentials (see below).

## Skills

| Name | Role | Description |
|------|------|-------------|
| [`sn-ppt-entry`](../skills/sn-ppt-entry/SKILL.md) | **PPT entry** | Collects role / audience / scene / page count / mode (creative or standard), parses pdf / docx / md / txt inputs, emits `task_pack.json` + `info_pack.json`, and dispatches to a downstream mode. |
| [`sn-ppt-doctor`](../skills/sn-ppt-doctor/SKILL.md) | PPT environment doctor | Checks local rendering/export dependencies (Python/Node Playwright, Chromium, PPTX exporter) and Bundled media config; reports only, never writes `.env` or modifies the task directory. |
| [`sn-ppt-creative`](../skills/sn-ppt-creative/SKILL.md) | PPT creative mode | One full-page 16:9 PNG per slide generated from a per-page composed prompt; exports PPTX. |
| [`sn-ppt-standard`](../skills/sn-ppt-standard/SKILL.md) | PPT standard mode | `style_spec` → outline → asset plan + per-slot images + VLM QA → per-page HTML → per-page review (optional rewrite) → summary `review.md` → PPTX export. |

Model chat, vision, and image generation prefer the host Agent's native tools; when native tools are absent or fail, `sn-ppt-tools` provides the Bundled fallback (web search, image search, image generation).

## Quick Start

On Hermes, copy or symlink the whole `sn-ppt-*` packages under this repo's `skills/` into `~/.hermes/skills/` to register them; on OpenClaw, use `~/.openclaw/skills/`. For per-host install steps, see the "How to Use" section in [`README.md`](../README.md#how-to-use).

### 1. Python dependencies

```bash
# sn-ppt-entry: PDF / DOCX parsing
pip install -r skills/sn-ppt-entry/requirements.txt

# sn-ppt-creative: PPTX export
pip install -r skills/sn-ppt-creative/requirements.txt

# sn-ppt-standard: first deployment runs its bundled install script (venv, fonts, Chromium, ...)
bash skills/sn-ppt-standard/scripts/install.sh
```

`sn-ppt-doctor` / `sn-ppt-tools` use only the Python stdlib; `sn-ppt-story` is pure orchestration with no extra dependencies; `sn-ppt-dazzle` ships its own renderer and reuses the installed Chromium. `sn-ppt-entry` relies on `pypdf` / `python-docx` / `PyMupdf`; `sn-ppt-standard` HTML rendering needs Python Playwright Chromium, installed on first deployment by `scripts/install.sh` (which also sets up the normalize venv, OFL fonts, FontTools/Brotli/Pillow).

HTML → PPTX export (`scripts/export_pptx/`) needs the Node.js runtime; the npm packages (`pptxgenjs` / `echarts` / `playwright`) ship inside the skill's `node_modules`, but its Playwright Chromium binary must be installed separately:

```bash
npm --prefix skills/sn-ppt-standard/scripts/export_pptx exec playwright install chromium
```

> Linux note: the Python renderer (`render.py`) automatically prepends `~/pwdeps/lib` (fallback `~/cdeps/lib`) to
> `LD_LIBRARY_PATH`; the HTML → PPTX exporter is a separate Node process without that logic. If export fails with a
> Chromium launch error (e.g. missing `libnspr4.so`), add the directory containing those libraries to the Agent
> process `LD_LIBRARY_PATH`, or follow the `install_hint` in `sn-ppt-doctor` output.

### 2. API keys and environment variables

LLM chat, vision, and page review use the host Agent's native model capabilities — **no model variables are required for this suite**.
Only configure the following when the host's native search / image-generation tools are absent or fail and the Bundled fallback is needed.
Write them to `~/.hermes/.env` (Hermes) or `~/.openclaw/.env` (OpenClaw);
`SN_PPT_ENV_FILE=/absolute/path/to/file` selects a custom file. Existing process variables override file values.
`sn-ppt-doctor` reports the `.env` file actually read and the missing fields (never the key values).

```ini
# Web and image search share one key (Bundled fallback): defaults to google.serper.dev
SN_PPT_SEARCH_API_KEY="<search-api-key>"

# Image generation (Bundled fallback): OpenAI / SenseNova-compatible sync /images/generations endpoint
SN_PPT_IMAGE_GEN_URL="https://your-host/images/generations"
SN_PPT_IMAGE_GEN_API_KEY="<image-generation-api-key>"
SN_PPT_IMAGE_GEN_MODEL="<image-generation-model>"
```

Fallback chains: search URL may also use `SN_PPT_SEARCH_BASE_URL` / `SERPER_BASE_URL` (default google.serper.dev), key may also be `SERPER_API_KEY`; image-gen URL falls back to `SN_IMAGE_GEN_BASE_URL` / `SN_BASE_URL` + `/images/generations`, key to `SN_IMAGE_GEN_API_KEY` / `SN_API_KEY`, model to `SN_IMAGE_GEN_MODEL`.
Full checklist: [`skills/sn-ppt-doctor/SKILL.md`](../skills/sn-ppt-doctor/SKILL.md).

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
