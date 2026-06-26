# Outline Schema v1.0

报告编排阶段的**契约文件**——planner 输出，writer / stitcher / render 全部消费。outline 是契约,不是建议:writer 严守 evidence_subset,不可越界引用。

下游消费者:
- `validate_outline.py` — 强制校验
- `report-writer` agent — 按 sections[i] 写章节,只读自己的 evidence_subset
- `report-stitcher` agent — 缝合时处理接缝,并按 visual_inventory 校验兑现
- `prepare_citations.py` — 生成 L0 摘要框、TOC、附录
- `review` agent — 终稿审查时按 global_arc 比对

## 文件位置

```
{report_dir}/outline.json                              ← 主契约
{report_dir}/sections/s{N}.evidence_subset.json        ← 派生切片(每节一份)
```

## 顶层结构

```json
{
  "schema_version": "1.0",
  "paradigm": { "main": "panorama", "secondary": "forecast" },
  "depth_level": "deep_analysis",
  "global_arc": "...",
  "L0_draft": { ... },
  "style_contract": { ... },
  "sections": [ ... ],
  "visual_inventory": [ ... ],
  "claim_routing_table": { ... },
  "scan_summary": { ... }
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `schema_version` | string | 固定 `"1.0"` |
| `paradigm` | object | 主副范式,影响章节骨架与组件触发 |
| `depth_level` | enum | `overview` / `deep_analysis` / `expert_level` |
| `global_arc` | string | 40-120 字。全文级写作方向,约束章节顺序、章节取舍和后续缝合 |
| `L0_draft` | object | 终稿顶部的 30 秒阅读层草稿,stitcher 阶段会修订 |
| `style_contract` | object | 声调、术语、引用风格 |
| `sections` | array | ≥ 3 节。每节是一个 writer agent 的工作单元 |
| `visual_inventory` | array | sections[].visuals 的扁平索引,stitcher 用它做兑现验证 |
| `claim_routing_table` | object | 每个 claim_id 的归属路由(primary 章节 + secondary 引用) |
| `scan_summary` | object | planner 第一步扫描的全局图谱(可审计依据) |

---

## Paradigm

```json
{ "main": "panorama", "secondary": "forecast" }
```

| 取值 | 适用 | 主要骨架 |
|---|---|---|
| `panorama` | "这领域什么样" | 切片 → 玩家分布 → 力量结构 → 趋势 |
| `comparison` | "X vs Y vs Z" | 选项概览 → 矩阵 → 强弱 → 选择指南 |
| `investigation` | "发生了什么 / 为什么" | 起点 → 触发 → 演化 → 现状 → 影响 |
| `timeline` | "怎么演化的" | 阶段划分 → 关键事件 → 转折分析 |
| `evaluation` | "X 值不值 / 行不行" | 核心判断 → 论据 → 反方 → 边界 |
| `forecast` | "未来会怎样" | 现状 → 关键变量 → 场景 → 监测信号 |

`secondary` 可以是 `null`。一份报告通常**主范式 + 副范式**——比如"中国 EV 行业未来 3 年"是 `panorama`(主) + `forecast`(副)。

范式专属的章节模板在另一份文档(`outline.paradigms.md`,后续补)。本 schema 只定义通用结构。

---

## L0_draft

读者 30 秒能拿走的内容。它是终稿顶部摘要层的草稿,stitcher 阶段会校对修订让其与正文一致。

```json
{
  "headline": "中国 EV 寡头化 + 全球化双拐点",
  "key_findings": [
    "前三家厂商 2024 合计份额 60%,集中度比 2022 升 11pp",
    "技术分层显著: 头部 2 家固态电池,腰部押注混动",
    "欧美关税与本地化建厂是 2026-28 关键变量"
  ],
  "abstract_visual": {
    "form": "distribution-chart",
    "data_refs": ["d1.c2", "d1.c4"]
  }
}
```

| 字段 | 取值 | 说明 |
|---|---|---|
| `headline` | 8-30 字 | 结论性短语,压缩报告主题和判断方向;不是报告标题、章节名或泛话题 |
| `key_findings` | 3-5 条 | 每条 20-60 字。最能回答用户需求的核心判断;必须有 evidence 支撑,并能在正文 section lead/blocks 中展开 |
| `abstract_visual` | object 或 null | 可选。最快解释整体格局、关键对比或主要分歧的图/表;`data_refs` 必须来自 evidence |

证据不足但用户关心的内容,不要放进 `key_findings`;应放入对应 section 的 gap / limitation。

---

## Style contract

表达一致性合同,用于约束 writer 的体裁、语气、术语和引用方式;不决定事实、结论或章节结构。所有字段都必须存在,但 `terminology.preferred` 可以为空对象。

```json
{
  "register": "research_brief",
  "voice": "neutral_analytical",
  "terminology": {
    "preferred": {
      "国产替代率": ["自给率", "本土化率"]
    }
  },
  "citation_style": "footnote"
}
```

| 字段 | 取值 | 说明 |
|---|---|---|
| `register` | `research_brief` / `academic` / `executive_memo` / `industry_report` / `policy_analysis` | 必填。报告体裁/读者语境,决定摘要密度、章节语气和解释粒度 |
| `voice` | `neutral_analytical` / `hedged_scholarly` / `declarative_executive` / `opinionated_supported` | 必填。判断力度和措辞方式;应与 register 和证据强度匹配 |
| `terminology.preferred` | dict: 标准词 → [变体列表] | 必填,可为空 `{}`。统一同义术语;stitcher 用此把变体替换为标准词 |
| `citation_style` | `footnote` / `inline` | 必填。引用渲染约定;当前管线通常固定 `footnote` |

字段使用原则:
- `register` 解决"这是什么类型的报告、写给谁"。
- `voice` 解决"判断说得多直接、多谨慎"。
- `terminology.preferred` 解决"同一概念全文叫什么"。
- `citation_style` 解决"writer 和 render 如何约定引用格式"。

---

## Section

每个 section 是一个 writer agent 的工作单元。

```json
{
  "id": "s2",
  "title": "成本结构对比",
  "reader_question": "三家厂商的成本差距来自哪个环节?",
  "section_role": "comparison",
  "word_budget": 800,

  "lead": "三家在 BOM 成本上的差距 60% 来自电池模组,而非整车工艺。",

  "blocks": [
    {
      "id": "b1",
      "level": 3,
      "heading": "BYD 电池自产率与成本结构",
      "thesis": "BYD 的电池自产带来 18% 成本优势",
      "evidence_refs": [
        { "claim_id": "d2.c3", "role": "primary_support" },
        { "claim_id": "d2.c5", "role": "quantifier" }
      ],
      "writing_context_refs": []
    }
  ],

  "visuals": [
    {
      "position": "after_lead",
      "information_type": "multi-entity-comparison",
      "form": "comparison-table",
      "render": "markdown-table",
      "data_refs": ["d2.c3", "d2.c5", "d2.c8"],
      "caption": "三家 BOM 成本拆解(2024)",
      "purpose": "把多实体多维度成本差异压缩成可比较矩阵",
      "replaces_words": 400
    }
  ],

  "evidence_subset": ["d2.c3", "d2.c5", "d2.c8"]
}
```

| 字段 | 取值 | 说明 |
|---|---|---|
| `id` | `^s\d+$` | 形如 `s1`、`s2` |
| `title` | 4-30 字 | 章节标题 |
| `reader_question` | 10-80 字 | 读者来这章带着的问题。必须以 `?` 或 `？` 结尾 |
| `section_role` | enum, 见下 | 章节在叙事中的功能 |
| `word_budget` | 200-3000 | 该章预计字数(整数) |
| `lead` | 30-150 字 | 章首 BLUF 草稿 |
| `blocks` | 1-10 个 | 小节/段落级写作合同 |
| `visuals` | 0-3 个 | 该章所有视觉元素,包括图表、表格、callout、AI 插图和已有图片 |
| `evidence_subset` | claim_id 数组,长度 ≥ 1 | **writer 只能引用这些 claim**。必须精确等于本节 blocks.evidence_refs 与 visuals.data_refs 的去重并集 |

### Section contract completeness

每个 section 是交给 writer 的最小工作合同,不能只是资料篮子。合格 section 必须满足:

| 契约项 | 对应字段 | 说明 |
|---|---|---|
| 读者问题 | `reader_question` | 真问句,限定本节要回答的问题 |
| 核心答案 | `lead` | 章首 BLUF,第一句直接回答 reader_question |
| 小节标题 | `blocks[].heading` / `blocks[].level` | 控制正文 H3/H4 标题树;heading 应写“对象 + 信息方面”,不写抽象栏目、元问题或判断句 |
| 段落主张 | `blocks[].thesis` | 完整承载性主张,可作为段首句 |
| 证据绑定 | `blocks[].evidence_refs[]` | 每个 thesis 显式绑定 claim_id 与 narrative role |
| 视觉承诺 | `visuals[]` | 所有视觉都提前声明 information_type / form / render / data_refs / caption / position |
| 引用边界 | `evidence_subset[]` | 只包含上述主张和视觉实际会用到的 claim,不能多放备用材料 |
| 全文路由 | `claim_routing_table` | 每个 claim 只能有一个 primary 展开章节 |

如果某个 claim 只是背景,也必须挂到某个 block,role 用 `supporting_context` 或 `reference_only`。如果某个 claim 只服务于图表,它必须出现在对应 visual 的 `data_refs`。否则 writer 没有明确写作义务,该 claim 不应进入本节。

### Section role 枚举

| role | 章节功能 |
|---|---|
| `context` | 设定背景 / 定义术语 |
| `exposition` | 铺陈展开核心事实 |
| `comparison` | 横向对比多实体 |
| `argument` | 推进核心论证 |
| `counter` | 反方观点 / 限定条件 |
| `synthesis` | 综合 / 收束 |
| `outlook` | 展望未来 / 场景 |
| `action` | 行动建议(仅 evaluation 范式适用) |

---

## Block

小节/段落级写作合同。一个 block 通常对应正文里的一个 H3/H4 小节或一组围绕同一 thesis 的段落。

```json
{
  "id": "b1",
  "level": 3,
  "heading": "BYD 电池自产率与成本结构",
  "thesis": "BYD 的电池自产带来 18% 成本优势",
  "evidence_refs": [
    { "claim_id": "d2.c3", "role": "primary_support" },
    { "claim_id": "d2.c5", "role": "quantifier" }
  ],
  "writing_context_refs": []
}
```

| 字段 | 取值 | 说明 |
|---|---|---|
| `id` | `^b\d+$` | section 内唯一,形如 `b1`、`b2` |
| `level` | 3 或 4 | 对应 writer 输出的 `###` / `####` |
| `heading` | 4-80 字 | 小节标题。必须带对象限定,接近“研究对象/人群/地区/行业 + 信息方面”;不要写成抽象栏目、元问题或 thesis 判断 |
| `thesis` | 10-160 字 | **完整句**,不是话题。段落首句的 BLUF 草稿 |
| `evidence_refs` | 1-10 个 | 该 thesis 引用的 claim |
| `writing_context_refs` | `dN.wM` 数组,可空 | 补充写作信息,不作为事实 claim |

