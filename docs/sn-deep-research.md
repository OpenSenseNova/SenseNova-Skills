# SenseNova Deep Research Skills

English | [简体中文](sn-deep-research_cn.md)

This document describes the current deep-research stack after the integrated `sn-deep-research` upgrade. The old split planning / dimension-research / synthesis pipeline has been retired: planning, evidence gathering, review, synthesis, writing, stitching, and citation rendering now live under the `sn-deep-research` controller and its `agents/*` contracts.

## Current Deep Research Pipeline

| Skill / component | Role |
|---|---|
| [`sn-deep-research`](../skills/sn-deep-research/SKILL.md) | Unified entry point. Chooses quick / normal / heavy mode, creates the report directory, dispatches specialist agents, runs validators, and renders the final report. |
| `sn-deep-research/agents/scout.md` | Pre-research briefing and mode recommendation for normal / heavy runs. |
| `sn-deep-research/agents/plan.md` | Report type, dimensions, waves, dependencies, and perspective lenses. |
| `sn-deep-research/agents/research.md` | Per-dimension evidence gathering. Outputs schema-validated `sub_reports/dN.evidence.json`. |
| `validate_evidence.py` / `validate_outline.py` | Hard gates for evidence and outline contracts. |
| `review.md`, `perspective.md`, `supplement-planner.md` | Evidence review, coverage-gap checks, and targeted supplement plans. |
| `report-planner.md`, `report-writer.md`, `report-stitcher.md` | Outline/subset planning, section writing, and heavy-mode stitching. |
| [`sn-prepare-citations`](../skills/sn-prepare-citations/SKILL.md) | Converts `[^source_id]` footnotes into numbered citations and writes `report.md` + `citations.json`. |
| [`sn-report-format-discovery`](../skills/sn-report-format-discovery/SKILL.md) | Optional report-format discovery used by the planning agent when the target report format is unknown. |
| [`sn-research-report`](../skills/sn-research-report/SKILL.md) | Standalone report-structure reference/template skill; not part of the integrated pipeline control flow. |

## Search Skills Used by Research Agents

Research agents select search skills according to the dimension's source categories. Credentials are read from environment variables; the recommended convention is to keep them in the repository root `.env` (copy `.env.example`) and load them before running the skill.

| Skill | Coverage |
|---|---|
| [`sn-search-academic`](../skills/sn-search-academic/SKILL.md) | Academic papers, scholarly metadata, citation chains, encyclopedic context. |
| [`sn-search-code`](../skills/sn-search-code/SKILL.md) | GitHub, HuggingFace, StackOverflow, Hacker News developer sources. |
| [`sn-search-finance`](../skills/sn-search-finance/SKILL.md) | Securities, market data, financial reports, filings, and finance news. |
| [`sn-search-market-cn`](../skills/sn-search-market-cn/SKILL.md) | China market and industry data. |
| [`sn-search-social-cn`](../skills/sn-search-social-cn/SKILL.md) | Zhihu, Xiaohongshu, Weibo, Douyin, Bilibili. |
| [`sn-search-social-en`](../skills/sn-search-social-en/SKILL.md) | Reddit, Twitter/X via TikHub, YouTube. |
| [`sn-search-social-media`](../skills/sn-search-social-media/SKILL.md) | Public social/media trend sources such as GitHub public search, Hacker News hotspots, StackExchange, Wikimedia pageviews. |
| [`sn-search-year-report`](../skills/sn-search-year-report/SKILL.md) | Annual reports, SEC-style filings, and public company disclosures. |

## Quick Start

Use the unified entry point for deep research requests:

```text
/skill sn-deep-research "Home robotics supply chain"
```

The controller chooses a mode and follows the corresponding pipeline:

- **quick**: one skim evidence dimension → single writer → citation rendering.
- **normal**: scout → plan → parallel evidence research + validation/review → report planner → single full-outline writer → final review → citation rendering.
- **heavy**: normal plus multi-wave scheduling, perspectives, supplement planning, parallel section writers, stitcher, and full final review.

## Configuration

1. Copy `.env.example` to `.env`.
2. Fill only the keys needed for the sources you want to use.
3. Load `.env` into the runtime environment before invoking skills.
4. Do not pass secrets in skill payloads, prompts, reports, logs, or commits.

Missing optional credentials degrade the relevant source family to public/general search rather than blocking the whole run. Tier-1 runtime capabilities (file I/O, shell execution, web search, web fetch) are still required for reliable deep research.
