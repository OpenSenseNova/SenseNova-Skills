# Hermes 接入

本文件负责安装对话采集组件、Web-only 续跑桥，以及检查目标 Session 是否真正工作。
运行包安装见 [通用流程](../install/overview.md)，变量和路径写法见
[macOS](../install/macos.md)或 [Windows](../install/windows.md)。
建议与接受/忽略只在 Web 展示；Hermes 窗口负责正常对话和获批后的可见执行，不增加原生建议框。

## 接入前提

当前安装说明对应已发布的 `0.1.3`，发布状态与获取前提见通用流程。安装器支持 Hermes 基线
`b03c94dbed5ee72e97eace2376e02092cc854f6a` 对应的 TUI 入口与构建脚本，
以文件指纹核对兼容性，不是声称所有 Hermes 版本都兼容。

需要已可用的 Hermes、Node.js 22+，以及 Hermes 源码根目录的构建依赖。
安装器不会下载或升级 Hermes、Node.js，也不会自动安装构建依赖。
依赖缺失时先核对该版本的锁文件与官方构建方式，再经用户授权补装；
不要为通过检查而覆盖本地改动或修改预期指纹。

```text
hermes --version
hermes --help
node --version
sn-proactive-agent setup --help
sn-proactive-agent doctor --help
```

