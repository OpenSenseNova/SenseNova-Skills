---
name: sn-deep-research
description: 用于用户请求深度研究、系统性研究、竞品分析、方案对比、趋势分析或事实核查时。不用于单一事实查询或快速摘要。**遇到以下任一情况就主动使用本 skill，不要自行搜几条就回答**：①用户出现触发词：深度研究 / 深度调研 / 深入研究 / 全面研究 / 系统研究 / 调研 / 调查 / 尽调 / 行业研究 / 市场研究 / 竞品分析 / 政策研究 / 技术研究 / 趋势研究 / 事实核查 / 写一份研究报告 / 调研报告 / 深度报告 / research / deep research；②请求需要跨多来源取证、多维度对比、交叉验证才能给出可靠结论；③用户要求产出报告、白皮书、行业分析或尽调文档；④话题涉及最新政策/市场/产品/价格/法规，需要系统核查。模糊或宽泛的"研究/了解一下 X"也优先触发。仅不用于：单点事实问答（"X 是什么"）、一句话摘要、已给定单一来源的整理、纯文字润色改写。
---

# 深度研究（多 Agent 深度研究编排）

你是深度研究总控。职责是**调度**专家角色完成研究、校验、写作与渲染；不要自己做研究、写章节、缝合或审查。

阅读地图：§1 总则 → §2 派发机制 → §3 报告目录 → **§4 档位选择器（决定跑什么）** → **§5 阶段库（每个角色怎么派，仅一次）** → §6 附录。运行时先按 §4 选定本次档位的流水线，再按流水线逐步跳转 §5 的对应条目。

## 1. 总则

**控制器铁律**：

- **只调度，不读大文件**：evidence / 章节 / outline 等大文件通过绝对路径传给角色自读；controller 只读调度所需的小字段（见 §6）。
- **所有文件路径使用绝对路径**，不下发未解析 token。
- **通过文件路径传递内容**，不在消息里粘贴大段正文。
- **Schema 由 validator 守门**：controller 不自行判断 JSON 字段是否合规。
- **报告阶段只消费 evidence 边界**：review / perspective / supplement_plan 是流程产物，不作为 report-planner 的事实输入。
- **补研按维度决策**：每维度生成自己的 `d{N}.supplement_plan.json`，不用全局 board 计划筛掉局部硬缺口。

搜索能力由各角色按其 `agents/*.md` 自行调用专业 search skills / scripts；controller 不直接做搜索。

**环境配置分级**（任务开始前，controller 处理一次）：

**Tier 1 — 强制能力，必须探测**：文件读写、命令执行、网页搜索、网页抓取。controller 建目录 / 跑 validator / 调脚本、取证角色联网取证都依赖它们，是产出可靠研究的硬前提。**探测到任一未就绪 → 暂停，提醒用户配置 / 启用，在具备前不派发任何角色。**

**Tier 2 / Tier 3 — 可选配置，不探测但须告知 + 确认**：controller 不探测（此刻尚不知会用哪些来源，凭证又是 per-skill 环境变量、调用才知有无）。但**必须一次性告知用户：下列可选项未配置会降级、影响效果，请确认是否继续**（或先配置再跑）；可与 §4.1 档位确认合并为同一次询问。确认后照常派发，缺失项由各角色按「能力降级契约」自行兜底。

**统一凭证配置**：搜索、社媒、金融、学术与图片生成所需的 API key / token / cookie 统一建议写在仓库根目录 `.env`（参考 `.env.example`），由 runtime 或用户在执行前加载为同名环境变量。skill 与脚本只读取环境变量；不要把密钥写入 payload、命令行参数、报告正文、日志或 transcript。

| 层级 | 可选配置（环境变量） | 缺失影响 |
|---|---|---|
| Tier 2 | `SN_IMAGE_GEN_API_KEY` / `SN_API_KEY` | 无 AI 概念配图，输出无图版 |
| Tier 2 | `XHS_COOKIE` / `ZHIHU_COOKIE` / `WEIBO_COOKIE` / `DOUYIN_COOKIE` / `BILIBILI_COOKIE` | 中文社媒（小红书/知乎/微博/抖音/B站）无站内检索，转通用搜索兜底 |
| Tier 2 | `TIKHUB_TOKEN`（Twitter/X）、`YOUTUBE_API_KEY` | 对应平台无站内检索，转通用搜索兜底（Reddit 免认证） |
| Tier 3 | GitHub token、`HF_TOKEN`、`SO_API_KEY`、学术 API key | 仅速率受限、更慢更易限流（GitHub `code` 搜索无 token 则不可用；arXiv 等开放获取与金融/市场/年报等免认证来源无需配置） |

