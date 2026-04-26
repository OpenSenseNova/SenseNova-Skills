# 单技能示例：具身智能行业深度调研

[English version](README.md)

本示例演示如何使用 SenseNova-Skills 中的 **深度调研** 能力，仅依靠一句指令、不提供任何输入文件，让智能体联网调研某个行业并产出图文并茂的专业调研报告。

> 主线：自动检索公开资料 → 整理市场规模 / 玩家份额 / 融资 / 成本 / 路线图等关键维度 → 生成可视化的行业调研报告。

## 输入

无。仅依靠 prompt 中的行业关键词，全部资料由智能体在调研过程中检索整理。

## 涉及技能

| 步骤 | 技能 | 作用 |
|------|------|------|
| 1️⃣ 深度调研 | [`sn-deep-research`](../../skills/sn-deep-research/SKILL.md) | 调用搜索/抓取/综合等子技能，产出 Markdown 调研报告与配套图表 |
| 2️⃣ 渲染 | [`sn-md-to-html-report`](../../skills/sn-md-to-html-report/SKILL.md) | 把 Markdown 调研报告转成可视化 HTML |

## 操作流程

### 第一步：深度调研

直接向智能体发起：

```text
帮我对具身智能行业做个调研，生成一份专业的行业调研报告
```

智能体会触发 `sn-deep-research`，输出 Markdown 报告，并生成 5 张配图（市场规模、份额、融资、成本结构、发展路线）。

### 第二步：渲染为 HTML

继续追问把 Markdown 转成 HTML，得到可视化报告。本次执行的最终产物已打包为 [`result/具身智能行业调研.zip`](result/具身智能行业调研.zip)。

## 产物

[`result/具身智能行业调研.zip`](result/具身智能行业调研.zip)，解压后目录 `具身智能行业调研/` 内含：

- `report.html`：可视化 HTML 报告（推荐打开）
- `report.md`：Markdown 原文
- `01_market_size_trend.jpg`：市场规模趋势
- `02_market_share.jpg`：全球人形机器人市场份额
- `03_financing.jpg`：国内企业融资额对比
- `04_cost_structure.jpg`：人形机器人成本结构
- `05_development_roadmap.jpg`：产业发展路线图

## 产物总览

```
result/
└── 具身智能行业调研.zip   # 深度调研产物（HTML + Markdown + 5 张图表）
```