### Narrative role 枚举

每条 evidence_ref 的 role 表明该 claim 在此 thesis 下扮演什么角色:

| role | 含义 | 写作行为 |
|---|---|---|
| `primary_support` | 该 thesis 的核心论据 | 详细展开(出处、方法、数据) |
| `supporting_context` | 提供背景,非主论据 | 一句话引用 |
| `quantifier` | 提供具体数值/比例 | 数字 + 引用 |
| `counter` | 反方 / 限定条件 | 显式标记反方语气 |
| `reference_only` | 仅提及,详细展开在别处 | 链回 primary section(如"参见 §X") |

**关键纪律**:同一 claim 在不同 section 出现时,role 可以不同(在 s2 是 primary,在 s5 是 reference_only),但**全文只能有一个 primary**——详细展开只发生一次。

---

## Visual

```json
{
  "position": "after_lead",
  "information_type": "multi-entity-comparison",
  "form": "comparison-table",
  "render": "markdown-table",
  "data_refs": ["d2.c3", "d2.c5", "d2.c8"],
  "caption": "三家 BOM 成本拆解",
  "purpose": "对比三家厂商在 BOM、电池占比、自供率上的差异",
  "replaces_words": 400
}
```

| 字段 | 取值 | 说明 |
|---|---|---|
| `position` | `after_lead` / `mid` / `before_close` | 章内位置 |
| `information_type` | enum,见下 | 这张视觉表达的**信息类型** |
| `form` | enum,见下 | 读者看到的**视觉形态** |
| `render` | enum,见下 | writer 最终使用的**渲染方式** |
| `data_refs` | claim_id 数组 | 数据来源。除 `concept-illustration` 外必须 ≥ 1,且必须是 section.evidence_subset 子集 |
| `caption` | 5-50 字 | 图说 |
| `purpose` | string(5-100 字) | 为什么需要这个视觉;不能写成"美化页面" |
| `prompt_hint` | string(5-200 字) 或 null | 仅 `ai-generated-image` 常用,给 writer 的提示词方向 |
| `image_ref` | string 或 null | 仅 `existing-image` 常用,已有图片路径 / URL / source locator |
| `replaces_words` | int | 估算该视觉替代了多少字的文字描述(强迫 planner 思考价值) |

