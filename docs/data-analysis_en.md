# Data Analysis (DA) Skills

English | [简体中文](data-analysis.md)

This document collects the data-analysis skills (`sn-da-excel-workflow`, `sn-da-image-caption`, `sn-da-large-file-analysis`) covering multi-sheet Excel ingestion and cleaning, high-performance large-file analysis, and image-based data extraction and visualization.

## Prerequisites

- **Python** 3.9 or later (3.10+ recommended).
- Standard data stack: `pandas`, `openpyxl` (with read_only mode), `pyarrow`, `matplotlib`, `numpy`.
- `sn-da-image-caption` requires VLM API credentials.

## Skills

| Name | Role | Description |
|------|------|-------------|
| [`sn-da-excel-workflow`](../skills/sn-da-excel-workflow/SKILL.md) | Excel analysis orchestrator | Multi-sheet read, large-file detection (≥10k rows triggers Parquet optimization, ≥100k routes to `sn-da-large-file-analysis`), cleaning, conditional filtering, cross-sheet aggregation, and Excel/CSV export. |
| [`sn-da-image-caption`](../skills/sn-da-image-caption/SKILL.md) | Image understanding & data extraction | Table OCR / chart interpretation / screenshot description / UI description; can return DataFrame, re-render visualizations, and export Excel/CSV. |
| [`sn-da-large-file-analysis`](../skills/sn-da-large-file-analysis/SKILL.md) | High-performance large-file analysis | Streaming read (`openpyxl read_only` + `iter_rows`), Parquet conversion, memory optimization (dtype downcasting), vectorized operations, chunked writes. |

`sn-da-excel-workflow` is the typical entry point and auto-selects read/write strategy by file size, routing to `sn-da-large-file-analysis` when needed.

## Quick Start

Use these skills from [OpenClaw](https://openclaw.ai/). For skill registration steps, see [`sn-image-generate_en.md`](sn-image-generate_en.md#1-register-skills).

### 1. Python dependencies

DA skills do not ship a per-skill `requirements.txt`; deps are typically present in the base execution image. If preparing a fresh environment:

```bash
pip install pandas openpyxl pyarrow matplotlib numpy
```

`sn-da-image-caption` additionally needs an HTTP client (`requests` or `httpx`).

### 2. API keys and environment variables

`sn-da-image-caption` calls a vision model for image parsing. Set in `~/.openclaw/.env` (or `~/.hermes/.env`):

```ini
VISION_API_KEY="your-vision-api-key"
VISION_API_BASE="https://your-vlm-endpoint"
```

`sn-da-excel-workflow` and `sn-da-large-file-analysis` do not call models directly and need no API key.

### 3. Invoke in Agent

Provide the data file and describe the task:

> "Analyze this Excel: aggregate sales by department, export CSV"

Or call by name:

> /skill sn-da-excel-workflow

Image tasks:

> "Read this chart and extract the data into Excel"
> /skill sn-da-image-caption

## Outputs

- Analysis results are written to `*.xlsx` / `*.csv` (or visualization images)
- Large-file flows produce intermediate Parquet files to accelerate subsequent steps
- Image parsing returns structured JSON or Markdown tables
