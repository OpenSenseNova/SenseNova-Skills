---
name: report-format-discovery
description: 从权威源发现特定领域/类型的报告格式标准：通过锚点注册表定位元权威入口，动态导航到具体领域的报告规范和真实范例，提取结构化的 Report Blueprint。覆盖学术研究和行业研究两大领域。
---

# report-format-discovery（报告格式发现）

在规划研究维度之前，先搞清楚目标报告应该长什么样。本 skill 提供"如何发现报告格式标准"的方法论，而非固定模板。

## 核心原则

1. **报告格式是可研究的问题**——标准的制定者是确定的，可以被搜索和验证
2. **固定入口，动态导航**——写死的是"去哪里找"（锚点），动态的是"找什么"（具体领域标准）
3. **区分标准指南和真实范例**——指南告诉你"应该怎么写"，范例告诉你"实际长什么样"，两者互补

## 工作流程

```
Step 1: 从 briefing 识别 → 领域 + 报告类型 + 受众
Step 2: 选择锚点策略（学术 or 行业）
Step 3: 从锚点出发搜索 → 标准指南 + 真实范例
Step 4: 每搜到一个结果，验证 is_primary_source
Step 5: 通过验证的来源 ≥ 3 份 → 停止搜索；不足则继续下一锚点（最多 8 轮）
Step 6: 提取结构规范 → 输出 blueprint.json
```

---

## 锚点注册表

### 学术领域锚点

#### 锚点 A1：EQUATOR Network（报告规范总站）

EQUATOR Network 索引了 400+ 个研究报告规范（PRISMA、CONSORT、STROBE、MOOSE 等），覆盖几乎所有学术报告类型。

**搜索方式**：
```
site:equator-network.org {report_type} reporting guideline
```

**示例**：
- 系统综述 → `site:equator-network.org systematic review` → PRISMA 2020
- 随机对照试验 → `site:equator-network.org randomised trial` → CONSORT
- 观察性研究 → `site:equator-network.org observational study` → STROBE
- 诊断准确性 → `site:equator-network.org diagnostic accuracy` → STARD
- 质性研究 → `site:equator-network.org qualitative research` → SRQR / COREQ

**适用范围**：生物医学、心理学、公共卫生、护理等有成熟报告规范的领域。

#### 锚点 A2：期刊 Author Guidelines（投稿指南）

期刊自己定义了投稿格式。不写死具体期刊，而是**先找到领域对应的顶级期刊，再获取其投稿指南**。

**搜索方式**（两步）：
```
# Step 1: 找到领域顶级期刊（通过高引综述）
用 search-academic skill 搜索: "{领域关键词} survey OR review"
从结果中提取发表期刊名（优选引用数高的）

# Step 2: 获取该期刊的投稿指南
"{journal_name}" author guidelines OR guide to authors OR submission guidelines
```

**验证**：URL 路径通常包含 `/authors/`、`/submit/`、`/guidelines/`、`/for-authors/`。

**适用范围**：所有学术领域——每个领域都有对应的顶级期刊。

#### 锚点 A3：方法论权威手册（少量极稳定来源）

| 手册 | 域名 | 覆盖范围 |
|------|------|---------|
| Cochrane Handbook | training.cochrane.org | 系统综述、Meta 分析 |
| NLM Reporting Guidelines | nlm.nih.gov | 所有生物医学研究类型的报告标准索引 |
| APA Publication Manual | apastyle.apa.org | 心理学及社科领域写作规范 |

**搜索方式**：
```
site:training.cochrane.org {report_type} structure
site:nlm.nih.gov reporting guidelines {research_type}
```

#### 学术领域搜索优先级

```
1. EQUATOR Network（如果领域有对应的 reporting guideline）
2. 期刊 Author Guidelines（通过高引综述定位期刊）
3. 方法论手册（Cochrane / NLM / APA）
4. 领域内高引综述论文的实际目录结构（作为范例）
```

对于 CS/AI/工程等**无成熟报告规范**的领域，EQUATOR 可能无结果。此时跳过步骤 1，直接从步骤 2（期刊指南）和步骤 4（高引综述范例）入手。

---

### 行业研究领域锚点

#### 锚点 B1：监管机构披露模板（法定标准）

监管机构定义了法定的报告格式。不写死具体机构，而是**根据行业所在地区定位对应监管机构**。

**搜索策略**：
```
# 识别地区 → 搜索对应监管机构
中国上市公司: site:csrc.gov.cn 信息披露 OR 年报格式
美国上市公司: site:sec.gov filing template OR form 10-K
欧盟: site:esma.europa.eu reporting template
香港: site:hkex.com.hk listing rules disclosure

# 特定行业监管
银行: site:cbirc.gov.cn OR site:federalreserve.gov
医药: site:nmpa.gov.cn OR site:fda.gov
```

**适用范围**：涉及合规、上市公司分析、监管政策的研究。无监管要求的行业可跳过。

#### 锚点 B2：CFA Institute Research Standards（职业标准）

投资研究领域的全球职业标准。

**搜索方式**：
```
site:cfainstitute.org research objectivity standards
site:cfainstitute.org global investment performance standards
```

**适用范围**：投资研究、券商研报、基金分析。

#### 锚点 B3：真实范例发现（行业头部机构报告）

不写死哪些券商/咨询公司，而是**搜索同类报告，从结果中识别头部机构**。

