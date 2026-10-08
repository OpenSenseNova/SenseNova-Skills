# OpenClaw 接入

用户继续在 OpenClaw 中聊天；插件把问答交给 Proactive Agent，在 Web 展示项目进展与建议。
用户接受后，插件在原会话执行一次，并回传结果。无需另开一套聊天窗口。

## 接入前提

- 先按 [通用流程](../install/overview.md) 安装并检查 `0.1.4` 运行包。
- 已安装且能够正常对话的 OpenClaw Gateway。真实闭环验收基线为 macOS、OpenClaw `2026.6.11`；其他版本和系统需单独验证。
- Core 当前仍使用已配置模型的 Hermes CLI 完成语义整理和判断。只监听 OpenClaw 时无需安装 Hermes Connector，但不能省略这个后台工作器。
- 确认实际 Gateway 实例、端口，以及其配置与状态目录；已有 `OPENCLAW_CONFIG_PATH`、`OPENCLAW_STATE_DIR` 或 profile 设置时，所有命令沿用同一实例。
- 模型由用户通过 Harness 配置入口设置，不读取或展示凭据。服务和 Gateway 默认仅绑定本机；保留已有 Gateway 鉴权，不为接入关闭鉴权。

```text
openclaw --version
openclaw plugins install --help
openclaw plugins list
openclaw gateway status
hermes --version
sn-proactive-agent --version
```

`sn-proactive-agent setup --harness openclaw` 尚未提供，不套用 Hermes 安装命令。

## 安装 Connector

在通用流程已确认的同一 Release 下载目录中取得插件，并按 `SHA256SUMS` 核对插件文件：

```text
gh release download v0.1.4 --repo OpenSenseNova/SenseNova-Skills-ProactiveAgent --pattern sn-proactive-agent-openclaw-0.1.4.tgz
```

校验成功且用户授权修改对应 Gateway 配置后：

```text
openclaw plugins install ./sn-proactive-agent-openclaw-0.1.4.tgz
openclaw plugins enable sn-proactive-agent
openclaw config set plugins.entries.sn-proactive-agent.hooks.allowConversationAccess true
openclaw config set plugins.entries.sn-proactive-agent.config.serviceUrl http://127.0.0.1:8080
```

安装到已有插件时先检查版本与本地修改，不直接 `--force` 覆盖。如果配置了 `plugins.allow`，
保留原列表并加入 `sn-proactive-agent`，不要用单个插件替换其他已信任插件。
只修改本插件对应配置；`allowConversationAccess` 允许插件读取接入后的问答，安装前向用户说明。

安全重启指定 Gateway 使插件生效。由服务管理器运行的实例使用：

```text
openclaw gateway restart
```

前台启动的实例由用户结束原进程，再按原启动方式启动；不要同时启动第二个 Gateway。

## 启动与启用监听

先确认没有同地址运行中的 Proactive Agent 实例。以下默认 Gateway 地址须与实际实例一致：

```text
sn-proactive-agent serve --web-only --openclaw-gateway-url http://127.0.0.1:18789
```

如 Gateway 使用 Token 鉴权，由用户在启动服务的环境中提供
`SN_PROACTIVE_AGENT_OPENCLAW_GATEWAY_TOKEN`；不在命令参数、截图或日志里展示 Token。
其他鉴权模式需先确认兼容性，不能通过关闭鉴权来绕过。

打开 <http://127.0.0.1:8080/>，在“设置”中启用 OpenClaw；只监听 OpenClaw 时可关闭 Hermes。
开关控制对话是否进入 Core，不负责启动或连接 Gateway。当前设置中的状态不是实时健康探测，
显示可用或已启用不代表问答采集和续跑已验证。

## 真实对话验收

在用户授权的模型服务上使用一条合成任务，逐项确认：

1. 从用户正常使用的 OpenClaw 界面发消息，回答完成后 Web 出现对应 Project / Item / Event；核对问答和会话标识。
2. 同一会话继续聊天，后续 Event 保持关联。当前插件采集文本 QA；不把附件文件或工具轨迹当作完整采集已验收。
3. 有价值时生成建议，无价值时静默；从 Web 接受建议后回到 OpenClaw，确认原会话执行且未重复提交。
4. 确认实际工作结果和状态更新，回流 Event 包含对应 `source_suggestion_id`，建议变为已执行；该轮不再连续生成新建议。

`doctor --url` 只证明服务健康；当前没有 OpenClaw 专用的 Session doctor，不能将 Hermes 的检查结果当作 OpenClaw 验收。
单个文本字段当前上限为 120,000 字符，超长内容会截断；验收报告不要声称任意长度或所有附件都完整保留。
Gateway 重启会丢失内存中的续跑去重状态；结果不确定时先核对原会话和日志，不自动重发动作。

## 升级与卸载

升级运行包后还需升级已复制的插件。确认当前无运行任务、备份本插件配置与目录，
校验新版插件包后使用 `openclaw plugins install` 的升级方式；只有确认没有需要保留的本地修改时才使用 `--force`，然后重启与复验。

用户要求停用或卸载时，在 Web 设置关闭 OpenClaw，并对原 Gateway 实例执行：

```text
openclaw plugins disable sn-proactive-agent
openclaw plugins uninstall sn-proactive-agent
```

按原方式重启 Gateway，核对本插件配置和信任列表残留。保留用户会话、项目数据和其他插件，
再按通用流程卸载 Proactive Agent 运行包。`sn-proactive-agent uninstall` 当前只管理 Hermes，不能代替上述 OpenClaw 插件卸载。
