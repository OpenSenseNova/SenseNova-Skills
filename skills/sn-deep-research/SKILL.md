---
name: sn-deep-research
description: 用于用户请求深度研究、系统性研究、竞品分析、方案对比、趋势分析或事实核查时。**遇到以下任一情况就主动使用本 skill，不要自行搜几条就回答**：①用户出现触发词：深度研究 / 深度调研 / 深入研究 / 全面研究 / 系统研究 / 调研 / 调查 / 尽调 / 行业研究 / 市场研究 / 竞品分析 / 政策研究 / 技术研究 / 趋势研究 / 事实核查 / 写一份研究报告 / 调研报告 / 深度报告 / research / deep research；②请求需要跨多来源取证、多维度对比、交叉验证才能给出可靠结论；③用户要求产出报告、白皮书、行业分析或尽调文档；④话题涉及最新政策/市场/产品/价格/法规，需要系统核查。无核验要求的简单常识问答不使用。模糊或宽泛的"研究/了解一下 X"也优先触发。仅不用于：一句话摘要、已给定单一来源的整理、纯文字润色改写。
---

# 深度研究（多 Agent 深度研究编排）

你是深度研究总控。职责是**调度**专家角色完成研究、写作与渲染。

阅读地图：§1 总则 → §2 派发机制 → §3 报告目录 → **§4 档位选择器（决定跑什么）** → **§5 阶段库（每个角色怎么派，仅一次）** → §6 附录。运行时先按 §4 选定本次档位的流水线，再按流水线逐步跳转 §5 的对应条目。

## 1. 总则

**控制器铁律**：

- **只调度，不读大文件**：evidence / 章节 / outline 等大文件通过绝对路径传给角色自读；你只读调度所需的小字段（见 §6）。
- **所有文件路径使用绝对路径**。
- **通过文件路径传递内容**，不在消息里粘贴大段正文。
- **子角色内部检查透明**：各子 agent 自行完成交付检查和必要修复。
- **语言锚定（全档位、全流程硬约束）**：你在首次派发前只确定一次请求级输出语言并保存为 `language`。用户明确指定的输出语言优先；否则使用原始 query 的主要指令语言。不要因专名、代码、引用、搜索词或来源语言改变该判断；混合语言且无显式要求时，以用户提出任务和约束所用的主要自然语言为准。
- **格式锚定（全档位、全流程硬约束）**：你在首次派发前只确定一次请求级最终形式并保存为一个非空字符串 `format`。用户明确指定的形式优先；否则使用 `report`。常见值如 `report`、`paper`、`table`、`memo`，也允许用户自己的短名称。`format` 只存在于本次运行上下文和角色 payload，不创建 `format.json`、proposal 或配套 schema。
- 你的进度更新、档位/格式确认、澄清问题、错误/降级说明和最终交付回复都使用 `language`。
- 你的子任务 payload 都必须显式传递 `language:{language}` 与 `format:{format}`。
- 用户在运行中明确要求切换输出语言时，你需要更新 `language`，之后的派发使用新值。
- 用户在运行中明确要求切换最终形式时，你需要更新 `format`，之后的派发使用新值；已经生成且会进入终稿的编排或正文产物必须按新形式重做。

**环境配置分级**（任务开始前，你统一处理一次）：

**Tier 1 — 强制能力，必须探测**：文件读写、命令执行、网页搜索、网页抓取，是产出可靠研究的硬前提。**探测到任一未就绪 → 暂停，提醒用户配置 / 启用，在具备前不派发任何角色。**

**Tier 2 / Tier 3 — 可选配置，不探测但须告知 + 确认**：你在开始时**一次性告知用户：下列可选项未配置会降级、影响效果，请确认是否继续**（或先配置再跑）。

**统一凭证配置**：搜索、社媒、金融、学术与图片生成所需的 API key / token / cookie 统一建议写在仓库根目录 `.env`（参考 `.env.example`），由 runtime 或用户在执行前加载为同名环境变量。skill 与脚本只读取环境变量；不要把密钥写入 payload、命令行参数、报告正文、日志或 transcript。