此处只做派发前的集中处理，不替代各角色运行时的自降级与反捏造底线。

## 2. 派发机制（runtime 通用）

「派发 role」=一次专家角色调用；「并行派发」=同阶段内可并发的一组调用。派发机制由 runtime 决定，本 skill 只规定 payload 契约。

### 2.1 路径与 token

先解析当前 skill 目录绝对路径。不同 runtime 暴露不同占位符，只用被替换成真实路径的那个，其余保持字面量时忽略：

```text
${SKILL_DIR}          ← Claude Code
${HERMES_SKILL_DIR}   ← Hermes
{baseDir}             ← OpenClaw
```

设解析后的真实路径为 `SKILL_DIR`：

- `{plugin_skills_dir}` = `dirname(SKILL_DIR)`
- `{plugin_role_dir}` = `SKILL_DIR/agents`

路径解析只在 controller 侧发生；下发给 role 的路径必须是解析后的绝对路径。

### 2.2 payload 契约

1. **角色加载**：每条 payload 第一行必须是 `先读取 {plugin_role_dir}/<role>.md 并严格遵守。`
2. **原始 query 必传**：每条含 `原始需求:{query}` 或等价字段。
3. **自包含**：明确目标、输入/输出路径、schema/validator、边界与运行上下文；不假设 role 能看到主对话。
4. **工具名中性**：payload 与角色文件中的「读取/写入/搜索/抓取/命令执行」均指当前 runtime 的等价能力，不假定具体工具名。
5. **并行收敛**：同阶段互不依赖的角色尽量同批派发；有 validator / review 门禁 / depends_on 时再分批。

## 3. 报告目录

所有产物落在**单一报告目录**下，子 agent 之间只经文件通信。命名为 `YYYY-MM-DD-{topic}-{hex4}`，其中 `{hex4}` 是随机 4 位十六进制运行号——**同一需求可能跑多次**，用它区分各次运行、避免目录互相覆盖。下文统一以 `{report_dir}` 指代解析后的绝对路径。

**controller 起步只建空目录**，其余文件由各阶段写入：

```bash
run=$(openssl rand -hex 2 2>/dev/null || printf '%04x' "$RANDOM")
report_dir="$PWD/deep-research-reports/$(date +%F)-{topic}-$run"
mkdir -p "$report_dir"/sub_reports "$report_dir"/board "$report_dir"/sections
echo "$report_dir"   # 记录为后续所有 payload 的 report_dir
```

最终骨架（`[N/H]`=仅 normal/heavy，`[H]`=仅 heavy，无标=全档；quick 仅最小子集）：

```text
{report_dir}/
├── briefing.json / blueprint.json / plan.json   [N/H]
├── sub_reports/   每维度 dN：evidence.json · review.md[N/H] · perspectives/[H] · supplement_plan.json[H]
├── board/         perspective 协作区  [H]
├── outline.json   [N/H]
├── sections/      每节 sN：evidence_subset.json[N/H] · sN.md[H] / s_full.md（quick·normal）
├── stitched.md    [H]
└── report.md / citations.json   渲染终稿
```

文件由谁产出见 §5 阶段库；controller 读取边界与各档差异见 §6。

## 4. 档位选择器

**本节是唯一决定「跑哪些阶段、什么顺序、什么偏差」的地方。** §5 的阶段本身不含档位逻辑。

### 4.1 判档位

三档：`quick` / `normal` / `heavy`。区别不在「几次搜索能搞定」，而在**流程复杂度**。

**quick —— 两条同时满足**（在派 scout 之前由你判定）：

- **不需拆分子任务**：单一维度即可覆盖。正例「X 的现任 CEO 是谁」「某政策何时生效」「Y 公司 2025 营收区间」；反例（不判 quick）：逐实体多属性画像、多子问题拼装、多方案对比。
- **不需多元交叉验证**：单一权威来源即可定论。反例（不判 quick）：口径随来源变化需核实、需对比分析、需论证「为什么」。

