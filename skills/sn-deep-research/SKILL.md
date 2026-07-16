---
name: sn-deep-research
description: 用于用户请求深度研究、系统性研究、竞品分析、方案对比、趋势分析或事实核查时。**遇到以下任一情况就主动使用本 skill，不要自行搜几条就回答**：①用户出现触发词：深度研究 / 深度调研 / 深入研究 / 全面研究 / 系统研究 / 调研 / 调查 / 尽调 / 行业研究 / 市场研究 / 竞品分析 / 政策研究 / 技术研究 / 趋势研究 / 事实核查 / 写一份研究报告 / 调研报告 / 深度报告 / research / deep research；②请求需要跨多来源取证、多维度对比、交叉验证才能给出可靠结论；③用户要求产出报告、白皮书、行业分析或尽调文档；④话题涉及最新政策/市场/产品/价格/法规，需要系统核查。明确要求核验来源的单点事实可走 quick；无核验要求的简单常识问答不使用。模糊或宽泛的"研究/了解一下 X"也优先触发。仅不用于：一句话摘要、已给定单一来源的整理、纯文字润色改写。
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

**语言锚定（全档位、全流程硬约束）**：controller 在首次派发前只解析一次请求级输出语言，规范化为 BCP 47 标签并保存为 `language`。用户明确指定的输出语言优先；否则使用原始 query 的主要指令语言（例如简体中文 `zh-Hans`、繁体中文 `zh-Hant`、英文 `en`、日文 `ja`）。不要因专名、代码、引用、搜索词或来源语言改变该判断；混合语言且无显式要求时，以用户提出任务和约束所用的主要自然语言为准。

- controller 的进度更新、档位/格式确认、澄清问题、错误/降级说明和最终交付回复都使用 `language`。
- 每条角色 payload 都必须显式传递 `language:{language}`；角色不得从自己的提示词、上游文件、来源或搜索结果重新推断语言。缺少 `language` 时不得派发。
- 所有角色自行撰写的自然语言产物与 completion reply 都使用 `language`。来源原始标题/逐字引语、专名、URL、代码、ID、schema key/枚举可保持原样；搜索可以使用任意有助取证的语言。
- 用户在运行中明确要求切换输出语言时，controller 更新请求级 `language`，之后的派发使用新值；已经生成且会进入终稿的自然语言产物必须用新语言重做，不能把多种输出语言直接拼接。

**环境配置分级**（任务开始前，controller 处理一次）：

**Tier 1 — 强制能力，必须探测**：文件读写、命令执行、网页搜索、网页抓取。controller 建目录 / 跑 validator / 调脚本、取证角色联网取证都依赖它们，是产出可靠研究的硬前提。**探测到任一未就绪 → 暂停，提醒用户配置 / 启用，在具备前不派发任何角色。**

**Tier 2 / Tier 3 — 可选配置，不探测但须告知 + 确认**：controller 不探测（此刻尚不知会用哪些来源，凭证又是 per-skill 环境变量、调用才知有无）。但**必须一次性告知用户：下列可选项未配置会降级、影响效果，请确认是否继续**（或先配置再跑）；可与 §4.1 档位确认合并为同一次询问。确认后照常派发，缺失项由各角色按「能力降级契约」自行兜底。

**统一凭证配置**：搜索、社媒、金融、学术与图片生成所需的 API key / token / cookie 统一建议写在仓库根目录 `.env`（参考 `.env.example`），由 runtime 或用户在执行前加载为同名环境变量。skill 与脚本只读取环境变量；不要把密钥写入 payload、命令行参数、报告正文、日志或 transcript。

| 层级 | 可选配置（环境变量） | 缺失影响 |
|---|---|---|
| Tier 2 | `SN_IMAGE_GEN_API_KEY` / `SN_API_KEY` | 无 AI 概念配图，输出无图版 |
| Tier 2 | `ZHIHU_COOKIE` / `DOUYIN_COOKIE` / `BILIBILI_COOKIE` | 知乎/抖音/B站的脚本检索能力受限，转通用搜索兜底；小红书/微博当前本就使用 browser-use / 公开网页兜底 |
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
3. **语言锚点必传**：每条含 `language:{language}`；role 必须使用该参数。controller 面向用户的过程消息也必须使用同一语言。
4. **自包含**：明确目标、输入/输出路径、schema/validator、边界与运行上下文；不假设 role 能看到主对话。
5. **工具名中性**：payload 与角色文件中的「读取/写入/搜索/抓取/命令执行」均指当前 runtime 的等价能力，不假定具体工具名。
6. **并行收敛**：同阶段互不依赖的角色尽量同批派发；有 validator / review 门禁 / depends_on 时再分批。