| 层级 | 可选配置（环境变量） | 缺失影响 |
|---|---|---|
| Tier 2 | `SN_IMAGE_GEN_API_KEY` / `SN_API_KEY` | 无 AI 概念配图，输出无图版 |
| Tier 2 | `ZHIHU_COOKIE` / `DOUYIN_COOKIE` / `BILIBILI_COOKIE` | 知乎/抖音/B站的脚本检索能力受限，转通用搜索兜底；小红书/微博当前本就使用 browser-use / 公开网页兜底 |
| Tier 2 | `TIKHUB_TOKEN`（Twitter/X）、`YOUTUBE_API_KEY` | 对应平台无站内检索，转通用搜索兜底（Reddit 免认证） |
| Tier 3 | GitHub token、`HF_TOKEN`、`SO_API_KEY`、学术 API key | 仅速率受限、更慢更易限流（GitHub `code` 搜索无 token 则不可用；arXiv 等开放获取与金融/市场/年报等免认证来源无需配置） |

## 2. 子 agent 派发机制

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

你解析到真实的skill路径后，在 payload 中下发给各个子 agent 的路径必须是解析后的绝对路径。

### 2.2 payload 契约

1. **角色加载**：每条 payload 第一行必须是 `先读取 {plugin_role_dir}/<role>.md 并严格遵守。`
2. **原始 query**：每条含 `原始需求:{query}`。
3. **语言锚点**：每条含 `language:{language}`。
4. **格式锚点**：每条含 `format:{format}`；role 不创建或查找格式状态文件。
5. **子任务包含**：明确目标、输入/输出路径和任务边界。
6. **工具名中性**：payload 与角色文件中的「读取/写入/搜索/抓取/命令执行」均指当前 runtime 的等价能力，不假定具体工具名。
7. **文件交接**：上游角色写出的内容只传文件路径。派发 Research 时传 `plan_path + dimension_id`，由 Research 自行读取对应 work package。
8. **并行收敛**：同阶段可并行的角色尽量并行派发。

## 3. 报告目录

所有产物落在**单一报告目录**下，子 agent 之间只经文件通信。命名为 `YYYY-MM-DD-{topic}-{hex4}`，其中 `{hex4}` 是随机 4 位十六进制运行号——**同一需求可能跑多次**，用它区分各次运行、避免目录互相覆盖。下文统一以 `{report_dir}` 指代解析后的绝对路径。

**你起步先建报告目录**，随后写入 `request.md` 并启动进度页；其余文件由各阶段写入：

```bash
run=$(openssl rand -hex 2 2>/dev/null || printf '%04x' "$RANDOM")
report_dir="$PWD/deep-research-reports/$(date +%F)-{topic}-$run"
mkdir -p "$report_dir"/sub_reports "$report_dir"/board "$report_dir"/sections \
  "$report_dir"/content_units
echo "$report_dir"   # 记录为后续所有 payload 的 report_dir
```

最终骨架（`[N/H]`=仅 normal/heavy，`[H]`=仅 heavy，无标=全档；quick 仅最小子集）：

```text
{report_dir}/
├── request.md     原始研究请求（启动进度页前必须存在）
├── .workbench/progress.json   进度页实时状态
├── briefing.json   [H]
├── plan.json   [N/H]
├── sub_reports/   每维度 dN：evidence.json · research/过程文件 · review.md[H] · perspectives/[H] · supplement_plan.json[H]
├── board/         perspective 协作区  [H]
├── outline.json   [H]
├── content_units/ 每个 uN：evidence_subset.json · uN.md  [H]
├── sections/s_full.md  quick / normal 一次成文
├── stitched.md    [H]
└── report.md / citations.json   渲染终稿
```

### 3.1 深度研究进度 WebUI（必须在研究开始时启动）

创建 `{report_dir}` 后、进入 §4 启动确认之前，你必须完成以下操作，不得等到研究产物生成后再启动：

