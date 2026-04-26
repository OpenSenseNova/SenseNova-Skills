# End-to-end example: memory price analysis

This example shows how to chain SenseNova-Skills' **Data Analysis → Deep Research → PPT Generation** abilities end-to-end: starting from a raw price CSV and ending with a magazine-style PPT deck.

> Storyline: first prove from data that "prices are rising and the gains are concentrated in key categories", then use external research to explain "why prices are rising and what's driving them", and finally deliver trend judgments and action recommendations.

[中文版 / Chinese](README_CN.md)

## Input

- [`result/芯片价格汇总.csv`](result/芯片价格汇总.csv): storage chip quotes from China Flash Market, 2026-01-22 ~ 2026-04-21. 1,835 records covering 5 top categories, 15 sub-categories, 77 SKUs.

## Skills involved

| Step | Skill | Purpose |
|------|-------|---------|
| 1️⃣ Data analysis | [`sn-da-excel-workflow`](../../skills/sn-da-excel-workflow/SKILL.md) | Read CSV, clean, aggregate, produce a structured analysis report |
| 1️⃣/2️⃣ Render | [`sn-md-to-html-report`](../../skills/sn-md-to-html-report/SKILL.md) | Convert the Markdown report into a visualized HTML page |
| 2️⃣ Deep research | [`sn-deep-research`](../../skills/sn-deep-research/SKILL.md) | Extend the data findings with external research |
| 3️⃣ PPT generation | [`sn-ppt-standard`](../../skills/sn-ppt-standard/SKILL.md) (dispatched by [`sn-ppt-entry`](../../skills/sn-ppt-entry/SKILL.md)) | Render report content into a PPTX |

## Walkthrough

### Step 1: Data analysis

Place `芯片价格汇总.csv` in the working directory and prompt the agent:

```text
Please read 芯片价格汇总.csv and clean / analyze the recent storage chip quote data.
```

The agent triggers `sn-da-excel-workflow` and emits a Markdown summary report. This run produced:

- [`result/半导体-数据分析-汇总分析报告.md`](result/半导体-数据分析-汇总分析报告.md)

> **Data analysis takeaway**: storage prices are trending up overall, with select DRAM and NAND products posting the largest gains. The inflection appeared in late February, accelerated through March, and the rebound is uneven across categories — server-grade products lead while consumer-grade products lag, indicating that key categories drove the rally rather than a synchronous broad-based move.

You can ask the agent to render the Markdown into HTML for easier browsing:

```text
Use the sn-md-to-html-report skill to convert the markdown output into an html file.
```

Output: [`result/半导体-数据分析-汇总分析报告.html`](result/半导体-数据分析-汇总分析报告.html)

### Step 2: Deep research

Building on Step 1, follow up to dig into the "why":

```text
Based on the data analysis, research the main causes of memory and flash price volatility since 2026.
```

The agent triggers `sn-deep-research`, calling its search/fetch/synthesis sub-skills, and produces an illustrated deep-dive report:

- [`result/内存条价格暴涨原因分析/深度调研-内存条价格暴涨原因分析.md`](result/内存条价格暴涨原因分析/深度调研-内存条价格暴涨原因分析.md)
- [`result/内存条价格暴涨原因分析/深度调研-内存条价格暴涨原因分析.html`](result/内存条价格暴涨原因分析/深度调研-内存条价格暴涨原因分析.html)
- [`result/内存条价格暴涨原因分析/figures/`](result/内存条价格暴涨原因分析/figures/): 9 figures referenced by the report

> **Deep research takeaway**: this round of price hikes is driven by supply contraction, surging AI-server demand, and proactive output discipline by some vendors. Short term, sentiment and restocking amplify volatility; medium term, this looks more like a structural rebalance. If high-end demand persists and vendors keep supply tight, prices may continue to climb or oscillate at elevated levels.

The agent can also render this report to HTML in the same way.

### Step 3: PPT generation

Use the previous outputs as source material to generate the final PPT:

```text
Based on the data analysis result, build a PPT that presents the report. Reuse all figures from the report,
keep data and conclusions consistent with the report, cap it at 16 pages, use standard mode.
The look should be a high-end magazine style — red and gold accents, bright background, with strong emphasis.
```

Routed via `sn-ppt-entry` into `sn-ppt-standard`, which produces:

- [`result/半导体存储市场研究报告_20260426_015200.pptx`](result/半导体存储市场研究报告_20260426_015200.pptx): the PPTX file you can open directly
- [`result/半导体存储市场研究报告_20260426_015200.zip`](result/半导体存储市场研究报告_20260426_015200.zip): zipped per-page HTML sources, handy for re-editing or browser preview

## Artifacts overview

```
result/
├── 芯片价格汇总.csv                                       # Input
├── 半导体-数据分析-汇总分析报告.md                          # Step 1 (Markdown)
├── 半导体-数据分析-汇总分析报告.html                        # Step 1 (HTML)
├── 内存条价格暴涨原因分析/
│   ├── 深度调研-内存条价格暴涨原因分析.md                   # Step 2 (Markdown)
│   ├── 深度调研-内存条价格暴涨原因分析.html                 # Step 2 (HTML)
│   └── figures/                                          # 9 figures
├── 半导体存储市场研究报告_20260426_015200.pptx              # Step 3 (PPTX)
└── 半导体存储市场研究报告_20260426_015200.zip               # Step 3 (HTML sources)
```

Open any file under `result/` to inspect this run's real output.