## 3. 报告目录

所有产物落在**单一报告目录**下，子 agent 之间只经文件通信。命名为 `YYYY-MM-DD-{topic}-{hex4}`，其中 `{hex4}` 是随机 4 位十六进制运行号——**同一需求可能跑多次**，用它区分各次运行、避免目录互相覆盖。下文统一以 `{report_dir}` 指代解析后的绝对路径。

**controller 起步只建空目录**，其余文件由各阶段写入：

```bash
run=$(openssl rand -hex 2 2>/dev/null || printf '%04x' "$RANDOM")
report_dir="$PWD/deep-research-reports/$(date +%F)-{topic}-$run"
mkdir -p "$report_dir"/sub_reports "$report_dir"/board "$report_dir"/sections \
  "$report_dir"/content_units "$report_dir"/source_cache
echo "$report_dir"   # 记录为后续所有 payload 的 report_dir
```

最终骨架（`[N/H]`=仅 normal/heavy，`[H]`=仅 heavy，无标=全档；quick 仅最小子集）：

```text
{report_dir}/
├── briefing.json / format_proposal.json / format.json / plan.json   [N/H]
├── source_cache/  本次报告的不可变来源正文快照
├── sub_reports/   每维度 dN：evidence.json · review.md[N/H] · perspectives/[H] · supplement_plan.json[H 或 N-repair]
├── board/         perspective 协作区  [H]
├── outline.json   [N/H]
├── content_units/ 每个 uN：evidence_subset.json · uN.md  [N/H]
├── sections/s_full.md  quick 直出正文
├── stitched.md    [N/H]
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

任一不满足 → normal/heavy（两者都做拆分子任务 + 多源核实）。两者区别在**研究力度**：normal 维度较少、轻量 review；heavy 可为覆盖义务增加更多维度，并加入 perspective、supplement 补研和完整 review。两档都使用同一 content-unit 成品合同，不能靠固定文章骨架区分档位。

**确认纪律（不经确认直接开跑属于违规）**：quick 单独确认档位；normal/heavy 在预研结束后一次性确认档位与最终呈现形式。

- 初判 quick：**不派 scout**，controller 先对原始 query 做一次轻量口径自检——只看「不澄清就会明显误配」的 blocking 级歧义（通常为零）；有则把这句反问折进档位确认里，无则直接向用户确认「建议 quick：单维度 skim 直出，不跑多源核实与报告论证」。确认即定 quick；用户要求升级则改派 scout。
- 初判 normal/heavy：派 scout 产出 `briefing.json`，并由 scout 调用 `sn-report-format-discovery` 产出 `format_proposal.json`。controller 先处理 blocking 澄清，再执行 §4.1.2 格式确认；若用户未显式指定档位，档位推荐与格式放在同一次询问中确认。
- 用户确认后：controller 固化 `format.json`，normal/heavy 由 plan 写回 `plan.json.mode` + `format_id`，作为后续分支与格式一致性依据；quick 无 plan.json，controller 直接持有 mode。

### 4.1.1 澄清门（预研之后，定档/规划之前）

scout 在 briefing 里把**只有用户能定**的口径分歧抽成 `user_confirmations_needed`，三 tier 各有处理：

- **blocking[]**：不澄清无法合理规划。**暂停流程**，把每条 `question` + 各 `options[].label` + `impact_on_plan` 展示给用户反问；收到回答后继续。
- **high_value[]**：有合理默认但确认后更好。展示问题并高亮 `default_if_unanswered.option_id` 对应 option（附 `rationale`）；用户可改可默许，不响应即用默认。
- **optional[]**：静默采用 `default_if_unanswered.option_id`，不打断用户。

用户答案以 `{qid: option_id}` 形式收集，**直接透传给 §5.2 plan 的 `user_clarification_answers` 字段**，不覆写 briefing.json。若 blocking 回答改变了用户目标、受众或使用场景，带这些答案重派 scout 的 format-revision 路径，由它重新调用 `sn-report-format-discovery`，只更新 `format_proposal.json` 后再进入 §4.1.2；否则不重跑。三个 list 均为 `[]` 时本门为空操作。

### 4.1.2 最终呈现形式确认（预研之后，规划之前）

normal/heavy 必须在 plan 和 research 之前确认最终结果的呈现形式。这里的格式是研究报告、学术论文、表格优先报表、决策备忘录或其他用户自定义形式；不是 Markdown 文件后缀，也不是具体章节目录。

1. controller 读取 `format_proposal.json` 的 `recommended_format_id`、`candidates[]` 与 `structure_preference`。展示推荐形式、理由、核心 `defining_features` 及最多两个替代项；另行说明当前主载体偏好是 `required / preferred / auto`，有 requested/custom type 时一并展示，让用户可单独修改。同时展示 scout 推荐档位，不粘贴格式调研来源全文。
2. 用户确认推荐项或选择替代项后，controller 写出 `{report_dir}/format.json`：`container=markdown`、`selected_format=<所选 candidate 原样复制>`、`structure_preference=<format_proposal 中经用户确认的偏好与强度>`、`confirmed_by_user=true`。用户只确认候选形式、不另改主载体时，也必须原样保留 proposal 的 `structure_preference`。
3. 用户提出新的自定义形式或修改 defining features 时，重派 scout 调用 `sn-report-format-discovery` 修订 `format_proposal.json`，再次确认；不要让 scout 或 plan 自己代做格式选择。
4. `format.json` 一经确认即只读。plan、research、report-planner、writer、stitcher、review 不得更换 `selected_format`；只有用户明确改格式时才终止当前流程并从本门重启。

### 4.2 三档流水线

每步指向 §5 阶段库；本节只给顺序与档位偏差。

#### quick（自包含，无 scout/plan/多维度）

1. **构造单维度 d1**：`name=原始需求`、`description=空`、`key_questions=[kq1: 原始需求]`、`focus=空`、`sources=空`（research 自选入口）、`depth=skim`、`time_sensitivity=moderate`、`scope_ownership` 覆盖原始问题、`upstream_inputs=[]` → 派 §5.3 research，`mode=quick`，产出 `sub_reports/d1.evidence.json` 并缓存正文。
2. §5.4 evidence validator（quick 省略 `--plan`）。
3. §5.10 report-writer，`write_mode=quick_synthesis`，读 `sub_reports/d1.evidence.json`，整篇写入 `sections/s_full.md`。
4. §5.12 render，输入 `sections/s_full.md`，**不带 --outline**。

**跳过**：子报告 review / perspective / supplement / report-planner / outline validator / stitcher / 终稿 review。

#### normal（单 wave）

1. §5.1 scout → §4.1.1 澄清门 → §4.1.2 确认档位与最终呈现形式。
2. §5.2 plan（轻量）→ plan validator，读取只读 `format.json`。
3. **每维度并行**：§5.3 research(`mode=initial`) → §5.4 evidence validator → §5.5 review（子报告）。通常不跑 perspective/supplement；若 review=`revise`，仅对该维度调用 §5.7 把硬伤转成 repair supplement plan，再补研、重校验并重审一次。plan 已保证 `depends_on` 为空，故单 wave。
4. §5.8 report-planner（outline v2 + per-unit evidence subsets）→ §5.9 outline validator。
5. 按 `outline.content_units[].id` 派 §5.10 report-writer，`write_mode=write_unit`；互不依赖的 unit 可并行。全部完成后派 §5.11 report-stitcher，写入 `stitched.md`。
6. §5.5 review（终稿，轻量）：输入 `stitched.md`，`review_paths` 仅含 normal 实际产出的 `d*.review.md`，无 `perspective_glob`。
7. §5.12 render，输入 `stitched.md`，带 `--outline` 并服从 `organization_decision` 的摘要/目录开关。

#### heavy（= normal + 以下增量）

在 normal 流水线基础上：

- **覆盖更深但不强造拓扑**：heavy 可按覆盖义务拆出更多 dimensions；所有 `depends_on=[]` 的维度直接并行启动。只有下游检索范围必须消费上游结果时才形成后续 wave。
- **依赖按产物就绪触发**：一个维度完成 initial research、validator、review、perspective、supplement decision，以及必要补研后的最终 validator/review 后，才算 evidence finalized。下游在全部直接上游 finalized 后启动，先读 `key_findings`，再按 `dependency_inputs.scope_rule` 收窄检索。wave 是依赖拓扑的派生标记，不是整波屏障；不相关的维度不互相等待。
- 每维度加 §5.6 perspective（按 `lenses[]` 并行，可与 §5.5 review 并行，不等 review）。
- 每维度的 review 与全部 perspective 完成后再派 §5.7 supplement-planner；必要时进入补研循环。
- **报告阶段**与 normal 使用同一 v2 content-unit 合同；heavy 可拥有更多 units，但不得为了体现档位增加章节或辅助结构。

### 4.3 失败与重试

**唯一来源**；§5 各阶段门控只引用本表。

| 阶段 | 失败判据 | 路由 | 上限 |
|---|---|---|---|
| scout format proposal | `format_proposal.json` 缺失/非法 | 回 scout 修复 proposal | 1 |
| plan | plan validator `ok:false` 或 format binding 不一致 | errors 回 plan 修复 | 1 |
| research | evidence validator `ok:false` | errors 回同维 research 修复 | 1 |
| 子报告 review | revise verdict | heavy 交常规 supplement-planner；normal 仅为该维度生成 repair supplement plan，补研后重校验/重审 | normal 1 / heavy 0 |
| supplement research | evidence validator `ok:false` | 回同维 research | 1 |
| report-planner | outline validator `ok:false` | errors 回 planner | 2 |
| report-writer | unit 合同或越界引用反馈 | 路由问题回 planner；表达/形态问题以 `revise_unit` 重派受影响 unit | 各 1 |
| report-stitcher | blocker | 按 `problem_type`/`location`/`required_fix` 回 planner 或 writer | 1 |
| 终稿 review | revise verdict | 局部：回对应 writer 后重跑 stitcher；全局：回 planner 重做编排 | heavy 2 / normal 1 |

**终稿失败路由**：局部问题用 `revise_unit` 重写受影响 unit 后重跑 stitcher；全局组织问题回 planner 重做 outline 和受影响 units。

**超预算**：失败超过上限时，在终稿标注「质量受限」并完成流程，不要无限循环。

### 4.4 流程变更

- 用户中途修改 query → 终止当前流程，从 §4.1 重启。
- plan 需追加新维度 / 调整 depends_on → 只阻塞受影响的新维度，不影响已合法启动的 wave。
- 已 finalized 的上游 evidence 若因补研发生变化，尚未启动的下游使用新版本；不得让下游消费首轮、随后又被覆盖的 `key_findings`。

## 5. 阶段库

每个角色只在此描述一次：**作用** + **payload** + **门控**。是否运行、运行几次、顺序——全由 §4 决定，本节不写档位。所有 payload 第一行均为 `先读取 {plugin_role_dir}/<role>.md 并严格遵守。`（见 §2.2）。

### 5.1 scout

**作用**：预检需求并产出领域 briefing，再调用 `sn-report-format-discovery` 生成最终呈现形式 proposal。scout 负责传递预研上下文，不实现格式发现规则。

```text
先读取 {plugin_role_dir}/scout.md 并严格遵守。