1. 写入 `{report_dir}/request.md`，内容包含原始用户需求与启动时间。该文件用于进度页在其他产物尚未出现时识别 Deep Research 工作区。
2. 用共享进度事件脚本写入首个事件，并显式指定 `workflow=deep-research`：

   ```bash
   python3 {plugin_skills_dir}/sn-ppt-standard/scripts/progress_event.py \
     --deck-dir "{report_dir}" \
     --workflow deep-research \
     --stage mode-selection \
     --status running \
     --artifact request.md \
     --label "<使用 language 的简短状态>"
   ```

3. 立即启动或复用 Research Workbench。Deep Research 进度页使用独立的根路由 `/`：

   ```bash
   python3 {plugin_skills_dir}/sn-ppt-standard/scripts/launch_workbench.py \
     --deck-dir "{report_dir}" \
     --product research \
     --progress-route / \
     --source-session-id "${HERMES_SESSION_KEY:-}" \
     --agent-managed 1 \
     --require-webui \
     --host 0.0.0.0
   ```

原生 Windows 环境若无 `python3`，改用 `python`。在 Windows 的 Git Bash / MSYS 下传递根路由 `/` 时，命令前加 `MSYS_NO_PATHCONV=1`，避免路径被改写。

启动结果处理：

- 若返回 `{"status":"ok", ...}`，立即使用请求级 `language` 向用户提供 `research_progress_url`；若该字段不存在，使用兼容字段 `generation_url`。URL 必须指向根路由 `/`，不要提供 PPT 编辑器或 PPT 进度页导航。
- 因使用了 `--require-webui`，helper 不应返回 `skipped`。若返回 `failed` 或等价错误，暂停研究流程并处理 WebUI 启动问题，不要静默继续。
- Deep Research 与 PPT 使用相互独立的进度页。Deep Research skill 只提供 Research Workbench 的根路由。

后续每个主要阶段开始、完成或失败时，继续写入同一个进度文件：

```bash
python3 {plugin_skills_dir}/sn-ppt-standard/scripts/progress_event.py \
  --deck-dir "{report_dir}" \
  --workflow deep-research \
  --stage mode-selection|scout|plan|research|review|report-planner|report-writer|finalizing|done \
  --status running|ok|failed \
  --artifact "<当前主要产物路径>" \
  --label "<使用 language 的简短状态>"
```

## 4. 启动确认与档位选择

**本节是唯一决定跑哪些角色和顺序的地方。Mode 表达流程复杂度。**

### 4.1 开始前一次确认

你在正式开始前先根据原始 query 给出档位建议，把以下内容合并成一次简短启动确认：

1. **输出语言**：展示推断的 `language`，允许用户改；
2. **流程模式**：展示推荐的 quick/normal/heavy 及介绍其简要流程；
3. **最终呈现形式**：展示请求级 `format` 字符串；优先使用用户明确指定的形式，未指定时使用 `report`；
4. **研究范围和口径**：只询问那些不回答就会明显改变研究对象、范围、时点、地域或比较标准的问题；
5. **能力降级**：把 Tier 2/3 可选配置缺失影响并入同一次提示，不另开一轮流程确认。

不得在用户确认 mode 前派 scout、plan 或 research。

启动确认中的研究范围和口径按以下规则处理：

- **必须确认**：只有用户能决定，且不回答就会明显改变研究对象、范围、时点、地域或比较标准。为每项给出简短问题、可选项及其影响，和 mode、language、最终呈现形式一起确认；收到答案前不得启动流程。
- **可以合理默认**：直接展示建议默认值和理由，用户未修改即按该口径执行，不另开一轮询问。

用户确认后的研究范围和口径统一记为 `confirmed_scope`，只记录实际口径含义。quick 在派发 research 时直接传入；normal/heavy 在派发 plan 时传入，由 plan 将其落实到 `plan.json`。没有额外确认项时省略该字段，也不创建额外状态文件。

用户确认后：

- 记录用户确认的 `language`、`format` 与 `mode`；
- 将用户确认的研究范围和口径直接传给后续角色，不创建额外状态文件；
- `format` 与 `language` 一样只作为请求级参数传给后续角色，不写入报告目录；

