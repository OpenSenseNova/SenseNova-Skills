<p align="center">
  <img src="assets/logo.webp" alt="SenseNova logo" width="180" />
</p>

# SenseNova-Skills

English | [简体中文](README.md)

The SenseNova model family plugs directly into agent runtimes such as [OpenClaw](https://openclaw.ai/) and [hermes-agent](https://github.com/OpenSenseNova/hermes-agent), and gains stronger capabilities through skills.

In this repository each skill lives in its own directory and declares triggers, capabilities, and execution flow through a `SKILL.md` file, following the [Agent Skills](https://agentskills.io/) convention.

The skills cover **image generation & visualization**, **slide-deck (PPT) generation**, **Excel data analysis**, and **deep research** — usable standalone or composed into end-to-end workflows.

## What is a SKILL.md?

A `SKILL.md` is a Markdown document that teaches an AI agent how to perform a specific task. It typically contains:

- **Frontmatter metadata**: `name`, `description`, plus optional fields such as `triggers` and `metadata`
- **Instructions**: when the skill triggers, what steps to run in what order, and where the artifacts land
- **References** (optional): supporting docs, methodology notes, examples
- **Scripts** (optional): executable scripts the skill calls into

## Directory Structure

```
skills/
├── <skill-name>/
│   ├── SKILL.md          # Main skill definition (required)
│   ├── references/       # Supporting docs (optional)
│   │   └── *.md
│   ├── scripts/          # Executable scripts (optional)
│   │   └── *.py
│   ├── prompts/          # Prompt templates (optional)
│   │   └── *.md
│   └── requirements.txt  # Python deps (optional)
```

## How to Use

Clone this repository, then copy subdirectories under `skills/` into the skills directory your agent loads from:

| Agent | Target directory |
|-------|------------------|
| [OpenClaw](https://openclaw.ai/) | `~/.openclaw/skills/` |
| [hermes-agent](https://github.com/OpenSenseNova/hermes-agent) | `~/.hermes/skills/` |

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

### 📊 Presentations (sn-ppt-standard / sn-ppt-creative)

A few `sn-ppt-standard` and `sn-ppt-creative` outputs (more in [`docs/ppt-examples.md`](docs/ppt-examples.md)).

<!-- TODO: add PPT sample images -->

### 🔬 Deep Research (sn-deep-research)

Sample reports orchestrated by `sn-deep-research` (more in [`docs/sn-deep-research-examples.md`](docs/sn-deep-research-examples.md)).

<!-- TODO: add sn-deep-research sample screenshots or links -->

## Contributing

Feel free to use the skills here as templates for your own OpenClaw skills. The qualities that make a skill good:

- **Clear triggers**: state in `description` exactly when the skill should and should not run, so the agent recognizes it accurately
- **Focused scope**: each skill does one thing well; complex workflows compose multiple skills
- **Solid documentation**: examples, artifact contracts, edge cases, failure handling
- **Supporting resources**: use `references/`, `scripts/`, `prompts/` to provide additional context

## License

MIT — see [LICENSE](LICENSE).