原始需求:{query}
language:{language}
report_dir:{report_dir 绝对路径}
plugin_skills_dir:{plugin_skills_dir}
format_revision_request:{用户对上一版格式候选的修改；首次为空}

请按 scout agent 契约写入 briefing，并调用 `sn-report-format-discovery` 写入 format proposal：
- {report_dir}/briefing.json
- {report_dir}/format_proposal.json
```

**门控**：读 `briefing.json` 做存在性与调度字段检查，据 `user_confirmations_needed` 执行 §4.1.1；再读取 `format_proposal.json` 的小字段执行 §4.1.2。

### 5.2 plan

**作用**：读取已确认的最终呈现形式，拆解研究维度、规划 wave/depends_on 与 lenses，并写回 `plan.json.mode` + `format_id`。不再做格式调研或格式选择。

```text
先读取 {plugin_role_dir}/plan.md 并严格遵守。

原始需求:{query}
language:{language}
report_dir:{report_dir 绝对路径}
plugin_skills_dir:{plugin_skills_dir}
briefing_path:{report_dir}/briefing.json
format_path:{report_dir}/format.json
plan_schema_path:{plugin_skills_dir}/sn-deep-research/schemas/plan.schema.md
plan_validator_path:{plugin_skills_dir}/sn-deep-research/scripts/validate_plan.py
format_confirmed:true
mode:{最终确定的 mode}
user_clarification_answers:{qid: option_id, ...}   # §4.1.1 澄清门用户回答；无则留空

