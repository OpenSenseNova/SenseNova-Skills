# Evidence Schema v1.1

研究产出的**唯一真相来源**（single source of truth）。每个研究维度产出一份 `evidence.json`。

下游消费者：
- `validate_evidence.py` — 强制校验
- `review` agent — 子报告级审查
- **下游研究维度**（`depends_on` 指向本维度的后续 dim）— 读 `key_findings` 取上游结论形状，按 `topic_tag` 过滤具体 claim 作为分析输入
- `report-planner` agent — 编排时用 `key_findings` 作显著性/路由线索
- `report` agent — 综合终稿（直接消费 claims + sources）
- `prepare_citations.py` — 最终编号
- `lint_citations.py`（未来）— 引用纪律检查
- `scan_contradictions.py`（未来）— 跨维度矛盾检测

> **v1.1 变更**：新增顶层 `key_findings`（综合层）——把扁平 claim 袋升级为带显著性的结论形状，专供下游研究维度和 report-planner 廉价消费，不放弃原子 claim。

## 文件位置

```
{report_dir}/sub_reports/{dimension_id}.evidence.json
```

例如 `d1.evidence.json`、`d3.evidence.json`。

## 顶层结构

```json
{
  "schema_version": "1.1",
  "mode": "initial",
  "dimension_id": "d1",
  "headline": "中国半导体设备 2024 年国产替代率约 12%，先进制程仍 < 5%",
  "key_findings": [ ... ],
  "claims": [ ... ],
  "sources": [ ... ]
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `schema_version` | string | 固定为 `"1.1"`。改 schema 必升版。 |
| `mode` | string? | 可选。`initial` / `quick` / `supplement`。标记本 evidence 的研究模式：`quick` 会放宽 V040/V041（tertiary 来源即可满足 factual/interpretive 门槛），用于查证型任务避免为凑来源门槛去抓付费墙/404 源。未填按 `initial` 严格档处理。 |
| `dimension_id` | string | 形如 `d1`、`d2`。必须与 plan.json 中 dimension id 对应。 |
| `headline` | string | 5-200 字。一句话总结本维度核心结论。 |
| `key_findings` | array | 2-6 条综合发现。承载性主张 + 指向支撑 claim 的 `claim_ids`。供下游廉价消费。 |
| `claims` | array | ≥ 1 条 claim。研究的全部断言都在这里。 |
| `sources` | array | ≥ 1 条 source。本维度引用的全部来源。 |

## Key Findings（综合层）

`headline` 太薄（一句话），扁平的 `claims[]` 又丢了"哪些断言抱团、哪个是头条"的形状。`key_findings` 补上这一层：2-6 条**承载性结论**，每条指回支撑它的 `claim_ids`。

**谁消费它：**
- **下游研究维度**（`depends_on` 指向本 dim 的后续 dim）——先读 `key_findings` 取上游结论形状，再按需顺着 `claim_ids` / `topic_tag` 深入具体 claim，避免把整袋 claim 全部读进上下文
- **report-planner**——SCAN 阶段用它判断显著性、起草 `L0_draft`、做 claim 路由

```json
{
  "finding": "国产替代在成熟制程已基本完成，但先进制程（14nm 以下）国产化率不足 5%，是结构性短板",
  "claim_ids": ["d1.c1", "d1.c2"]
}
```

| 字段 | 取值 | 说明 |
|---|---|---|
| `finding` | 10-300 字 | **承载性主张**——完整句，带方向（数字/比较/趋势）。不是话题（"国产替代概况"❌），不是单 claim 的复述，而是对一组 claim 的综合。 |
| `claim_ids` | 非空数组 | 支撑该 finding 的 claim id 列表。每个 id **必须存在于本文件 `claims[]`**（同 dim 内引用，不跨文件）。 |

**写作纪律：**
- `key_findings` 是 `claims[]` 的**派生综合**，不引入 claims 里没有的新事实——每条 finding 都要能落到具体 claim_ids 上
- 覆盖本维度最重要的结论即可（2-6 条），不是 claim 的全量目录
- 至少应反映 headline 的核心，并把 headline 装不下的关键张力（如 refute 方向、结构性矛盾）显式拎出来

## Claim

每条 claim 是一个可被验证的断言。

```json
{
  "id": "d1.c1",
  "text": "中国 2024 年半导体设备国产替代率约 12%",
  "kind": "factual",
  "polarity": "neutral",
  "topic_tag": "domestic_substitution_rate",
  "answers_key_question": "kq2",
  "evidence": [
    {
      "source_id": "semi_industry_2024",
      "snippet": "2024 年中国半导体设备国产化率达到 11.7%，较 2023 年提升 2.3 个百分点",
      "quote_type": "direct"
    }
  ]
}
```

| 字段 | 取值 | 说明 |
|---|---|---|
| `id` | `^d\d+\.c\d+$` | 形如 `d1.c1`。c 编号从 1 递增。**全局唯一**——下游用它做跨文件引用。 |
| `text` | 5-500 字 | 断言本身。**应是一个完整可验证的陈述**，不是段落标题、不是转述。 |
| `kind` | `factual` / `interpretive` / `projective` | 见下表。**禁止规范性**（"应该"/"必须"）。 |
| `polarity` | `support` / `refute` / `neutral` | 立场。用于跨维度矛盾检测。 |
| `topic_tag` | `^[a-z][a-z0-9_]{0,29}$` | 主题 tag。**优先复用已有 tag**——只在确实没有合适 tag 时新建。 |
| `answers_key_question` | `^kq\d+$` 或 `null` | 关联的 key_question id。计划外发现用 `null`（即"额外发现"）。 |
| `evidence` | array | ≥ 1 条 evidence。见下方 evidence 规则。 |

### Claim kind 三态

| kind | 定义 | 示例 | 引用要求 |
|---|---|---|---|
| `factual` | 可被独立验证的事实（数字、事件、状态） | "Tesla Q4 营收 257 亿美元" | ≥ 1 evidence，**至少 1 个 source 是 primary 或 secondary** |
| `interpretive` | 基于证据的解释、分析、归因 | "Tesla 利润率受价格战影响" | ≥ 2 evidence，且来自**不同 source** |
| `projective` | 关于未来的推断、预测、外推 | "中国 7nm 量产预计 2027 年规模化" | ≥ 1 evidence + claim text 内说明前提 |

**`normative`（规范性）claim 直接禁止**——研究报告陈述事实和分析，不做"应该如何"的主张。validator 会拒绝任何 `kind: normative`。

### Polarity 三态

| polarity | 何时用 |
|---|---|
| `support` | 该 claim 支持 key_question 的某个肯定方向（"X 是可行的因为 ..."） |
| `refute` | 该 claim 反驳常见假设或支持否定方向（"X 不可行因为 ..."） |
| `neutral` | 描述性陈述，无明确立场（占大多数 factual claim） |

`refute` 必须主动产出——只有 `support` 和 `neutral` = 偏向性研究，质量不合格。

## Evidence

每条 evidence 是 claim 的一个证据点。

```json
{
  "source_id": "semi_industry_2024",
  "snippet": "2024 年中国半导体设备国产化率达到 11.7%...",
  "quote_type": "direct"
}
```

| 字段 | 取值 | 说明 |
|---|---|---|
| `source_id` | string | 必须在本文件 `sources[]` 里出现。 |
| `snippet` | non-empty string | **源文里的实际语句**。direct = 逐字、paraphrase = 改写但忠于原意、numeric = 数据点。**不允许凭印象编造**。 |
| `quote_type` | `direct` / `paraphrase` / `numeric` | direct 引用未来会被 verbatim 校验工具抽查（症状 B 防线）。 |

## Source

```json
{
  "id": "semi_industry_2024",
  "url": "https://www.semi.org.cn/...",
  "title": "中国半导体行业 2024 年度报告",
  "quality": "primary",
  "published_at": "2024-12"
}
```

| 字段 | 取值 | 说明 |
|---|---|---|
| `id` | `^[a-z][a-z0-9_]*$` | 跨维度复用——同一 URL 应该用同一个 id。命名建议：`{publisher}_{topic}_{year}`。 |
| `url` | http(s) | 必须是完整可访问的 URL。 |
| `title` | non-empty string | 来源标题。 |
| `quality` | `primary` / `secondary` / `tertiary` | 见下表。 |
| `published_at` | `YYYY` / `YYYY-MM` / `YYYY-MM-DD` 或 omit | 原文发表时间。**对时效敏感的研究必填**，不可考则省略。 |

### Source quality 三档

| quality | 定义 | 示例 |
|---|---|---|
| `primary` | 一手材料：原始数据、官方公告、SEC 申报、政府统计、原始论文 | 财报、白皮书、政府数据库、arXiv 原文 |
| `secondary` | 二手报道/分析：基于一手材料的报道或专业分析 | Reuters / Bloomberg / FT、行业分析师报告 |
| `tertiary` | 三手综合：综述、维基、二次转载、聚合内容 | 维基百科、Substack 综述、聚合新闻 |

## 完整示例

```json
{
  "schema_version": "1.1",
  "dimension_id": "d1",
  "headline": "中国半导体设备 2024 年国产替代率约 12%，但先进制程仍依赖海外，国产替代速度受美方管制影响",
  "key_findings": [
    {
      "finding": "2024 年国产替代率约 11.7%，同比提升 2.3 个百分点，整体仍处低位",
      "claim_ids": ["d1.c1"]
    },
    {
      "finding": "替代呈结构性分化：成熟制程国产化率超 70%，14nm 以下先进制程不足 5%",
      "claim_ids": ["d1.c2"]
    }
  ],
  "claims": [
    {
      "id": "d1.c1",
      "text": "中国 2024 年半导体设备国产替代率约 11.7%，较 2023 年提升 2.3 个百分点",
      "kind": "factual",
      "polarity": "neutral",
      "topic_tag": "domestic_substitution_rate",
      "answers_key_question": "kq1",
      "evidence": [
        {
          "source_id": "semi_industry_2024",
          "snippet": "2024 年中国半导体设备国产化率达到 11.7%，较 2023 年提升 2.3 个百分点",
          "quote_type": "direct"
        }
      ]
    },
    {
      "id": "d1.c2",
      "text": "国产替代在成熟制程（28nm 以上）已基本实现，但 14nm 以下先进制程国产化率不足 5%",
      "kind": "interpretive",
      "polarity": "neutral",
      "topic_tag": "advanced_node_substitution",
      "answers_key_question": "kq1",
      "evidence": [
        {
          "source_id": "semi_industry_2024",
          "snippet": "成熟制程国产化率超过 70%，14nm 以下不足 5%",
          "quote_type": "direct"
        },
        {
          "source_id": "ft_china_chip_2024",
          "snippet": "China's mature node fabs are domestically supplied, but advanced nodes remain dependent on foreign equipment",
          "quote_type": "paraphrase"
        }
      ]
    }
  ],
  "sources": [
    {
      "id": "semi_industry_2024",
      "url": "https://www.semi.org.cn/report/2024",
      "title": "中国半导体行业 2024 年度报告",
      "quality": "primary",
      "published_at": "2024-12"
    },
    {
      "id": "ft_china_chip_2024",
      "url": "https://www.ft.com/content/china-chip-2024",
      "title": "China's chip industry: domestic substitution drive",
      "quality": "secondary",
      "published_at": "2024-11"
    }
  ]
}
```

## 校验规则（validator 强制）

每条规则违反 = validator 返回 fail，evidence.json 必须修复后重跑。

### 结构

- V001 `schema_version` 必须是 `"1.1"`
- V002 `dimension_id` 必须匹配 `^d\d+$`
- V003 `headline` 5-200 字
- V004 `claims` 是非空数组
- V005 `sources` 是非空数组
- V006 `key_findings` 是 2-6 项的数组

### Source

- V010 sources[i] 是 object
- V011 `source.id` 匹配 `^[a-z][a-z0-9_]*$`
- V012 source id 唯一（不重复）
- V013 `source.url` 非空字符串
- V014 `source.url` 是 http(s) URL，host 非空
- V015 `source.title` 非空
- V016 `source.quality` ∈ {primary, secondary, tertiary}
- V017 `source.published_at` 形如 `YYYY[-MM[-DD]]`（如果存在）
- V018 `mode` 若存在必须 ∈ {initial, quick, supplement}

### Claim

- V020 claims[i] 是 object
- V021 `claim.id` 匹配 `^d\d+\.c\d+$`
- V022 claim id 唯一
- V023 `claim.id` 必须以 `{dimension_id}.` 开头
- V024 `claim.text` 5-500 字
- V025 `claim.kind` ∈ {factual, interpretive, projective}
- V026 `claim.polarity` ∈ {support, refute, neutral}
- V027 `claim.topic_tag` 匹配 `^[a-z][a-z0-9_]{0,29}$`
- V028 `claim.answers_key_question` 是 `null` 或匹配 `^kq\d+$`
- V029 `claim.evidence` 是非空数组

### Evidence

- V030 evidence[j] 是 object
- V031 `evidence.source_id` 必须在本文件 `sources[]` 中存在
- V032 `evidence.snippet` 非空
- V033 `evidence.quote_type` ∈ {direct, paraphrase, numeric}

### Kind-specific（最关键的纪律）

- V040 `factual` claim 的 evidence 至少 1 条 source quality 是 `primary` 或 `secondary`（`mode: quick` 下放宽：tertiary 亦可，避免查证型任务为凑门槛去抓不可访问源）
- V041 `interpretive` claim 至少 2 条 evidence，且来自**不同 source**（`mode: quick` 下放宽为 ≥1 条）

### Key Findings

- V050 key_findings[i] 是 object
- V051 `key_findings[i].finding` 是 10-300 字字符串
- V052 `key_findings[i].claim_ids` 是非空数组
- V053 `key_findings[i].claim_ids[j]` 必须是字符串且存在于本文件 `claims[]` 中

## 设计决策（速查）

| 你可能想加 | 为什么没加 |
|---|---|
| `claim.confidence` (high/medium/low) | LLM 自评 confidence 几乎全标 high，信号噪比太低 |
| `narrative_arc` (论证骨架) | 这是**报告级**叙事，report agent 自己组织；`key_findings` 不同——它是**维度级**综合，下游研究维度和 planner 是明确消费者，故 v1.1 收入 |
| `claim.extracted_at` / `generated_at` | 文件 mtime 可推 |
| `extra_findings` 独立列表 | `claims[]` 中 `answers_key_question: null` 即可表达 |
| `key_question_coverage` 反向索引 | 完全可从 `answers_key_question` 推导，冗余 = bug 入口 |
| `source.publisher` | 80% 可从 URL host 推 |
| `data_visualizations` | 图表是 report 阶段的全局决策，dim 级别画图浪费 |
| `source.fetched_at` | 当前无缓存层，无消费者 |

**第一性原理**：字段必须有明确下游消费者，否则不进 schema。冗余字段是永久维护成本。
