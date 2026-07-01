# SenseNova 深度研究技能

简体中文 | [English](sn-deep-research.md)

本文说明集成版 `sn-deep-research` 升级后的当前深度研究栈。旧的拆分式规划 / 分维取证 / 综合判断流水线已下线：规划、取证、审查、综合、写作、缝合与引用渲染现在统一收进 `sn-deep-research` controller 及其 `agents/*` 契约中。

## 当前深度研究流水线

| 技能 / 组件 | 作用 |
|---|---|
| [`sn-deep-research`](../skills/sn-deep-research/SKILL.md) | 统一入口。选择 quick / normal / heavy 档位，创建报告目录，调度专家 agent，运行 validator，并渲染最终报告。 |
| `sn-deep-research/agents/scout.md` | normal / heavy 运行前的预研 briefing 与档位建议。 |
| `sn-deep-research/agents/plan.md` | 报告类型、研究维度、wave、依赖关系与 perspective lenses。 |
| `sn-deep-research/agents/research.md` | 分维度取证，输出 schema 化的 `sub_reports/dN.evidence.json`。 |
| `validate_evidence.py` / `validate_outline.py` | evidence 与 outline 契约的硬门禁。 |
| `review.md`、`perspective.md`、`supplement-planner.md` | evidence 审查、覆盖缺口检查与定向补研计划。 |
| `report-planner.md`、`report-writer.md`、`report-stitcher.md` | outline/subset 编排、章节写作与 heavy 模式缝合。 |
| [`sn-prepare-citations`](../skills/sn-prepare-citations/SKILL.md) | 将 `[^source_id]` 脚注转换为编号引用，并写出 `report.md` + `citations.json`。 |
| [`sn-report-format-discovery`](../skills/sn-report-format-discovery/SKILL.md) | 当目标报告形态未知时，供 plan agent 使用的可选报告格式发现能力。 |
| [`sn-research-report`](../skills/sn-research-report/SKILL.md) | 独立的报告结构参考 / 模板技能；不参与集成流水线控制流。 |

## Research Agent 可调用的搜索技能

research agent 会按维度的 source category 选择合适搜索技能。凭证均从环境变量读取；推荐统一写在仓库根目录 `.env`（复制 `.env.example`），运行前加载到环境变量。

| 技能 | 覆盖范围 |
|---|---|
| [`sn-search-academic`](../skills/sn-search-academic/SKILL.md) | 学术论文、论文元数据、引用链、百科背景。 |
| [`sn-search-code`](../skills/sn-search-code/SKILL.md) | GitHub、HuggingFace、StackOverflow、Hacker News 等开发者来源。 |
| [`sn-search-finance`](../skills/sn-search-finance/SKILL.md) | 证券、市场数据、财报、披露文件与财经新闻。 |
| [`sn-search-market-cn`](../skills/sn-search-market-cn/SKILL.md) | 中国市场与行业数据。 |
| [`sn-search-social-cn`](../skills/sn-search-social-cn/SKILL.md) | 知乎、小红书、微博、抖音、B站。 |
| [`sn-search-social-en`](../skills/sn-search-social-en/SKILL.md) | Reddit、Twitter/X（TikHub）、YouTube。 |
| [`sn-search-social-media`](../skills/sn-search-social-media/SKILL.md) | GitHub public search、Hacker News 热点、StackExchange、Wikimedia pageviews 等公开社媒/社区趋势来源。 |
| [`sn-search-year-report`](../skills/sn-search-year-report/SKILL.md) | 年报、SEC 类披露文件与上市公司公开披露。 |

## 快速开始

深度研究需求统一使用入口：

```text
/skill sn-deep-research "家用机器人产业链"
```

controller 会选择档位并执行对应流水线：

- **quick**：单个 skim evidence 维度 → 单 writer → 引用渲染。
- **normal**：scout → plan → 并行 evidence research + validation/review → report planner → 单个 full-outline writer → 终稿 review → 引用渲染。
- **heavy**：normal 基础上增加多 wave 调度、perspective、supplement planning、并行分节 writer、stitcher 与完整终稿 review。

## 配置

1. 复制 `.env.example` 为 `.env`。
2. 只填写本次需要使用的来源凭证。
3. 运行 skill 前把 `.env` 加载到 runtime 环境变量。
4. 不要把真实密钥写进 skill payload、prompt、报告、日志或提交。

可选凭证缺失时，对应来源族降级为公开 / 通用搜索兜底，不阻断整个流程。文件读写、命令执行、网页搜索、网页抓取等 Tier-1 runtime 能力仍是可靠深度研究的硬前提。
