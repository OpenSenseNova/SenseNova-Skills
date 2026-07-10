# Plan Schema v1.0

`{report_dir}/plan.json` is the executable research contract for normal and heavy mode. Quick mode does not create this file.

The plan separates two concerns:

- `scope_ownership` says which dimension owns, excludes, or intentionally shares each research scope.
- `depends_on` plus `dependency_inputs` says which downstream dimension must consume an upstream result before its own search scope can be determined.

Related topics, report order, cross-dimension synthesis, and runtime batching are not research dependencies. Cross-dimension synthesis over existing evidence belongs to report-planner.

## Top-level object

| field | type | required | contract |
| --- | --- | --- | --- |
| `schema_version` | string | yes | Fixed value `1.0` |
| `mode` | enum | yes | `normal` / `heavy` |
| `format_id` | string | yes | Non-empty; exactly equals confirmed `format.json.selected_format.id`; controller validates this binding with `validate_plan.py --format` |
| `strategy` | object | yes | Research decomposition strategy |
| `dimensions` | array | yes | Non-empty list of executable research work packages |
| `notes` | string | no | Plan-level note; empty string is allowed |

## `strategy`

| field | type | required | contract |
| --- | --- | --- | --- |
| `relevant_dimensions` | array[string] | yes | Non-empty unique values from the decomposition-axis enum below |
| `primary_dimension` | string | yes | One value present in `relevant_dimensions` |
| `rationale` | string | yes | Non-empty explanation of why this decomposition fits the research task |

Decomposition-axis enum:

```text
by_topic, by_entity, by_timeline, by_stakeholder, by_causal_chain,
by_evidence_type, by_region, by_value_chain, by_methodology,
by_process_stage, by_requirement, by_risk
```

## `dimensions[]`

| field | type | required | contract |
| --- | --- | --- | --- |
| `id` | string | yes | Unique id matching `^d[1-9]\d*$` |
| `name` | string | yes | Non-empty work-package name |
| `description` | string | yes | Non-empty statement of the research delivery |
| `key_questions` | array[string] | yes | Non-empty, unique, substantive research questions |
| `focus` | string | yes | Non-empty evidence focus; not search keywords |
| `context_from_briefing` | string | yes | Briefing context relevant to this dimension; may be empty |
| `sources` | array[object] | yes | At least one `{category, description}` source requirement |
| `lenses` | array[object] | yes | Coverage hints; always empty in normal mode |
| `depth` | enum | yes | `skim` / `moderate` / `thorough` |
| `time_sensitivity` | string | yes | Non-empty change speed, upper bound, and recommended time window |
| `scope_ownership` | object | yes | Required scope boundary; see below |
| `wave` | integer | yes | Positive integer derived from the dependency topology |
| `depends_on` | array[string] | yes | Unique direct upstream dimension ids |
| `dependency_inputs` | array[object] | yes | One input contract for every `depends_on` id |

Allowed `sources[].category` values:

```text
official, news, social_media, github, developer, community, trend,
academic, forum, analyst, review, data, legal, financial, finance,
securities, annual_report, filing, market_cn, policy, regulation,
multi_platform
```

Each lens contains non-empty `axis`, `value`, and `rationale` strings. The `(axis, value)` pair is unique within a dimension. Controller assigns stable positional ids (`l1`, `l2`, ...) for filenames; axis/value are content, never path segments.

## `scope_ownership`

```json
{
  "owns": ["候选对象的识别标准与完整名单"],
  "excludes": ["各对象的采用成效，由 d2 负责"],
  "shared_topics": ["对象定义"],
  "overlap_policy": "d1 只确定纳入边界；d2 复用定义但不重新搜索候选对象"
}
```

| field | type | required | contract |
| --- | --- | --- | --- |
| `owns` | array[string] | yes | At least one unique, non-empty, concrete owned scope |
| `excludes` | array[string] | yes | Unique non-empty exclusions; may be empty |
| `shared_topics` | array[string] | yes | Unique non-empty intentional overlaps; may be empty |
| `overlap_policy` | string | yes | Non-empty execution rule for avoiding duplicate search, including when there is no shared topic |

An exact string cannot occur in more than one of `owns`, `excludes`, and `shared_topics`. Scope ownership does not create an execution dependency.

## Dependencies

