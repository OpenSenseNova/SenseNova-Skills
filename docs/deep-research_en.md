# Deep Research & Search Skills

English | [简体中文](deep-research.md)

This document collects the sn-deep-research skills (`sn-deep-research`, `sn-research-planning`, `sn-dimension-research`, `sn-research-synthesis`, `sn-research-report`, `sn-report-format-discovery`) and the search skills (`sn-search-academic`, `sn-search-code`, `sn-search-social-cn`, `sn-search-social-en`).

Deep-research skills handle planning, synthesis, and final writing. Search skills are invoked by `sn-dimension-research` during per-dimension evidence gathering, covering academic papers, developer resources, and Chinese & English social platforms. Together they form an end-to-end pipeline.

## Prerequisites

- **Python** 3.9 or later (3.10+ recommended).
- **OpenClaw `web_search` must be configured and available** — the sn-deep-research orchestrator gates on it at startup.
- Optional / required platform API keys depending on the dimensions you research (see [API Keys](#2-api-keys)).

## Deep-Research Skills

| Name | Role | Description |
|------|------|-------------|
| [`sn-deep-research`](../skills/sn-deep-research/SKILL.md) | **Deep-research entry** | End-to-end orchestrator: `request.md → plan.json → sub_reports/*.md → synthesis.md → report.md`; artifacts persisted to `report_dir`; supports resume. |
| [`sn-research-planning`](../skills/sn-research-planning/SKILL.md) | Research planning | Produces `plan.json` from `request.md` in a single pass, covering scope, report shape, dimension breakdown (3–8), key questions, search strategies, dependencies, and completion criteria. |
| [`sn-dimension-research`](../skills/sn-dimension-research/SKILL.md) | Per-dimension evidence | Calls [search skills](#search-skills) per the dimension's `search_strategy` for multi-round gathering and cross-validation; emits `sub_reports/{dimension_id}.md`. |
| [`sn-research-synthesis`](../skills/sn-research-synthesis/SKILL.md) | Synthesis & judgment | Synthesizes multiple `sub_reports` into `synthesis.md`: main conclusions, evidence strength, cross-dimension consensus, key conflicts, and uncertainties. |
| [`sn-research-report`](../skills/sn-research-report/SKILL.md) | Final writing / rewriting | Turns the judgment layer into final `report.md`; also supports targeted edits on existing reports (rewrite, polish, restructure, add tables). |
| [`sn-report-format-discovery`](../skills/sn-report-format-discovery/SKILL.md) | Report-format discovery | Researches what such a report typically looks like, returning section structure, mandatory elements, and style constraints; usable standalone or as input for `sn-deep-research`'s `report_shape`. |

## Search Skills

| Name | Role | Description |
|------|------|-------------|
| [`sn-search-academic`](../skills/sn-search-academic/SKILL.md) | Academic search | ArXiv (with section-by-section HTML full-text reading) / Semantic Scholar (citation counts and forward/backward citation chains) / PubMed (with PMC open-access full text) / Wikipedia (multi-language). |
| [`sn-search-code`](../skills/sn-search-code/SKILL.md) | Developer search | GitHub (repos / code / issues) / Stack Overflow (by tag / votes) / Hacker News / HuggingFace (models / datasets / Spaces). |
| [`sn-search-social-cn`](../skills/sn-search-social-cn/SKILL.md) | Chinese social search | Bilibili / Zhihu / Douyin; Zhihu and Douyin require cookies, Bilibili cookie is optional. |
| [`sn-search-social-en`](../skills/sn-search-social-en/SKILL.md) | English social search | Reddit (subreddit / sort / time range) / Twitter (X) (via TikHub) / YouTube (API key). |

Each search skill ships its own copy of `search_utils.py` under its `scripts/` directory; it is a shared internal module, not user-facing.

## Quick Start

Use these skills from [OpenClaw](https://openclaw.ai/). For skill registration steps, see [`sn-image-generate_en.md`](sn-image-generate_en.md#1-register-skills).

### 1. Hard precheck: `web_search`

Before creating `report_dir`, writing `request.md`, or entering any research stage, `sn-deep-research` **must confirm that OpenClaw `web_search` is currently available**. Do not start research — and do not substitute memory/prior knowledge for online evidence — until this is confirmed.

- Static check: `tools.web.search.provider` and `plugins.entries.<plugin>.config.webSearch.*` are configured
- If unsure, issue a minimal `web_search` probe; proceed on success; stop on missing key, provider not ready, service unreachable, or `search disabled`

### 2. API Keys

Set as needed in `~/.openclaw/.env` (or `~/.hermes/.env`):

| Platform | Required / Optional | Env var | Notes |
|----------|--------|---------|-------|
| GitHub repo/issue search | Optional (rate-limit boost) | `GITHUB_TOKEN` | Anonymous works for public search |
| GitHub code search | **Required** | `GITHUB_TOKEN` | Mandatory for `--type code` |
| Semantic Scholar | Optional | `S2_API_KEY` | Rate-limit boost |
| PubMed | Optional | `NCBI_API_KEY` | Lifts cap from 3 req/s to 10 req/s |
| HuggingFace | Optional | `HF_TOKEN` | Rate-limit boost |
| Bilibili | Optional | `BILIBILI_COOKIE` | Improves result quality |
| Zhihu | **Required** | `ZHIHU_COOKIE` | Search will not work without it |
| Douyin | **Required** | `DOUYIN_COOKIE` | Search will not work without it |
| Twitter/X | **Required** | `TIKHUB_TOKEN` | Routed via TikHub |
| YouTube | **Required** | `YOUTUBE_API_KEY` | YouTube Data API v3 |

ArXiv, Stack Overflow, Hacker News, and Reddit public search require no key.

### 3. Python dependencies

Search skills do not ship a per-skill `requirements.txt`; deps are typically present in the base execution image. If preparing a fresh environment:

```bash
pip install requests httpx lxml beautifulsoup4
```

Deep-research skills do not call HTTP directly — they rely on OpenClaw `web_search` and the search scripts above.

### 4. Invoke in Agent

**Deep-research entry** — describe the topic to trigger:

> "Deep research: home robotics supply chain and key players in 2025"

Or call by name:

> /skill sn-deep-research "Home robotics supply chain"

**Standalone search** — describe the request:

> "Find recent ArXiv papers on RAG, sorted by citation count"
> "Search GitHub for Python implementations of in-context learning"

Or call by name:

> /skill sn-search-academic "retrieval-augmented generation"
> /skill sn-search-code "in-context learning python"
> /skill sn-search-social-cn "扩散模型 教程"
> /skill sn-search-social-en "vision transformer explained"

**Per-stage sn-deep-research invocation** (advanced):

> /skill sn-research-planning  # produce plan.json from a written request.md
> /skill sn-dimension-research # gather evidence for a specific dimension in plan.json
> /skill sn-research-synthesis # synthesize existing sub_reports into synthesis.md
> /skill sn-research-report    # write report.md from synthesis.md + sub_reports

**Directly invoking search scripts as subprocesses**:

```bash
GITHUB_TOKEN=ghp_xxx python3 skills/sn-search-code/scripts/github_search.py "import asyncio" --type code --limit 5
ZHIHU_COOKIE="..." python3 skills/sn-search-social-cn/scripts/zhihu_search.py "Python 异步编程" --limit 5
```

## Outputs

### Deep Research

Report artifacts are written to `{workspace}/reports/{YYYY-MM-DD}-{slug}-{hex4}/`:

- `request.md` — original user request and scope
- `plan.json` — dimension breakdown, key questions, search strategies, report shape
- `sub_reports/d1.md` … `d8.md` — per-dimension evidence (with evidence table and confidence)
- `synthesis.md` — synthesis (main lines, consensus, conflicts, uncertainty)
- `report.md` — final report

_See the "Sample Outputs" section in the top-level [`README.md`](../README.md#sample-outputs) for end-to-end examples._

### Search

All search scripts emit JSON to stdout in a unified shape:

```json
{
  "success": true,
  "query": "...",
  "provider": "...",
  "items": [
    {"title": "...", "url": "...", "snippet": "..."}
  ],
  "error": null
}
```

ArXiv and PMC full-text readers additionally return structured section content for incremental reading.
