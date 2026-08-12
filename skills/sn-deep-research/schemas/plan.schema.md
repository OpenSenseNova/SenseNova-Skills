# 研究计划字段契约

`{report_dir}/plan.json` 是 `normal` 和 `heavy` 模式下可执行的研究契约。`quick` 模式不创建此文件。

请求级 `language` 与 `format` 只通过 payload 传递，不写入 `plan.json`。

`scope_ownership` 说明每项研究范围由哪个维度负责、排除或有意共享。规划完成后，每个维度都必须能够独立执行。基于已完成证据的跨维度综合由 `report-planner` 负责。

## 顶层对象

| 字段 | 类型 | 必填 | 契约 |
| --- | --- | --- | --- |
| `mode` | 枚举 | 是 | `normal` / `heavy` |
| `strategy` | 对象 | 是 | 研究拆分策略 |
| `dimensions` | 数组 | 是 | 非空的可执行研究工作包列表 |
| `notes` | 字符串 | 否 | 计划级备注；允许为空字符串 |

## `strategy`

| 字段 | 类型 | 必填 | 契约 |
| --- | --- | --- | --- |
| `relevant_dimensions` | 字符串数组 | 是 | 非空且不重复；取值来自下方的拆分轴枚举 |
| `primary_dimension` | 字符串 | 是 | 必须是 `relevant_dimensions` 中已有的一个值 |
| `rationale` | 字符串 | 是 | 非空；说明为什么该拆分方式适合当前研究任务 |

拆分轴枚举：

```text
by_topic, by_entity, by_timeline, by_stakeholder, by_causal_chain,
by_evidence_type, by_region, by_value_chain, by_methodology,
by_process_stage, by_requirement, by_risk
```

## `dimensions[]`

| 字段 | 类型 | 必填 | 契约 |
| --- | --- | --- | --- |
| `id` | 字符串 | 是 | 唯一 ID，匹配 `^d[1-9]\d*$` |
| `name` | 字符串 | 是 | 非空的工作包名称 |
| `description` | 字符串 | 是 | 非空；说明该研究工作包要交付什么 |
| `key_questions` | 字符串数组 | 是 | 非空、不重复且具有实质内容的研究问题 |
| `focus` | 字符串 | 是 | 非空的证据重点；不能只是搜索关键词 |
| `sources` | 对象数组 | 是 | 至少一项 `{category, description}` 来源要求 |
| `lenses` | 对象数组 | 是 | 覆盖面提示；在 `normal` 模式下始终为空 |
| `depth` | 枚举 | 是 | `skim` / `moderate` / `thorough` |
| `time_sensitivity` | 字符串 | 是 | 非空；说明变化速度、时间上限和建议时间窗口 |
| `scope_ownership` | 对象 | 是 | 必填的范围边界；见下文 |

`sources[].category` 的允许值：

```text
official, news, social_media, github, developer, community, trend,
academic, forum, analyst, review, data, legal, financial, finance,
securities, annual_report, filing, market_cn, policy, regulation,
multi_platform
```

每个视角都包含非空字符串 `axis`、`value` 和 `rationale`。同一维度内的 `(axis, value)` 组合必须唯一。控制器为文件名分配稳定的位置 ID（`l1`、`l2`……）；`axis` 和 `value` 是内容，不得作为路径片段。

## `scope_ownership`

```json
{
  "owns": ["候选对象的识别标准与完整名单"],
  "excludes": ["各对象的采用成效，由 d2 负责"],
  "shared_topics": ["对象定义"],
  "overlap_policy": "d1 只确定纳入边界；d2 复用定义但不重新搜索候选对象"
}
```

| 字段 | 类型 | 必填 | 契约 |
| --- | --- | --- | --- |
| `owns` | 字符串数组 | 是 | 至少包含一个不重复、非空且具体的负责范围 |
| `excludes` | 字符串数组 | 是 | 不重复且非空的排除项；数组本身可以为空 |
| `shared_topics` | 字符串数组 | 是 | 不重复且非空的有意共享主题；数组本身可以为空 |
| `overlap_policy` | 字符串 | 是 | 非空；说明如何避免重复搜索；没有共享主题时也必须给出执行规则 |

同一个完整字符串不能同时出现在 `owns`、`excludes` 和 `shared_topics` 中的多个数组里。

## 独立执行

计划通过校验后，每个维度都必须能够立即开始执行。如果深入研究前需要先发现实体、分类体系、时间窗口或目标来源，应把发现工作及后续搜索保留在同一个维度内。

不要为只合并既有证据的工作单独创建研究维度。跨维度综合由 `report-planner` 负责。

## 模式契约

两种模式下，维度数量都应由可独立执行的搜索空间决定。不同的搜索空间使用不同维度；明显重叠的搜索路径应合并，或指定唯一负责维度。

### `normal` 模式

- 每个维度都必须使用 `lenses: []`。

### `heavy` 模式

- 视角是可选项，只用于需要额外覆盖面审查的维度。
- 新增维度必须代表需要外部检索的研究工作。只合并既有证据的综合工作由 `report-planner` 完成，不应作为研究维度。

## `normal` 模式最小示例

在真实计划中，下方省略的每个内容字符串仍必须具有实质内容。

```json
{
  "mode": "normal",
  "strategy": {
    "relevant_dimensions": ["by_topic"],
    "primary_dimension": "by_topic",
    "rationale": "三个主题可独立取证"
  },
  "dimensions": [
    {
      "id": "d1",
      "name": "主题一",
      "description": "收集主题一的实质证据",
      "key_questions": ["主题一当前有哪些可验证事实？"],
      "focus": "范围、变化与证据边界",
      "sources": [{"category": "official", "description": "权威定义与原始数据"}],
      "lenses": [],
      "depth": "moderate",
      "time_sensitivity": "变化较慢，以最新有效资料为准，回看近三年",
      "scope_ownership": {
        "owns": ["主题一事实"],
        "excludes": ["主题二与主题三"],
        "shared_topics": [],
        "overlap_policy": "无共享主题，按 owns 独立取证"
      }
    },
    {
      "id": "d2",
      "name": "主题二",
      "description": "收集主题二的实质证据",
      "key_questions": ["主题二当前有哪些可验证事实？"],
      "focus": "范围、变化与证据边界",
      "sources": [{"category": "official", "description": "权威定义与原始数据"}],
      "lenses": [],
      "depth": "moderate",
      "time_sensitivity": "变化较慢，以最新有效资料为准，回看近三年",
      "scope_ownership": {
        "owns": ["主题二事实"],
        "excludes": ["主题一与主题三"],
        "shared_topics": [],
        "overlap_policy": "无共享主题，按 owns 独立取证"
      }
    },
    {
      "id": "d3",
      "name": "主题三",
      "description": "收集主题三的实质证据",
      "key_questions": ["主题三当前有哪些可验证事实？"],
      "focus": "范围、变化与证据边界",
      "sources": [{"category": "official", "description": "权威定义与原始数据"}],
      "lenses": [],
      "depth": "moderate",
      "time_sensitivity": "变化较慢，以最新有效资料为准，回看近三年",
      "scope_ownership": {
        "owns": ["主题三事实"],
        "excludes": ["主题一与主题二"],
        "shared_topics": [],
        "overlap_policy": "无共享主题，按 owns 独立取证"
      }
    }
  ],
  "notes": ""
}
```