任一不满足 → normal/heavy（两者都做拆分子任务 + 多源核实）。两者区别在**力度**：normal 轻量——维度较少、单 writer 出整篇、轻量 review；heavy 全力——维度更多，且加 perspective / supplement 补研 / stitcher / 完整 review。query 越复杂或越重要 → 越倾向 heavy。

**确认纪律（不经确认直接开跑属于违规）**：档位须经用户一句话确认后再进入对应流水线。

- 初判 quick：**不派 scout**，controller 先对原始 query 做一次轻量口径自检——只看「不澄清就会明显误配」的 blocking 级歧义（通常为零）；有则把这句反问折进档位确认里，无则直接向用户确认「建议 quick：单维度 skim 直出，不跑多源核实与报告论证」。确认即定 quick；用户要求升级则改派 scout。
- 初判 normal/heavy：派 scout 产出 `briefing.json`，含 `recommended_mode ∈ {normal, heavy}` + `mode_rationale` 及 `user_confirmations_needed`（口径澄清）；controller 读后**先过澄清门再定档**（见 §4.1.1），可与档位确认合并为同一次询问；若用户已显式指定档位则用用户值，否则回报 scout 推荐请用户确认/覆盖。
- 定档后：normal/heavy 由 plan 写回 `plan.json.mode`，作为后续所有分支的唯一依据；quick 无 plan.json，controller 直接持有 mode。

### 4.1.1 澄清门（预研之后，定档/规划之前）

scout 在 briefing 里把**只有用户能定**的口径分歧抽成 `user_confirmations_needed`，三 tier 各有处理：

- **blocking[]**：不澄清无法合理规划。**暂停流程**，把每条 `question` + 各 `options[].label` + `impact_on_plan` 展示给用户反问；收到回答后继续。
- **high_value[]**：有合理默认但确认后更好。展示问题并高亮 `default_if_unanswered.option_id` 对应 option（附 `rationale`）；用户可改可默许，不响应即用默认。
- **optional[]**：静默采用 `default_if_unanswered.option_id`，不打断用户。

用户答案以 `{qid: option_id}` 形式收集，**直接透传给 §5.2 plan 的 `user_clarification_answers` 字段**——不重跑 scout、不覆写 briefing.json。三个 list 均为 `[]` 时本门为空操作，直接进入定档/规划。

### 4.2 三档流水线

每步指向 §5 阶段库；本节只给顺序与档位偏差。

#### quick（自包含，无 scout/plan/多维度）

1. **构造单维度 d1**：`name=原始需求`、`description=空`、`key_questions=[kq1: 原始需求]`、`focus=空`、`sources=空`（research 自选入口）、`depth=skim`、`time_sensitivity=moderate`、`upstream_evidence=空` → 派 §5.3 research，`mode=quick`，产出 `sub_reports/d1.evidence.json`。**遵守 §5.3 的 quick 派发纪律。**
2. §5.10 report-writer，`write_mode=synthesis`，读 `sub_reports/d1.evidence.json`，整篇写入 `sections/s_full.md`。
3. §5.12 render，输入 `sections/s_full.md`，**不带 --outline**。

**跳过**：evidence validator / 子报告 review / perspective / supplement / 波间回顾 / report-planner / outline validator / stitcher / 终稿 review。

#### normal（单 wave）

1. §5.1 scout → 2. §5.2 plan（轻量）。
3. **每维度并行**：§5.3 research(`mode=initial`) → §5.4 evidence validator → §5.5 review（子报告）。无 perspective / supplement / 波间回顾；plan 已保证 `depends_on` 为空，故单 wave、无波间流水线。
4. §5.8 report-planner（完整 outline + per-section evidence subsets）→ §5.9 outline validator。
5. **单个** §5.10 report-writer，`write_mode=full_outline`，读 outline + 全部 `sections/s*.evidence_subset.json`（每节边界为该节 subset），整篇写入 `sections/s_full.md`（不并行、无 stitcher）。
6. §5.5 review（终稿，轻量）：输入 `sections/s_full.md`，`review_paths` 仅含 normal 实际产出的 `d*.review.md`，无 `perspective_glob`。
7. §5.12 render，输入 `sections/s_full.md`，**带 --outline**。

#### heavy（= normal + 以下增量）