### Visual form 枚举

| information_type | form | render | 最适合表达 |
|---|---|---|---|
| `numeric-ranking` | `bar-chart` | `mermaid-code` | 2-8 项数值排序、规模比较、增速比较 |
| `part-to-whole-distribution` | `distribution-chart` | `mermaid-code` | ≤ 6 类份额、构成、占比 |
| `multi-entity-comparison` | `comparison-table` | `markdown-table` | 多实体 × 多维度对比、评分矩阵 |
| `multi-metric-summary` | `metric-strip` | `markdown-table` | 3-6 个 KPI 或摘要指标并列展示 |
| `timeline-events` | `timeline` | `mermaid-code` | 3-8 个带时间顺序的事件 / 阶段 |
| `process-or-causal-flow` | `flowchart` | `mermaid-code` | 流程、机制、因果链、决策树 |
| `system-structure` | `flowchart` | `mermaid-code` | 产业链、架构层级、角色关系 |
| `two-axis-positioning` | `quadrant-chart` | `mermaid-code` | 双维度定位、象限分布 |
| `key-fact-highlight` | `key-fact-callout` | `markdown-callout` | 需要从正文中拎出的关键事实 / 数字 |
| `evidence-conflict` | `evidence-conflict-callout` | `markdown-callout` | support/refute 并存、口径冲突、来源分歧 |
| `evidence-gap` | `evidence-gap-callout` | `markdown-callout` | 缺 primary、缺时间窗、缺用户关心维度 |
| `entity-profile` | `entity-profile-card` | `markdown-callout` | 公司、产品、人物、地区等实体画像 |
| `concept-or-scene-illustration` | `concept-illustration` | `ai-generated-image` | 非证据型概念插图、场景直觉、陌生对象直观印象 |
| `source-or-screenshot-image` | `source-image` | `existing-image` | 已有图片、截图、地图、产品照片、原始图表 |

