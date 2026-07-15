---
name: sn-report-format-discovery
description: 用于研究任务的最终呈现形式未知时。比较研究报告、学术论文、表格优先报表、决策备忘录或自定义形式，并用权威标准与真实范例支持推荐。
---

# sn-report-format-discovery（最终呈现形式发现）

在规划研究维度之前，先搞清楚最终结果应以什么形式呈现。本 skill 研究的是**呈现形式**，例如研究报告、学术论文、表格优先报表、决策备忘录或用户自定义形式；同时登记用户对主信息载体的偏好强度。它不决定文件后缀，也不在研究前生成具体章节目录。

## 核心原则

1. **呈现形式是可研究的问题**——读者任务、使用场景、信息形态和领域惯例决定什么形式更合适
2. **固定入口，动态导航**——写死的是"去哪里找"（锚点），动态的是"找什么"（具体领域标准）
3. **区分标准指南和真实范例**——指南告诉你"应该怎么写"，范例告诉你"实际长什么样"，两者互补
4. **容器与形式分开**——当前 deep-research 最终仍以 Markdown 承载；研究报告、论文、报表等是 Markdown 内的信息呈现形态
5. **形式、内容范式、信息载体正交**——研究报告等形式回答"交付物是什么"，六种 research paradigm 回答"内容如何推进"，主信息载体回答"核心信息由什么结构承载"；三者不得建立固定映射
6. **偏好不等于最终编排**——研究前只登记 `required|preferred|auto`；研究完成后由 report-planner 根据实际 evidence 生成 `organization_decision`
7. **语言只服从运行锚点**——使用 payload 的 `language`；候选 label、best_for、defining_features、rationale、来源提取说明与 completion reply 使用该语言，不得因本 skill 的中文提示或外部来源语言改变输出语言

## 职责边界

- 本 skill 是格式发现的唯一责任方：比较候选、调研惯例、提取 defining features，并写出 `format_proposal.json`。
- scout 只在完成 briefing 后传入预研上下文并调用本 skill，不在自身契约中复制格式规则。
- plan 只根据已确认形式准备相应证据，不重新选择格式。
- report-planner 在研究完成后同时读取已确认形式、结构偏好和 evidence，生成可审计的 `organization_decision`；本 skill 不提前生成章节 blueprint，也不替 planner 预判 evidence 适合哪种结构。

## 输入

- 原始研究需求 `query`
- `language`：controller 根据 query 固化的请求级语言参数
- briefing 中的 `task_interpretation`、目标读者、使用场景和用户已表达的格式要求
- 可选 `format_revision_request`；修订时同时读取现有 `format_proposal.json`
- `report_dir`，用于写入 `{report_dir}/format_proposal.json`

## 工作流程

```
步骤 1: 从 briefing 识别 → 用户任务 + 读者 + 使用场景 + 用户明确表达的结构偏好
步骤 2: 比较 2-3 种可行呈现形式，选出推荐项
步骤 3: 为候选形式选择锚点策略并搜索 → 标准指南 + 真实范例
步骤 4: 每搜到一个结果，验证 is_primary_source
步骤 5: 通过验证的来源 ≥ 3 份 → 停止搜索；不足则继续下一锚点（最多 8 轮）
步骤 6: 提取形式特征 + 登记结构偏好强度 → 输出 format_proposal.json
```

## 呈现形式判断

先判断读者最终要**阅读、复核、比较还是决策**。下表是常见起点，不是封闭枚举；用户可以指定任何其他形式。

| 呈现形式 | 适合的任务 | 主要信息形态 |
|---|---|---|
| `research_report` | 多维度综合、行业/市场/政策/技术研究 | 结论前置的叙事 + 图表/表格 |
| `academic_paper` | 明确研究问题、方法、证据过程与学术论证 | 摘要、方法、结果、讨论式论证 |
| `analytical_table` | 读者主要需要逐项比较、查数或筛选 | 表格为主体，文字只解释口径与结论 |
| `decision_memo` | 面向单一决策，需要建议、依据和风险 | 短篇决策结论 + 选项/风险 |
| `timeline` | 事件演变、政策沿革、项目复盘 | 时间序列为主体 |
| `faq` | 问题集合相对独立，读者按需查阅 | 问答单元 |
| `custom` | 用户点名的其他形式 | 由用户定义 |