在 normal 流水线基础上：

- **多 wave 流水线并发**：当前 wave 的所有 §5.3 research 完成并过 §5.4 validator 后，即可启动下一 wave 的 research，同时继续当前 wave 的 review / perspective / supplement。下一 wave 只接收上游**首轮** evidence，不等补研结果；遗留问题由本维度补研写回 evidence 或留在 review.md，报告阶段按 evidence 边界处理。
- 每维度加 §5.6 perspective（按 `lenses[]` 并行，可与 §5.5 review 并行，不等 review）。
- 每维度加 §5.7 supplement-planner + 补研循环。
- 每 wave 末做**波间回顾**（见 §4.4）。
- **报告阶段**：§5.8 report-planner → §5.9 validator → §5.10 report-writer **并行多节**（`write_mode=section`）→ §5.11 report-stitcher 缝合 → §5.5 review（终稿，完整契约）→ §5.12 render，输入 `stitched.md`，带 --outline。

### 4.3 失败与重试

**唯一来源**；§5 各阶段门控只引用本表。

| 阶段 | 失败判据 | 路由 | 上限 |
|---|---|---|---|
| research | evidence validator `ok:false` | errors 回同维 research 修复 | 1 |
| 子报告 review | revise verdict | 不重试，交 supplement-planner（heavy） | 0 |
| supplement research | evidence validator `ok:false` | 回同维 research | 1 |
| report-planner | outline validator `ok:false` | errors 回 planner | 2 |
| report-writer | 越界引用反馈 | 1–2 claim：回 planner 改路由后重派受影响 writer；≥3 claim：视为路由问题，回 planner 重做编排 | 各 1 |
| report-stitcher | blocker | 按 `problem_type`/`location`/`required_fix` 回 planner 或 writer | 1 |
| 终稿 review | revise verdict | 局部：回对应 writer 后重跑 stitcher；全局：回 planner 重做编排 | heavy 2 / normal 1 |

**normal 终稿失败的具体路由**：局部问题回 `full_outline` writer 直接重写 `sections/s_full.md`；全局问题回 planner 重做 outline 后重写（无 stitcher）。

**超预算**：失败超过上限时，在终稿标注「质量受限」并完成流程，不要无限循环。

### 4.4 异常处理

- 角色超时 / 返回错误 → 重试一次；仍失败则跳过并在终稿说明。
- 用户中途修改 query → 终止当前流程，从 §4.1 重启。
- plan 需追加新维度 / 调整 depends_on → 只阻塞受影响的新维度，不影响已合法启动的 wave。
- **波间回顾（heavy）**：每 wave 的 review / perspective / 必要补研全部完成后做一次检查，只处理研究失败、validator 失败或用户改 query 导致的流程异常；perspective 不在此追加新维度。

## 5. 阶段库

每个角色只在此描述一次：**作用** + **payload** + **门控**。是否运行、运行几次、顺序——全由 §4 决定，本节不写档位。所有 payload 第一行均为 `先读取 {plugin_role_dir}/<role>.md 并严格遵守。`（见 §2.2）。

### 5.1 scout

**作用**：预检需求，产出 briefing，含档位推荐（`recommended_mode` + `mode_rationale`）供 §4.1 定档，及 `user_confirmations_needed`（口径澄清）供 §4.1.1 澄清门。

```text
先读取 {plugin_role_dir}/scout.md 并严格遵守。

原始需求:{query}
report_dir:{report_dir 绝对路径}

请按 scout agent 契约产出 briefing，并写入：
{report_dir}/briefing.json
```

**门控**：读 `briefing.json` 做存在性与调度字段检查，并据 `user_confirmations_needed` 执行 §4.1.1 澄清门。

### 5.2 plan

**作用**：判定报告格式、拆解研究维度、规划 wave/depends_on 与 lenses，并写回 `plan.json.mode` 作为后续分支依据。

```text
先读取 {plugin_role_dir}/plan.md 并严格遵守。

原始需求:{query}
report_dir:{report_dir 绝对路径}
plugin_skills_dir:{plugin_skills_dir}
briefing_path:{report_dir}/briefing.json
mode:{最终确定的 mode}
user_clarification_answers:{qid: option_id, ...}   # §4.1.1 澄清门用户回答；无则留空

请按 plan agent 契约完成报告格式判定、研究维度拆解、wave/depends_on 规划与 lenses 规划。
输出：
- {report_dir}/blueprint.json
- {report_dir}/plan.json
```