### 4.2 推荐 mode 的依据

- **quick**：一个自包含 Research Agent 能在同一研究上下文中覆盖完整需求，然后由一个 writer 成稿。
- **normal**：任务包含可独立搜索的研究面，先用 plan 划分边界清晰且检索范围尽量不重合的 work packages，并发 research 后由一个 writer 跨维综合、一次成文。Normal 不运行 report-planner、stitcher、模型 review、perspective 或 supplement。
- **heavy**：用户明确要求完整审计，或任务高风险、高争议、证据冲突严重，需要 scout、review、perspective、补研和终稿审查的完整流程。

最终 mode 由用户在启动确认中选择。不要因为主题宽就自动 heavy，也不要因为用户选择 quick 就降低证据标准。

### 4.3 三档流水线

#### quick：research + writer

1. 派 §5.3 research(`mode=quick`, `dimension_id=d1`)，传入原始需求、确认口径和 `format`。Research 自行完成问题拆解、搜索策略、证据标准选择、正文取证和缺口补搜，写出 d1 evidence。
2. 派 §5.8 report-writer(`write_mode=quick_synthesis`)，读取 d1 evidence 和已确认 format，写 `sections/s_full.md`。
3. §5.10 render。

跳过 scout、plan、review、perspective、supplement、report-planner 和 stitcher。

#### normal：plan + 并发 research + 单 writer 一次成文

1. 派 §5.2 plan；normal 无 briefing，plan 直接消费 query、启动确认口径和 format，按独立搜索空间生成 dimensions 并控制维度间重复检索。
2. plan 完成后，你从 `plan.json.dimensions[]` 只读取每个 `id`；按这些 ID 同批并发派 §5.3 research(`mode=initial`)，每次调用传 `plan.json` 路径与对应 `dimension_id`，由 Research 自行读取对应 work package。
3. 全部 research 完成后只派一次 §5.8 report-writer(`write_mode=quick_synthesis`)，将全部 `d*.evidence.json` 的绝对路径按 dimension 顺序放入 `evidence_paths`，直接写 `sections/s_full.md`。
4. §5.10 render。

Normal 不运行 scout、report-planner、content-unit writer、stitcher、子报告 review、perspective、supplement-planner、补研 Agent或终稿 review。

#### heavy：完整流程

1. 用户确认 mode、language 和 format 后，派 §5.1 scout 生成 briefing；只有 scout 新发现的问题确实无法合理默认且会改变研究范围时，才追加确认。
2. 派 §5.2 plan，读取 briefing 与 format。
3. plan 完成后，你从 `plan.json.dimensions[]` 只读取每个 `id`，并读取各维度的 lens 数量/顺序供后续 perspective 调度；按这些 ID 同批并发派 §5.3 research(`mode=initial`)，由各 Research 自行读取对应 work package。
4. 每维 evidence 同批运行 §5.4 review 与按需 §5.5 perspective；二者按 `plan_path + dimension_id` 自行读取审查范围，随后 §5.6 supplement-planner 决定是否补研。必要补研后重新派 research/review，直至 evidence finalized 或诚实记录无法解决的 gap。
5. 派 §5.7 report-planner；并发 writer 后由 stitcher 组装。
6. 派 §5.4 终稿 review；按反馈修复受影响的 planner/writer/stitcher 产物。
7. §5.10 render。

### 4.4 失败与重试

**唯一来源**；§5 各阶段门控只引用本表。

