# SenseNova Proactive Agent

简体中文 | [English](sn-proactive-agent.md)

[`sn-proactive-agent`](../skills/sn-proactive-agent/SKILL.md) 从长期对话中记录项目进展，
维护可审计的项目状态，并在 Web 工作台展示有价值的下一步建议。用户接受建议后，
对应的 Connector 会回到原 Session 继续执行，让动作保持在同一段对话中可见。

## 提供的能力

- 从包含明确长期目标的对话中创建和更新 Project、Item 与 Event。
- 对没有明确推进价值的对话保持静默，不生成无效建议。
- 在本地 Web 工作台展示建议、项目进展和日报。
- 用户接受建议后，在原 Hermes Session 中继续执行，并带 `source_suggestion_id` 回写结果。
- 将运行数据保存在用户 Home 目录下，不写入源码仓库。

## 组件与边界

| 组件 | 职责 |
|---|---|
| Skill | 告诉 Agent 何时检查、安装、配置或使用服务。 |
| 运行包 | 提供 `sn-proactive-agent` CLI、Core、Web 工作台与诊断能力。 |
| Hermes Connector | 采集对话 QA，并在原 Session 中继续执行已接受的动作。 |
| 用户数据 | 默认在 `~/.sn-proactive-agent/` 保存 Project、Item、Event、运行记录和恢复状态。 |

安装 Skill 不会安装运行包、配置 Hermes 或启动服务。当前安装入口只支持 Hermes；
其他 Harness 不能直接套用 Hermes 命令。

## 环境要求

- 已可用的 Hermes，以及受支持版本的 Hermes 源码目录。
- Python 3.11 或更高版本与 `pipx`。
- Node.js 22 或更高版本，以及目标 Hermes 版本要求的构建依赖。
- 安装已发布运行包时，具备读取私有 GitHub Release 仓库的权限。
- 已在 Hermes 中配置模型。安装流程不会读取或打印 API Key。

当前工作区文档对应统一改名后的 `0.1.3` 候选版。下载前请确认对应 GitHub Release
已经发布、不是草稿，并同时包含 wheel 与 `SHA256SUMS`。不要用源码目录、未校验的 URL
或旧的 `proactive-memory-service` 包替代。

## 安装与配置

### 1. 安装 Skill

将完整的 `skills/sn-proactive-agent/` 目录复制到 Harness 的 Skill 目录中。目录必须包含
`SKILL.md` 与 `references/`；只安装运行包不会安装本 Skill。

### 2. 安装运行包

按照[通用安装流程](../skills/sn-proactive-agent/references/install/overview.md)中的检查和下载步骤操作：

```text
gh release view v0.1.3 --repo OpenSenseNova/SenseNova-Skills-ProactiveAgent --json tagName,isDraft,isPrerelease,assets
gh release download v0.1.3 --repo OpenSenseNova/SenseNova-Skills-ProactiveAgent --pattern sn_proactive_agent-0.1.3-py3-none-any.whl --pattern SHA256SUMS
```

先使用 `SHA256SUMS` 校验 wheel，再使用目标环境中已确认的 Python 解释器安装：

```text
pipx install --python "$SNPA_PYTHON" "$SNPA_PACKAGE"
sn-proactive-agent --version
sn-proactive-agent doctor --json
```

`SNPA_PYTHON` 必须指向 Python 3.11 或更高版本，`SNPA_PACKAGE` 必须是已校验 wheel
的绝对路径。

### 3. 配置 Hermes Connector

将 `SNPA_HERMES_ROOT` 设置为目标实例实际使用的 Hermes 源码目录。正式修改前先预览：

```text
sn-proactive-agent setup --harness hermes --web-only --hermes-root "$SNPA_HERMES_ROOT" --dry-run
sn-proactive-agent setup --harness hermes --web-only --hermes-root "$SNPA_HERMES_ROOT"
```

安装器会检查兼容性，备份受影响的 TUI 与构建文件，安装观测资源并构建 Web-only bridge。
它不会复制 Skill、启动 Hermes、启动 Web 服务或发送测试消息。

### 4. 启动 Web 工作台

在单独的终端启动服务：

```text
sn-proactive-agent serve --web-only
sn-proactive-agent doctor --url http://127.0.0.1:8080 --json
```

浏览器打开 <http://127.0.0.1:8080/>。如果使用自定义端口或数据目录，服务、Connector、
诊断命令和浏览器必须指向同一组实际配置。

### 5. 验证真实 Session 流程

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

## 数据与生命周期

默认数据根目录为 `~/.sn-proactive-agent/`，包含：

- `projects/<project-id>/project.md`：项目概述与 Item 索引。
- `projects/<project-id>/items/<item-id>/item.md`：Item 最新状态。
- `projects/<project-id>/items/<item-id>/events.md`：QA 与状态变化。
- `runtime.jsonl`：接收、归属、建议、用户决定、执行、日报与恢复记录。

可通过 `--data-root` 或 `SN_PROACTIVE_AGENT_DATA_ROOT` 指定其他位置。已有
`~/.proactive-memory/` 的用户按文档中的迁移规则处理；新服务不会自动合并两个数据目录。

停止、升级和卸载时，只处理目标服务与 Connector。回滚、升级和清理请遵循[生命周期说明](../skills/sn-proactive-agent/references/install/overview.md)
及 [Hermes 接入说明](../skills/sn-proactive-agent/references/connectors/hermes.md)。

## 安全边界

服务会处理从对话中提取的项目状态，并可能把用户接受的动作提交回原 Session。请将 Web
服务保持在预期的本地监听地址；未经独立安全评审不要对公网开放，也不要提交 API Key、
`.env`、运行数据、日志或本地 Hermes 配置。