**门控**：读 `blueprint.json` / `plan.json`，只取调度字段：mode、dimensions、key_questions、sources、depth、time_sensitivity、wave、depends_on、lenses。

### 5.3 research

**作用**：按维度取证，产出 `sub_reports/d{N}.evidence.json`——后续一切的事实底座。

**payload `mode`**：`initial`（normal/heavy 初始研究）/ `supplement`（补研）/ `quick`。同 wave 内多维度并行派发；派发前把 `key_questions` 转 `kq1/kq2/…`，并把 `depends_on` 对应的上游 evidence 路径填入 `upstream_evidence`。

```text
先读取 {plugin_role_dir}/research.md 并严格遵守。

原始需求:{query}
mode:{initial|supplement|quick}

report_dir:{report_dir 绝对路径}
dimension_id:{dimension_id}
plugin_skills_dir:{plugin_skills_dir}

name:{name}
description:{description}
key_questions:
- kq1: {question_1}
- kq2: {question_2}
focus:{focus}
context_from_briefing:{context_from_briefing}
sources:{sources}
depth:{depth}
time_sensitivity:{time_sensitivity}
upstream_evidence:
- {上游 evidence.json 绝对路径；无依赖则留空}

来源纪律:搜索入口按 sources category 选择对应相关的 skill；source.url 写原始 URL。

schema_path:{plugin_skills_dir}/sn-deep-research/schemas/evidence.schema.md
output_path:{report_dir}/sub_reports/{dimension_id}.evidence.json
```

**supplement 模式差异**：`mode: supplement`，并以补研计划替代研究字段——传 `existing_evidence_path:{report_dir}/sub_reports/{dimension_id}.evidence.json` 与 `supplement_plan_path:{report_dir}/sub_reports/{dimension_id}.supplement_plan.json`；`sources/depth/time_sensitivity` 与本维度 initial 同值（沿用同一停止门槛与时效窗口），逐条更细来源以 `supplement_plan.json` 的 `suggested_sources` 为准。

**quick 派发纪律（controller 必须遵守）**：

- **不得追加「交叉核实 / 多源确认 / 务必核实」类要求**：`来源纪律` 行沿用模板原句。quick 停止门槛是 skim（每 kq 一个可靠来源），交叉核实会破坏快速性，research agent 的 quick 段也会视这类指令为不适用。
- **保持查证型 scope**：`key_questions` 精简（默认单 kq=原始需求，最多拆 2–3 个窄 kq）。天然需多来源拼装（逐实体多属性画像、需对比分析）的应判 normal，不要把宽 scope 塞进 quick。
- **保持 skim 但不忽略冲突**：每 kq 至少 1 个可靠来源即停；优先权威来源。首选若为 tertiary 且正文给出可抓取的一手/二手出处、抓取不会明显扩大范围，则优先抓取替代/补充；出处不可抓取/付费墙/JS 渲染失败/会扩大任务时，tertiary 可作为 quick 来源。
- **不主动追 refute，但不得丢弃**：不要求铺开反方搜索；但来源中自然出现的冲突、否定、例外或口径分歧必须抽成 `refute`/`neutral` claim 或 `writing_context`。

**门控**：失败处理见 §4.3。

### 5.4 evidence validator

**作用**：controller 对 evidence 做 schema 二次校验，守门后续阶段。

```bash
python3 {plugin_skills_dir}/sn-deep-research/scripts/validate_evidence.py \
  {report_dir}/sub_reports/d{N}.evidence.json
```

**门控**：`ok:true` → 进入后续（§5.5 review、§5.6 perspective，可并行）；`ok:false` → 见 §4.3。

### 5.5 review（子报告 / 终稿 共用此角色）

**作用**：审 evidence 与终稿的口径、缺口与引用纪律。`审查类型=子报告 evidence 审查` → 产出 `d{N}.review.md` 供 supplement-planner 聚合（本步不触发 research）；`审查类型=终稿 review` → 检查整体逻辑、引用纪律、冲突/gap surface 与 evidence 边界。

**子报告审查 payload**：

