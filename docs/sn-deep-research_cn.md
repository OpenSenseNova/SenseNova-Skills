# SenseNova 深度研究技能

简体中文 | [English](sn-deep-research.md)

本文说明集成版 `sn-deep-research` 升级后的当前深度研究栈。旧的拆分式规划 / 分维取证 / 综合判断流水线已下线：规划、取证、审查、综合、写作、缝合与引用渲染现在统一收进 `sn-deep-research` controller 及其 `agents/*` 契约中。

## 当前深度研究流水线

| 技能 / 组件 | 作用 |
|---|---|
| [`sn-deep-research`](../skills/sn-deep-research/SKILL.md) | 统一入口。选择 quick / normal / heavy 档位，创建报告目录，调度专家 agent，运行 validator，并渲染最终报告。 |
| `sn-deep-research/agents/scout.md` | normal / heavy 运行前的预研 briefing、档位建议，以及对格式发现 skill 的调用。 |
| `sn-deep-research/agents/plan.md` | 只负责研究计划：按覆盖义务拆分维度；仅当下游检索范围必须消费上游结果时建立依赖与 wave。 |
| `sn-deep-research/agents/research.md` | 分维度取证，输出 schema 化的 `sub_reports/dN.evidence.json`，并把实际使用的完整正文固定到报告级 `source_cache/`。 |
| `validate_plan.py` / `validate_evidence.py` / `validate_outline.py` | 计划拓扑、来源快照、格式偏好、outline 与 evidence subset 的硬门禁。 |
| `review.md`、`perspective.md`、`supplement-planner.md` | evidence 审查、覆盖缺口检查与定向补研计划。 |
| `report-planner.md`、`report-writer.md`、`report-stitcher.md` | 把用户已确认的呈现形式实现为 evidence-bound content units，并为 normal / heavy 组装成品；结构件可以直接作为主体。 |
| `source_snapshot.py` | 对 URL 正规化后的完整 UTF-8 正文做不可变、内容寻址缓存；research、review 与补研复用同一快照。 |
| [`sn-prepare-citations`](../skills/sn-prepare-citations/SKILL.md) | 将 `[^source_id]` 脚注转换为编号引用，并写出 `report.md` + `citations.json`。 |
| [`sn-report-format-discovery`](../skills/sn-report-format-discovery/SKILL.md) | 格式发现的唯一责任方；由 scout 传入预研上下文，比较研究报告、学术论文、表格优先报表、决策备忘录或自定义最终呈现形式。 |
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
| [`sn-md-to-html-report`](../skills/sn-md-to-html-report/SKILL.md) | 将已生成的 Markdown 报告重组为自包含 HTML 专题页；不由 `sn-deep-research` 自动调用。 |
| [`sn-search-image`](../skills/sn-search-image/SKILL.md) | 图片搜索技能；当前 research agent 的 source category 未将它作为强制入口。 |
| [`sn-update`](../skills/sn-update/SKILL.md) | 刷新 / 更新 `sn-*` 技能包的维护技能；不参与研究执行流程。 |

## 快速开始

深度研究需求统一使用入口：

```text
/skill sn-deep-research "家用机器人产业链"
```

controller 会选择档位并执行对应流水线：

- **quick**：单个 skim evidence 维度 → 来源快照与 evidence 校验 → quick writer → 引用渲染。
- **normal**：scout + 格式确认 → plan 校验 → 并行 evidence research / review → outline v2 content units → per-unit writer → stitcher → 终稿 review → 引用渲染。
- **heavy**：在 normal 上增加覆盖维度、perspective、supplement planning 和完整 review。独立维度保持并行；只有真实信息依赖形成后续 wave，下游等上游最终 evidence 稳定后再检索。

normal / heavy 运行中，scout 调用 `sn-report-format-discovery` 写出 `format_proposal.json`。这里保留三层正交合同：`selected_format` 定义整体交付形态（报告、brief、board 等），内容 `paradigm` 定义论证如何推进，`structure_preference` 定义核心信息载体（narrative、matrix、timeline、checklist 等）的 `required / preferred / auto` 强度。研究完成后 report planner 才按真实 evidence 写出 `organization_decision + content_units`；不存在 comparison→matrix 或 investigation→timeline 的固定映射。

每条 v1.2 evidence 都包含 `snapshot_ref`，指向本次报告 `source_cache/{url_hash}/{content_hash}.md`。review 按 ref 分组核验，补研在任何抓取前先 lookup；已有正文不重复抓取，新增正文立即写入不可变缓存。

## 配置

1. 复制 `.env.example` 为 `.env`。
2. 只填写本次需要使用的来源凭证。
3. 运行 skill 前把 `.env` 加载到 runtime 环境变量。
4. 不要把真实密钥写进 skill payload、prompt、报告、日志或提交。

可选凭证缺失时，对应来源族降级为公开 / 通用搜索兜底，不阻断整个流程。文件读写、命令执行、网页搜索、网页抓取等 Tier-1 runtime 能力仍是可靠深度研究的硬前提。
