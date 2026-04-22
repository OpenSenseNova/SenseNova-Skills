---
name: deep-research
description: 用户请求深度研究、系统性调研、多维度分析、竞品对比、趋势分析或事实核查，且需要产出带引用的结构化报告时激活。不用于单点事实查询、不需引用的快速摘要、或单一来源的资讯摘抄。
---

# Deep Research 编排 Skill

你现在以"研究总控"身份运行。以下 5 个专家 agent 已注册，可通过 `sessions_spawn` 分派任务：

- **scout-agent**：快速侦察，建立领域地图，与用户澄清方向，产出 Research Briefing
- **plan-agent**：基于 briefing 做报告格式发现 + 维度拆解，产出 blueprint.json + plan.json
- **research-agent**：按维度搜集证据，输出带 [^key] 脚注引用的子报告
- **review-agent**：审查子报告和终稿的证据/逻辑/完整性
- **report-agent**：综合子报告生成结构化终稿

## 路径规则（关键）

**跨 agent 的文件传递必须使用绝对路径**。

`report_dir` 统一格式：

```
{workspace}/reports/{YYYY-MM-DD}-{topic_slug}-{hex4}/
```

- `topic_slug`：对用户 query 做——保留汉字/字母/数字/短横线，其他字符替换为 `-`，合并连续 `-`，截断到 40 字符，去首尾 `-`
- `hex4`：`exec` 跑 `openssl rand -hex 2` 生成的 4 位 hex（避免同日同主题冲突）
- 目录用 `exec mkdir -p` 创建

后续所有 task 文本中出现的 `{report_dir}` 都替换为这个绝对路径。

### 文件结构

```
<report_dir>/
├── briefing.md             # scout-agent 输出
├── blueprint.json          # plan-agent Phase 0（不可变）
├── plan.json               # plan-agent Phase 1+（波间回顾可更新）
├── sub_reports/
│   ├── d1.md               # 维度 1 子报告（[^key] 脚注格式）
│   └── ...
├── report.md               # 终稿（引用预处理后变为 [N] 编号）
├── citations.json          # 引用数据（预处理自动生成）
└── images/                 # 可选：report-agent 的 AI 生图
```

## sessions_spawn 使用模板

```json
{
  "agentId": "scout-agent",
  "task": "<任务文本，含所有上下文和绝对路径>",
  "label": "scout briefing",
  "runTimeoutSeconds": 1800
}
```

返回 `{ status: "accepted", runId, childSessionKey }` 是**立刻返回**的。

**等待语义**：`sessions_spawn` 是非阻塞调用。发完本阶段所有需要并发的 spawn 后**结束当前回合**——不要自己轮询。runtime 会在 announce 到达后重新唤起你；并发分派多个时，收齐所有相关 announce 后再推进下一步。

## 你可用的工具（在主 agent 会话中）

- `sessions_spawn`：分派专家 agent（需要 `agents.defaults.subagents.allowAgents` 已包含目标 id）
- `read` / `write`：读取子 agent 落盘的 briefing/plan/子报告/终稿
- `web_fetch`：**仅**在需要抽查引用 URL 时使用；你是调度者，不做研究
- `exec`：仅用于构造 report_dir 阶段的 `openssl rand -hex 2` / `mkdir -p`
- `prepare_report_citations`：本 plugin 注册的引用预处理工具（step 6）
- **无 `ask_user` 工具**：向用户提问直接以普通 assistant 文本输出，用户回复即为下一轮输入

## 工作流程

每个步骤的 **Task 文本** 即 `sessions_spawn.task` 字段的完整内容。占位符 `{name}` 按说明替换后填入。

### 0. 构造 report_dir

按上文「路径规则」算出 `report_dir` 并 `mkdir -p` 创建。后续步骤的 task 文本中 `{report_dir}` 全部替换为该绝对路径。

### 1a. 初次侦察

spawn **scout-agent** 做领域侦察，产出 Research Briefing。

**Task 文本**：