请按 plan agent 契约完成研究维度拆解、wave/depends_on 规划与 lenses 规划，只输出：
- {report_dir}/plan.json
```

**门控**：controller 再运行：

```bash
python3 {plugin_skills_dir}/sn-deep-research/scripts/validate_plan.py \
  {report_dir}/plan.json \
  --format {report_dir}/format.json
```

`ok:true` 后只取调度字段：mode、dimensions、key_questions、sources、depth、time_sensitivity、scope_ownership、wave、depends_on、dependency_inputs、lenses。

### 5.3 research

**作用**：按维度取证，产出 `sub_reports/d{N}.evidence.json`——后续一切的事实底座。

**payload `mode`**：`initial`（normal/heavy 初始研究）/ `supplement`（补研）/ `quick`。派发前把 `key_questions` 转 `kq1/kq2/…`。`depends_on=[]` 的维度可直接并行；有依赖的维度须等全部直接上游 evidence finalized，并把 `dependency_inputs` 展开为结构化 `upstream_inputs`。

```text
先读取 {plugin_role_dir}/research.md 并严格遵守。

原始需求:{query}
language:{language}
mode:{initial|supplement|quick}

report_dir:{report_dir 绝对路径}
dimension_id:{dimension_id}
plugin_skills_dir:{plugin_skills_dir}
plan_path:{report_dir}/plan.json                 # quick 省略
source_cache_path:{report_dir}/source_cache
source_snapshot_tool:{plugin_skills_dir}/sn-deep-research/scripts/source_snapshot.py

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
scope_ownership:{scope_ownership object}
upstream_inputs:
- dimension_id:{dependency_inputs[].dimension_id}
  evidence_path:{report_dir}/sub_reports/{dependency_inputs[].dimension_id}.evidence.json
  needed_for:{dependency_inputs[].needed_for}
  consume:key_findings
  scope_rule:{dependency_inputs[].scope_rule}