### Render 枚举

| render | 含义 |
|---|---|
| `mermaid-code` | writer 用 Mermaid 代码块生成图形 |
| `markdown-table` | writer 用 Markdown 表格渲染 |
| `markdown-callout` | writer 用 blockquote/callout 渲染强调框 |
| `ai-generated-image` | writer 调用图像生成脚本生成新图片 |
| `existing-image` | writer 插入已有图片路径、URL、截图或源图 |

### Visual 选择原则

- 数值排序 ≥ 3 项 → `numeric-ranking` + `bar-chart`
- 份额 / 构成 / 占比 → `part-to-whole-distribution` + `distribution-chart`
- 多实体多维对比 → `multi-entity-comparison` + `comparison-table`
- 时序事件 → `timeline-events` + `timeline`
- 流程 / 因果 / 系统结构 → `process-or-causal-flow` 或 `system-structure` + `flowchart`
- 矛盾观点 → `evidence-conflict` + `evidence-conflict-callout`
- 信息空白 → `evidence-gap` + `evidence-gap-callout`
- 非证据型场景直觉 → `concept-or-scene-illustration` + `concept-illustration`

`concept-illustration` 是唯一允许 `data_refs: []` 的 form。它只能帮助读者建立直观理解,不能承载事实、数字、排名、份额或证据比较。若插图内容依赖某条证据,仍应把对应 claim 放入 `data_refs`。

`source-image` 必须同时提供 `data_refs` 和 `image_ref`:前者说明这张图片为何可作为报告材料,后者说明 writer 从哪里插入图片。

