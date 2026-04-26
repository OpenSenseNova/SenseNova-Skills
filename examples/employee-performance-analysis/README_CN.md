# 单技能示例：员工绩效数据分析

[English version](README.md)

本示例演示如何使用 SenseNova-Skills 中的 **数据分析** 能力，从一组月度绩效考核 Excel 出发，产出包含趋势、岗位对比、个人表现与改进建议的可视化分析报告。

> 主线：把分散在 10 个月度报表里的考核数据汇总成一份可视化结论，回答「整体趋势如何 / 哪些岗位拉动 / 谁在持续进步、谁需要关注」。

## 输入

- [`result/风电事业部月度绩效考核表/`](result/风电事业部月度绩效考核表/)：风电事业部 2024-12 ~ 2025-09 共 10 个月的月度员工个人绩效考核汇总表（已脱敏，xlsx 格式）。

## 涉及技能

| 步骤 | 技能 | 作用 |
|------|------|------|
| 1️⃣ 数据分析 | [`sn-da-excel-workflow`](../../skills/sn-da-excel-workflow/SKILL.md) | 读取多份 xlsx、清洗、聚合、产出结构化分析报告 |
| 2️⃣ 渲染 | [`sn-md-to-html-report`](../../skills/sn-md-to-html-report/SKILL.md) | 把 Markdown 报告转成可视化 HTML |

## 操作流程

### 第一步：数据分析

把 `风电事业部月度绩效考核表/` 下的 10 份 xlsx 放到工作目录，向智能体发起：

```text
根据我上传的风电事业部月度绩效考核表，生成一份员工绩效分析报告，包含总体情况、趋势变化、岗位对比、个人表现和改进建议，并用图表展示关键结论。
```

智能体会触发 `sn-da-excel-workflow`，输出 Markdown 格式的分析报告与配套图表。直接交付的文档版产物：

- [`result/风电事业部2024-2025年度员工绩效分析报告.docx`](result/风电事业部2024-2025年度员工绩效分析报告.docx)：可直接下发或评审的 Word 版报告。

### 第二步：渲染为 HTML

继续向智能体追问：

```text
使用 sn-md-to-html-report 这个 skill 把输出的 markdown 转换成 html 文件
```

得到可在浏览器中直接查看的可视化版本，已打包为 [`result/员工绩效分析-output.zip`](result/员工绩效分析-output.zip)，解压后目录 `员工绩效分析报告/` 内含：

- `wind_energy_performance_report.html`：可视化 HTML 报告，浏览器直接打开
- `wind_power_case_all_figures_redownload/`：报告引用的 8 张图表 PNG + `manifest.json`

## 产物总览

```
result/
├── 风电事业部月度绩效考核表/                       # 输入：10 份月度考核 xlsx（已脱敏）
├── 风电事业部2024-2025年度员工绩效分析报告.docx     # 数据分析产物（Word 版）
└── 员工绩效分析-output.zip                       # 数据分析产物（HTML 版 + 8 张图表）
```