# 无依赖时为 []

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
  {report_dir}/sub_reports/d{N}.evidence.json \
  --require-version 1.2 \
  --expected-mode {initial|supplement} \
  --source-cache {report_dir}/source_cache \
  --plan {report_dir}/plan.json \
  [--upstream-evidence {把本维度全部 upstream_inputs.evidence_path 展开为独立参数}]
```

方括号行只在本维度存在直接依赖时加入，执行前必须移除括号并展开全部上游路径；无依赖时整行省略。quick 传 `--require-version 1.2 --expected-mode quick --source-cache ...`，但省略 `--plan` 与 `--upstream-evidence`。`expected-mode` 必须使用本次实际派发值，不得从 evidence 自己读取。

**门控**：`ok:true` → 进入后续（§5.5 review、§5.6 perspective，可并行）；`ok:false` → 见 §4.3。

### 5.5 review（子报告 / 终稿 共用此角色）

**作用**：审 evidence 与终稿的口径、缺口与引用纪律。`审查类型=子报告 evidence 审查` → 产出 `d{N}.review.md` 供 supplement-planner 聚合（本步不触发 research）；`审查类型=终稿 review` → 检查整体逻辑、引用纪律、冲突/gap surface 与 evidence 边界。

**子报告审查 payload**：

```text
先读取 {plugin_role_dir}/review.md 并严格遵守。

原始需求:{query}
language:{language}
审查类型:子报告 evidence 审查

report_dir:{report_dir 绝对路径}
plugin_skills_dir:{plugin_skills_dir}
dimension_id:{dimension_id}
evidence_path:{report_dir}/sub_reports/{dimension_id}.evidence.json
source_cache_path:{report_dir}/source_cache
source_snapshot_tool:{plugin_skills_dir}/sn-deep-research/scripts/source_snapshot.py
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
language:{language}
审查类型:终稿 review

