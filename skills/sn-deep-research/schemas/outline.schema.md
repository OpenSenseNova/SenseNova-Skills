# 报告编排字段契约

报告编排阶段的字段契约。最终产物由有序的 `content_units[]` 组成。`paradigm` 表示内容推进方式，`organization_decision` 表示核心信息的承载结构。请求级 `format` 由 payload 传入，不复制到 `outline.json`。

## 文件位置

```text
{report_dir}/outline.json
{report_dir}/content_units/{unit_id}.evidence_subset.json
{report_dir}/content_units/{unit_id}.md
```

## 顶层结构

```json
{
  "paradigm": { "main": "comparison", "secondary": "evaluation" },
  "depth_level": "deep_analysis",
  "global_arc": "从用户的选择问题出发，先统一比较口径，再用现有证据呈现差异、冲突和适用边界，最后给出有条件的判断。",
  "organization_decision": { "...": "见下文" },
  "L0_draft": { "...": "见下文；也可以为 null" },
  "style_contract": { "...": "见下文" },
  "content_units": [ "..." ],
  "claim_routing_table": { "...": "见下文" },
  "scan_summary": { "...": "见下文" }
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `paradigm` | 对象 | 内容推进范式，不决定产物结构 |
| `depth_level` | 枚举 | `overview` / `deep_analysis` / `expert_level` |
| `global_arc` | 字符串 | 非空的全文方向和证据边界，不设置字符数限制 |
| `organization_decision` | 对象 | 证据完成后的结构决定 |
| `L0_draft` | 对象 / `null` | 是否存在由 `opening_summary` 决定 |
| `style_contract` | 对象 | 体裁、语气、术语和引用约定 |
| `content_units` | 数组 | 1–20 个有序交付单元 |
| `claim_routing_table` | 对象 | 每个被引用断言的唯一主归属与可选次级引用 |
| `scan_summary` | 对象 | 规划器扫描证据后得到的可审计摘要 |

## 结构示例

```json
{
  "reader_task": "让采购负责人按同一口径比较三个方案，并识别在不同约束下的适用边界",
  "primary_unit_type": "matrix",
  "supporting_unit_types": ["callout", "narrative"],
  "opening_summary": "recommendation",
  "toc": false,
  "numbered_headings": false,
  "evidence_fit": "现有证据对三个对象覆盖同一组指标，适合用矩阵承载主体；分歧和口径限制由 supporting units 解释。"
}
```

### 内容单元类型

基础枚举：

- `narrative`：连续论述。
- `matrix`：实体乘维度的二维比较。
- `timeline`：按时间或阶段组织的事件链。
- `checklist`：逐项核对状态、要求或完成度。
- `scorecard`：按标准给出等级、分数或判断。
- `qa`：独立问题与回答。
- `callout`：关键事实、冲突、缺口或限制。
- `diagram`：流程、因果、关系或系统结构。
- `custom`：用户定义的其他结构；必须通过 `render_contract.instructions` 说明。

`supporting_unit_types` 是去重数组，可为空；`opening_summary` 取 `none|findings|recommendation`。`toc` 与 `numbered_headings` 必须由已确认形式决定，不能使用报告式默认值。

## `L0_draft`（L0 草稿）

- `opening_summary=none` 时，`L0_draft` 必须为 `null`。
- `opening_summary=findings|recommendation` 时，`L0_draft` 必须存在。

```json
{
  "headline": "三个方案的最优选择取决于规模门槛与部署约束",
  "key_findings": [
    "方案甲在大规模负载下成本最低，但前期部署与迁移要求最高",
    "方案乙在中等规模下保持成本和交付速度的平衡，证据覆盖最完整",
    "方案丙适合快速启动，但长期成本与扩展性数据仍存在明显缺口"
  ],
  "abstract_visual": {
    "form": "comparison-table",
    "data_refs": ["d1.c1", "d2.c1", "d3.c1"]
  }
}
```

约束：`headline` 必须非空；`key_findings` 保持 3–5 条且每条非空；`abstract_visual` 的事实型 `data_refs` 必须是有效的断言 ID，并进入内容单元路由。自然语言字段不设置字符数限制。

## `style_contract`（样式契约）

```json
{
  "register": "executive_memo",
  "voice": "declarative_executive",
  "terminology": {
    "preferred": {
      "总拥有成本": ["TCO", "全周期成本"]
    }
  },
  "citation_style": "footnote"
}
```

枚举：

- `register`：`research_brief|academic|executive_memo|industry_report|policy_analysis`
- `voice`：`neutral_analytical|hedged_scholarly|declarative_executive|opinionated_supported`
- `citation_style`：`footnote|inline`

## `content_unit`（内容单元）

```json
{
  "id": "u1",
  "type": "matrix",
  "role": "primary",
  "title": "三个方案的核心指标与适用边界",
  "reader_task": "按一致口径比较成本、交付、扩展性与主要风险",
  "word_budget": 900,
  "lead": "三个方案没有脱离场景的统一最优解；规模门槛和交付约束会改变排序。",
  "render_contract": {
    "mode": "markdown_table",
    "show_heading": true,
    "schema": ["方案", "成本", "交付周期", "扩展性", "适用边界"],
    "instructions": "用一张主矩阵承载所有同口径结果；每格只写结论和必要引用，口径差异放表注。"
  },
  "elements": [
    {
      "id": "e1",
      "label": "方案甲",
      "purpose": "呈现方案甲在统一指标下的结果与限制",
      "evidence_refs": [
        { "claim_id": "d1.c1", "role": "primary_support" },
        { "claim_id": "d1.c2", "role": "counter" }
      ],
      "writing_context_refs": ["d1.w1"]
    }
  ],
  "evidence_subset": ["d1.c1", "d1.c2"]
}
```

### 通用字段

| 字段 | 约束 | 说明 |
|---|---|---|
| `id` | `^u\d+$` | 内容单元的唯一 ID |
| `type` | 内容单元枚举 | 信息语义，不强制具体 Markdown 渲染方式 |
| `role` | `primary|supporting` | 主体或补充结构 |
| `title` | 非空字符串 | 可展示标题；是否显示由渲染契约决定。`numbered_headings=true` 且显示标题时，标题本身必须带稳定序号 |
| `reader_task` | 非空字符串 | 读者使用该内容单元完成什么任务，不要求写成问句 |
| `word_budget` | 50-3000 | 包含表格、列表和图中可见文字的粗略预算 |
| `lead` | `null` 或非空字符串 | 需要先给结论时使用；结构件不需要开场时为 `null` |
| `render_contract` | 对象 | Markdown 形态和字段契约 |
| `elements` | 1–20 项 | 内容单元内的行、问题、事件、检查项、论点或其他可执行元素 |
| `evidence_subset` | 0–30 个断言 | 写作智能体可见的事实边界；仅表达缺口的内容单元可以为空，但必须路由写作上下文 |

### 渲染契约

```json
{
  "mode": "prose|markdown_table|ordered_list|checklist|qa|callout|mermaid|mixed|custom",
  "show_heading": true,
  "schema": ["字段或列名"],
  "instructions": "非空的具体渲染约束"
}
```

- `mode` 与 `type` 不做硬编码映射。`timeline` 可渲染为表格、列表或 Mermaid；`investigation` 也可以使用 `diagram` 或 `narrative`。
- `schema` 是 0–20 个去重字段名。矩阵可以填写列名，`timeline` 可以填写事件字段，`narrative` 可以留空。
- `instructions` 必须说明本内容单元如何承载主要信息，不能只写“按要求输出”。

### 元素与证据边界

每个元素：

- `id`：内容单元内唯一，匹配 `^e\d+$`。
- `label`：非空字符串。
- `purpose`：非空字符串。
- `evidence_refs`：0–10 条，每条包含合法的 `claim_id` 和叙事角色。为空时，`writing_context_refs` 必须非空，并且只能表达有记录支撑的证据缺口。
- `writing_context_refs`：可选，0-20 个 `dN.wM`。

`evidence_refs[].role` 沿用：`primary_support|supporting_context|quantifier|counter|reference_only`。

边界是硬约束：

1. 单个元素最多包含 10 个证据引用；断言与写作上下文不得同时为空。
2. 单个内容单元的 `evidence_subset` 最多包含 30 个去重断言。
3. `evidence_subset` 必须与所有 `elements[].evidence_refs[].claim_id` 的去重并集完全相同。
4. 写作智能体只能读取和引用自己的证据子集，不得从其他内容单元或完整证据中补充材料。

## `claim_routing_table`（断言路由表）

```json
{
  "d1.c1": {
    "primary": "u1",
    "secondary": [
      { "unit": "u3", "role": "supporting_context" }
    ]
  }
}
```

- 每个进入任一 `evidence_subset` 的断言必须有且只有一个主内容单元。
- 主内容单元必须实际在元素中使用该断言。
- 次级角色只能是 `supporting_context|reference_only`，以避免在多个内容单元中重复展开。
- 路由键集合必须精确覆盖所有内容单元引用的断言；不允许存在未使用的路由项。

## `scan_summary`（扫描摘要）

```json
{
  "totals": { "claims": 18, "sources": 12, "primary_ratio": 0.67 },
  "topic_clusters": [],
  "conflicts": [],
  "key_entities": [],
  "timeline_density": [],
  "gaps": [],
  "reader_task_signal": {
    "panorama": 0.05,
    "comparison": 0.55,
    "investigation": 0.05,
    "timeline": 0.05,
    "evaluation": 0.25,
    "forecast": 0.05
  }
}
```

`reader_task_signal` 只为六种内容范式评分，不增加结构类型得分，也不用于自动映射 `primary_unit_type`。结构决定写入独立的 `organization_decision`。

## `evidence_subset.json`（证据子集）

```json
{
  "content_unit_id": "u1",
  "claims": [
    {
      "id": "d1.c1",
      "text": "...",
      "kind": "factual",
      "polarity": "neutral",
      "topic_tag": "cost",
      "narrative_role": "primary_support",
      "evidence": ["..."]
    }
  ],
  "writing_context": [],
  "sources": []
}
```

输出规则：

- `content_unit_id` 必须存在于 `outline.content_units`。
- `claims`、`writing_context` 与 `sources` 中的对象必须具备合法字段；传入原始证据时，断言和写作上下文 ID 必须存在。
- 子集必须包含本内容单元元素实际引用的断言和写作上下文；额外对象不会仅因重复索引关系而直接判错。
- `sources` 必须覆盖断言和写作上下文引用的来源 ID。

## 最小示例

```json
{
  "paradigm": { "main": "evaluation", "secondary": null },
  "depth_level": "overview",
  "global_arc": "围绕用户需要作出的选择，按统一标准核对关键证据、相反信息和适用边界，给出受证据强度约束的判断。",
  "organization_decision": {
    "reader_task": "快速核对方案是否满足关键条件，并看到每项判断的证据边界",
    "primary_unit_type": "checklist",
    "supporting_unit_types": [],
    "opening_summary": "none",
    "toc": false,
    "numbered_headings": false,
    "evidence_fit": "现有证据逐项对应明确条件，适合直接核对；无法确认的项目可以保留未知状态而不扩写成章节。"
  },
  "L0_draft": null,
  "style_contract": {
    "register": "research_brief",
    "voice": "neutral_analytical",
    "terminology": { "preferred": {} },
    "citation_style": "footnote"
  },
  "content_units": [
    {
      "id": "u1",
      "type": "checklist",
      "role": "primary",
      "title": "关键条件核对",
      "reader_task": "逐项确认关键要求是否满足以及证据是否充分",
      "word_budget": 500,
      "lead": null,
      "render_contract": {
        "mode": "checklist",
        "show_heading": true,
        "schema": ["条件", "状态", "依据", "限制"],
        "instructions": "每项只给满足、不满足或证据不足三种状态，并在同一项内附引用和限制。"
      },
      "elements": [
        {
          "id": "e1",
          "label": "条件甲",
          "purpose": "核对条件甲是否满足并呈现证据限制",
          "evidence_refs": [
            { "claim_id": "d1.c1", "role": "primary_support" }
          ],
          "writing_context_refs": []
        }
      ],
      "evidence_subset": ["d1.c1"]
    }
  ],
  "claim_routing_table": {
    "d1.c1": { "primary": "u1", "secondary": [] }
  },
  "scan_summary": {
    "totals": { "claims": 1, "sources": 1, "primary_ratio": 1.0 },
    "topic_clusters": [],
    "conflicts": [],
    "key_entities": [],
    "timeline_density": [],
    "gaps": [],
    "reader_task_signal": {
      "panorama": 0.0,
      "comparison": 0.0,
      "investigation": 0.0,
      "timeline": 0.0,
      "evaluation": 1.0,
      "forecast": 0.0
    }
  }
}
```
