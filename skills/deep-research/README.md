# openclaw-deep-research

OpenClaw plugin：多 agent 深度研究工作流。主 agent 触发 `/deep-research` 后，自动调度 5 个专家 agent 产出带 `[N]` 编号引用的完整研究报告。

## 能做什么

主 agent 接到深度研究需求，通过 `deep-research` skill 调度 5 个专家 agent：

- `scout-agent` 侦察 & 用户澄清 → `briefing.md`
- `plan-agent` 格式发现 + 维度拆解 → `blueprint.json` + `plan.json`
- `research-agent` 按维度搜证 → `sub_reports/*.md`（`[^key]` 脚注格式）
- `review-agent` 审查子报告与终稿
- `report-agent` 综合生成终稿 → `report.md`

流程尾部调用 plugin 注册的 `prepare_report_citations` 工具，把 `[^key]` 转成 `[N]` 编号 + 生成 `citations.json`。

插件首次加载会自动 bootstrap 所需资产：

- `workspaces/<id>/AGENTS.md` → `~/.openclaw/workspace-<id>/AGENTS.md`
- 辅助 skills → `~/.openclaw/skills/*`
- 默认配置 → `~/.openclaw/openclaw.json`

## 安装

```bash
openclaw plugins install deep-research --marketplace github-repo
openclaw gateway restart
```

重启 Gateway 后，plugin 首次加载时自动 bootstrap 所需 helper skills、专家 agent workspace 模板和 `openclaw.json` 配置。

### 验证加载

```bash
openclaw plugins inspect deep-research
openclaw agents list
openclaw skills list | grep deep-research
```

预期：

1. `deep-research` plugin 已启用
2. `scout-agent` / `plan-agent` / `research-agent` / `review-agent` / `report-agent` 出现在 agent 列表
3. controller skill `deep-research` 可见

### 手动修复或强制刷新

首次自动 bootstrap 失败，或升级后想强制刷新 plugin 托管资产，调 plugin 提供的 `deep_research_install` 工具：

- `force: false`：保守修复，只补缺失内容
- `force: true`：覆盖 plugin 托管的 helper skills 和 `workspace-*/AGENTS.md`
- `dryRun: true`：仅预览变更，不写盘

### Python 依赖

`_search-common/search_utils.py` 依赖 `httpx`，bootstrap 不会替你装 Python 依赖：

```bash
python3 -m pip install -r requirements.txt
```

## 用法

在与主 agent 的对话里：

```text
/deep-research 帮我研究 2026 年 AI 芯片市场格局
```

或直接自然语言："帮我做一份 2026 AI 芯片市场的深度调研"。主 agent 激活 `deep-research` skill，自动走完 scout → plan → research → review → report → prepare_report_citations 全流程，最终给出 `report_dir/report.md` 和 `citations.json` 路径。

## 自定义

### 切换专家模型

默认所有专家继承主 agent 的模型。要单独指定：

1. 设 `plugins.entries.deep-research.config.subagent.allowModelOverride: true`
2. 在 skill 的 `sessions_spawn` 调用里加 `model: "provider/model-id"` 参数

### 调整并发与超时

- `agents.defaults.subagents.maxConcurrent`（默认 8）：同时运行的 subagent 数
- `agents.defaults.subagents.runTimeoutSeconds`（默认 1800s / 30 分钟）：单次 subagent 超时

bootstrap 只在首次写入；用户已设过的值不会被覆盖。要强制覆盖，用 `deep_research_install` + `force: true`。

### 自定义 report 根目录

设 `plugins.entries.deep-research.config.reports.rootDir`。留空则用主 agent workspace 下的 `reports/`。

## 关键约束

- **`_search-common/` 必须与 `search-*` skill 同级**：搜索脚本通过 `parent.parent.parent / "_search-common"` 硬编码定位，bootstrap 会放到 `~/.openclaw/skills/_search-common/`
- **工具名使用 OpenClaw 原生名**：`read` / `write` / `web_fetch` / `exec` / `web_search`；时间过滤参数因 provider 而异（brave:`freshness` / tavily:`time_range` / exa:`start_published_date`），按 tool 响应提示使用
- scout-agent 不能自己问用户；需要澄清时把问题结构化写入输出的 `## 待澄清问题` 段，由 controller skill 转达
- report-agent 的 AI 生图 `ARK_API_KEY` 由 OpenClaw 从 `skills.entries.generate-image.apiKey` 自动注入 `process.env`；用户未配置时 generate-image 脚本返回 `success: false`，report-agent 降级为"仅 Mermaid"

## 依赖的外部工具

专家 agent 需主 agent workspace 已启用：

- 搜索：`web_search`（任一 provider：brave / tavily / exa 等）
- 读写与执行：`read` / `write` / `web_fetch` / `exec`

若缺 `web_search`，research-agent 与 scout-agent 会按 skill 文本的降级路径继续执行。

## 目录结构

```text
openclaw-deep-research/
├── openclaw.plugin.json       # plugin manifest
├── src/                       # TS 源码（plugin 入口 + bootstrap + tools）
├── skills/                    # 随 plugin 发行的 skill
├── workspaces/                # 5 个专家 agent 的 workspace 模板
├── scripts/                   # 本地开发辅助脚本
└── tests/
```

## 本地开发

从源码构建：

```bash
npm install
npm run build
```

SDK 解析：`openclaw/plugin-sdk/*` 需要能被 npm 解析到。若 `openclaw` 仓库独立在插件外部：

```bash
# 先在 openclaw 仓库
npm link

# 回到本仓库
npm link openclaw
npm run build
```

如果插件已放进 `openclaw` workspace 内部，或 `package.json` 通过 `file:` 依赖解析，可跳过 `npm link`。

`scripts/install.sh` / `scripts/install.ps1` 是发布前手工验证用的 legacy 路径，语义已迁到 TS runtime 的 `ensureInstalled()`。