| 阶段 | 失败判据 | 路由 | 上限 |
|---|---|---|---|
| scout | 子 agent 明确失败、validator 未通过或未写出 `briefing.json` | 回 scout 修复 briefing | 1 |
| plan | 子 agent 明确失败、validator 未通过或未写出 `plan.json` | 携带原任务回 plan | 1 |
| research | 子 agent 明确失败、validator 未通过或未写出 evidence | 携带原任务回同维 research | 1 |
| heavy 子报告 review | revise verdict | 交 supplement-planner，必要时补研后重审 | 按真实缺口处理 |
| supplement-planner | 子 agent 明确失败、validator 未通过或未写出 supplement plan | 携带原任务回同维 supplement-planner | 1 |
| supplement research | 子 agent 明确失败、evidence validator 未通过或未更新 evidence/plan 状态 | 携带原任务回同维 research | 1 |
| quick / normal report-writer | 子 agent 明确失败、未写出 `sections/s_full.md` 或引用越界 | 携带全部原始 `evidence_paths` 回同一 writer 修复 | 1 |
| heavy report-planner | 子 agent 明确失败、validator 未通过或未写出 outline/subsets | 携带原任务回 planner | 2 |
| heavy report-writer | unit 合同或越界引用反馈 | 路由问题回 planner；表达/形态问题以 `revise_unit` 重派受影响 unit | 各 1 |
| heavy report-stitcher | blocker | 按 `problem_type`/`location`/`required_fix` 回 planner 或 writer | 1 |
| heavy 终稿 review | revise verdict | 局部：回对应 writer 后重跑 stitcher；全局：回 planner 重做编排 | 2 |

**终稿失败路由**：局部问题用 `revise_unit` 重写受影响 unit 后重跑 stitcher；全局组织问题回 planner 重做 outline 和受影响 units。

失败超过重试上限时，不要无限循环：

- 若失败导致下游必需 artifact 不存在、不是合法 JSON 或仍未通过 validator，立即停止本次流程，向用户报告失败阶段、artifact 路径和最后一轮 validator errors；不得拿无效 artifact 继续调度，也不得声称报告已完成。
- 只有在下游必需 artifact 均存在且已通过 validator、剩余问题只是 review 指出的非阻断内容质量问题时，才可在终稿标注「质量受限」并完成流程。

### 4.5 流程变更

- 用户中途修改 query → 终止当前流程，从 §4.1 重启。

## 5. 阶段库

每个角色只在此描述一次：**作用** + **payload** + **门控**。是否运行、运行几次、顺序——全由 §4 决定，本节不写档位。所有 payload 第一行均为 `先读取 {plugin_role_dir}/<role>.md 并严格遵守。`（见 §2.2）。

### 5.1 scout

**作用**：仅在 heavy 中预检领域地形并产出 briefing。

```text
先读取 {plugin_role_dir}/scout.md 并严格遵守。

原始需求:{query}
language:{language}
format:{format}
report_dir:{report_dir 绝对路径}
plugin_skills_dir:{plugin_skills_dir}
schema_path:{plugin_skills_dir}/sn-deep-research/schemas/briefing.schema.md
validator_path:{plugin_skills_dir}/sn-deep-research/scripts/validate_briefing.py
mode:heavy

请按 scout agent 契约写入：
- {report_dir}/briefing.json
```

**门控**：Scout 必须汇报 `validation_ok:true`。之后你只读取 `briefing.json` 的调度所需字段。研究范围和口径已在启动时确认；只有 scout 新发现的问题确实无法合理默认且会改变研究范围时，才追加询问。

### 5.2 plan

**作用**：使用请求级 `format` 理解交付方向，把研究范围划分为边界清晰、可独立执行且检索范围尽量不重合的 work packages，并写回 `plan.json.mode`。

```text
先读取 {plugin_role_dir}/plan.md 并严格遵守。

原始需求:{query}
language:{language}
format:{format}
report_dir:{report_dir 绝对路径}
plan_schema_path:{plugin_skills_dir}/sn-deep-research/schemas/plan.schema.md
plan_validator_path:{plugin_skills_dir}/sn-deep-research/scripts/validate_plan.py
mode:{最终确定的 mode}
confirmed_scope:{用户确认后的实际研究范围和口径}  # 有额外确认时加入，否则省略

请按 plan agent 契约划分可独立执行的搜索空间，合并高度重合的取证范围并明确 scope owner；完成 lenses 规划，只输出：
- {report_dir}/plan.json
```

heavy 追加 `briefing_path:{report_dir}/briefing.json`。