选择规则：

- 用户已明确指定形式：只登记该形式，不用外部惯例替换用户选择。
- 用户未指定：推荐 1 个主选项，并保留最多 2 个真正可行的替代项。
- 不要因为最终容器是 Markdown 就默认 `research_report`；表格优先、论文式或其他形式同样可以在 Markdown 中实现。
- `defining_features` 只描述该形式必须保持的呈现特征，不写本次研究的具体章节标题或结论。

### 结构偏好强度

主信息载体使用开放但稳定的基础类型：`narrative`、`matrix`、`timeline`、`checklist`、`scorecard`、`qa`、`callout`、`diagram`、`custom`。这些类型不是与 panorama、comparison、investigation、timeline、evaluation、forecast 的配对表；任一内容范式都可以根据读者任务和 evidence 采用任一载体或多个载体组合。

这里区分三层，不能混成一个枚举：

- `selected_format` 是整体交付形态，例如研究报告、brief、memo、board 或用户自定义形式。
- `structure_preference` 是核心信息由哪种原子载体承载，例如 narrative、matrix 或 checklist。
- 研究完成后的 `organization_decision` 才决定实际 content units、主次关系和 Markdown 渲染方式。

因此 brief/board 不和 matrix/checklist 竞争同一个 `requested_type`。用户要求“board 中以矩阵为主体”时，board 进入 `selected_format`（必要时为 custom candidate），matrix 进入 `structure_preference`；两者都要保留。

```json
{
  "requested_type": "matrix",
  "custom_type": null,
  "strength": "required|preferred|auto",
  "notes": "用户希望核心比较能直接扫读"
}
```

判定规则：

- `required`：用户明确使用“必须”“只要”“以……为主体”等硬约束。`requested_type` 必填；后续 planner 不得改成其他主载体。
- `preferred`：用户表达“优先”“最好”“倾向”等偏好。`requested_type` 必填；planner 只有在 evidence 明显不适配时才可调整，并必须在 `organization_decision` 说明原因。
- `auto`：用户没有表达主载体偏好。`requested_type` 与 `custom_type` 均为 `null`；planner 在 evidence 完成后选择。
- 用户描述了枚举外的载体时用 `requested_type=custom`，并在 `custom_type` 写用户原话；不得为了套枚举改写用户要求。
- 不从 query 的研究范式反推结构偏好。例如竞品分析不自动写成 matrix，事件调查也不自动写成 timeline。

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

#### 锚点 A2：期刊投稿指南

期刊自己定义了投稿格式。不写死具体期刊，而是**先找到领域对应的顶级期刊，再获取其投稿指南**。

**搜索方式**（两步）：
```
# 步骤 1: 找到领域顶级期刊（通过高引综述）
用 sn-search-academic skill 搜索: "{领域关键词} survey OR review"
从结果中提取发表期刊名（优选引用数高的）

# 步骤 2: 获取该期刊的投稿指南
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
2. 期刊投稿指南（通过高引综述定位期刊）
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
2. CFA 标准（如果是投资研究）
3. 同类真实报告范例（从搜索结果中识别头部机构发布的报告）
4. 头部咨询公司的公开方法论（McKinsey/BCG/Bain）
```

---

## 验证协议：is_primary_source

搜到内容后，需要验证**拿到的是报告本体/标准原文，而不是二手描述**。

这是一个结构特征检测，不需要模型做主观判断。

### 采信规则：命中 2+ 个 positive signal

| # | 正向信号 | 检测方式 |
|---|----------------|---------|
| 1 | 有完整目录/标题层级结构（至少 3 级） | 计数 heading 层级 |
| 2 | 有明确的发布机构和日期 | 页面中存在机构名 + 发布/更新日期 |
| 3 | 有 DOI 或官方文档编号 | 页面中存在 `10.xxxx/` 或编号 |
| 4 | 来自 PDF 原文或官方页面 | URL 以 .pdf 结尾，或路径含 /publications/ /research/ /reports/ |
| 5 | 包含 checklist 或结构性要求列表 | 页面中有编号列表描述必选章节/元素 |

### 丢弃规则：命中任意 1 个 negative signal

| # | 负向信号 | 说明 |
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

