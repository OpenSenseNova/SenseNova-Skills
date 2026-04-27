# Single-skill example: employee performance data analysis

This example shows how to use SenseNova-Skills' **data analysis** ability on a set of monthly performance review spreadsheets — producing a visualized report covering trends, role comparisons, individual performance, and improvement suggestions.

> Storyline: roll up review data spread across 10 monthly reports into one visualized conclusion that answers "what's the overall trend, which roles are pulling the numbers, and who is consistently improving versus needing attention".

[中文版 / Chinese](README_CN.md)

## Input

- [`result/风电事业部月度绩效考核表.zip`](result/风电事业部月度绩效考核表.zip): the wind-power business unit's monthly individual performance review spreadsheets, 2024-12 through 2025-09 (10 months, anonymized, xlsx). Unzipped directory `风电事业部月度绩效考核表/` contains the 10 xlsx files.

## Skills involved

| Step | Skill | Purpose |
|------|-------|---------|
| 1️⃣ Data analysis | [`sn-da-excel-workflow`](../../skills/sn-da-excel-workflow/SKILL.md) | Read multiple xlsx files, clean, aggregate, produce a structured report |
| 2️⃣ Render | [`sn-md-to-html-report`](../../skills/sn-md-to-html-report/SKILL.md) | Convert the Markdown report into a visualized HTML page |

## Walkthrough

### Step 1: Data analysis

Unzip `风电事业部月度绩效考核表.zip`, place the 10 xlsx files in the working directory, and prompt the agent:

```text
Based on the wind-power business unit's monthly performance review spreadsheets I uploaded, produce an
employee performance analysis report. Cover the overall picture, trend changes, role comparisons,
individual performance, and improvement suggestions, and visualize the key findings with charts.
```

The agent triggers `sn-da-excel-workflow` and produces a Markdown analysis report along with the figures it references. The directly deliverable Word document:

- [`result/风电事业部2024-2025年度员工绩效分析报告.docx`](result/风电事业部2024-2025年度员工绩效分析报告.docx): Word version, ready to share or review.

### Step 2: Render to HTML

Follow up with:

```text
Use the sn-md-to-html-report skill to convert the markdown output into an html file.
```

You'll get a browser-friendly visualization, packaged as [`result/员工绩效分析-output.zip`](result/员工绩效分析-output.zip). Inside the zip, the directory `员工绩效分析报告/` contains:

- `wind_energy_performance_report.html`: visualized HTML report — open in any browser
- `wind_power_case_all_figures_redownload/`: the 8 PNG figures referenced by the report plus `manifest.json`

## Artifacts overview

```
result/
├── 风电事业部月度绩效考核表.zip                    # Input: 10 monthly review xlsx files (anonymized)
├── 风电事业部2024-2025年度员工绩效分析报告.docx     # Data analysis artifact (Word)
└── 员工绩效分析-output.zip                       # Data analysis artifact (HTML + 8 figures)
```