**搜索方式**：
```
# 中文行业研报
"{行业}" 深度研报 OR 行业研究报告 filetype:pdf
"{行业}" 行业深度 site:research.cicc.com OR site:mckinsey.com.cn

# 英文行业报告
"{industry}" industry report OR market analysis filetype:pdf
"{industry}" deep dive site:mckinsey.com OR site:bcg.com OR site:bain.com

# 国际组织报告（特定行业）
"{industry}" report site:worldbank.org OR site:imf.org OR site:oecd.org OR site:who.int
```

**适用范围**：所有行业研究。不要求找到特定机构的报告，而是找到**任何头部机构发布的同类报告作为结构范例**。

#### 行业研究搜索优先级

```
1. 监管模板（如果涉及合规/上市公司）
2. CFA Standards（如果是投资研究）
3. 同类真实报告范例（从搜索结果中识别头部机构发布的报告）
4. 头部咨询公司的公开方法论（McKinsey/BCG/Bain）
```

---

## 验证协议：is_primary_source

搜到内容后，需要验证**拿到的是报告本体/标准原文，而不是二手描述**。

这是一个结构特征检测，不需要模型做主观判断。

### 采信规则：命中 2+ 个 positive signal

| # | Positive Signal | 检测方式 |
|---|----------------|---------|
| 1 | 有完整目录/标题层级结构（至少 3 级） | 计数 heading 层级 |
| 2 | 有明确的发布机构和日期 | 页面中存在机构名 + 发布/更新日期 |
| 3 | 有 DOI 或官方文档编号 | 页面中存在 `10.xxxx/` 或编号 |
| 4 | 来自 PDF 原文或官方页面 | URL 以 .pdf 结尾，或路径含 /publications/ /research/ /reports/ |
| 5 | 包含 checklist 或结构性要求列表 | 页面中有编号列表描述必选章节/元素 |

### 丢弃规则：命中任意 1 个 negative signal

| # | Negative Signal | 说明 |
|---|----------------|------|
| 1 | 是"如何写报告"的教程 | 二手描述，非标准本身 |
| 2 | 是报告的新闻摘要/媒体报道 | 转述不是原文 |
| 3 | 正文内容不超过 500 字 | 摘要而非全文 |
| 4 | 来自内容聚合站 | 知乎/CSDN/medium/搜狐/百家号 |
| 5 | URL 含 blog/post/answer/article 等路径 | 通常是个人博文 |

### 验证失败处理

单次验证失败不终止搜索——丢弃该结果，继续尝试下一个候选。只有当退出条件触发时才停止。

---

## 退出条件

格式发现按目标驱动，不按轮次驱动。

### 成功退出

**通过验证的来源（标准指南 + 真实范例合计）≥ 3 份** → 停止搜索，提取 blueprint。

示例：
- 1 份标准指南 + 2 份真实范例 = 3 ✓
- 0 份标准指南 + 3 份真实范例 = 3 ✓（有些领域没有正式标准，纯靠范例也可以）
- 2 份标准指南 + 1 份真实范例 = 3 ✓

### 超时退出

**已执行 8 轮搜索仍不足 3 份** → 用已有结果生成 blueprint：
- 如果有 1-2 份通过验证的来源 → 基于已有结果生成 blueprint，在 `fallback_reason` 中说明来源不足
- 如果 0 份 → `fallback_used: true`，回退到通用模板

### 不要做

- 不要为了凑数降低验证标准
- 不要因为"已经搜了 3 轮"而提前停止——如果还有未尝试的锚点且当前不足 3 份，继续搜
- 不要重复搜索同一个锚点

---

## 输出格式：Report Blueprint

格式发现的产出是一个独立的 `blueprint.json` 文件（不嵌入 plan.json，因为 blueprint 一旦确定不再变化，而 plan.json 在波间回顾时会被修改）。

```json
{
  "genre": "报告类型名称（如 Systematic Review / 行业深度研报）",
  "domain": "领域（如 AI/NLP / 新能源汽车）",
  "discovery_sources": [
    {
      "type": "standard_guideline",
      "name": "来源名称（如 PRISMA 2020）",
      "url": "原文 URL",
      "what_extracted": "从中提取了什么（如 27-item checklist）"
    },
    {
      "type": "real_exemplar",
      "name": "范例名称（如 ACM Computing Surveys 综述投稿指南）",
      "url": "原文 URL",
      "what_extracted": "从中提取了什么（如 章节结构要求）"
    }
  ],
  "sections": [
    {
      "name": "章节名",
      "required": true,
      "elements": ["该章节必须包含的元素"],
      "notes": "来自标准的特殊要求说明"
    }
  ],
  "mandatory_elements": [
    "必须包含的非章节元素（如 PRISMA flow diagram、对比矩阵表格）"
  ],
  "conventions": {
    "citation_style": "引用格式（如 Vancouver numbered / APA 7th）",
    "tone": "写作风格（如 objective, evidence-based）",
    "domain_specific_metrics": ["领域特有指标（如 effect sizes, I², p-value）"],
    "anti_patterns": ["不应做的事（如 不要在 Results 中加入 Discussion）"]
  },
  "fallback_used": false,
  "fallback_reason": null
}
```

当回退到通用模板时：

```json
{
  "genre": "...",
  "domain": "...",
  "discovery_sources": [],
  "sections": [],
  "mandatory_elements": [],
  "conventions": {},
  "fallback_used": true,
  "fallback_reason": "已执行 8 轮搜索，未找到该领域的权威报告标准，使用 research-report skill 通用模板"
}
```
