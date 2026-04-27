# Single-skill example: embodied AI industry deep research

This example shows how to use SenseNova-Skills' **deep research** ability with nothing but a single prompt — no input file at all — to have the agent investigate an industry online and produce a polished, illustrated research report.

> Storyline: automatically gather public material → organize it across key dimensions (market size, vendor share, financing, cost structure, roadmap) → emit a visualized industry report.

[中文版 / Chinese](README_CN.md)

## Input

None. Everything is gathered by the agent during research, given only the industry keyword in the prompt.

## Skills involved

| Step | Skill | Purpose |
|------|-------|---------|
| 1️⃣ Deep research | [`sn-deep-research`](../../skills/sn-deep-research/SKILL.md) | Drive search / fetch / synthesis sub-skills to produce a Markdown research report and supporting figures |
| 2️⃣ Render | [`sn-md-to-html-report`](../../skills/sn-md-to-html-report/SKILL.md) | Convert the Markdown report into a visualized HTML page |

## Walkthrough

### Step 1: Deep research

Prompt the agent directly:

```text
Please research the embodied AI industry and produce a professional industry research report.
```

The agent triggers `sn-deep-research`, emits a Markdown report, and generates 5 figures (market size, share, financing, cost structure, roadmap).

### Step 2: Render to HTML

Follow up to convert Markdown into HTML for browser viewing. The final artifact for this run is packaged as [`result/具身智能行业调研.zip`](result/具身智能行业调研.zip).

## Artifact

[`result/具身智能行业调研.zip`](result/具身智能行业调研.zip). Inside, the directory `具身智能行业调研/` contains:

- `report.html`: visualized HTML report (recommended view)
- `report.md`: original Markdown
- `01_market_size_trend.jpg`: market size trend
- `02_market_share.jpg`: global humanoid robot market share
- `03_financing.jpg`: domestic vendor financing comparison
- `04_cost_structure.jpg`: humanoid robot cost structure
- `05_development_roadmap.jpg`: industry roadmap

## Artifacts overview

```
result/
└── 具身智能行业调研.zip   # Deep research artifact (HTML + Markdown + 5 figures)
```
