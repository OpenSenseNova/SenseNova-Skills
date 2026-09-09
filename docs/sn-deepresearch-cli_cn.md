# SenseNova 深度研究 CLI

简体中文 | [English](sn-deepresearch-cli.md)

`sn-deepresearch-cli` 是用于安装和运行独立
[`sensenova-skills-deepresearch`](https://www.npmjs.com/package/sensenova-skills-deepresearch)
CLI 的仓库 skill，适合多来源研究、实时进度跟踪、可恢复运行，以及通过指定 Harness
或 Agent 交付简报或正式报告。

如果希望使用仓库内置的集成式 controller，请使用
[`sn-deep-research`](../skills/sn-deep-research/SKILL.md)；如果需要独立安装的命令、明确
的 Harness 选择、进度监控和恢复控制，请使用本 CLI 入口。

## 环境要求

- Node.js 22 及以上、Python 3.10 及以上和 npm。
- 支持的 Harness 之一：Hermes、Codex、Claude Code 或 OpenClaw。
- 只有使用扩展来源时才需要对应的搜索凭证。
- 导出 DOCX 需要 Pandoc，导出 PDF 需要 Typst。

公开来源不配置额外 API key 也可以使用。不要把 token、cookie 或 Harness 配置写入
prompt、报告、日志或提交。

## 安装

安装已发布的 npm 包，不要直接 clone 或本地构建源码仓库：

```bash
npm install --global sensenova-skills-deepresearch
deepresearch --help
deepresearch sources init
deepresearch sources list --json
```

源码仓库独立维护于
[`OpenSenseNova/SenseNova-Skills-DeepResearch`](https://github.com/OpenSenseNova/SenseNova-Skills-DeepResearch)。
用户级搜索配置位于 `~/.deepresearch-cli/search/.env`。

## 准备 Harness

优先复用已有的登录状态和模型配置：

- Hermes：确认 Hermes 已安装并完成登录。
- Codex：确认 `codex` 可用，必要时执行 `codex login`。
- Claude Code：确认存在 `claude-agent-acp`；普通 `claude` 命令不能直接替代该适配器。
- OpenClaw：确认当前 Agent、Gateway 健康状态、工作区写权限，以及 `read`、`write`、
  `edit`、`apply_patch`、`exec`、`process` 工具权限。

正式研究前，对 OpenClaw 执行一次写入冒烟检查：

```bash
deepresearch doctor --harness openclaw --json
```

不要静默修改 Harness 的 provider、模型、超时或全局工作区权限；需要修改时先说明影响
并取得授权。

## 启动研究

启动前确认研究深度（`quick`、`normal` 或 `heavy`）、报告形式（`brief` 或
`formal_report`）、输出格式（`markdown`、`html`、`pdf` 或 `docx`）和语言。

Quick 模式使用前台命令：

```bash
deepresearch "<研究问题>" \
  --mode quick \
  --report-format <brief|formal_report> \
  --output-format <markdown|html|pdf|docx> \
  --harness <hermes|codex|claude-code|openclaw> \
  --language <语言> \
  --progress tools
```

Normal 和 Heavy 模式使用 Web 入口。选择一个实际可用的本地端口，并保持进程运行：

```bash
deepresearch web "<研究问题>" \
  --mode <normal|heavy> \
  --report-format <brief|formal_report> \
  --output-format <markdown|html|pdf|docx> \
  --harness <hermes|codex|claude-code|openclaw> \
  --language <语言> \
  --host 127.0.0.1 \
  --port <可用端口> \
  --progress tools
```

不要擅自改写用户的研究问题，也不要重复启动同一研究。只有确认 Web 服务已经监听后，
才向用户提供实际进度地址。

## 监控与恢复

保持 Harness 和 CLI 监控进程运行。日志暂时没有变化不代表任务已经失效，应先查看状态：

```bash
deepresearch status <run-id> --json
deepresearch diagnostics --json
```

任务失败或中断时保留运行目录；确认原进程结束后再恢复：

```bash
deepresearch resume <run-id> --harness <harness>
```

最终交付应包含 `run_id`、最终状态和输出目录。搜索命中结果或中间文件不能当作最终报告。