report_dir:{report_dir 绝对路径}
plugin_skills_dir:{plugin_skills_dir}
stitched_path:{report_dir}/stitched.md
format_path:{report_dir}/format.json
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
language:{language}

report_dir:{report_dir 绝对路径}
plugin_skills_dir:{plugin_skills_dir}
dimension_id:{dimension_id}
dimension_name:{name}
key_questions:
- kq1: {question_1}
- kq2: {question_2}
focus:{focus}
lens_id:l{该 dimension 内 1-based 顺序号}
lens:{"axis":"{lens.axis}","value":"{lens.value}","rationale":"{lens.rationale}"}

evidence_path:{report_dir}/sub_reports/{dimension_id}.evidence.json
output_path:{report_dir}/sub_reports/{dimension_id}.perspectives/l{同一顺序号}.md
```

文件名只使用 controller 生成的稳定 `lens_id`，不得把 axis/value 拼入路径。

### 5.7 supplement-planner

**作用**：按维度聚合 review/perspective 的缺口，产出补研计划。controller 不读 review/perspective 内容，只据本计划决定是否补研。

```text
先读取 {plugin_role_dir}/supplement-planner.md 并严格遵守。

原始需求:{query}
language:{language}

report_dir:{report_dir 绝对路径}
plugin_skills_dir:{plugin_skills_dir}
plan_path:{report_dir}/plan.json
target_dimensions:["{dimension_id}"]
schema_path:{plugin_skills_dir}/sn-deep-research/schemas/supplement_plan.schema.md
output_path:{report_dir}/sub_reports/{dimension_id}.supplement_plan.json
```

**门控**：controller 只读该 JSON 的 `dimension_id`、`supplement_items[].id/status` 与 `deferred_items` 数量，并与角色回复的 counts 对照。`supplement_items[]` 为空 → 本维度 evidence 可 finalized；非空且全部为 `pending` → 派 §5.3 research(`mode=supplement`)，补研后重读 status、重跑 §5.4 validator 并重派 §5.5 子报告 review。完成时不得残留 `pending`；`partial|no_data|out_of_scope` 必须已写入 evidence 的 schema-valid writing_context，且最终 validator/review 通过后才可 finalized。依赖它的下游在 finalized 前不得启动。

### 5.8 report-planner

**作用**：消费已确认 `format.json` 与各维 evidence 边界；内容范式决定信息如何推进，`structure_preference` 与 evidence shape 决定主信息载体，输出 outline v2 与 per-unit evidence subsets。不得使用固定范式到载体的配对表。

```text
先读取 {plugin_role_dir}/report-planner.md 并严格遵守。

原始需求:{query}
language:{language}

report_dir:{report_dir 绝对路径}
plugin_skills_dir:{plugin_skills_dir}
briefing_path:{report_dir}/briefing.json
format_path:{report_dir}/format.json
plan_path:{report_dir}/plan.json
evidence_paths:
- {report_dir}/sub_reports/d1.evidence.json
- {report_dir}/sub_reports/d2.evidence.json
- ...
schema_path:{plugin_skills_dir}/sn-deep-research/schemas/outline.schema.md

output_outline:{report_dir}/outline.json
output_subsets_dir:{report_dir}/content_units/
```

### 5.9 outline validator

**作用**：controller 对 outline + subsets 做二次校验，守门写作阶段。

```bash
python3 {plugin_skills_dir}/sn-deep-research/scripts/validate_outline.py \
  {report_dir}/outline.json \
  --require-version 2.0 \
  --language {language} \
  --subsets {report_dir}/content_units/ \
  --format {report_dir}/format.json \
  --evidence {report_dir}/sub_reports/d1.evidence.json {report_dir}/sub_reports/d2.evidence.json ...
```

**门控**：只有 `--require-version 2.0` 下 `ok:true` 才进入写作；随后只取 `content_units[].id`、`organization_decision.opening_summary` 与 `organization_decision.toc` 用于调度 writer/render。legacy v1 仅供独立校验既有报告，不能进入新 controller 路径。

### 5.10 report-writer

**作用**：执行单个 content unit，或在 quick 下直接综合。`write_mode`：

- `write_unit`（normal/heavy）：只读取指定 unit 与自己的 evidence subset。
- `revise_unit`（normal/heavy）：按 review/stitcher 的局部反馈覆盖指定 unit。
- `quick_synthesis`（quick）：读取 `d*.evidence.json` 直接输出简洁答案。

```text
先读取 {plugin_role_dir}/report-writer.md 并严格遵守。