---

## Transitions(可选遗留字段)

新 outline 不需要生成 `transitions`。章节接缝由 stitcher 在全文完成后,根据相邻章节实际内容统一处理。

为兼容旧 outline,如果仍出现该字段,validator 只做弱校验:

```json
{
  "from_prev": "上节确立了销量差距;现在向下钻到成本结构。",
  "to_next": "成本差距的工艺基础,在下节展开。"
}
```

| 字段 | 取值 |
|---|---|
| `from_prev` | string(15-80 字) 或 null |
| `to_next` | string(15-80 字) 或 null |

---

## Visual inventory(全局视觉清单)

sections[].visuals 的扁平索引,stitcher 用来做"兑现验证"——每个清单项必须在最终 stitched.md 中出现对应的图/表(通过 caption grep)。

```json
[
  { "section": "s1", "form": "distribution-chart", "purpose": "市场份额" },
  { "section": "s2", "form": "comparison-table", "purpose": "成本对比" },
  { "section": "s4", "form": "timeline", "purpose": "政策演进" }
]
```

| 字段 | 取值 |
|---|---|
| `section` | section.id |
| `form` | visual form 枚举 |
| `purpose` | 5-30 字。该视觉的目的(供人工审计) |

---

## Claim routing table

每个 claim_id 的归属路由——这是 outline 完整性的"反向索引"。

```json
{
  "d1.c3": {
    "primary": "s1",
    "secondary": [
      { "section": "s5", "role": "supporting_context" }
    ]
  },
  "d2.c8": {
    "primary": "s2",
    "secondary": []
  }
}
```

| 字段 | 取值 | 说明 |
|---|---|---|
| key | claim_id (`^d\d+\.c\d+$`) | claim 唯一标识 |
| `primary` | section.id | 该 claim 详细展开的章节(全文唯一) |
| `secondary[]` | 数组 | 其他章节的简短引用,可空 |
| `secondary[i].section` | section.id | 引用所在章 |
| `secondary[i].role` | `supporting_context` / `reference_only` | secondary 只能短引用,不能承担主展开 |

**关键纪律**:
- 每个 claim 至多一个 primary。这保证详细展开只发生一次,避免重复。
- secondary 不能指向 primary 同一章节。
- secondary 不能使用 `primary_support` / `quantifier` / `counter`,否则等于在多个章节重复展开。

---

## Scan summary

planner 第一步扫描的全局图谱。给后续阶段一个**可审计的依据**——为什么选这个范式、这种章节结构、这份视觉清单。

```json
{
  "totals": {
    "claims": 187,
    "sources": 92,
    "primary_ratio": 0.41
  },
  "topic_clusters": [
    {
      "tag": "cost_structure",
      "claim_count": 14,
      "dims": ["d1", "d3"],
      "polarity_mix": { "support": 11, "refute": 2, "neutral": 1 }
    }
  ],
  "conflicts": [
    {
      "tag": "ev_market_share_2024",
      "support_claims": ["d1.c3"],
      "refute_claims": ["d3.c7"],
      "severity": "high"
    }
  ],
  "key_entities": [
    { "name": "BYD", "appearances": 23, "primary_dims": ["d1", "d3"] }
  ],
  "timeline_density": [
    { "year": 2023, "claim_count": 18 },
    { "year": 2024, "claim_count": 41 }
  ],
  "gaps": [
    { "kq": "kq3", "issue": "无 primary source 支撑,均为媒体转载" }
  ],
  "reader_task_signal": {
    "panorama": 0.6,
    "comparison": 0.3,
    "evaluation": 0.1
  }
}
```

字段速查:

| 字段 | 说明 |
|---|---|
| `totals` | 总量统计 |
| `topic_clusters[]` | topic_tag 频次聚类,polarity_mix 用于检测偏向性 |
| `conflicts[]` | 同 tag 不同 polarity 的配对,severity ∈ {low, medium, high} |
| `key_entities[]` | 出现 ≥ 3 次的实体 |
| `timeline_density[]` | 时间窗证据分布,用于判断是否适合 timeline 范式 |
| `gaps[]` | 信息空白(kq 缺 primary、refute 空、时间窗稀疏等) |
| `reader_task_signal` | 6 范式的概率分布,planner 据此选 paradigm |