缺少 Hermes 时先说明缺项，获准后按 [Hermes 官方安装说明](https://hermes-agent.nousresearch.com/docs/getting-started/installation/)
选择系统对应方式。模型由用户通过 `hermes model` 配置；不读取、打印或复制凭据。
实际对话验收需使用用户同意的输入和模型服务，安装过程不调用模型。

确认两个不同目录：

- `SNPA_HERMES_ROOT`：当前可执行文件实际使用、且用户允许修改的 Hermes 源码根目录，内含 `ui-tui/`。
- `HERMES_HOME`：该实例的配置目录，默认是用户 Home 下的 `.hermes/`。安装、启动、检查和卸载必须一致；需要时显式使用 `--hermes-home`。

先按系统说明设置 `SNPA_HERMES_ROOT`，不能把配置目录、任意源码副本或本服务目录当成实际运行的 Hermes。
已有 ACP/TUI 定制版若与基线不同，安装器会停止并保留原文件；本次安装不迁移已有 ACP 链路。
Windows 与 WSL 文档是操作参考，新版完整接入仍需分别验收。

## 安装 Connector

从旧名称升级时，先按通用流程用旧包清理原接线。安装器发现 `proactive-memory-tui`、
旧 Hook 或未恢复的 `.proactive-memory-bridge` 记录时会停止，不覆盖旧配置或叠加第二套组件。

本节会修改指定的 Hermes 源码与配置，须先确认用户授权。先预览：

```text
sn-proactive-agent setup --harness hermes --web-only --hermes-root "$SNPA_HERMES_ROOT" --dry-run
```

预览检查路径、文件冲突和源码兼容性，不执行构建、不启用插件，也不能保证构建依赖齐全。
确认目标无误后安装：

```text
sn-proactive-agent setup --harness hermes --web-only --hermes-root "$SNPA_HERMES_ROOT"
```

安装器会预检查配置及观测文件，备份 TUI 入口与现有构建产物，加入 Web-only 桥接并构建，
再安装 Hook 和 Python 观测组件、启用插件。构建或启用失败时恢复本次改动的原文件。
TUI 备份与指纹记录位于源码下 `ui-tui/.sn-proactive-agent-bridge/`，恢复后仍保留备份。
重复安装同一版本不会重复接线或构建；未知文件修改会阻止安装。
`setup` 不复制 Skill、不启动服务或 Hermes、不发送验收消息。

只想安装观测资源时，必须明确选择：

```text
sn-proactive-agent setup --harness hermes --web-only --observer-only
```

该模式不安装续跑桥，不能报告完整接入成功。`--no-tui-plugin` 仅用于明确选择的 classic CLI。
历史补丁文件仍作为兼容资源保留，但新安装器不应用原生红框/ACP 补丁。

安装后核对静态资源，再继续通用流程第 4 步启动 `serve --web-only`：

```text
sn-proactive-agent doctor --harness hermes --hermes-root "$SNPA_HERMES_ROOT" --json
```

此时尚无真实回流，必需项显示 `unverified`、退出码为 1 是正常的，不应反复重装。

## 真实对话验收

Web 服务启动后，安全地重启接入后的 Hermes 窗口，使新构建与插件生效：

```text
hermes --tui --accept-hooks
```

自定义服务地址时，先按系统说明设置 `SN_PROACTIVE_AGENT_SERVICE_URL`，再从同一终端启动。
桥接通过当前窗口的原生 `prompt.submit` 接口提交获批动作，固定原 Session ID，
不模拟按键、不另开 Hermes 进程，也不把建议文本当成 Shell 或斜杠命令解释。
同一 Session 同时打开多个窗口时只允许一个在线桥接持有续跑权。

使用用户同意的真实对话，依次核对：

1. 新输入到达 `turn.started`；回答完成后到达含完整 QA 的 `turn.completed`，Project / Item / Event 随之更新。
2. 无推进价值时静默，有价值时仅在 Web 展示建议；用户开始下一轮后，上一轮只更新状态、不再生成建议。
3. 用户在 Web 接受后，原窗口可见地执行一次；忽略时不执行，不再手工粘贴同一动作。
4. 结果带 `source_suggestion_id` 回流，更新状态，本轮不连续生成下一条建议。

取得该窗口的实际 Session ID，按系统说明设置 `SNPA_SESSION_ID` 后检查：

```text
sn-proactive-agent doctor --harness hermes --hermes-root "$SNPA_HERMES_ROOT" --url http://127.0.0.1:8080 --session-id "$SNPA_SESSION_ID" --json
```

| 检查项 | 什么情况下通过 |
|---|---|
| `hermes_observer_installed` | 指定配置实例的观测文件与安装包一致；单独通过不代表启用 |
| `hermes_bridge_installed` | 指定源码的桥接文件与构建产物符合安装记录；不是在线证明 |
| `hermes_bridge_online` | 指定实例、Session 的活动窗口完成心跳往返探测 |
| `hermes_turn_capture` | 该在线窗口已收到配对的新轮次信号与完整 QA |
| `hermes_same_session_resume` | Core 授权动作被该窗口领取，并在原 Session 带对应来源 ID 完成回流 |

`doctor` 只读诊断回执，不启动 Hermes、不调用模型、不读取历史 QA 或配置凭据。
未发生真实对话/续跑时保持 `unverified`；窗口离线、服务重启或实例不匹配时，旧证据不能作为当前在线能力证明。
自动检查证明链路已产生对应回执，实际状态更新和业务执行结果仍按前四步核查。
旧服务没有诊断接口时明确报告缺少能力，不能以健康检查成功替代。
续跑只领取一次；网络结果不确定时不自动重发动作。需要了解失败原因时查看对应日志。

## 升级与卸载接入

升级前先安全停止相关服务与窗口，恢复旧桥，再更换运行包、重新安装并验收。
源码或构建产物若在安装后被修改，自动恢复会停止；保留修改并确认迁移方式，不强制覆盖。
用户要求卸载时，明确指定原来的源码目录与配置实例：

```text
sn-proactive-agent uninstall --harness hermes --hermes-root "$SNPA_HERMES_ROOT" --dry-run
sn-proactive-agent uninstall --harness hermes --hermes-root "$SNPA_HERMES_ROOT"
```

清理会恢复安装前的 TUI 入口和构建产物，移除本组件 Hook、观测文件与新桥接模块，
保留源代码备份、用户数据和其他 Hermes 配置。仅安装观测资源、没有续跑桥时可省略 `--hermes-root`。

已知限制：旧观测清理仍可能保留 `plugins.enabled` / `plugins.entries` 中的
`sn-proactive-agent-tui` 配置。发现时报告残留；需要进一步清理时只处理该组件对应项，
不覆盖整个配置，不宣称完整卸载。接入清理完成后，再按通用流程卸载运行包和独立 Skill。