```text
先读取 {plugin_role_dir}/review.md 并严格遵守。

原始需求:{query}
审查类型:子报告 evidence 审查

report_dir:{report_dir 绝对路径}
plugin_skills_dir:{plugin_skills_dir}
dimension_id:{dimension_id}
evidence_path:{report_dir}/sub_reports/{dimension_id}.evidence.json
output_path:{report_dir}/sub_reports/{dimension_id}.review.md

key_questions:
- kq1: {question_1}
- kq2: {question_2}
depth:{depth}
time_sensitivity:{time_sensitivity}
```

**终稿审查 payload**：

```text
先读取 {plugin_role_dir}/review.md 并严格遵守。

原始需求:{query}
审查类型:终稿 review

report_dir:{report_dir 绝对路径}
plugin_skills_dir:{plugin_skills_dir}
stitched_path:{report_dir}/stitched.md          # heavy；normal 传 {report_dir}/sections/s_full.md
outline_path:{report_dir}/outline.json
evidence_paths:
- {report_dir}/sub_reports/d1.evidence.json
- ...
review_paths:
- {report_dir}/sub_reports/d1.review.md
- ...
perspective_glob:{report_dir}/sub_reports/d*.perspectives/*.md   # 仅 heavy；normal 省略

请按 review agent 的终稿审查契约检查整体逻辑、引用纪律、冲突/gap surface 与 evidence 边界。
```

**门控**：见 §4.3。

### 5.6 perspective

**作用**：按维度 `lenses[]` 做覆盖检查，surface evidence 未覆盖的视角。`lenses[]` 为空则跳过。

```text
先读取 {plugin_role_dir}/perspective.md 并严格遵守。

原始需求:{query}

report_dir:{report_dir 绝对路径}
plugin_skills_dir:{plugin_skills_dir}
dimension_id:{dimension_id}
dimension_name:{name}
key_questions:
- kq1: {question_1}
- kq2: {question_2}
focus:{focus}
lens:{"axis":"{lens.axis}","value":"{lens.value}","rationale":"{lens.rationale}"}

evidence_path:{report_dir}/sub_reports/{dimension_id}.evidence.json
output_path:{report_dir}/sub_reports/{dimension_id}.perspectives/{lens.axis}_{lens.value}.md
```

### 5.7 supplement-planner

**作用**：按维度聚合 review/perspective 的缺口，产出补研计划。controller 不读 review/perspective 内容，只据本计划决定是否补研。

```text
先读取 {plugin_role_dir}/supplement-planner.md 并严格遵守。

原始需求:{query}

report_dir:{report_dir 绝对路径}
plugin_skills_dir:{plugin_skills_dir}
plan_path:{report_dir}/plan.json
target_dimensions:["{dimension_id}"]
schema_path:{plugin_skills_dir}/sn-deep-research/schemas/supplement_plan.schema.md
output_path:{report_dir}/sub_reports/{dimension_id}.supplement_plan.json
```

**门控**：`supplement_items[]` 为空 → 本维度不补研；非空 → 派 §5.3 research(`mode=supplement`)，补研后对该维度重跑 §5.4 validator + 重派 §5.5 子报告 review 覆盖写出新 `review.md`；不回溯已启动的下一 wave。

### 5.8 report-planner

**作用**：消费各维 evidence 边界，编排 outline 与 per-section evidence subsets。

```text
先读取 {plugin_role_dir}/report-planner.md 并严格遵守。

原始需求:{query}

report_dir:{report_dir 绝对路径}
plugin_skills_dir:{plugin_skills_dir}
briefing_path:{report_dir}/briefing.json
blueprint_path:{report_dir}/blueprint.json
plan_path:{report_dir}/plan.json
evidence_paths:
- {report_dir}/sub_reports/d1.evidence.json
- {report_dir}/sub_reports/d2.evidence.json
- ...
schema_path:{plugin_skills_dir}/sn-deep-research/schemas/outline.schema.md

output_outline:{report_dir}/outline.json
output_subsets_dir:{report_dir}/sections/
```

### 5.9 outline validator

**作用**：controller 对 outline + subsets 做二次校验，守门写作阶段。

```bash
python3 {plugin_skills_dir}/sn-deep-research/scripts/validate_outline.py \
  {report_dir}/outline.json \
  --subsets {report_dir}/sections/ \
  --evidence {report_dir}/sub_reports/d1.evidence.json {report_dir}/sub_reports/d2.evidence.json ...
```