---

## evidence_subset.json(派生切片)

planner 顺手为每个 section 落盘一份切片,**writer 只读这一份**——硬隔离 outline 契约。

文件位置: `{report_dir}/sections/s{N}.evidence_subset.json`

```json
{
  "schema_version": "1.0",
  "section_id": "s2",
  "claims": [
    {
      "id": "d2.c3",
      "text": "BYD 2024 Q3 电池自产率 78%",
      "kind": "factual",
      "polarity": "neutral",
      "topic_tag": "vertical_integration",
      "narrative_role": "primary_support",
      "evidence": [
        {
          "source_id": "byd_ar_2024",
          "snippet": "BYD 2024 年三季度自产电池占电池总用量 78%",
          "quote_type": "direct"
        }
      ]
    }
  ],
  "sources": [
    {
      "id": "byd_ar_2024",
      "url": "https://www.byd.com/...",
      "title": "BYD 2024 三季报",
      "quality": "primary",
      "published_at": "2024-Q3"
    }
  ]
}
```

字段说明:
- `claims[i]` 比 evidence.json 的 claim 多一个 `narrative_role`(从 outline.claim_routing_table 同步)
- `sources[]` 只包含 claims 实际引用的 source(剔除无关)
- `claims[i].text` / `evidence[].snippet` 等字段必须**从 evidence.json 整段拷贝**,不可篡改

---

## 完整示例(精简版)

```json
{
  "schema_version": "1.0",
  "paradigm": { "main": "panorama", "secondary": "forecast" },
  "depth_level": "deep_analysis",

  "global_arc": "中国 EV 产业从政策驱动转入技术分层,头部 3 家形成寡头格局,2026-28 年关键变量在固态电池和欧美市场准入。",

  "L0_draft": {
    "headline": "中国 EV 寡头化 + 全球化双拐点",
    "key_findings": [
      "前三家 2024 合计份额 60%,集中度比 2022 升 11pp",
      "技术分层显著: 头部 2 家固态电池,腰部押注混动",
      "欧美关税与本地化建厂是 2026-28 关键变量"
    ],
    "abstract_visual": {
      "form": "distribution-chart",
      "data_refs": ["d1.c2", "d1.c4"]
    }
  },

  "style_contract": {
    "register": "research_brief",
    "voice": "neutral_analytical",
    "terminology": {
      "preferred": { "国产替代率": ["自给率", "本土化率"] }
    },
    "citation_style": "footnote"
  },

  "sections": [
    {
      "id": "s1",
      "title": "市场结构现状",
      "reader_question": "中国 EV 市场目前是什么形态?",
      "section_role": "context",
      "word_budget": 1200,
      "lead": "2024 年中国 EV 市场前三家厂商合计份额超过 60%,集中度比 2022 年再升 11pp。",
      "blocks": [
        {
          "id": "b1",
          "level": 3,
          "heading": "头部厂商份额集中",
          "thesis": "BYD 领跑,以 35% 份额拉开身位",
          "evidence_refs": [
            { "claim_id": "d1.c3", "role": "primary_support" },
            { "claim_id": "d1.c5", "role": "quantifier" }
          ],
          "writing_context_refs": []
        }
      ],
      "visuals": [
        {
          "position": "after_lead",
          "information_type": "part-to-whole-distribution",
          "form": "distribution-chart",
          "render": "mermaid-code",
          "data_refs": ["d1.c2", "d1.c4", "d1.c6"],
          "caption": "2024 中国 EV 市场份额分布",
          "purpose": "展示主要厂商份额构成",
          "replaces_words": 300
        }
      ],
      "evidence_subset": ["d1.c2", "d1.c3", "d1.c4", "d1.c5", "d1.c6"]
    }
  ],

  "visual_inventory": [
    { "section": "s1", "form": "distribution-chart", "purpose": "2024 市场份额分布" }
  ],

  "claim_routing_table": {
    "d1.c2": { "primary": "s1", "secondary": [] },
    "d1.c3": { "primary": "s1", "secondary": [] },
    "d1.c4": { "primary": "s1", "secondary": [] },
    "d1.c5": { "primary": "s1", "secondary": [] },
    "d1.c6": { "primary": "s1", "secondary": [] }
  },

  "scan_summary": {
    "totals": { "claims": 187, "sources": 92, "primary_ratio": 0.41 },
    "topic_clusters": [
      { "tag": "market_share", "claim_count": 14, "dims": ["d1"], "polarity_mix": { "support": 11, "refute": 2, "neutral": 1 } }
    ],
    "conflicts": [],
    "key_entities": [{ "name": "BYD", "appearances": 23, "primary_dims": ["d1", "d3"] }],
    "timeline_density": [],
    "gaps": [],
    "reader_task_signal": { "panorama": 0.7, "forecast": 0.3 }
  }
}
```