Dependencies are allowed only when an upstream result is required to determine a downstream search scope. Every direct upstream id occurs exactly once in both `depends_on` and `dependency_inputs[].dimension_id`.

```json
{
  "depends_on": ["d1"],
  "dependency_inputs": [
    {
      "dimension_id": "d1",
      "needed_for": "entity_selection",
      "consume": "key_findings",
      "scope_rule": "先读取 d1.key_findings 中确认的对象名单，只检索入选对象的采用证据，不重复执行对象发现"
    }
  ]
}
```

| field | type | required | contract |
| --- | --- | --- | --- |
| `dimension_id` | string | yes | Existing direct upstream id, not the current dimension |
| `needed_for` | enum | yes | Why the upstream output changes downstream search scope |
| `consume` | enum | yes | Fixed value `key_findings` |
| `scope_rule` | string | yes | Non-empty rule explaining how upstream findings change scope and what search must not be repeated |

`needed_for` enum:

```text
entity_selection
taxonomy_definition
time_window
hypothesis_definition
source_targeting
```

“参考上游结果”“综合前序研究”或 report ordering does not satisfy `scope_rule`.

## Topology and waves

The dependency graph must contain no missing ids, self-dependencies, duplicate edges, or cycles. Wave is derived after direct dependencies are finalized:

```text
no direct dependency: wave = 1
with direct dependencies: wave = 1 + max(wave of every direct upstream)
```

This rule places every independent dimension in wave 1 and prevents artificial serialization. A heavy plan may have many dimensions and still have only wave 1. Multiple waves are valid only when the graph contains real downstream consumption contracts.

## Mode contracts

### Normal

- Exactly 2-5 dimensions.
- Every dimension has `wave: 1`.
- Every dimension has `depends_on: []`, `dependency_inputs: []`, and `lenses: []`.

### Heavy

- Dimension count follows distinct coverage obligations and evidence boundaries, not a quota.
- Independent dimensions remain in wave 1 regardless of count.
- Dependencies and later waves are optional.
- Additional dimensions must represent external research work. Synthesis that only combines existing evidence is performed by report-planner, not a research dimension.

## Minimal normal example

Every omitted content string below must still be substantive in a real plan.

```json
{
  "schema_version": "1.0",
  "mode": "normal",
  "format_id": "research_report",
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
      "context_from_briefing": "",
      "sources": [{"category": "official", "description": "权威定义与原始数据"}],
      "lenses": [],
      "depth": "moderate",
      "time_sensitivity": "变化较慢，以最新有效资料为准，回看近三年",
      "scope_ownership": {
        "owns": ["主题一事实"],
        "excludes": ["主题二与主题三"],
        "shared_topics": [],
        "overlap_policy": "无共享主题，按 owns 独立取证"
      },
      "wave": 1,
      "depends_on": [],
      "dependency_inputs": []
    },
    {
      "id": "d2",
      "name": "主题二",
      "description": "收集主题二的实质证据",
      "key_questions": ["主题二当前有哪些可验证事实？"],
      "focus": "范围、变化与证据边界",
      "context_from_briefing": "",
      "sources": [{"category": "official", "description": "权威定义与原始数据"}],
      "lenses": [],
      "depth": "moderate",
      "time_sensitivity": "变化较慢，以最新有效资料为准，回看近三年",
      "scope_ownership": {
        "owns": ["主题二事实"],
        "excludes": ["主题一与主题三"],
        "shared_topics": [],
        "overlap_policy": "无共享主题，按 owns 独立取证"
      },
      "wave": 1,
      "depends_on": [],
      "dependency_inputs": []
    },
    {
      "id": "d3",
      "name": "主题三",
      "description": "收集主题三的实质证据",
      "key_questions": ["主题三当前有哪些可验证事实？"],
      "focus": "范围、变化与证据边界",
      "context_from_briefing": "",
      "sources": [{"category": "official", "description": "权威定义与原始数据"}],
      "lenses": [],
      "depth": "moderate",
      "time_sensitivity": "变化较慢，以最新有效资料为准，回看近三年",
      "scope_ownership": {
        "owns": ["主题三事实"],
        "excludes": ["主题一与主题二"],
        "shared_topics": [],
        "overlap_policy": "无共享主题，按 owns 独立取证"
      },
      "wave": 1,
      "depends_on": [],
      "dependency_inputs": []
    }
  ],
  "notes": ""
}
```
