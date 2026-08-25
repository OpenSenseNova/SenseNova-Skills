# SenseNova 深度研究技能

简体中文 | [English](sn-deep-research.md)

本文说明集成版 `sn-deep-research` 升级后的当前深度研究栈。旧的拆分式规划 / 分维取证 / 综合判断流水线已下线：规划、取证、审查、综合、写作、缝合与引用渲染现在统一收进 `sn-deep-research` controller 及其 `agents/*` 契约中。

## 当前深度研究流水线

| 技能 / 组件 | 作用 |
|---|---|
| [`sn-deep-research`](../skills/sn-deep-research/SKILL.md) | 统一入口。选择 quick / normal / heavy 档位，启动 Research Workbench 进度页，调度专家 agent，运行 validator，并渲染最终报告。 |
| `sn-deep-research/agents/scout.md` | heavy 模式的预研 briefing。 |
| `sn-deep-research/agents/plan.md` | 只负责研究计划：把需求划分为范围归属清晰、可独立执行且尽量避免重复检索的工作包。 |
| `sn-deep-research/agents/research.md` | 分维度取证；从 `plan.json` 自行读取工作包、核验原始页面，并输出通过校验的 `sub_reports/dN.evidence.json`。 |
| `validate_briefing.py` / `validate_plan.py` / `validate_evidence.py` / `validate_supplement_plan.py` / `validate_outline.py` | briefing 结构、独立研究工作包、证据完整性、补研计划生成、outline 与 evidence subset 的硬门禁。 |
| `review.md`、`perspective.md`、`supplement-planner.md` | evidence 审查、覆盖缺口检查与定向补研计划。 |
| `report-writer.md` | quick / normal 读取全部已路由 evidence 一次成文；heavy 按 evidence-bound content units 写作。 |
| `report-planner.md`、`report-stitcher.md` | 仅 heavy 使用的报告组织与组装角色；结构件可以直接作为主体。 |
| [`sn-prepare-citations`](../skills/sn-prepare-citations/SKILL.md) | 将 `[^source_id]` 脚注转换为编号引用，并写出 `report.md` + `citations.json`。 |
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

## 相关但不属于当前 controller 流水线的技能

这些技能仍在仓库中，但不是 `sn-deep-research` 当前集成流水线的自动步骤；只有用户明确要求对应输出形态或维护操作时才单独使用。

| 技能 | 当前状态 |
|---|---|
| [`sn-report-format-discovery`](../skills/sn-report-format-discovery/SKILL.md) | 可选的独立格式推荐；`sn-deep-research` 自身只使用一个请求级 `format` 字符串，不创建格式产物。 |
| [`sn-md-to-html-report`](../skills/sn-md-to-html-report/SKILL.md) | 将已生成的 Markdown 报告重组为自包含 HTML 专题页；不由 `sn-deep-research` 自动调用。 |
| [`sn-search-image`](../skills/sn-search-image/SKILL.md) | 图片搜索技能；当前 research agent 的 source category 未将它作为强制入口。 |
| [`sn-update`](../skills/sn-update/SKILL.md) | 刷新 / 更新 `sn-*` 技能包的维护技能；不参与研究执行流程。 |

## 快速开始

深度研究需求统一使用入口：

```text
/skill sn-deep-research "家用机器人产业链"
```

controller 会选择档位并执行对应流水线：

- **quick**：单个自包含 research agent → 通过校验的 evidence → writer 一次成文 → 引用渲染。
- **normal**：plan 校验 → 并行 evidence research → 一个 `quick_synthesis` writer 综合全部 evidence 一次成文 → 引用渲染。
- **heavy**：briefing → plan 校验 → 并行 evidence research → review、perspective 与定向补研 → evidence-bound content units → stitcher 与完整终稿 review。

controller 在派发前确定一个请求级 `format` 字符串，例如 `report`、`paper`、`table` 或 `memo`，并像 `language` 一样随 payload 传递。不创建 `format.json`、proposal 或格式 schema。quick / normal 直接一次成文，只有 heavy 在研究完成后由 report planner 生成 `organization_decision + content_units`。

每份 evidence 都保留可核验的来源 URL、snippet、引用类型、claims 与 writing-context 边界。Research 只有读取原始页面后才能采信证据；heavy review 按 URL 去重，同一轮审查中每个页面只抓取一次。补研直接更新同一维度的 evidence，并把未解决边界写入 `writing_context`。

## 配置

1. 复制 `.env.example` 为 `.env`。
2. 只填写本次需要使用的来源凭证。
3. 运行 skill 前把 `.env` 加载到 runtime 环境变量。
4. 不要把真实密钥写进 skill payload、prompt、报告、日志或提交。

可选凭证缺失时，对应来源族降级为公开 / 通用搜索兜底，不阻断整个流程。文件读写、命令执行、网页搜索、网页抓取等 Tier-1 runtime 能力仍是可靠深度研究的硬前提。
