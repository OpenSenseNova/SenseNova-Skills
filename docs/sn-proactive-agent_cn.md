# SenseNova Proactive Agent

简体中文 | [English](sn-proactive-agent.md)

[`sn-proactive-agent`](../skills/sn-proactive-agent/SKILL.md) 从长期对话中记录项目进展，
维护可审计的项目状态，并在 Web 工作台展示有价值的下一步建议。用户接受建议后，
对应的 Connector 会回到原 Session 继续执行，让动作保持在同一段对话中可见。

## 提供的能力

- 从包含明确长期目标的对话中创建和更新 Project、Item 与 Event。
- 对没有明确推进价值的对话保持静默，不生成无效建议。
- 在本地 Web 工作台展示建议、项目进展和日报。
- 用户接受建议后，在原 Hermes 或 OpenClaw Session 中继续执行，并带 `source_suggestion_id` 回写结果。
- 将运行数据保存在用户 Home 目录下，不写入源码仓库。

## 组件与边界

| 组件 | 职责 |
|---|---|
| Skill | 告诉 Agent 何时检查、安装、配置或使用服务。 |
| 运行包 | 提供 `sn-proactive-agent` CLI、Core、Web 工作台与诊断能力。 |
| Hermes Connector | 采集对话 QA，并在原 Session 中继续执行已接受的动作。 |
| OpenClaw Gateway 插件 | 采集 OpenClaw 文本 QA，并将已接受的动作交回原 Session 执行。 |
| 用户数据 | 默认在 `~/.sn-proactive-agent/` 保存 Project、Item、Event、运行记录和恢复状态。 |

安装 Skill 不会安装运行包、配置 Connector 或启动服务。Hermes 使用 Web-only 续跑桥，
OpenClaw 使用 Gateway 插件。请按所选 Harness 的说明操作，不能直接替换 Hermes 命令中的平台名称。

## 环境要求

- Python 3.11 或更高版本与 `pipx`。
- 已配置模型且可用的 Hermes CLI，用于 Core 后台处理；即使只监听 OpenClaw 对话也需要。
  仅接入 OpenClaw 时无需安装 Hermes Connector，也无需 Hermes TUI 源码目录或 Hermes Session 诊断。
- Hermes 接入：受支持版本的 Hermes 源码目录、Node.js 22 或更高版本，以及该 Hermes 版本要求的构建依赖。
- OpenClaw 接入：已配置模型且能正常对话的 OpenClaw Gateway。已记录的真实闭环验收基线为
  macOS、OpenClaw `2026.6.11`；其他版本和系统需单独验证。Windows 说明属于安装参考，不代表完整接入已验收。
- 具备读取运行包 GitHub Release 仓库的权限。模型通过 Harness 自身的配置入口设置，安装流程不会读取或打印 API Key。

本文对应运行包版本 `0.1.4`。下载前请确认对应 GitHub Release 已经发布、不是草稿，
并包含 wheel 与 `SHA256SUMS`；接入 OpenClaw 还需 `sn-proactive-agent-openclaw-0.1.4.tgz`。
不要用源码目录、未校验的 URL
或旧的 `proactive-memory-service` 包替代。

## 安装与配置

### 1. 安装 Skill

将完整的 `skills/sn-proactive-agent/` 目录复制到 Harness 的 Skill 目录中。目录必须包含
`SKILL.md` 与 `references/`；只安装运行包不会安装本 Skill。

### 2. 安装运行包

按照[通用安装流程](../skills/sn-proactive-agent/references/install/overview.md)中的检查和下载步骤操作：

```text
gh release view v0.1.4 --repo OpenSenseNova/SenseNova-Skills-ProactiveAgent --json tagName,isDraft,isPrerelease,assets
gh release download v0.1.4 --repo OpenSenseNova/SenseNova-Skills-ProactiveAgent --pattern sn_proactive_agent-0.1.4-py3-none-any.whl --pattern SHA256SUMS
```

先使用 `SHA256SUMS` 校验 wheel，再使用目标环境中已确认的 Python 解释器安装：

```text
pipx install --python "$SNPA_PYTHON" "$SNPA_PACKAGE"
sn-proactive-agent --version
sn-proactive-agent doctor --json
```

`SNPA_PYTHON` 必须指向 Python 3.11 或更高版本，`SNPA_PACKAGE` 必须是已校验 wheel
的绝对路径。

### 3. 配置 Connector

#### Hermes

将 `SNPA_HERMES_ROOT` 设置为目标实例实际使用的 Hermes 源码目录。正式修改前先预览：

```text
sn-proactive-agent setup --harness hermes --web-only --hermes-root "$SNPA_HERMES_ROOT" --dry-run
sn-proactive-agent setup --harness hermes --web-only --hermes-root "$SNPA_HERMES_ROOT"
```

安装器会检查兼容性，备份受影响的 TUI 与构建文件，安装观测资源并构建 Web-only bridge。
它不会复制 Skill、启动 Hermes、启动 Web 服务或发送测试消息。

#### OpenClaw

按 [OpenClaw 接入说明](../skills/sn-proactive-agent/references/connectors/openclaw.md)操作。
在同一已确认 Release 的下载目录中取得插件，并在安装前使用 `SHA256SUMS` 中的对应记录校验：

```text
gh release download v0.1.4 --repo OpenSenseNova/SenseNova-Skills-ProactiveAgent --pattern sn-proactive-agent-openclaw-0.1.4.tgz
```

针对目标 Gateway 实例安装并配置已校验的插件：