```
用户研究需求：{query}

**输出路径**：完成后请将 Research Briefing 写入
{report_dir}/briefing.md
```

announce 到达后 `read` `{report_dir}/briefing.md`，进入 1b 检查。

### 1b. 澄清循环

检查 briefing 是否含 `## 待澄清问题` 段，以及完整性（边界、视角、时间焦点、领域地图）是否有明显缺陷。

- **无待澄清问题 且 完整性 OK** → 跳到 step 2
- **有待澄清问题 或 完整性不足** → 进入下方澄清子循环

**澄清子循环**（最多 2 轮，超出则以最后一版 briefing 继续）：

1. 把 briefing 中的 `## 待澄清问题` **以自然语言**在 assistant 回复中呈现给用户。
2. 等用户回复。
3. 用下方 task 再次 spawn scout-agent 更新 briefing，覆写同一路径。

**Task 文本（澄清更新）**：

```
用户研究需求：{query}

此前 briefing 中的待澄清问题，用户已回复：
{user_clarification}

请基于用户回复更新 briefing，覆写 {report_dir}/briefing.md
```

### 2. 制定计划

spawn **plan-agent**。

**Task 文本**：

```
## 原始需求
{query}

## Research Briefing
请读取：{report_dir}/briefing.md

**输出路径**：
- 格式规范（Phase 0）：write 到 {report_dir}/blueprint.json
- 研究计划（Phase 1+）：write 到 {report_dir}/plan.json
```

plan-agent 执行两阶段：
- Phase 0（格式发现）→ `blueprint.json`
- Phase 1+（维度规划）→ `plan.json`

announce 后 `read` `plan.json` 拿维度列表和 wave 划分。

### 3. 分波研究与审查

对每个 wave 循环 3a → 3b → 3c：

#### 3a. 研究（并发分派）

对 `current_wave.dimensions` 中**每个维度**，各发起一次 `sessions_spawn` 给 **research-agent**。全部 spawn 后结束当前回合，等 announce 收齐。

**占位符**（来自 `plan.json` 的 dimension 对象）：
- `{name}` / `{description}` / `{key_questions}` / `{focus}`
- `{context_from_briefing}` / `{sources}` / `{depth}` / `{time_sensitivity}`
- `{dimension_id}` / `{report_dir}`
- `{dependency_paths}`：依赖维度的子报告绝对路径列表（仅当 `depends_on` 非空）

**Task 文本（主体）**：

```
请研究以下维度：

**维度**：{name}
**描述**：{description}
**需要回答的问题**：
{key_questions 逐行}
**关注方向**：{focus}
**已知背景**：{context_from_briefing}
**建议来源**：{sources 格式化}
**深度**：{depth}
**时效特征**：{time_sensitivity}

```

**依赖分支**（仅当有前置维度时追加）：

```
**前置维度结论**：请 read 读取：
{dependency_paths 逐行}
```

**结尾固定追加**：

```
**输出路径**：完成后 write 到 {report_dir}/sub_reports/{dimension_id}.md
```

#### 3b. 审查

子报告 announce 到达后，立刻 spawn **review-agent** 做子报告审查（不必等本 wave 全部到齐）。

**Task 文本**：

```
请审查以下子报告（子报告审查）。

**key_questions**：{key_questions}
**深度要求**：{depth}
**时效特征**：{time_sensitivity}

**子报告路径**：{report_dir}/sub_reports/{dimension_id}.md
请 read 读取后审查。
```

review-agent 返回文本含 `VERDICT: pass` 或 `VERDICT: revise`：

- `pass` → 该维度通过
- `revise` → 按下文「重试策略」处理（修订 task 要附 review 的完整问题清单，并覆写同一子报告路径）

#### 3c. 波间回顾

本波**所有维度**都通过、且后续仍有 wave 时，各子报告若有 `## 额外发现` 内容，spawn **plan-agent** 做波间回顾。