---

## 校验规则(validator 强制)

`severity: error` 的规则违反 = validator 返回 fail，outline.json 必须修复后重跑。`severity: warning` 只提示表达或规划异常，不阻塞流程。

### 顶层结构

- O001 `schema_version` = `"1.0"`
- O002 `paradigm.main` ∈ 6 种范式枚举
- O003 `paradigm.secondary` 是 `null` 或上述枚举
- O004 `paradigm.main !== paradigm.secondary`
- O005 `depth_level` ∈ {overview, deep_analysis, expert_level}
- O006 `global_arc` 40-120 字
- O007 `sections` 长度 ≥ 3
- O008 `sections[].id` 全 outline 唯一

### L0_draft

- O010 `L0_draft.headline` 8-30 字
- O011 `L0_draft.key_findings` 长度 3-5
- O012 每条 key_finding 20-60 字
- O013 `L0_draft.abstract_visual` 是 null,或其 `form` ∈ visual form 枚举

### Style contract

- O020 `register` ∈ 5 种枚举
- O021 `voice` ∈ 4 种枚举
- O022 `citation_style` ∈ {footnote, inline}
- O023 `terminology.preferred` 是 dict,key/value 都非空字符串

### Section

- O030 `section.id` 匹配 `^s\d+$`
- O031 `title` 4-30 字
- O032 `reader_question` 10-80 字,且以 `?` 或 `？` 结尾
- O033 `section_role` ∈ 8 种枚举
- O034 `word_budget` 是 200-3000 之间整数
- O035 `lead` 30-150 字
- O036 `blocks` 长度 1-10
- O037 `visuals` 长度 0-3
- O038 `evidence_subset` 是 claim_id 数组,长度 ≥ 1
- O039 `evidence_subset` 中 claim_id 全唯一(同一节内不重复)
- O045 `evidence_subset` 必须精确等于该节 `blocks[].evidence_refs[].claim_id` ∪ `visuals[].data_refs[]`

### Block

- O040 `id` 匹配 `^b\d+$`,同一 section 内唯一;`level` 是 3 或 4;`heading` 4-80 字;`thesis` 10-160 字
- O041 `evidence_refs` 长度 1-10
- O042 每个 evidence_ref.claim_id 匹配 `^d\d+\.c\d+$`
- O043 每个 evidence_ref.role ∈ 5 种 narrative_role 枚举
- O044 evidence_ref.claim_id 必须出现在该 section.evidence_subset;`writing_context_refs` 如存在,必须是 `dN.wM` 数组

### Visual

- O050 `position` ∈ {after_lead, mid, before_close}
- O051 `form` ∈ visual form 枚举
- O052 `data_refs` 是 claim_id 数组;除 `concept-illustration` 外长度 ≥ 1
- O053 `caption` 5-50 字
- O054 `replaces_words` 是非负整数
- O055 visual.data_refs 中每个 claim_id 必须出现在该 section.evidence_subset
- O056 `render` ∈ render 枚举,且必须与 `form` 匹配
- O057 `information_type` ∈ information_type 枚举,且必须与 `form` 匹配;`purpose` 必填;`prompt_hint` / `image_ref` 满足字段约束

### Transitions(可选遗留字段)

- O060 如果 `transitions.from_prev` 存在,必须是 null 或 15-80 字
- O061 如果 `transitions.to_next` 存在,必须是 null 或 15-80 字

### Visual inventory

- O070 `visual_inventory[i].section` 必须存在于 sections
- O071 `visual_inventory[i].form` ∈ visual form 枚举
- O072 `visual_inventory[i].purpose` 5-30 字
- O073 visual_inventory **必须与 sections[].visuals 完全一致**(扁平化后,数量相同、对应关系一致)