原始需求:{query}
language:{language}

report_dir:{report_dir 绝对路径}
plugin_skills_dir:{plugin_skills_dir}
write_mode:{write_unit|revise_unit|quick_synthesis}

# normal/heavy
content_unit_id:{unit_id}
outline_path:{report_dir}/outline.json
format_path:{report_dir}/format.json
subset_path:{report_dir}/content_units/{unit_id}.evidence_subset.json
output_path:{report_dir}/content_units/{unit_id}.md

# 仅 revise_unit
draft_path:{report_dir}/content_units/{unit_id}.md
revision_instructions:{review/stitcher 的局部修订要求}

# quick（省略上面五项）
evidence_paths:[{report_dir}/sub_reports/d1.evidence.json]
output_path:{report_dir}/sections/s_full.md
```

**门控**：越界引用反馈处理见 §4.3。

### 5.11 report-stitcher

**作用**：按 `organization_decision` 组装 content units，并校准可选 L0、术语和结构合同。主结构可以是矩阵、时间线、清单、问答或其他 unit，不强制文章化。

```text
先读取 {plugin_role_dir}/report-stitcher.md 并严格遵守。

原始需求:{query}
language:{language}

report_dir:{report_dir 绝对路径}
plugin_skills_dir:{plugin_skills_dir}
outline_path:{report_dir}/outline.json
format_path:{report_dir}/format.json
content_units_dir:{report_dir}/content_units/
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
  [--no-l0] [--no-toc] \
  --output {report_dir}/report.md
```

| mode | `--report` 输入 | `--outline` |
|---|---|---|
| heavy | `{report_dir}/stitched.md` | 带 |
| normal | `{report_dir}/stitched.md` | 带 |
| quick | `{report_dir}/sections/s_full.md` | 省略（无 outline.json） |

normal/heavy 的 L0 已由 stitcher 按 `organization_decision.opening_summary` 写入，因此 render 固定传 `--no-l0`，避免再次生成通用摘要。`organization_decision.toc=false` 时同时传 `--no-toc`；为 true 时不传 `--no-toc`，让脚本替换 stitcher 放置的 TOC placeholder。不得根据 selected format 名称另套摘要/目录默认值。

**门控**（检查 stdout JSON）：

- `orphan_citations` 非空 → 不交付，回 writer/stitcher 修正。
- `claim_id_leakage.unresolved` 非空 → 不交付，回 writer 修正 `[^dN.cM]`。
- `claim_id_leakage.resolved` 非空但 `unresolved` 为空 → 可继续，记录警告。
- 无 orphan / unresolved → 完成。

## 6. 附录：controller 上下文边界

| 文件 | controller 是否读取 |
|---|---|
| `briefing.json` | 是：存在性和调度字段检查（quick 无） |
| `format_proposal.json` | 是：只读推荐形式、候选及 defining_features（quick 无） |
| `format.json` / `plan.json` | 是：取确认状态、structure preference 和调度字段；具体合法性由 validator 守门（quick 无 plan.json） |
| `outline.json` | 是（normal/heavy）：只取 `content_units[].id` 与 organization decision 的 render 开关 |
| `sub_reports/d*.evidence.json` | 否 |
| `sub_reports/d*.review.md` | 否 |
| `sub_reports/d*.perspectives/*.md` | 否 |
| `sub_reports/d*.supplement_plan.json` | 是（heavy 或 normal repair）：只读 dimension_id、supplement item id/status 和 deferred 数量用于调度，不读描述正文 |
| `content_units/*.evidence_subset.json` | 否 |
| `content_units/*.md` | 否 |
| `sections/s_full.md` | 否（仅 quick） |
| `stitched.md` | 否 |
| `report.md` | 否：完成时给用户路径 |

quick 模式无 `briefing/format_proposal/format/plan/outline/content_units/stitched`；其正文为 `sections/s_full.md`。normal/heavy 均以 `stitched.md` 作为 render 输入。