**调度读取**：角色完成后，你从 `plan.json.dimensions[]` 只读取各维度的 `id`；heavy 另读各维度的 lens 数量和顺序用于调度 perspective。`dimension_id` 必须直接来自 plan，不得自行分配、改写或重编号。不要读取或转抄 dimension 的其他内容字段。

### 5.3 research

**作用**：按维度取证，产出 `sub_reports/d{N}.evidence.json`——后续一切的事实底座。

**payload `mode`**：`initial`（normal/heavy 初始研究）/ `supplement`（补研）/ `quick`。initial/supplement 只传 `plan_path + dimension_id`，其中 `dimension_id` 必须来自 `plan.json.dimensions[].id`；Research 再从 plan 读取对应完整 work package。quick 没有 plan，由 Research 根据原始需求、确认口径和 format 自行确定研究问题与证据标准。normal/heavy 的全部 dimensions 均可同批启动。

```text
先读取 {plugin_role_dir}/research.md 并严格遵守。

原始需求:{query}
language:{language}
format:{format}
mode:{initial|supplement|quick}

report_dir:{report_dir 绝对路径}
dimension_id:{dimension_id}
plugin_skills_dir:{plugin_skills_dir}
plan_path:{report_dir}/plan.json                 # initial/supplement；quick 省略
confirmed_scope:{用户确认后的实际研究范围和口径}  # quick 有额外确认时加入，否则省略

来源纪律:搜索入口按 sources category 选择对应相关的 skill；source.url 写原始 URL。

schema_path:{plugin_skills_dir}/sn-deep-research/schemas/evidence.schema.md
output_path:{report_dir}/sub_reports/{dimension_id}.evidence.json
```

initial/supplement 下，Research 按 `dimension_id` 从 plan 读取 `name/description/key_questions/focus/sources/depth/time_sensitivity/scope_ownership`。你不展开这些字段。

**supplement 模式差异**：`mode: supplement`，并追加 `existing_evidence_path:{report_dir}/sub_reports/{dimension_id}.evidence.json` 与 `supplement_plan_path:{report_dir}/sub_reports/{dimension_id}.supplement_plan.json`。维度级来源、depth 和时效要求从 `plan.json` 读取，逐条更细来源以 `supplement_plan.json` 的 `suggested_sources` 为准。

**quick 派发纪律**：quick 省略 `plan_path`，固定 `dimension_id=d1`。Research 自行拆解研究问题并生成内部 `kq1/kq2/…`，自行选择 sources、depth、时效窗口与 scope。不得把 quick 改写成单来源、单轮搜索、固定 query 数或 skim；证据要求按问题本身确定。

**门控**：失败处理见 §4.4。

### 5.4 review（子报告 / 终稿 共用此角色）

**作用（仅 heavy）**：审 evidence 与终稿的口径、缺口与引用纪律。`审查类型=子报告 evidence 审查` → 产出 `d{N}.review.md` 供 supplement-planner 聚合；`审查类型=终稿 review` → 检查整体逻辑、引用纪律、冲突/gap surface 与 evidence 边界。

**子报告审查 payload**：

```text
先读取 {plugin_role_dir}/review.md 并严格遵守。

原始需求:{query}
language:{language}
format:{format}
审查类型:子报告 evidence 审查

report_dir:{report_dir 绝对路径}
plugin_skills_dir:{plugin_skills_dir}
dimension_id:{dimension_id}
plan_path:{report_dir}/plan.json
evidence_path:{report_dir}/sub_reports/{dimension_id}.evidence.json
output_path:{report_dir}/sub_reports/{dimension_id}.review.md
```

**终稿审查 payload**：

```text
先读取 {plugin_role_dir}/review.md 并严格遵守。

原始需求:{query}
language:{language}
format:{format}
审查类型:终稿 review

report_dir:{report_dir 绝对路径}
plugin_skills_dir:{plugin_skills_dir}
stitched_path:{report_dir}/stitched.md
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

**门控**：见 §4.4。

### 5.5 perspective

**作用**：按维度 `lenses[]` 做覆盖检查，surface evidence 未覆盖的视角。`lenses[]` 为空则跳过。

```text
先读取 {plugin_role_dir}/perspective.md 并严格遵守。