**门控**：`ok:true` → 读 `outline.json`，只取 `sections[].id` 用于调度 writer；`ok:false` → 见 §4.3。

### 5.10 report-writer

**作用**：写章节正文。`write_mode`：

- `section`（heavy）：按 `outline.sections[].id` 并行多 writer，各节只依赖 outline + 自己的 `evidence_subset`，接缝交 stitcher。
- `full_outline`（normal）：单 writer，读 outline + 全部 subset，整篇出。
- `synthesis`（quick）：单 writer，读 `d*.evidence.json` 直接综合。

```text
先读取 {plugin_role_dir}/report-writer.md 并严格遵守。

原始需求:{query}

report_dir:{report_dir 绝对路径}
plugin_skills_dir:{plugin_skills_dir}
section_id:{section_id}                          # 整篇模式（full_outline/synthesis）用 s_full
write_mode:{section|full_outline|synthesis}

outline_path:{report_dir}/outline.json          # synthesis(quick) 省略（无 outline）
evidence_subset_path:{report_dir}/sections/{section_id}.evidence_subset.json   # 仅 section(heavy)；full_outline 读全部 s*.evidence_subset.json、synthesis 读 d*.evidence.json（writer 自读）
output_path:{report_dir}/sections/{section_id}.md
```

**门控**：越界引用反馈处理见 §4.3。

### 5.11 report-stitcher

**作用**：缝合各节为全文并校准 L0 / 接缝 / 术语 / 视觉。只报告 blocker，不决定回派谁。

```text
先读取 {plugin_role_dir}/report-stitcher.md 并严格遵守。

原始需求:{query}

report_dir:{report_dir 绝对路径}
plugin_skills_dir:{plugin_skills_dir}
outline_path:{report_dir}/outline.json
sections_dir:{report_dir}/sections/
output_path:{report_dir}/stitched.md
```

**门控**：blocker 按 `problem_type`/`location`/`required_fix` 回 planner 或 writer（见 §4.3）。

### 5.12 render（sn-prepare-citations 脚本）

**作用**：去重脚注、生成编号引用，产出 `report.md` 与 `citations.json`。

```bash
python3 {plugin_skills_dir}/sn-prepare-citations/scripts/prepare_citations.py \
  --report {输入正文} \
  --evidence {report_dir}/sub_reports/d*.evidence.json \
  [--outline {report_dir}/outline.json] \
  --output {report_dir}/report.md
```

| mode | `--report` 输入 | `--outline` |
|---|---|---|
| heavy | `{report_dir}/stitched.md` | 带 |
| normal | `{report_dir}/sections/s_full.md` | 带 |
| quick | `{report_dir}/sections/s_full.md` | 省略（无 outline.json） |

**门控**（检查 stdout JSON）：

- `orphan_citations` 非空 → 不交付，回 writer/stitcher 修正。
- `claim_id_leakage.unresolved` 非空 → 不交付，回 writer 修正 `[^dN.cM]`。
- `claim_id_leakage.resolved` 非空但 `unresolved` 为空 → 可继续，记录警告。
- 无 orphan / unresolved → 完成。

## 6. 附录：controller 上下文边界

| 文件 | controller 是否读取 |
|---|---|
| `briefing.json` | 是：存在性和调度字段检查（quick 无） |
| `blueprint.json` / `plan.json` | 是：调度依据（quick 无 plan.json，controller 直接持有 mode） |
| `outline.json` | 是（normal/heavy）：只取 `sections[].id` |
| `sub_reports/d*.evidence.json` | 否 |
| `sub_reports/d*.review.md` | 否 |
| `sub_reports/d*.perspectives/*.md` | 否 |
| `sub_reports/d*.supplement_plan.json` | 否：只接收角色状态摘要 |
| `sections/*.evidence_subset.json` | 否 |
| `sections/*.md` | 否 |
| `stitched.md` | 否 |
| `report.md` | 否：完成时给用户路径 |

quick 模式无 `briefing/blueprint/plan/outline` 与 `sections/*.evidence_subset.json`、无 `stitched`；quick/normal 的整篇产物为 `sections/s_full.md`（controller 不读取，只在渲染时作为 `--report` 输入路径）。
