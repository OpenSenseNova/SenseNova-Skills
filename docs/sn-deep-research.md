# SenseNova Deep Research Skills

English | [简体中文](sn-deep-research_cn.md)

This document describes the current deep-research stack after the integrated `sn-deep-research` upgrade. The old split planning / dimension-research / synthesis pipeline has been retired: planning, evidence gathering, review, synthesis, writing, stitching, and citation rendering now live under the `sn-deep-research` controller and its `agents/*` contracts.

## Current Deep Research Pipeline

| Skill / component | Role |
|---|---|
| [`sn-deep-research`](../skills/sn-deep-research/SKILL.md) | Unified entry point. Chooses quick / normal / heavy mode, creates the report directory, dispatches specialist agents, runs validators, and renders the final report. |
| `sn-deep-research/agents/scout.md` | Pre-research briefing, mode recommendation, and invocation of the format-discovery skill for normal / heavy runs. |
| `sn-deep-research/agents/plan.md` | Research planner only: turns the briefing and confirmed presentation format's evidence needs into dimensions, waves, dependencies, and perspective lenses. |
| `sn-deep-research/agents/research.md` | Per-dimension evidence gathering. Outputs schema-validated `sub_reports/dN.evidence.json`. |
| `validate_evidence.py` / `validate_outline.py` | Hard gates for evidence and outline contracts. |
| `review.md`, `perspective.md`, `supplement-planner.md` | Evidence review, coverage-gap checks, and targeted supplement plans. |
| `report-planner.md`, `report-writer.md`, `report-stitcher.md` | Implements the user-confirmed presentation format as an evidence-bound outline, writes its content, and stitches heavy-mode output. These roles do not reselect the format. |
| [`sn-prepare-citations`](../skills/sn-prepare-citations/SKILL.md) | Converts `[^source_id]` footnotes into numbered citations and writes `report.md` + `citations.json`. |
| [`sn-report-format-discovery`](../skills/sn-report-format-discovery/SKILL.md) | The sole owner of format discovery; scout supplies briefing context so it can compare a research report, academic paper, table-first analytical output, decision memo, or a custom form. |
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

## Related Skills Outside the Current Controller Pipeline

These skills remain in the repository, but they are not automatic steps in the current `sn-deep-research` integrated pipeline. Use them separately only when the user explicitly asks for the corresponding output format or maintenance action.

| Skill | Current status |
|---|---|
| [`sn-md-to-html-report`](../skills/sn-md-to-html-report/SKILL.md) | Reworks an existing Markdown report into a self-contained HTML feature page; not called automatically by `sn-deep-research`. |
| [`sn-search-image`](../skills/sn-search-image/SKILL.md) | Image search skill; the current research-agent source categories do not map it as a mandatory entry point. |
| [`sn-update`](../skills/sn-update/SKILL.md) | Maintenance skill for refreshing/updating the `sn-*` bundle; not part of research execution. |

## Quick Start

Use the unified entry point for deep research requests:

```text
/skill sn-deep-research "Home robotics supply chain"
```

The controller chooses a mode and follows the corresponding pipeline:

- **quick**: one skim evidence dimension → single writer → citation rendering.
- **normal**: scout briefing + format-discovery invocation → one pre-research confirmation (mode + final form) → research plan → parallel evidence research + validation/review → report planner implements the confirmed form → writer → final review → citation rendering.
- **heavy**: normal plus multi-wave scheduling, perspectives, supplement planning, parallel section writers, stitcher, and full final review.

For normal and heavy runs, scout invokes `sn-report-format-discovery` to write `format_proposal.json`. The proposal concerns the final presentation form inside Markdown, not a file suffix or a concrete chapter blueprint. After the user chooses a candidate, the controller writes read-only `format.json`; plan, report planner, writer, stitcher, and review must preserve its `selected_format` and `defining_features`.

## Configuration

1. Copy `.env.example` to `.env`.
2. Fill only the keys needed for the sources you want to use.
3. Load `.env` into the runtime environment before invoking skills.
4. Do not pass secrets in skill payloads, prompts, reports, logs, or commits.

Missing optional credentials degrade the relevant source family to public/general search rather than blocking the whole run. Tier-1 runtime capabilities (file I/O, shell execution, web search, web fetch) are still required for reliable deep research.