### Claim routing table(关键纪律)

- O080 routing_table 的 key 匹配 `^d\d+\.c\d+$`
- O081 每个 entry.primary 必须存在于 sections
- O082 每个 entry.secondary[i].section 必须存在于 sections
- O083 entry.secondary[i].role ∈ 5 种 narrative_role 枚举
- O084 同一 claim_id 至多 1 个 primary(详细展开只发生一次)
- O085 entry.secondary[i].role 只能是 `supporting_context` 或 `reference_only`
- O086 entry.secondary 不能指向 primary 同一章节,且同一 secondary section 不重复

### 跨结构完整性

- O090 sections 中所有 evidence_subset 引用的 claim_id 必须出现在 claim_routing_table
- O091 反过来:claim_routing_table 中 entry.primary === section.id 时,该 claim_id 必须出现在 section.evidence_subset
- O092 entry.secondary[i].section === some_section.id 时,该 claim_id 必须出现在 some_section.evidence_subset
- O093 claim_routing_table 中 primary/secondary 所指章节必须与该 claim 在该 section 的实际使用位置一致
- O094 视觉密度软约束(warning,不阻塞):`sum(word_budget) / 1000 ≤ total_visuals + 1`

### Scan summary

- O100 `totals.claims` 是非负整数
- O101 `totals.primary_ratio` ∈ [0, 1]
- O102 `topic_clusters[i].polarity_mix` 三态求和等于 `topic_clusters[i].claim_count`
- O103 `conflicts[i].severity` ∈ {low, medium, high}
- O104 `reader_task_signal` 各值 ∈ [0, 1],总和接近 1.0(±0.05)

---

## evidence_subset.json 校验规则

### 顶层

- S001 `schema_version` = `"1.0"`
- S002 `section_id` 匹配 `^s\d+$`
- S003 `section_id` 必须存在于对应 outline.sections

### 与 outline 一致性

- S010 evidence_subset.claims[].id 集合 必须等于 outline.sections[where id===section_id].evidence_subset
- S011 evidence_subset.sources[].id 必须覆盖所有 claims[].evidence[].source_id
- S012 claims[i] 的 text / kind / polarity / topic_tag / evidence 必须**从原 d{N}.evidence.json 整段拷贝**——不可篡改
- S013 `narrative_role` ∈ 5 种枚举
- S014 `narrative_role` 必须与 outline.claim_routing_table 中该 claim 关于此 section 的 role 一致(primary 或某个 secondary 的 role)

---

## 设计决策(速查)

| 你可能想加 | 为什么没加 |
|---|---|
| `section.summary`(章节摘要) | `lead` 字段已经是这个,另起会冗余 |
| `claim.confidence` 透传到 outline | 已在 evidence.json,outline 不重复 |
| `section.depends_on`(章节依赖图) | sections 数组顺序就是隐式依赖,显式 DAG 是过度设计 |
| `paradigm` 多于 2 个 | 三主范式以上就该拆成两份报告 |
| `style_contract.tone_examples`(范例片段) | 给 sonnet 看几个例子有用,但写在 SKILL.md / agent prompt 即可 |
| `visual.mermaid_code`(直接出代码) | mermaid 是 writer 阶段才需要的 detail,outline 只决定 form |
| `quality_gates`(自校验阈值) | gate 是 validator 的责任,不进 schema |
| `section.dependencies`(claim 复用提示) | claim_routing_table 已表达,冗余 |
| `outline.version` / `outline.created_at` | 文件 mtime 可推 |

**字段设计原则**:outline 的字段必须有明确下游消费者(writer / stitcher / render),且必须是 planner 可以负责任地填的。冗余字段是永久维护成本。

---

## 与现有 schema 的关系

```
evidence.schema.md (research 阶段产出)
        │
        │ planner 读取 + 抽取 claim 子集
        ▼
outline.schema.md (本文档,报告阶段契约)
        │
        ├── outline.json (主契约)
        └── sections/s{N}.evidence_subset.json (派生切片)
                │
                ▼
           writer 只读自己的切片
                │
                ▼
        sections/s{N}.md (章节草稿)
                │
                ▼
        stitched.md (stitcher 缝合)
                │
                ▼
        report.md (sn-prepare-citations 渲染)
```
