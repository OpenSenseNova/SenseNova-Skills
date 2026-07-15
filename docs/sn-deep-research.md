# SenseNova Deep Research Skills

English | [简体中文](sn-deep-research_cn.md)

This document describes the current deep-research stack after the integrated `sn-deep-research` upgrade. The old split planning / dimension-research / synthesis pipeline has been retired: planning, evidence gathering, review, synthesis, writing, stitching, and citation rendering now live under the `sn-deep-research` controller and its `agents/*` contracts.

## Current Deep Research Pipeline

| Skill / component | Role |
|---|---|
| [`sn-deep-research`](../skills/sn-deep-research/SKILL.md) | Unified entry point. Chooses quick / normal / heavy mode, creates the report directory, dispatches specialist agents, runs validators, and renders the final report. |
| `sn-deep-research/agents/scout.md` | Pre-research briefing, mode recommendation, and invocation of the format-discovery skill for normal / heavy runs. |
| `sn-deep-research/agents/plan.md` | Research planner only: splits dimensions by coverage obligations and creates a dependency/wave only when downstream search scope truly needs upstream findings. |
| `sn-deep-research/agents/research.md` | Per-dimension evidence gathering. Outputs `sub_reports/dN.evidence.json` and pins every used full text in the report-scoped `source_cache/`. |
| `validate_plan.py` / `validate_evidence.py` / `validate_outline.py` | Hard gates for topology, source snapshots, format preference, outlines, and evidence subsets. |
| `review.md`, `perspective.md`, `supplement-planner.md` | Evidence review, coverage-gap checks, and targeted supplement plans. |
| `report-planner.md`, `report-writer.md`, `report-stitcher.md` | Implements the confirmed form as evidence-bound content units, then assembles normal/heavy output without forcing article sections. |
| `source_snapshot.py` | Stores normalized-URL, content-addressed, immutable UTF-8 source snapshots reused by research, review, and supplements. |
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

- **quick**: one skim evidence dimension → source snapshot and evidence validation → quick writer → citation rendering.
- **normal**: scout + format confirmation → validated plan → parallel evidence research/review → v2 content units → per-unit writers → stitcher → final review → citation rendering.
- **heavy**: normal plus broader coverage, perspectives, supplement planning, and full review. Independent dimensions stay parallel; only true information dependencies create later waves, and downstream search waits for finalized upstream evidence.

For normal and heavy runs, scout invokes `sn-report-format-discovery` to write `format_proposal.json`. Three orthogonal contracts remain separate: `selected_format` is the overall deliverable form (report, brief, board, and so on), the content `paradigm` controls how reasoning advances, and `structure_preference` records whether the primary information carrier (narrative, matrix, timeline, checklist, and so on) is required, preferred, or automatic. Report planning chooses `organization_decision + content_units` only after evidence exists; there is no fixed comparison-to-matrix or investigation-to-timeline mapping.

Every v1.2 evidence item has a `snapshot_ref` into `source_cache/{url_hash}/{content_hash}.md`. Review groups checks by ref, and supplement work performs cache lookup before any fetch; existing bodies are reused and newly fetched bodies are stored immediately.

## Configuration

1. Copy `.env.example` to `.env`.
2. Fill only the keys needed for the sources you want to use.
3. Load `.env` into the runtime environment before invoking skills.
4. Do not pass secrets in skill payloads, prompts, reports, logs, or commits.

Missing optional credentials degrade the relevant source family to public/general search rather than blocking the whole run. Tier-1 runtime capabilities (file I/O, shell execution, web search, web fetch) are still required for reliable deep research.
