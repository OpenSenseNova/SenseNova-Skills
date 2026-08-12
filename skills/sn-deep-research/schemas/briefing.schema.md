# 预研简报字段契约

`{report_dir}/briefing.json` 是 `heavy` 模式下由 `scout` 智能体产出的初步领域地图。

除本文档明确列出的字段外，不得自行扩展字段。

## 顶层结构

```json
{
  "user_confirmations_needed": {},
  "task_interpretation": {},
  "context_entities": [],
  "terminology": [],
  "subdomain_partitions": {},
  "knowledge_topology": {},
  "information_landscape": {},
  "critical_unknowns": [],
  "candidate_lenses": [],
  "coverage_boundary": {},
  "hypotheses_to_test": [],
  "risk_flags": []
}
```

以上 12 个顶层字段全部必填。

## `user_confirmations_needed`

```json
{
  "blocking": [],
  "high_value": [],
  "optional": []
}
```

- `blocking` 最多 3 条；`default_if_unanswered` 必须为 `null`。
- `high_value` 与 `optional` 必须提供默认选项。
- 每条问题必须有 2–4 个 `options[]`。
- 问题 ID 在三个数组之间全局唯一。
- `default_if_unanswered.option_id` 必须引用同一问题的某个 `options[].id`。

通用问题字段：

| 字段 | 类型 | 必填 |
|---|---|---|
| `id` | 稳定标识符 | 是 |
| `question` | 非空字符串 | 是 |
| `uncertainty_type` | 枚举 | 是 |
| `why_it_matters` | 非空字符串 | 是 |
| `impact_on_plan` | 非空字符串 | `blocking` / `high_value` 必填，`optional` 可选 |
| `options` | 对象数组 | 是，2–4 条 |
| `default_if_unanswered` | 对象 / `null` | 是 |

`uncertainty_type`：

```text
goal, scope, criteria, constraint, audience, time_range, assumption
```

每个选项：

```json
{
  "id": "stable_option_id",
  "label": "选项名称",
  "planning_implication": "选择该项对后续规划的影响"
}
```

`high_value.default_if_unanswered`：

```json
{
  "option_id": "某个 options[].id",
  "rationale": "采用该默认项的理由",
  "confidence": "low|medium|high"
}
```

`optional.default_if_unanswered`：

```json
{
  "option_id": "某个 options[].id",
  "rationale": "采用该默认项的理由"
}
```

## `task_interpretation`

```json
{
  "user_goal": "用户真正要完成什么",
  "requested_output_inferred": "用户要求的交付物",
  "research_type_inferred": "academic",
  "audience_inferred": "预期读者",
  "time_focus": "current",
  "explicit_constraints": [],
  "implicit_scope_hints": []
}
```

`research_type_inferred`：

```text
academic, commercial, financial, medical, legal, trending,
tech_evaluation, profile
```

`time_focus`：

```text
historical, current, forward, full_span
```

## `context_entities`

至少 5 条，实体名称不得重复。

```json
{
  "name": "实体名称",
  "type": "company",
  "explicit_or_inferred": "explicit",
  "why_it_matters": "与研究问题的关系",
  "confidence": "high"
}
```

`type`：

```text
company, technology, person, product, concept, policy, event, location
```

`explicit_or_inferred`：`explicit` / `inferred`。

`confidence`：`low` / `medium` / `high`。

## `terminology`

只记录确有歧义的术语；无则使用空数组。术语不得重复。

```json
{
  "term": "术语",
  "aliases": ["别名"],
  "note": "需要澄清的歧义"
}
```

## `subdomain_partitions`

```json
{
  "partition_basis": "by_topic",
  "subdomains": [
    {
      "name": "实质子领域",
      "scope_hint": "该子领域覆盖的内容"
    }
  ]
}
```

- `subdomains` 至少 3 条，名称不得重复。
- `partition_basis`：

```text
by_topic, by_value_chain, by_methodology, by_stakeholder,
by_timeline, other
```

## `knowledge_topology`

```json
{
  "consensus": [
    {
      "fact": "已发现的对象实质共识方向",
      "source_hint": "对应来源线索"
    }
  ],
  "disputes": [
    {
      "issue": "对象本身的分歧，或明确说明未发现显著分歧",
      "positions_exist": ["立场 A", "立场 B"],
      "representative_sources": ["来源线索"]
    }
  ],
  "blanks": [
    {
      "blank": "实质信息空白",
      "blank_nature": "info_scarce"
    }
  ]
}
```

- `consensus` 至少 2 条。
- `disputes` 至少 1 条；未发现显著争议时也要显式记录。
- `blanks` 可为空。
- `blank_nature`：