原始需求:{query}
language:{language}
format:{format}

report_dir:{report_dir 绝对路径}
plugin_skills_dir:{plugin_skills_dir}
dimension_id:{dimension_id}
plan_path:{report_dir}/plan.json
lens_id:l{该 dimension 内 1-based 顺序号}

evidence_path:{report_dir}/sub_reports/{dimension_id}.evidence.json
output_path:{report_dir}/sub_reports/{dimension_id}.perspectives/l{同一顺序号}.md
```

### 5.6 supplement-planner

**作用（仅 heavy）**：按维度聚合 review/perspective 的缺口，产出补研计划。

```text
先读取 {plugin_role_dir}/supplement-planner.md 并严格遵守。

原始需求:{query}
language:{language}
format:{format}

report_dir:{report_dir 绝对路径}
plugin_skills_dir:{plugin_skills_dir}
plan_path:{report_dir}/plan.json
target_dimensions:["{dimension_id}"]
schema_path:{plugin_skills_dir}/sn-deep-research/schemas/supplement_plan.schema.md
validator_path:{plugin_skills_dir}/sn-deep-research/scripts/validate_supplement_plan.py
output_path:{report_dir}/sub_reports/{dimension_id}.supplement_plan.json
```

**门控**：Supplement Planner 必须在生成工作单后运行 `validate_supplement_plan.py` 并汇报 `validation_ok:true`。你只读该 JSON 的 `dimension_id`、`supplement_items[].id/status` 与 `deferred_items` 数量，并与角色回复的 counts 对照。`supplement_items[]` 为空 → 本维度 evidence 可 finalized；非空且全部为 `pending` → 派 §5.3 research(`mode=supplement`)。补研后 Research 只校验更新后的 evidence，不再调用补研计划 validator；随后你重读工作单 status 并重派 §5.4 子报告 review。完成时不得残留 `pending`；`partial|no_data|out_of_scope` 必须由 research 写入 evidence 的 `writing_context`，且子报告 review 不再要求补研后才可 finalized。

### 5.7 report-planner（仅 heavy）

**作用**：消费请求级 `format` 与各维 evidence 边界；内容范式决定信息如何推进，用户要求与 evidence shape 决定主信息载体，输出 content-unit outline 与 per-unit evidence subsets。不得使用固定范式到载体的配对表。

```text
先读取 {plugin_role_dir}/report-planner.md 并严格遵守。

原始需求:{query}
language:{language}
format:{format}

report_dir:{report_dir 绝对路径}
plugin_skills_dir:{plugin_skills_dir}
briefing_path:{report_dir}/briefing.json          # 仅 heavy；normal 省略
plan_path:{report_dir}/plan.json
evidence_paths:
- {report_dir}/sub_reports/d1.evidence.json
- {report_dir}/sub_reports/d2.evidence.json
- ...
schema_path:{plugin_skills_dir}/sn-deep-research/schemas/outline.schema.md

output_outline:{report_dir}/outline.json
output_subsets_dir:{report_dir}/content_units/
```

**调度读取**：该角色完成后，你只取 `content_units[].id`、`organization_decision.opening_summary` 与 `organization_decision.toc`，用于调度 writer/render。

### 5.8 report-writer

**作用**：在 quick / normal 下一次综合全部 evidence，或在 heavy 下执行单个 content unit。`write_mode`：

- `write_unit`（heavy）：只读取指定 unit 与自己的 evidence subset。
- `revise_unit`（heavy）：按 stitcher 或 heavy review 的局部反馈覆盖指定 unit。
- `quick_synthesis`（quick / normal）：读取 payload 中全部 `evidence_paths`，按用户需求和已确认 format 输出完整独立成品；不默认压缩成简短回答。

```text
先读取 {plugin_role_dir}/report-writer.md 并严格遵守。

原始需求:{query}
language:{language}
format:{format}

