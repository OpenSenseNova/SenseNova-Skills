# Outline Schema v2.0

报告编排阶段的契约文件。v2 把最终产物建模为有序的 `content_units[]`，不再要求所有任务都落入 `sections -> lead -> blocks` 的文章骨架。一个 content unit 可以是正文、矩阵、时间线、清单、评分卡、问答、callout、关系图或用户自定义结构。

`paradigm` 与 `organization_decision` 是正交维度：

- `paradigm` 回答内容如何推进，可取 panorama、comparison、investigation、timeline、evaluation、forecast。
- `organization_decision` 回答研究完成后用什么结构承载核心信息。
- 不存在 paradigm 到 content unit type 的固定映射。comparison 不必使用 matrix，investigation 不必使用 timeline，evaluation 不必使用 checklist。

下游消费者：

- `validate_outline.py`：同时校验 v2.0 和遗留 v1.0。
- `report-writer`：每次只执行一个 content unit，只读该 unit 的 evidence subset。
- `report-stitcher`：按 content unit 顺序组装，不强加标题、摘要、目录或结论章节。
- review / render：以 `organization_decision` 和 `render_contract` 为准核对成品。

## 文件位置

```text
{report_dir}/outline.json
{report_dir}/content_units/{unit_id}.evidence_subset.json
{report_dir}/content_units/{unit_id}.md
```

v1.0 文件仍沿用 `{report_dir}/sections/s{N}.*`，迁移期间不得把两种路径混用。

## 顶层结构

