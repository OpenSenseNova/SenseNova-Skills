# `supplement_plan.json` 补研计划字段契约

`{report_dir}/sub_reports/d{N}.supplement_plan.json` 记录某个现有研究维度的补研决定。

## 顶层对象

```json
{
  "meta": {...},
  "dimension_id": "d1",
  "dimension_name": "维度名称",
  "supplement_items": [...],
  "deferred_items": [...]
}
```

## `meta`

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `task` | 字符串 | 是 | 通常填写 `补研计划` |
| `generated_from` | 字符串 | 是 | 当前维度的证据、审查和视角反馈文件 |
| `target_report` | 字符串 | 是 | 报告主题或空字符串 |
| `date` | 字符串 | 是 | 生成日期，格式为 `YYYY-MM-DD` |
| `principle` | 字符串 | 是 | 一句话说明决策原则 |

## 维度字段

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `dimension_id` | 字符串 | 是 | 已存在的维度 ID，例如 `d1` |
| `dimension_name` | 字符串 | 是 | 来自 `plan.json` 的维度名称 |
| `supplement_items` | 数组 | 是 | `research` 补研模式需要执行的事项；可以为空 |
| `deferred_items` | 数组 | 是 | 不作为补研任务执行的事项；可以为空 |

## `supplement_items[]`

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `id` | 字符串 | 是 | 稳定 ID，例如 `d1-s1`、`d1-s2` |
| `type` | 枚举 | 是 | `coverage` / `claim_fix` / `both` |
| `gap` | 字符串 | 是 | 简要说明证据缺口或断言质量缺口 |
| `question` | 字符串 | 是 | 交给 `research` 智能体回答的具体问题 |
| `rationale` | 字符串 | 是 | 说明这项补研为什么重要 |
| `suggested_sources` | 字符串数组 | 是 | 建议的来源类别或具体来源类型 |
| `candidate_leads` | 字符串数组 | 是 | 输入文件中已有的候选 URL、来源名称或搜索线索；可以为空。|
| `source_refs` | 字符串数组 | 是 | 提出该事项的审查或视角反馈位置 |
| `review_refs` | 字符串数组 | 是 | 涉及的断言 ID 或审查要点；纯覆盖型事项可以为空 |
| `impact_if_skipped` | 字符串 | 是 | 如果跳过，最终报告应受到什么限制 |
| `status` | 枚举 | 是 | 初始值为 `pending`；`research` 后续更新为 `resolved` / `partial` / `no_data` / `out_of_scope` |
| `resolution_note` | 字符串 | 是 | 初始为空；`research` 执行后填写 |

## `deferred_items[]`

该数组用于记录不应触发补研的候选事项。

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `id` | 字符串 | 是 | 稳定 ID，例如 `d1-d1` |
| `reason` | 枚举 | 是 | `writing_context_only` / `low_value` / `not_actionable` / `out_of_scope` / `already_covered` / `unavailable` |
| `item` | 字符串 | 是 | 简要说明被延后的候选事项 |
| `source_refs` | 字符串数组 | 是 | 提出该事项的审查或视角反馈位置 |
| `writing_context_use` | 字符串 | 是 | 说明如何呈现；不适用时填写空字符串 |

## 空计划

如果无需补研，写入一份合法的空计划：

```json
{
  "meta": {
    "task": "补研计划",
    "generated_from": "当前维度 evidence/review/perspective 文件",
    "target_report": "",
    "date": "YYYY-MM-DD",
    "principle": "无必要补研"
  },
  "dimension_id": "d1",
  "dimension_name": "维度名称",
  "supplement_items": [],
  "deferred_items": []
}
```