```text
info_scarce, paywall, language_barrier, geo_restricted,
too_recent, proprietary
```

## `information_landscape`

```json
{
  "primary_source_categories": [],
  "secondary_source_categories": [],
  "data_source_categories": [],
  "expert_or_industry_sources": [],
  "weak_or_risky_sources": [],
  "high_value_urls": [
    {
      "url": "https://example.com",
      "category": "official",
      "why": "该入口的规划价值"
    }
  ],
  "search_terms": [
    {
      "term": "检索词",
      "language": "zh-Hans",
      "use_case": "用于发现什么规划变量"
    }
  ],
  "time_sensitivity": {
    "rate": "fast_changing",
    "recommended_window": "推荐时间窗口",
    "reason": "为什么采用该窗口"
  },
  "access_barriers": [
    {
      "barrier": "paywall",
      "affected_sources": "受影响的来源",
      "workaround_hint": "后续研究可采用的替代入口"
    }
  ]
}
```

- `high_value_urls[].url` 必须是普通 HTTP(S) URL，不得包含用户凭据。
- `high_value_urls` 至少覆盖 3 个不同类别。
- URL 类别：

```text
official, news, academic, data, forum, analyst, review
```

- `time_sensitivity.rate`：

```text
fast_changing, moderate, slow
```

- `access_barriers[].barrier`：

```text
paywall, language, geo, login_required, rate_limited
```

## `critical_unknowns`

可为空。每条结构：

```json
{
  "unknown": "未知事实、机制、分布、影响或边界",
  "why_it_matters": "为什么影响规划",
  "evidence_needed": "后续 Research 需要什么证据",
  "can_be_resolved_by_research": true,
  "importance": "high"
}
```

`can_be_resolved_by_research` 必须为 `true`；不能靠研究解决的口径分歧应进入 `user_confirmations_needed`。

## `candidate_lenses`

至少 3 个差异化观察位置，视角名称不得重复。

```json
{
  "lens": "观察位置",
  "useful_for": "能看到对象的什么内容面",
  "may_miss": "该视角可能遗漏什么",
  "binding_strength": "suggestive"
}
```

`binding_strength` 必须为 `suggestive`。

## `coverage_boundary`

```json
{
  "adjacent_fields_not_explored": [],
  "opposing_perspectives_not_searched": [],
  "second_order_effects_not_explored": [],
  "alternative_paths_not_explored": [],
  "scan_scope": {
    "zoom_level": "domain",
    "scanned_angles": ["已扫描方向"],
    "unscanned_angles": ["未扫描方向"]
  },
  "lists_known_partial": {
    "entities": {
      "more_likely_in": []
    },
    "subdomains": {
      "alternative_partitions_exist": []
    },
    "terminology": {
      "jargon_pockets_not_covered": []
    },
    "unknowns": {
      "research_will_surface_more": true
    },
    "disputes": {
      "more_likely_in": []
    },
    "risks": {
      "more_likely_in": []
    }
  }
}
```

- 四个方向数组必须显式存在，可为空。
- `scan_scope.scanned_angles` 与 `unscanned_angles` 均至少一条。
- `zoom_level`：`broad` / `domain` / `subdomain` / `niche`。
- `lists_known_partial` 六个子对象全部必填。

## `hypotheses_to_test`

最多 3 条；无初步假设时使用空数组。

```json
{
  "claim": "待检验假设",
  "basis": "形成该假设的依据",
  "confidence": "medium",
  "disconfirming_evidence": "什么证据会推翻它"
}
```

## `risk_flags`

必须逐项记录以下 10 类风险的扫描结果；未发现实质风险时可使用 `severity: low` 并在说明中如实记录。

```text
时效性, 来源偏见, 口径不一致, 数据过时, 地区差异,
法规不确定, 营销话术, 缺一手证据, 幸存者偏差, benchmark不可比
```

每条结构：

```json
{
  "risk": "时效性",
  "why_it_matters": "该风险如何影响后续规划",
  "mitigation": "后续 Research 的处理方式",
  "severity": "low"
}
```

风险类型不得重复，`severity` 使用 `low` / `medium` / `high`。

## 校验规则

`validate_briefing.py` 强制：

1. 顶层和嵌套必填字段、类型、枚举合法，拒绝未知字段。
2. 问题、选项、实体、术语、子领域、视角和风险类型满足唯一性要求。
3. 确认项的默认选项引用合法，`blocking` 不超过 3 条。
4. 完成阈值中的结构数量要求满足。
5. URL、布尔值和跨字段状态关系合法。
6. 自然语言字段必须非空，但不按固定字符数判定失败。