```json
{
  "schema_version": "2.0",
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
| `schema_version` | string | 固定为 `"2.0"` |
| `paradigm` | object | 内容推进范式，不决定产物结构 |
| `depth_level` | enum | `overview` / `deep_analysis` / `expert_level` |
| `global_arc` | string | 40-120 字的全文方向和证据边界 |
| `organization_decision` | object | evidence 完成后的结构决定 |
| `L0_draft` | object / null | 是否存在由 `opening_summary` 决定 |
| `style_contract` | object | 输出语言、体裁、语气、术语和引用约定 |
| `content_units` | array | 1-20 个有序交付单元 |
| `claim_routing_table` | object | 每个被引用 claim 的唯一主归属与可选次级引用 |
| `scan_summary` | object | planner 扫描 evidence 得到的可审计摘要 |

## Organization decision

这是 report-planner 在 evidence 全部完成后作出的决定，不是 format discovery 在研究前的猜测。

```json
{
  "reader_task": "让采购负责人按同一口径比较三个方案，并识别在不同约束下的适用边界",
  "primary_unit_type": "matrix",
  "supporting_unit_types": ["callout", "narrative"],
  "opening_summary": "recommendation",
  "toc": false,
  "numbered_headings": false,
  "preference": {
    "requested_type": "matrix",
    "custom_type": null,
    "strength": "preferred",
    "resolution": "preferred_honored",
    "adaptation_reason": null
  },
  "evidence_fit": "现有证据对三个对象覆盖同一组指标，适合用矩阵承载主体；分歧和口径限制由 supporting units 解释。"
}
```

### Content unit type

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

这是一组可扩展的合同类型，不是 paradigm 配对表。

### Preference resolution

`preference` 必须复制 `format.json.structure_preference` 的 `requested_type`、`custom_type` 和 `strength`，再补充 planner 的 resolution：

| strength | requested_type | resolution | 约束 |
|---|---|---|---|
| `required` | 必填 | `required_honored` | `primary_unit_type` 必须等于 requested_type；custom 时必须保留 custom_type |
| `preferred` | 必填 | `preferred_honored` / `preferred_adapted` | 调整时必须写 20-300 字 `adaptation_reason` |
| `auto` | 必须为 null | `auto_selected` | 根据 reader task 和 evidence 选择 |

禁止行为：

- 因为 `paradigm.main=comparison` 就自动选择 matrix。
- 因为 `paradigm.main=timeline` 就自动选择 timeline。
- 把用户的 preferred 当作 required。
- 在 evidence 完成前固定 `organization_decision`。

`supporting_unit_types` 是去重数组，可为空；`opening_summary` 取 `none|findings|recommendation`。`toc` 与 `numbered_headings` 必须由已确认形式决定，不能使用报告式默认值。

## L0 draft

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

约束延续 v1：headline 8-30 字；key_findings 3-5 条、每条 20-60 字；abstract visual 的事实型 `data_refs` 必须是有效 claim id 并进入 content unit 路由。

## Style contract

```json
{
  "language": "zh-Hans",
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

枚举与 v1 一致：

- `language`：非空 BCP 47 标签，必须逐字复制 payload 的 `language`；validator 传 `--language <BCP47>` 时做参数绑定
- `register`：`research_brief|academic|executive_memo|industry_report|policy_analysis`
- `voice`：`neutral_analytical|hedged_scholarly|declarative_executive|opinionated_supported`
- `citation_style`：`footnote|inline`

## Content unit

content unit 是 writer 的最小执行边界，也是最终产物的一级结构件。结构件可以是主体，不再只能作为 section 的辅助 visual。

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

### Common fields

| 字段 | 约束 | 说明 |
|---|---|---|
| `id` | `^u\d+$` | unit 唯一 ID |
| `type` | content unit enum | 信息语义，不强制具体 Markdown 渲染方式 |
| `role` | `primary|supporting` | 主体或补充结构 |
| `title` | 2-80 字 | 可展示标题；是否显示由 render contract 决定。`numbered_headings=true` 且显示标题时，title 自身必须带稳定序号 |
| `reader_task` | 10-160 字 | 读者使用该 unit 完成什么任务，不要求写成问句 |
| `word_budget` | 50-3000 | 包含表格、列表和图中可见文字的粗略预算 |
| `lead` | null 或 20-180 字 | 需要 BLUF 时使用；结构件不需要开场时为 null |
| `render_contract` | object | Markdown 形态和字段合同 |
| `elements` | 1-20 项 | unit 内的行、问题、事件、检查项、论点或其他可执行元素 |
| `evidence_subset` | 0-30 个 claim | writer 可见的事实边界；gap-only unit 可为空，但必须路由 writing context |

### Render contract

```json
{
  "mode": "prose|markdown_table|ordered_list|checklist|qa|callout|mermaid|mixed|custom",
  "show_heading": true,
  "schema": ["字段或列名"],
  "instructions": "10-500 字的具体渲染约束"
}
```

- `mode` 与 `type` 不做硬编码映射。timeline 可渲染为表格、列表或 Mermaid；investigation 也可以用 diagram 或 narrative。
- `schema` 是 0-20 个去重字段名。矩阵可写列名，timeline 可写事件字段，narrative 可留空。
- `instructions` 必须说明本 unit 如何承载主要信息，不能只写“按要求输出”。

### Element and evidence boundary

每个 element：

- `id`：unit 内唯一，匹配 `^e\d+$`。
- `label`：2-100 字。
- `purpose`：10-240 字。
- `evidence_refs`：0-10 条，每条含合法 `claim_id` 与 narrative role。为空时 `writing_context_refs` 必须非空，只能表达有记录支撑的证据缺口。
- `writing_context_refs`：可选，0-20 个 `dN.wM`。

`evidence_refs[].role` 沿用：`primary_support|supporting_context|quantifier|counter|reference_only`。

边界是硬约束：

1. 单 element 最多 10 个 evidence refs；claim 与 writing context 不得同时为空。
2. 单 unit 的 `evidence_subset` 最多 30 个去重 claim。
3. `evidence_subset` 必须精确等于所有 `elements[].evidence_refs[].claim_id` 的去重并集。
4. writer 只能读取和引用自己的 evidence subset，不得从其他 unit 或完整 evidence 中补材料。
5. 需要超过上限时拆分 content unit，而不是扩大“备用资料篮子”。

## Claim routing table

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

- 每个进入任一 `evidence_subset` 的 claim 必须有且只有一个 primary unit。
- primary unit 必须实际在 element 中使用该 claim。
- secondary role 只能是 `supporting_context|reference_only`，避免在多个 unit 重复展开。
- routing key 集合必须精确覆盖所有 unit 引用的 claim；不允许未使用的路由项。

## Scan summary

v2 保留 v1 的 evidence 扫描结果：

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

`reader_task_signal` 只给六种内容范式打分，不增加结构类型得分，也不用于自动映射 `primary_unit_type`。结构决定写入独立的 `organization_decision`。

## evidence_subset.json

```json
{
  "schema_version": "2.0",
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

校验规则：

- `schema_version` 必须与 outline 一致。
- `content_unit_id` 必须存在于 `outline.content_units`。
- `claims[].id` 必须精确等于对应 unit 的 `evidence_subset`；gap-only unit 允许 `claims=[]`，但 `writing_context` 必须精确包含 element 路由的缺口记录。
- claim 内容与原始 evidence 一致；sources 覆盖 claim 和 writing_context 引用的 source id。
- `narrative_role` 必须与 routing table 中该 unit 的角色一致。

## Minimal v2 example

```json
{
  "schema_version": "2.0",
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
    "preference": {
      "requested_type": null,
      "custom_type": null,
      "strength": "auto",
      "resolution": "auto_selected",
      "adaptation_reason": null
    },
    "evidence_fit": "现有证据逐项对应明确条件，适合直接核对；无法确认的项目可以保留未知状态而不扩写成章节。"
  },
  "L0_draft": null,
  "style_contract": {
    "language": "zh-Hans",
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

## Validator rules

`validate_outline.py` 对 v2 强制：

1. organization preference 的 required / preferred / auto 语义一致；传 `--format` 时与用户确认的 `format.json` 精确绑定；传 `--language` 时 `style_contract.language` 与运行语言锚点精确绑定。
2. 至少一个 `role=primary` 的 unit，且所有 primary unit 的 type 均等于单数 `primary_unit_type`；其他类型必须标为 supporting。
3. supporting unit type 与 `supporting_unit_types` 精确一致。
4. unit、element、schema 字段和 evidence refs 均满足数量上限；gap-only element 必须路由 writing context。
5. evidence subset 精确等于 element refs 并与 claim routing 双向一致；每个 unit 恰好一个 `{unit_id}.evidence_subset.json`，文件名与内部 id 一致。
6. subset 中的 claim、evidence、snapshot_ref 与 writing context 必须从原始 evidence 精确复制，不得出现未知或改写对象。
7. L0 是否存在与 `opening_summary` 一致，abstract visual refs 已进入路由。
8. reader task signal 仍只包含六种 paradigm 且总和约等于 1。

## v1.0 compatibility

validator 继续完整支持 `schema_version="1.0"` 的既有结构：

```text
sections[] -> lead -> blocks[] -> visuals[]
sections/{section_id}.evidence_subset.json
visual_inventory
claim_routing_table[].secondary[].section
```

兼容原则：

- 既有 v1 outline 不需要就地升级即可继续校验。
- 新 planner 默认输出 v2；不得在同一 outline 同时写 `sections` 和 `content_units`。
- v1 的 `primary_information_shape` 只作为遗留输入读取，不应出现在新 v2 决策中。
- 迁移是消费方显式按 `schema_version` 分支，不通过向 v1 section 不断增加例外完成。
- 新 controller 固定使用 `--require-version 2.0`；v1 通过只表示既有产物可独立校验，不代表可以进入 v2 writer/stitcher 路径。
