# Perspective Feedback Markdown Contract

`{report_dir}/sub_reports/d{N}.perspectives/{lens.axis}_{lens.value}.md` records one lens coverage review for a single research dimension.

It is not formal evidence. It can diagnose coverage gaps, propose supplement questions, and describe writing-context boundaries. Any new factual lead must be verified by `research` and written into `d{N}.evidence.json` before it can support report claims.

## File location

```text
{report_dir}/sub_reports/d{N}.perspectives/{lens.axis}_{lens.value}.md
```

## Required sections

```markdown
# Perspective Feedback: {dimension_id} / {lens.axis}:{lens.value}

## Lens 定位

## 对本维度的关键反馈

### 写作补充边界（非正文主张）

### 需要补研后才能使用

## 探索性搜索线索

## 维度内补研需求

## 写回摘要
```

## Section contract

### Lens 定位

Must include:

- `lens: {axis}:{value}`
- `rationale`
- reviewed evidence path

### 写作补充边界（非正文主张）

Use for structure, explanation order, source-boundary notes, risk reminders, and gap/callout wording boundaries.

Each item should state:

- title
- explanation
- suggested use: `writing_context` / table note / paragraph-end qualifier / gap-callout
- evidence dependency: `none` or current-dimension evidence

These items must not become lead, block thesis, L0, or new factual claims.

### 需要补研后才能使用

Use for factual, trend, comparison, causal, quantitative, or case judgments that are not yet supported by evidence.

Each item should state:

- pending judgment
- current problem
- concrete supplement question
- impact if skipped

### 探索性搜索线索

A markdown table with columns:

| 线索 | URL/来源 | 可能意义 | 是否需要 research 复核 |
| --- | --- | --- | --- |

All leads require research verification and are not evidence.

### 维度内补研需求

A markdown table with columns:

| 缺口 | 补研问题 | 建议来源 | 候选线索 | 不补研的影响 |
| --- | --- | --- | --- | --- |

If no supplement is needed, write exactly: `无必要补研。`

### 写回摘要

3-6 short bullets for controller / supplement-planner. Bullets must distinguish:

- claims needing supplement research
- writing_context boundaries
- no-supplement decisions

Do not write final-report prose here.

## Consumer rules

- `supplement-planner` reads this markdown together with `review.md` and current `evidence.json`.
- Controller should use only the role completion summary for scheduling; it should not read full perspective markdown.
- Report-stage agents do not consume perspective feedback as evidence.
- Unresolved perspective feedback can only surface as limitations or gap-callouts after being routed through evidence or writing_context boundaries.
