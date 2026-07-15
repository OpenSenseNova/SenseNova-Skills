# supplement_plan.json Schema

`{report_dir}/sub_reports/d{N}.supplement_plan.json` records supplement decisions for one existing research dimension.

It is a controller-facing audit and execution artifact, not formal evidence. It must not introduce new facts into the final report. Any factual lead listed here must be re-checked by a research agent and incorporated into `d{N}.evidence.json` before it can support report claims.

The supplement planner is file-only. It derives this artifact from the target dimension's `plan.json` fields, `evidence.json`, optional `review.md`, optional `perspectives/*.md`, and exact source snapshots already referenced by that evidence. It does not search the web or open source URLs.

## Top-level object

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

| field | type | required | description |
| --- | --- | --- | --- |
| `task` | string | yes | Usually `补研计划` |
| `generated_from` | string | yes | Current dimension evidence/review/perspective files and, when needed, their pinned source snapshots |
| `target_report` | string | yes | Report topic or empty string |
| `date` | string | yes | Generation date, `YYYY-MM-DD` |
| `principle` | string | yes | One-sentence decision principle |

## Dimension fields

| field | type | required | description |
| --- | --- | --- | --- |
| `dimension_id` | string | yes | Existing dimension id, e.g. `d1` |
| `dimension_name` | string | yes | Dimension name from `plan.json` |
| `supplement_items` | array | yes | Items that research supplement mode should execute; may be empty |
| `deferred_items` | array | yes | Items not executed as supplement research; may be empty |

## `supplement_items[]`

| field | type | required | description |
| --- | --- | --- | --- |
| `id` | string | yes | Stable id, e.g. `d1-s1`, `d1-s2` |
| `type` | enum | yes | `coverage` / `claim_fix` / `both` |
| `gap` | string | yes | Short description of the evidence or claim-quality gap |
| `question` | string | yes | Specific question for research agent to answer |
| `rationale` | string | yes | Why this supplement matters |
| `suggested_sources` | array[string] | yes | Source categories or concrete source types |
| `candidate_leads` | array[string] | yes | Candidate URLs, source names, or search leads already present in input files; may be empty. Planner must not add external leads |
| `source_refs` | array[string] | yes | Review/perspective locations that raised this item |
| `review_refs` | array[string] | yes | Claim ids or review bullets involved; may be empty for pure coverage items |
| `impact_if_skipped` | string | yes | How final report should be constrained if skipped |
| `status` | enum | yes | Initial value `pending`; research later updates to `resolved` / `partial` / `no_data` / `out_of_scope` |
| `resolution_note` | string | yes | Empty initially; research fills after execution |

For `partial`, `no_data`, and `out_of_scope`, `resolution_note` is not the downstream boundary. Research must also write a schema-valid `writing_context` object into the target evidence: `unresolved_gap`, `availability_gap`, or `scope_boundary` respectively. Report planning consumes only evidence, not this audit file.

## `deferred_items[]`

Use this array for candidates that should not trigger supplement research.

| field | type | required | description |
| --- | --- | --- | --- |
| `id` | string | yes | Stable id, e.g. `d1-d1` |
| `reason` | enum | yes | `writing_context_only` / `low_value` / `not_actionable` / `out_of_scope` / `already_covered` / `unavailable` |
| `item` | string | yes | Short description of the deferred candidate |
| `source_refs` | array[string] | yes | Review/perspective locations that raised it |
| `writing_context_use` | string | yes | How to surface it, or empty string if not applicable |

## Empty plan

If no supplement is needed, write a valid empty plan:

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

## Consumer rules

- Controller uses `supplement_items[]` only to decide whether to run `research` in `mode: supplement` for this dimension.
- Supplement research executes only `supplement_items[]`; it does not process `deferred_items[]`.
- Report-stage agents do not consume this file as evidence.
- `deferred_items[]` can only inform writing-context boundaries, limitations, or audit notes.
- Planner may copy and deduplicate `candidate_leads[]` from its input files, but it must not perform validation searches or introduce a new URL/source/search lead.
