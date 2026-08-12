# SenseNova Deep Research Skills

English | [简体中文](sn-deep-research_cn.md)

This document describes the current deep-research stack after the integrated `sn-deep-research` upgrade. The old split planning / dimension-research / synthesis pipeline has been retired: planning, evidence gathering, review, synthesis, writing, stitching, and citation rendering now live under the `sn-deep-research` controller and its `agents/*` contracts.

## Current Deep Research Pipeline

| Skill / component | Role |
|---|---|
| [`sn-deep-research`](../skills/sn-deep-research/SKILL.md) | Unified entry point. Chooses quick / normal / heavy mode, starts the Research Workbench progress page, dispatches specialist agents, runs validators, and renders the final report. |
| `sn-deep-research/agents/scout.md` | Heavy-mode pre-research briefing. It consumes the request-level `format` string but does not discover or persist format state. |
| `sn-deep-research/agents/plan.md` | Research planner only: divides the request into independently executable work packages with explicit scope ownership and minimal duplicate search. |
| `sn-deep-research/agents/research.md` | Per-dimension evidence gathering. Reads its work package from `plan.json`, verifies original pages, and outputs validated `sub_reports/dN.evidence.json`. |
| `validate_briefing.py` / `validate_plan.py` / `validate_evidence.py` / `validate_supplement_plan.py` / `validate_outline.py` | Hard gates for briefing structure, independent plan work packages, evidence integrity, supplement-plan generation, outlines, and evidence subsets. |
| `review.md`, `perspective.md`, `supplement-planner.md` | Evidence review, coverage-gap checks, and targeted supplement plans. |
| `report-writer.md` | Writes quick and normal reports in one pass from all routed evidence; in heavy mode it writes evidence-bound content units. |
| `report-planner.md`, `report-stitcher.md` | Heavy-only report organization and assembly without forcing article sections. |
| [`sn-prepare-citations`](../skills/sn-prepare-citations/SKILL.md) | Converts `[^source_id]` footnotes into numbered citations and writes `report.md` + `citations.json`. |
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
| [`sn-report-format-discovery`](../skills/sn-report-format-discovery/SKILL.md) | Optional standalone format recommendation; `sn-deep-research` itself uses one request-level `format` string and does not create format artifacts. |
| [`sn-md-to-html-report`](../skills/sn-md-to-html-report/SKILL.md) | Reworks an existing Markdown report into a self-contained HTML feature page; not called automatically by `sn-deep-research`. |
| [`sn-search-image`](../skills/sn-search-image/SKILL.md) | Image search skill; the current research-agent source categories do not map it as a mandatory entry point. |
| [`sn-update`](../skills/sn-update/SKILL.md) | Maintenance skill for refreshing/updating the `sn-*` bundle; not part of research execution. |

## Quick Start

Use the unified entry point for deep research requests:

```text
/skill sn-deep-research "Home robotics supply chain"
```

The controller chooses a mode and follows the corresponding pipeline:

- **quick**: one self-contained research agent → validated evidence → one-pass writer → citation rendering.
- **normal**: validated plan → parallel evidence research → one `quick_synthesis` writer over all evidence → citation rendering.
- **heavy**: briefing → validated plan → parallel evidence research → review, perspectives, and targeted supplements → evidence-bound content units → stitching and full review.

The controller resolves one request-level `format` string before dispatch, for example `report`, `paper`, `table`, or `memo`, and passes it alongside `language`. It creates no `format.json`, proposal, or format schema. Quick and normal write the complete report directly; only heavy uses report planning and content units.

Each evidence file keeps verifiable source URLs, snippets, quote types, claims, and writing-context boundaries. Research must read the original page before admitting evidence; heavy-mode review deduplicates URLs and fetches each page once per review pass. Supplement research updates the same dimension evidence file and records unresolved boundaries in `writing_context`.

## Configuration

1. Copy `.env.example` to `.env`.
2. Fill only the keys needed for the sources you want to use.
3. Load `.env` into the runtime environment before invoking skills.
4. Do not pass secrets in skill payloads, prompts, reports, logs, or commits.

Missing optional credentials degrade the relevant source family to public/general search rather than blocking the whole run. Tier-1 runtime capabilities (file I/O, shell execution, web search, web fetch) are still required for reliable deep research.