```text
openclaw plugins install ./sn-proactive-agent-openclaw-0.1.4.tgz
openclaw plugins enable sn-proactive-agent
openclaw config set plugins.entries.sn-proactive-agent.hooks.allowConversationAccess true
openclaw config set plugins.entries.sn-proactive-agent.config.serviceUrl http://127.0.0.1:8080
```

`allowConversationAccess` 允许插件读取接入后的对话。所有命令须沿用同一 profile、
`OPENCLAW_CONFIG_PATH` 和 `OPENCLAW_STATE_DIR`。若配置了 `plugins.allow`，保留原列表并加入
`sn-proactive-agent`。升级已有插件前先检查版本与本地修改，不直接覆盖。

由服务管理器运行的 Gateway 使用 `openclaw gateway restart` 重启；前台运行的实例则结束
目标进程后按原方式启动。当前尚未提供 `sn-proactive-agent setup --harness openclaw`。

### 4. 启动 Web 工作台

仅接入 Hermes 时，在单独的终端启动服务：

```text
sn-proactive-agent serve --web-only
```

接入 OpenClaw（包括同时接入两个 Harness）时，使用实际 Gateway 地址启动：

```text
sn-proactive-agent serve --web-only --openclaw-gateway-url http://127.0.0.1:18789
```

选择一种启动方式，不要同时启动两个 Core 实例。Gateway 使用 Token 鉴权时，在服务环境中
提供 `SN_PROACTIVE_AGENT_OPENCLAW_GATEWAY_TOKEN`。保留已有鉴权，不把 Token 写入命令参数或日志；
使用其他鉴权模式前须确认兼容性。

在另一个终端检查服务：

```text
sn-proactive-agent doctor --url http://127.0.0.1:8080 --json
```

浏览器打开 <http://127.0.0.1:8080/>。如果使用自定义端口或数据目录，服务、Connector、
诊断命令和浏览器必须指向同一组实际配置。
OpenClaw 用户还需在 Web 设置中启用 OpenClaw；只监听 OpenClaw 时可关闭 Hermes 监听。
监听开关不会启动 Gateway，也不会移除 Hermes CLI 后台依赖。

### 5. 验证真实 Session 流程

#### Hermes

重启已配置的 Hermes 实例，然后使用双方同意的测试对话：

```text
hermes --tui --accept-hooks
```

确认对话已被采集；有推进价值的建议只出现在 Web 工作台；用户接受建议后，原 Session
只执行一次；执行结果带 `source_suggestion_id` 回流。只有运行包或静态接入检查通过，
不能视为完整的真实接入验收。

最终诊断时使用目标窗口的真实 Session ID：

```text
sn-proactive-agent doctor --harness hermes --hermes-root "$SNPA_HERMES_ROOT" \
  --url http://127.0.0.1:8080 --session-id "$SNPA_SESSION_ID" --json
```

#### OpenClaw

通过用户平时使用的 OpenClaw 界面，以双方同意的测试对话逐项验证：

1. 一轮文本 QA 完成后，Web 中出现对应 Project、Item 和 Event，会话关联正确；同一会话的后续消息继续关联。
2. 出现有推进价值的建议后，在 Web 接受，确认原 OpenClaw Session 执行一次且没有重复提交。
3. 核对实际工作结果、项目状态更新和回流 Event 的 `source_suggestion_id`；该轮结果不应立即触发下一条建议。

`doctor --url` 只检查服务健康。当前没有 OpenClaw 专用 Session doctor，Hermes 诊断和 Web 监听状态
都不能代替 OpenClaw 真实接入验收。插件采集文本 QA，不代表完整采集附件或工具轨迹；
单个文本字段超过 120,000 字符会被截断。Gateway 重启会清除内存中的续跑去重状态，
动作结果不确定时，应先核对原会话和日志，再决定是否重试。

## 数据与生命周期

默认数据根目录为 `~/.sn-proactive-agent/`，包含：

- `projects/<project-id>/project.md`：项目概述与 Item 索引。
- `projects/<project-id>/items/<item-id>/item.md`：Item 最新状态。
- `projects/<project-id>/items/<item-id>/events.md`：QA 与状态变化。
- `runtime.jsonl`：接收、归属、建议、用户决定、执行、日报与恢复记录。

可通过 `--data-root` 或 `SN_PROACTIVE_AGENT_DATA_ROOT` 指定其他位置。已有
`~/.proactive-memory/` 的用户按文档中的迁移规则处理；新服务不会自动合并两个数据目录。

停止、升级和卸载时，只处理目标服务与 Connector。回滚、升级和清理请遵循[生命周期说明](../skills/sn-proactive-agent/references/install/overview.md)
及对应的 [Hermes](../skills/sn-proactive-agent/references/connectors/hermes.md) 或
[OpenClaw 接入说明](../skills/sn-proactive-agent/references/connectors/openclaw.md)。

OpenClaw 用户升级运行包 wheel 后，还需单独更新已复制的 Gateway 插件、重启目标 Gateway 并重新验证对话流程。
移除接入时，先在 Web 设置中关闭 OpenClaw 监听，再针对同一 Gateway 实例执行：

```text
openclaw plugins disable sn-proactive-agent
openclaw plugins uninstall sn-proactive-agent
```

重启 Gateway，并检查本插件配置和信任列表残留。`sn-proactive-agent uninstall` 当前只管理 Hermes，
不能代替 OpenClaw 插件卸载。清理时保留用户会话、项目数据及其他插件。

## 安全边界

服务会处理从对话中提取的项目状态，并可能把用户接受的动作提交回原 Session。请将 Web
服务保持在预期的本地监听地址；未经独立安全评审不要对公网开放，也不要提交 API Key、
`.env`、运行数据、日志或本地 Hermes / OpenClaw 配置。