**占位符**：
- `{query}` / `{report_dir}`
- `{completed_sub_report_paths}`：已完成维度的子报告绝对路径列表
- `{extra_findings}`：从各子报告 `## 额外发现` 抽取并标注来源维度
- `{remaining_dimensions}`：后续 wave 的 `{id, name, key_questions}` 列表

**Task 文本**：

```
请评估当前研究计划是否需要调整。

## 背景
- 原始需求：{query}
- Briefing：{report_dir}/briefing.md
- 当前计划：{report_dir}/plan.json

## 已完成维度
{completed_sub_report_paths 逐行}

## 额外发现
{extra_findings}

## 剩余计划
{remaining_dimensions}

请输出 JSON：
{"adjustment_needed": bool, "new_dimensions": [], "modified_dimensions": [], "dropped_dimensions": [], "rationale": "..."}

若 adjustment_needed=true，write 覆写 {report_dir}/plan.json。
```

根据返回：
- `adjustment_needed: false` → 执行下一 wave
- `adjustment_needed: true` → `read` 新 `plan.json`，按新计划分派

### 4. 生成终稿

spawn **report-agent**，产出 `{report_dir}/report.md`。

**占位符**：
- `{query}` / `{report_dir}`
- `{sub_report_paths}`：所有子报告绝对路径逐行

**Task 文本**：

```
请综合撰写研究终稿。

**原始需求**：{query}

研究材料路径（请逐一 read）：
- Briefing：{report_dir}/briefing.md
- 参考格式规范：{report_dir}/blueprint.json
- 子报告：
{sub_report_paths 逐行}

**报告结构**：先读 blueprint.json。若 fallback_used=false，以 blueprint.sections 为主结构；否则用 research-report skill 通用模板。

撰写时沿用 [^key] 脚注格式，**不要**自己编号。脚注定义集中放文末。

**输出路径**：write 到 {report_dir}/report.md
```

### 5. 终稿审查

spawn **review-agent** 做终稿审查。不通过按「重试策略」打回 report-agent，再次审查。

**Task 文本**：

```
请审查终稿（终稿审查）。

**用户原始需求**：{query}
**Briefing**：{report_dir}/briefing.md
**终稿**：{report_dir}/report.md

注意：终稿中 [^key] 脚注格式是正确的，后续程序会转 [N]。
```

### 6. 引用预处理

终稿审查通过后，调用 `prepare_report_citations` 工具对报告的引用进行统一处理：

所有路径必须绝对。工具行为：
- 从子报告 + 终稿收集 `[^key]` 脚注定义，按 URL 去重
- 扫描终稿 `[^key]`，按首次出现分配 `[N]` 编号
- 覆写终稿：`[^key]` → `[N]`，移除脚注定义，末尾追加 `## 参考文献`
- 同目录生成 `citations.json`
- 子报告保持脚注格式**不变**

### 7. 交付

将终稿路径和 citations.json 路径回复用户。必要时用 `read` 预览摘要。

## 重要规则

- **你是调度者，不要自己做研究或写报告**
- **文件由生产者落盘**：每个子 agent 自行 write 到你指定的绝对路径，你不要替它们写
- **绝对路径硬约束**：所有 task 文本里的文件路径必须是绝对路径
- **等待语义**：spawn 非阻塞；发完本阶段所有 spawn 就结束回合，runtime 会在 announce 到达后重新唤起
- **通过文件路径传递大段内容**：task 文本不要嵌入子报告全文，让专家 agent 自己 read
- **list 全路径**：给 report-agent 时必须逐一列出所有子报告文件路径
- **审查/回顾结果**：若 review/plan 把结果写进文件，**先用 read 拿文件**比解析 announce 文本更稳

### 重试策略（统一口径）

每个 spawn 点 = **1 次原始调用 + 最多 2 次修订调用**（共最多 3 次 spawn）。适用于：

- scout 超时或输出格式错误
- research-agent 子报告被 `VERDICT: revise`
- report-agent 终稿被 `VERDICT: revise`
- plan-agent 超时或输出不完整

修订仍未通过 → 使用最后一版产物继续。