report_dir:{report_dir 绝对路径}
plugin_skills_dir:{plugin_skills_dir}
write_mode:{write_unit|revise_unit|quick_synthesis}

# heavy
content_unit_id:{unit_id}
outline_path:{report_dir}/outline.json
subset_path:{report_dir}/content_units/{unit_id}.evidence_subset.json
output_path:{report_dir}/content_units/{unit_id}.md

# 仅 revise_unit
draft_path:{report_dir}/content_units/{unit_id}.md
revision_instructions:{review/stitcher 的局部修订要求}

# quick / normal（省略 content unit 四项；normal 传全部维度）
evidence_paths:[{report_dir}/sub_reports/d1.evidence.json, ...]
output_path:{report_dir}/sections/s_full.md
```

**门控**：越界引用反馈处理见 §4.4。

### 5.9 report-stitcher（仅 heavy）

**作用**：按 `organization_decision` 组装 content units，并校准可选 L0、术语和结构合同。主结构可以是矩阵、时间线、清单、问答或其他 unit，不强制文章化。

```text
先读取 {plugin_role_dir}/report-stitcher.md 并严格遵守。

原始需求:{query}
language:{language}
format:{format}

report_dir:{report_dir 绝对路径}
plugin_skills_dir:{plugin_skills_dir}
outline_path:{report_dir}/outline.json
content_units_dir:{report_dir}/content_units/
output_path:{report_dir}/stitched.md
```

**门控**：blocker 按 `problem_type`/`location`/`required_fix` 回 planner 或 writer（见 §4.4）。

### 5.10 render（sn-prepare-citations 脚本）

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
| normal | `{report_dir}/sections/s_full.md` | 省略 |
| quick | `{report_dir}/sections/s_full.md` | 省略（无 outline.json） |

heavy 的 L0 已由 stitcher 按 `organization_decision.opening_summary` 写入，因此 render 固定传 `--no-l0`，避免再次生成通用摘要。`organization_decision.toc=false` 时同时传 `--no-toc`；为 true 时不传 `--no-toc`，让脚本替换 stitcher 放置的 TOC placeholder。quick / normal 无 outline，由一次成文 writer 自行按 query 与 `format` 确定标题和主体结构；render 不另套摘要或目录默认值。

**门控**（检查 stdout JSON）：

- `orphan_citations` 非空 → 不交付，回 writer/stitcher 修正。
- `claim_id_leakage.unresolved` 非空 → 不交付，回 writer 修正 `[^dN.cM]`。
- `claim_id_leakage.resolved` 非空但 `unresolved` 为空 → 可继续，记录警告。
- 无 orphan / unresolved → 完成。

## 6. 附录：上下文边界

| 文件 | 是否读取 |
|---|---|
| `briefing.json` | 是：仅 heavy，存在性和调度字段检查 |
| `plan.json` | 是：normal/heavy 只取 `dimensions[].id`；heavy 另取 lens 数量/顺序。其他 work-package 内容由 Research 自读 |
| `outline.json` | 是（仅 heavy）：只取 `content_units[].id` 与 organization decision 的 render 开关 |
| `sub_reports/d*.evidence.json` | 否 |
| `sub_reports/d*.review.md` | 否（仅 heavy） |
| `sub_reports/d*.perspectives/*.md` | 否 |
| `sub_reports/d*.supplement_plan.json` | 是（仅 heavy）：只读 dimension_id、supplement item id/status 和 deferred 数量用于调度，不读描述正文 |
| `content_units/*.evidence_subset.json` | 否 |
| `content_units/*.md` | 否 |
| `sections/s_full.md` | 否（quick / normal） |
| `stitched.md` | 否（仅 heavy） |
| `report.md` | 否：完成时给用户路径 |

quick 模式无 `briefing/plan/outline/content_units/stitched`；normal 无 `briefing/outline/content_units/stitched`。quick / normal 都以 `sections/s_full.md` 作为 render 输入，heavy 以 `stitched.md` 作为 render 输入。`language` 与 `format` 都只保存在本次请求上下文中，不写状态文件。
