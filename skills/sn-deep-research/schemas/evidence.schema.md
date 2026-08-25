# 证据字段契约

`evidence.json` 的字段与引用完整性契约。每个研究维度产出一份文件。

## 文件位置

```
{report_dir}/sub_reports/{dimension_id}.evidence.json
```

例如 `d1.evidence.json`、`d3.evidence.json`。

## 顶层结构

```json
{
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
| `mode` | 可选字符串 | `initial` / `quick` / `supplement`。|
| `dimension_id` | 字符串 | 形如 `d1`、`d2`。必须与 `plan.json` 中的维度 ID 对应。 |
| `headline` | 字符串 | 非空。一句话总结本维度核心结论。 |
| `key_findings` | 数组 | 非空；数量由真实结论决定，禁止用流程元信息凑数。每项包含承载性主张和支撑它的 `claim_ids`。 |
| `claims` | 数组 | 至少 1 条断言。研究的全部断言都在这里。 |
| `sources` | 数组 | 至少 1 条来源。本维度引用的全部来源。 |
| `writing_context` | 可选数组 | 可选。保存口径、方法、范围或可得性边界等辅助研究结果表述的信息。 |

## `key_findings`（综合层）

`key_findings` 是 `claims[]` 的维度级综合；每条综合结论通过 `claim_ids` 指回支撑它的断言。

```json
{
  "finding": "国产替代在成熟制程已基本完成，但先进制程（14nm 以下）国产化率不足 5%，是结构性短板",
  "claim_ids": ["d1.c1", "d1.c2"]
}
```

| 字段 | 取值 | 说明 |
|---|---|---|
| `finding` | 非空字符串 | **承载性主张**——完整句，带方向（数字/比较/趋势）。|
| `claim_ids` | 非空数组 | 支撑该综合结论的断言 ID 列表。每个 ID **必须存在于本文件 `claims[]`**。 |

## 断言（`claims[]`）

每条 `claim` 都是一个可被验证的断言。

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
| `id` | `^d\d+\.c\d+$` | 形如 `d1.c1`，必须属于当前维度，且在本文件内唯一。 |
| `text` | 非空字符串 | 断言本身。**应是一个完整可验证的陈述**，不是段落标题、不是转述。 |
| `kind` | `factual` / `interpretive` / `projective` | 见下表。 |
| `polarity` | `support` / `refute` / `neutral` | 立场。用于跨维度矛盾检测。 |
| `topic_tag` | `^[a-z][a-z0-9_]*$` | 主题标签。 |
| `answers_key_question` | `^kq\d+$` 或 `null` | 关联的关键问题 ID。计划外发现使用 `null`（即“额外发现”）。 |
| `evidence` | 数组 | 至少 1 条证据。见下方证据规则。 |

### 断言类型三态

| 类型 | 定义 | 示例 | 引用要求 |
|---|---|---|---|
| `factual` | 可被独立验证的事实（数字、事件、状态） | “Tesla 第四季度营收 257 亿美元” | 至少 1 条证据 |
| `interpretive` | 基于证据的解释、分析、归因 | “Tesla 利润率受价格战影响” | 至少 1 条证据 |
| `projective` | 关于未来的推断、预测、外推 | “中国 7nm 量产预计 2027 年规模化” | 至少 1 条证据 |

### 立场三态

| 立场 | 使用场景 |
|---|---|
| `support` | 该断言支持关键问题的某个肯定方向（“X 是可行的，因为……”） |
| `refute` | 该断言反驳常见假设或支持否定方向（“X 不可行，因为……”） |
| `neutral` | 描述性陈述，无明确立场（大多数事实型断言属于此类） |

## 证据项（`evidence[]`）

每条 `evidence` 都是某条断言的一个证据点。

```json
{
  "source_id": "semi_industry_2024",
  "snippet": "2024 年中国半导体设备国产化率达到 11.7%...",
  "quote_type": "direct"
}
```

| 字段 | 取值 | 说明 |
|---|---|---|
| `source_id` | 字符串 | 必须在本文件 `sources[]` 里出现。 |
| `snippet` | 非空字符串 | 支撑断言的证据文本。`direct` 表示连续原文，`paraphrase` 表示忠于原意的改写或组合摘要，`numeric` 表示带口径的数据点。**不允许凭印象编造**。 |
| `quote_type` | `direct` / `paraphrase` / `numeric` | 只有逐字复制连续原文时使用 `direct`；组合多个位置的信息必须使用 `paraphrase`；抽取数字及其必要口径时使用 `numeric`。 |

## 来源（`sources[]`）

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
| `id` | `^[a-z][a-z0-9_]*$` | 本文件内唯一。 |
| `url` | http(s) | 合法的完整 URL。 |
| `title` | 非空字符串 | 来源标题。 |
| `quality` | `primary` / `secondary` / `tertiary` | 见下表。 |
| `published_at` | `YYYY` / `YYYY-MM` / `YYYY-MM-DD` 或省略 | 原文发表时间。 |

### 来源质量三档

| 质量 | 定义 | 示例 |
|---|---|---|
| `primary` | 一手材料：原始数据、官方公告、SEC 申报、政府统计、原始论文 | 财报、白皮书、政府数据库、arXiv 原文 |
| `secondary` | 二手报道/分析：基于一手材料的报道或专业分析 | Reuters / Bloomberg / FT、行业分析师报告 |
| `tertiary` | 三手综合：综述、维基、二次转载、聚合内容 | 维基百科、Substack 综述、聚合新闻 |

## `writing_context`（写作上下文）

`writing_context[]` 保存不属于断言的口径、方法、范围和可得性边界。每项结构：

```json
{
  "id": "d1.w1",
  "kind": "availability_gap",
  "text": "公开资料未披露 2024 年按地区拆分的数据，当前无法确认该口径。",
  "source_ids": ["official_report"],
  "applies_to": ["kq2"],
  "use": "在对应检查项中标为证据不足，不推断地区差异。"
}
```

- `id` 匹配 `^d\d+\.w\d+$`，属于当前维度，且在本文件内唯一。
- `kind` 取 `source_profile|methodology|scope_boundary|availability_gap|unresolved_gap`。
- `text` 是非空的实际边界，`use` 是非空的成品使用约束；两者均不设置字符数限制。
- `source_ids` 是 `sources[]` ID 的去重子集，可为空；`applies_to` 是去重 `kqN` 数组，可为空。
- 只写 `{id}` 的空对象不合格。

## 完整示例

```json
{
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