**通过验证的来源（标准指南 + 真实范例合计）≥ 3 份** → 停止搜索，提取候选形式及其 defining features。

示例：
- 1 份标准指南 + 2 份真实范例 = 3 ✓
- 0 份标准指南 + 3 份真实范例 = 3 ✓（有些领域没有正式标准，纯靠范例也可以）
- 2 份标准指南 + 1 份真实范例 = 3 ✓

### 来源不足退出

**达到 8 轮搜索预算后仍不足 3 份** → 用已有结果生成 proposal：
- 如果有 1-2 份通过验证的来源 → 基于已有结果生成 proposal，在 `fallback_reason` 中说明来源不足
- 如果 0 份 → `fallback_used: true`，仅按用户任务、受众与信息形态给出候选，并明确缺少外部惯例依据

### 不要做

- 不要为了凑数降低验证标准
- 不要因为"已经搜了 3 轮"而提前停止——如果还有未尝试的锚点且当前不足 3 份，继续搜
- 不要重复搜索同一个锚点

---

## 输出格式：呈现形式候选

格式发现的产出是独立的 `format_proposal.json`。它只供 controller 展示给用户确认，不进入正式研究。

写入前使用 `language`。所有由本 skill 撰写的自然语言值必须使用该语言；来源 `name` 可保留原始官方名称，URL、ID、枚举与结构 key 不翻译。

```json
{
  "container": "markdown",
  "source": "user_specified|format_research|fallback",
  "recommended_format_id": "research_report",
  "structure_preference": {
    "requested_type": null,
    "custom_type": null,
    "strength": "auto",
    "notes": "用户未指定主信息载体，由 report-planner 在研究后按 evidence 决定"
  },
  "candidates": [
    {
      "id": "research_report",
      "label": "研究报告",
      "best_for": "该形式最适合解决什么读者任务",
      "defining_features": ["该形式必须保持的呈现特征"],
      "rationale": "为什么适合本次任务"
    }
  ],
  "format_research_sources": [
    {
      "type": "standard_guideline",
      "name": "来源名称",
      "url": "原文 URL",
      "what_extracted": "该来源支持了哪项形式判断"
    },
    {
      "type": "real_exemplar",
      "name": "真实范例名称",
      "url": "原文 URL",
      "what_extracted": "从中提取的呈现特征"
    }
  ],
  "fallback_used": false,
  "fallback_reason": null,
  "confirmed_by_user": false
}
```

约束：

- `recommended_format_id` 必须引用 `candidates[].id`。
- `structure_preference.strength` 必须是 `required|preferred|auto`；`required|preferred` 必须有 `requested_type`，`auto` 的 `requested_type` 必须为 `null`。
- 用户明确指定时，`source=user_specified`，候选只保留用户指定形式，`format_research_sources=[]`。
- 用户未指定时，候选 2-3 个；每个 ID 使用稳定的小写 snake_case，也允许用户自定义 ID。
- `defining_features` 是后续保持格式不变的核心合同；不得混入本次研究的事实或具体目录。
- 0 个可靠来源时可 `fallback_used=true`，但仍须给出基于任务/受众/信息形态的候选，并说明 fallback reason。
- `confirmed_by_user` 由 scout 保持 `false`；controller 收到用户确认后另行写出只读 `format.json`。

用户选定后，controller 写出的 `format.json` 只保留容器、所选候选和用户确认的结构偏好：

```json
{
  "container": "markdown",
  "selected_format": {
    "id": "analytical_table",
    "label": "表格优先报表",
    "best_for": "逐项比较与查数",
    "defining_features": ["主表承载核心结果", "文字只解释口径、发现和限制"],
    "rationale": "本次任务的核心是同口径比较"
  },
  "structure_preference": {
    "requested_type": "matrix",
    "custom_type": null,
    "strength": "required",
    "notes": "用户确认核心结果必须由主表承载"
  },
  "confirmed_by_user": true
}
```

`selected_format` 必须从用户实际确认的 candidate 原样复制，`structure_preference` 必须保留用户确认时的强度；后续 agent 不得增删或改写 defining features，也不得把 `preferred` 或 `auto` 偷换成 `required`。研究后的实际编排写在 outline v2 的 `organization_decision`，不回写 `format.json`。
