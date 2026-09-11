---
name: sn-proactive-agent
description: 安装、启动和使用 Proactive Agent，记录项目进展并在合适时机提醒下一步。
---

# Proactive Agent

本 Skill 是 Agent 的操作说明，运行代码通过独立的 Python 安装包获取。
服务整理多轮对话中的项目进展，发现值得推进的事情时在 Web 工作台提出建议；
用户接受后，由对应 Connector 交回原 Session 继续执行。

## 按任务读取说明

- 询问原理、状态或已有记录时，只做相关的只读检查，不因加载 Skill 就安装、改配置或启动服务。
- 用户要求安装、启动、升级或卸载时，先读 [通用流程](references/install/overview.md)，再按实际运行环境读取一份系统说明。
- 配置对话接入时，只读取当前 Harness 对应的 Connector 说明，不加载其他平台的资料。

| 条件 | 读取文件 |
|---|---|
| 安装、运行与维护服务 | [install/overview.md](references/install/overview.md) |
| macOS | [install/macos.md](references/install/macos.md) |
| Windows PowerShell 或 WSL | [install/windows.md](references/install/windows.md) |
| Hermes 接入 | [connectors/hermes.md](references/connectors/hermes.md) |

`install/` 负责操作系统、依赖和服务生命周期；`connectors/` 负责 Harness
配置、对话采集与获批续跑。当前安装入口只支持 Hermes；其他 Harness 不能直接套用
Hermes 的命令。当前运行包为已发布的 `0.1.3`，可安装指定 Hermes 基线的 Web-only 续跑桥，
会检查源码兼容性、备份并构建；不覆盖未知版本或本地改动。固定版本与 GitHub Release
下载前置检查见通用流程；目前通过 GitHub Release 安装，尚未发布到 PyPI。安装包验收不等于真实接入验收。
Windows 说明是安装参考，不代表完整接入已验收。

## 命名与命令

- 本 Skill 的目录和文件名使用英文；除标准入口 `SKILL.md` 外，使用小写与连字符。
- 示例命令、参数、变量名和命令块中的注释统一使用英文，中文解释放在命令块外。
- 保留程序原有的命令名称，不翻译参数。用户真实路径即使含中文，也应按原名正确引用，不为符合示例命名而改动用户文件。

## 运行边界

- 安装 Skill 与安装运行包是两件事；`pipx` 不会把 Skill 安装到 Harness，也不会自动启动服务。
- 区分运行包、安装文件、目标窗口在线与真实回流检查。`doctor --session-id` 读取指定窗口的实际证据，不主动发消息；`unverified` 不等于通过，旧包缺少检查能力也不能视为接入成功。
- 当前使用 Web 展示建议、接受或忽略、项目进展与日报；服务按 `serve --web-only` 启动，不启用终端内的重复建议界面。
- Connector 自动上报完整 QA 和新一轮输入信号；Core 负责归属、状态更新和提醒判断。
- 建议不是授权。用户接受后，只通过 Connector 续跑原 Session；读取 Skill 的 Agent 不应另外提交同一动作，造成重复执行。
- 执行结果由 Connector 带 `source_suggestion_id` 回流；本轮更新状态，不连续生成下一条建议。
- 不代替后台服务直接编辑 `project.md`、`item.md`、`events.md` 或 `runtime.jsonl`。
- 不读取、打印或复制 API Key、`.env` 或其他凭据。

## 查看记录

数据默认放在当前用户 Home 下的 `.sn-proactive-agent/`，不是安装包或源码目录。
可用 `--data-root` 或 `SN_PROACTIVE_AGENT_DATA_ROOT` 覆盖。首次有明确长期目标的
完整对话后，服务按归属创建 Project / Item，用户不需要手工建项目；一次性问题可仅记录在运行日志中。

升级用户若已有 `.proactive-memory/` 且新目录不存在，自动沿用旧目录，不搬迁或合并。
旧 `PROACTIVE_MEMORY_*` 环境变量可继续读取，同名的新 `SN_PROACTIVE_AGENT_*` 设置优先。

以下路径相对于数据根目录：

- `projects/<project-id>/project.md`：项目概述和 Item 索引。
- `projects/<project-id>/items/<item-id>/item.md`：事项最新状态。
- `projects/<project-id>/items/<item-id>/events.md`：相关 QA 与状态变化，用于溯源。
- `runtime.jsonl`：对话接收、归属、提醒或静默原因、用户决定、执行结果与日报记录，用于恢复、去重和审计。

Web 读取这些记录的 JSON 展示结果，不直接修改源文件。建议区域保持简短；
详细判断依据保存在运行记录中，按需检查。
