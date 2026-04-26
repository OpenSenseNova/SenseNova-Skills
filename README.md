<p align="center">
  <img src="assets/logo.webp" alt="SenseNova logo" width="180" />
</p>

# SenseNova-Skills

English | [简体中文](README_CN.md)

The SenseNova model family plugs directly into agent runtimes such as [OpenClaw](https://openclaw.ai/) and [hermes-agent](https://github.com/nousresearch/hermes-agent), and gains stronger capabilities through skills.

In this repository each skill lives in its own directory and declares triggers, capabilities, and execution flow through a `SKILL.md` file, following the [Agent Skills](https://agentskills.io/) convention.

The skills cover **image generation & visualization**, **slide-deck (PPT) generation**, **Excel data analysis**, and **deep research** — usable standalone or composed into end-to-end workflows.

## How to Use

**These skills are designed to run inside an [Agent Skills](https://agentskills.io/)-compatible agent — for the best experience, pair them with [OpenClaw](https://openclaw.ai/) or [hermes-agent](https://github.com/NousResearch/hermes-agent). See [`INSTALL.md`](INSTALL.md) for the full install + LLM configuration walkthrough.**

Clone this repository, then copy subdirectories under `skills/` into the skills directory your agent loads from:

| Agent | Target directory |
|-------|------------------|
| [OpenClaw](https://openclaw.ai/) | `~/.openclaw/skills/` |
| [hermes-agent](https://github.com/nousresearch/hermes-agent) | `~/.hermes/skills/` |

For example, copy all skills into OpenClaw:

```bash
git clone https://github.com/OpenSenseNova/SenseNova-Skills.git
mkdir -p ~/.openclaw/skills
cp -r SenseNova-Skills/skills/* ~/.openclaw/skills/
```

For Hermes, swap the target to `~/.hermes/skills/`.

Per-category Python dependencies, API keys, and invocation examples are documented in the 📖 Full guide for each section.

## Skills List

### 🎨 Image & Visualization

📖 Full guide: [`docs/sn-image-generate_en.md`](docs/sn-image-generate_en.md) (prerequisites, Quick Start, API config, and invocation samples).


| Name                                               | Label                          | Description                                                                                                                                                       |
| -------------------------------------------------- | ------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [`sn-image-doctor`](skills/sn-image-doctor/SKILL.md)           | Environment Doctor             | Validates the SenseNova-Skills environment — checks `sn-image-base` install, Python deps, and required env vars; interactively fills missing values into `.env`. |
| [`sn-image-base`](skills/sn-image-base/SKILL.md)   | Image Base Layer (Tier 0)      | Low-level tools — text-to-image (`sn-image-generate`), image recognition (`sn-image-recognize`), and text optimization (`sn-text-optimize`) — exposed through a unified `sn_agent_runner.py`, designed to be called by upper-layer skills. |
| [`sn-infographic`](skills/sn-infographic/SKILL.md) | Infographic Generation (Tier 1) | Auto prompt-quality scoring, layout/style selection (87 layouts / 66 styles), multi-round generation with VLM review and quality ranking, producing publication-ready infographics. |


### 📊 Presentations (PPT)

📖 Full guide: [`docs/ppt-generate_en.md`](docs/ppt-generate_en.md) (prerequisites, Quick Start, API config, and invocation samples).


| Name                                           | Label                  | Description                                                                                                                                                                                                              |
| ---------------------------------------------- | ---------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| [`sn-ppt-entry`](skills/sn-ppt-entry/SKILL.md)       | **PPT Entry Point**    | **Unified entry point for PPT generation.** Collects role / audience / scenario / page count / mode (creative or standard), parses uploaded pdf / docx / md / txt, emits `task_pack.json` + `info_pack.json`, and dispatches to the chosen mode. |
| [`sn-ppt-doctor`](skills/sn-ppt-doctor/SKILL.md)     | PPT Environment Doctor | Environment check for the PPT pipeline — validates `sn-image-base`, API keys, the Node runtime, and optional deps; writes missing required vars into `.env`.                                                             |
| [`sn-ppt-creative`](skills/sn-ppt-creative/SKILL.md) | PPT Creative Mode      | One full-page 16:9 PNG per slide, generated via `sn-image-generate` with a per-page composed prompt.                                                                                                                     |
| [`sn-ppt-standard`](skills/sn-ppt-standard/SKILL.md) | PPT Standard Mode      | `style_spec` → outline → asset plan + per-slot images + VLM QC → per-page HTML → per-page review (with optional rewrite) → aggregated `review.md` → PPTX export.                                                         |


### 📈 Data Analysis (DA)

📖 Full guide: [`docs/data-analysis_en.md`](docs/data-analysis_en.md) (prerequisites, Quick Start, API config, and invocation samples).


| Name                                                               | Label                                | Description                                                                                                                                                            |
| ------------------------------------------------------------------ | ------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [`sn-da-excel-workflow`](skills/sn-da-excel-workflow/SKILL.md)           | Excel Analysis Orchestration         | End-to-end Excel pipeline — multi-sheet read, large-file detection (≥10k rows triggers Parquet), cleaning, conditional filtering, cross-sheet aggregation, and Excel/CSV export. |
| [`sn-da-image-caption`](skills/sn-da-image-caption/SKILL.md)             | Image Understanding & Data Extraction | For image-first inputs — table OCR, chart understanding, screenshot/UI description; parses captions into DataFrames, recreates visualizations, exports Excel/CSV.    |
| [`sn-da-large-file-analysis`](skills/sn-da-large-file-analysis/SKILL.md) | High-Performance Large-File Analysis | Streaming reads for ≥10k-row Excel datasets (openpyxl read_only + iter_rows), Parquet conversion, memory optimization, chunked processing, large-file writes.        |


### 🔬 Deep Research

📖 Full guide: [`docs/deep-research_en.md`](docs/deep-research_en.md) (prerequisites, `web_search` precheck, Quick Start, and per-stage invocation).


| Name                                                                 | Label                          | Description                                                                                                                                                       |
| -------------------------------------------------------------------- | ------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [`sn-deep-research`](skills/sn-deep-research/SKILL.md)                     | **Deep Research Entry Point**  | **Unified entry point for deep research.** End-to-end orchestrator: planning → per-dimension evidence gathering → synthesis → final `report.md`. Artifacts persist to `report_dir`; supports resumable execution. |
| [`sn-research-planning`](skills/sn-research-planning/SKILL.md)             | Research Planning              | Produces `plan.json` from `request.md` in a single pass — scoping, report-shape, dimension breakdown, key questions, search strategy, dependencies, and completion criteria. |
| [`sn-dimension-research`](skills/sn-dimension-research/SKILL.md)           | Per-Dimension Evidence Gathering | Executes one dimension from `plan.json` — runs the dimension's `search_strategy`, filters evidence, cross-validates, and writes `sub_reports/{dimension_id}.md`. |
| [`sn-research-synthesis`](skills/sn-research-synthesis/SKILL.md)           | Judgment Synthesis             | Synthesizes multiple `sub_reports` into `synthesis.md` — main-thread judgments, evidence strength, cross-dimension consensus, key conflicts, and uncertainties.   |
| [`sn-research-report`](skills/sn-research-report/SKILL.md)                 | Final Report Writing & Editing | Renders the judgment layer into the final `report.md`; also handles targeted rewrites — restructuring, polishing, table-augmentation — for an existing draft.    |
| [`sn-report-format-discovery`](skills/sn-report-format-discovery/SKILL.md) | Report-Format Discovery        | Answers "what should this kind of report look like" — derives section structure, required elements, and style constraints. Usable standalone or as the `report_shape` source for sn-deep-research. |
| [`sn-md-to-html-report`](skills/sn-md-to-html-report/SKILL.md)             | Markdown → HTML Report          | Converts the research `report.md` (or any Markdown doc) into a clean, single-file HTML reading view that opens offline — embedded images, side-panel TOC, responsive tables, and table-delimiter repair. |


### 🔍 Search

📖 Search skills are documented together with deep research: [`docs/deep-research_en.md`](docs/deep-research_en.md) (includes per-platform API keys, invocation, and unified JSON output).


| Name                                                   | Label                  | Description                                                                                                                                |
| ------------------------------------------------------ | ---------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| [`sn-search-academic`](skills/sn-search-academic/SKILL.md)   | Academic Search        | ArXiv (with section-level HTML reading) / Semantic Scholar (with citation counts) / PubMed (with PMC open-access full text) / Wikipedia, in one aggregated interface. |
| [`sn-search-code`](skills/sn-search-code/SKILL.md)           | Developer Search       | GitHub (repo / code / issue) / Stack Overflow / Hacker News / HuggingFace (models / datasets / spaces), aggregated.                        |
| [`sn-search-social-cn`](skills/sn-search-social-cn/SKILL.md) | Chinese Social Search  | Bilibili / Zhihu / Douyin search; some platforms require cookie auth.                                                                      |
| [`sn-search-social-en`](skills/sn-search-social-en/SKILL.md) | English Social Search  | Reddit / Twitter (X) / YouTube search.                                                                                                     |


## Sample Outputs

### 🎨 Infographic (sn-infographic)

A few `sn-infographic` outputs (more in [`docs/sn-infographic-examples.md`](docs/sn-infographic-examples.md)).

<p align="center"><img src="docs/images/teaser_v1.1.webp" width="800" alt="sn-infographic sample outputs"></p>

### 🧩 Memory price analysis — end-to-end pipeline

[`examples/memory-price-end2end-analysis`](examples/memory-price-end2end-analysis/) — end-to-end example: chains data analysis → deep research → PPT generation. Starting from a price CSV, it produces a Markdown / HTML data analysis report, an illustrated deep research report, and a 16-page PPTX.

- Depends on: [`sn-da-excel-workflow`](skills/sn-da-excel-workflow/SKILL.md), [`sn-deep-research`](skills/sn-deep-research/SKILL.md), [`sn-ppt-entry`](skills/sn-ppt-entry/SKILL.md), [`sn-ppt-standard`](skills/sn-ppt-standard/SKILL.md), [`sn-md-to-html-report`](skills/sn-md-to-html-report/SKILL.md)

### 📊 Employee performance analysis — single-skill case (data analysis)

[`examples/employee-performance-analysis`](examples/employee-performance-analysis/) — distills 10 monthly performance review spreadsheets into a Word-format performance report plus a visualized HTML report with 8 figures.

- Depends on: [`sn-da-excel-workflow`](skills/sn-da-excel-workflow/SKILL.md)

### 🔬 Embodied AI industry research — single-skill case (deep research)

[`examples/embodied-ai-deep-research`](examples/embodied-ai-deep-research/) — built from a single prompt with no input file: an industry research report with 5 figures (market size, share, financing, cost structure, roadmap).

- Depends on: [`sn-deep-research`](skills/sn-deep-research/SKILL.md)

### 🎯 Property fee pricing PPT — single-skill case (PPT generation)

[`examples/property-fee-pricing-ppt`](examples/property-fee-pricing-ppt/) — a 26-page PPTX in a black-and-white warm style, plus the per-page HTML sources, generated from a single prompt.

- Depends on: [`sn-ppt-entry`](skills/sn-ppt-entry/SKILL.md), [`sn-ppt-standard`](skills/sn-ppt-standard/SKILL.md)

## Contributing

Feel free to use the skills here as templates for your own OpenClaw skills. The qualities that make a skill good:

- **Clear triggers**: state in `description` exactly when the skill should and should not run, so the agent recognizes it accurately
- **Focused scope**: each skill does one thing well; complex workflows compose multiple skills
- **Solid documentation**: examples, artifact contracts, edge cases, failure handling
- **Supporting resources**: use `references/`, `scripts/`, `prompts/` to provide additional context

## License

MIT — see [LICENSE](LICENSE).
