---
name: sn-deepresearch-cli
description: >-
  一键启用 SenseNova-Skills-DeepResearch，用于行业与市场研究、竞品分析、政策或技术调研、商业尽调、趋势分析、方案对比、事实核查，以及研究报告、白皮书等交付场景。用户提出深度研究、调研、调查、尽调、research/deepresearch，或任务需要跨来源取证、多维度比较和交叉验证时主动使用；Skill 会完成环境检查、SenseNova-Skills-DeepResearch 安装或升级、Harness 与 Search/Camofox 准备、参数确认、研究启动和 Web 进度提示。简单常识问答、单一来源整理和纯文字润色不使用。
---

# sn-deepresearch-cli

作为 SenseNova-Skills-DeepResearch 的用户入口，负责环境预检、安装引导、参数确认、任务启动、进度告知和结果交付。
默认 npm 包为 `sensenova-skills-deepresearch`，项目源码仓库为
`https://github.com/OpenSenseNova/SenseNova-Skills-DeepResearch`。用户侧直接安装已构建并发布到 npm 的包，
不需要 clone 仓库或本地构建。

## 环境预检

在安装或启动 SenseNova-Skills-DeepResearch 前，仅检查当前环境是否具备运行条件：

- Node.js >= 22、Python >= 3.10 和 npm 是否可用；
- 是否已安装 SenseNova-Skills-DeepResearch 提供的 `deepresearch` 命令；
- 用户选择的 Hermes、Codex、Claude Code 或 OpenClaw 是否存在。

这里使用系统的命令存在性和版本检查即可。SenseNova-Skills-DeepResearch 提供的 `deepresearch` 命令尚未安装时，不得提前调用
`deepresearch doctor`、`sources`、`browser`、`status` 等 SenseNova-Skills-DeepResearch 子命令。SenseNova-Skills-DeepResearch 或 Harness 缺失时先报告缺失项，
不要静默改用其他 Harness。

不得显示环境变量值、token、Cookie、npm 凭据或 Harness Profile。

## 安装或升级 SenseNova-Skills-DeepResearch

安装会访问网络并修改用户级 npm 目录，执行前先取得当前环境要求的授权。

从 npm 安装已构建好的包：

```bash
npm install --global sensenova-skills-deepresearch
deepresearch --help
```

升级到最新版本：

```bash
npm install --global sensenova-skills-deepresearch@latest
```

维护者在发布侧负责构建 Python wheel 和 npm tarball；Skill 不得让用户 clone 源码、运行
`scripts/build_npm_package.py`、创建构建虚拟环境或从 GitHub Release 下载 tarball。只有用户明确提供本地
`.tgz` 并要求测试时，才可执行 `npm install --global <local-tgz>`。

安装后初始化用户级 Search 配置：

```bash
deepresearch sources init
deepresearch sources list --json
```

配置文件位于 `~/.deepresearch-cli/search/.env`。公开来源无需 API key；需要扩展来源时，只告知应填写的变量名，
不索取或回显凭据。

## 准备 Harness

- Hermes：复用现有 Hermes 登录和模型配置。
- Codex：确认 `codex` 存在且已执行 `codex login`。
- Claude Code：当前 ACP Harness 必须能找到 `claude-agent-acp` 可执行文件；普通 `claude`
  命令不能直接替代它。SenseNova-Skills-DeepResearch 内含调用适配代码，但不捆绑外部 adapter。adapter 缺失时，在获得安装授权后执行
  `npm install -g @agentclientprotocol/claude-agent-acp`。安装完成不等于必须重复登录：先运行
  `deepresearch doctor --harness claude-code --json` 检查认证。已有 `ANTHROPIC_API_KEY`、
  `ANTHROPIC_AUTH_TOKEN`、Bedrock/Vertex 配置，或 adapter 可复用现有 Claude Code 登录时，直接使用；
  只有预检确认没有可用认证时，才提示用户执行 `claude-agent-acp --cli auth login`。不得读取或回显凭据值。
- OpenClaw：确认 `openclaw` 存在且 Gateway 正常。模型由 OpenClaw 配置选择，不传
  `--harness-model`。启动研究前先识别当前会话实际使用的 Agent 和工作区，不要把 `main`、
  `~/.openclaw/workspace` 或其他设备上的路径写死。检查该 Agent 是否具备当前工作区的写入能力：

  ```bash
  openclaw health --json
  openclaw agents list --json
  openclaw config get agents.entries.<current-agent>.sandbox --json
  openclaw config get agents.entries.<current-agent>.tools --json
  ```

  工作区必须允许写入（`workspaceAccess: rw`，或使用非沙箱工作区），工具策略至少要能使用
  `read`、`write`、`edit`、`apply_patch`、`exec` 和 `process`。如果配置缺失，先说明
  DeepResearch 的 `plan`、研究和报告节点需要在本次 Run 的 attempt 工作区创建产物。先向用户说明
  需要为当前 Agent 的当前工作区授予写权限，取得授权后再修改对应 Agent 配置、重启 Gateway 和复核；
  不要静默扩大其他 Agent 或其他工作区的权限。检查未通过时不要启动 SenseNova-Skills-DeepResearch。换设备或换 Agent 时重复
  这项预检，不复用旧机器的固定路径或配置。

  配置检查通过后，在启动正式研究前执行一次 OpenClaw 写入冒烟检查：

  ```bash
  deepresearch doctor --harness openclaw --json
  ```

  该检查必须确认 ACP 子会话能够在当前 SenseNova-Skills-DeepResearch 工作区创建并删除临时文件；如果返回
  `workspace-write` 失败，先停止，不要启动正式研究。冒烟检查使用当前设备和当前 Agent 的
  实际工作区，不复用其他机器的测试结果。

模型、登录或 Provider 凭据缺失时，说明缺失配置，不替用户改写 Harness 全局配置。

## 模型调用超时与恢复

如果节点日志显示模型调用因连接层长时间无响应、stale/idle timeout、request timeout、broken pipe或类似 provider 错误中止，先向用户说明：失败发生在模型 provider/连接层，并确认失败节点、重试次数、实际 harness、provider、model 和超时类型；不要把它误判为搜索、报告转换或 SenseNova-Skills-DeepResearch 安装失败。

先读取该 Harness 的官方配置或诊断输出，确认是“无响应空闲超时”还是“整次请求超时”，并只展示配置键名和当前值，不展示凭据。任何修改超时、重试次数、provider 或模型的操作都必须先向用户说明影响并申请授权，不得静默修改全局配置。

获得授权后，优先只针对本次实际使用的 provider/model 将无响应空闲超时调到 300 秒，再使用原 harness 从失败 Run 恢复；不要从头重跑已成功的 plan/research。以 Hermes 为例，确认配置键为 `providers.<provider_id>.models.<model>.stale_timeout_seconds` 后，才可执行：

```bash
hermes config set providers.<provider_id>.models.<model>.stale_timeout_seconds 300
deepresearch resume <run-id> --harness hermes --progress tools
```

如果实际使用的是其他 Harness，先查明其等价配置键和修改命令，再向用户确认，不凭记忆猜测命令。
重试仍失败时，保留原 Run 和日志，报告新的失败节点及 provider 错误。

## 准备 Camofox

Camofox 是普通网页抓取失败后的可选回退，基础 SenseNova-Skills-DeepResearch 不包含浏览器文件。
用户希望启用时，先说明需额外下载数百 MB 资源，再在授权后执行：

```bash
deepresearch browser setup
deepresearch browser start
deepresearch browser status --json
```

用户选择启用时确认健康状态。Camofox 只访问公开网页，不用于绕过 CAPTCHA、登录、付费墙或访问控制。
未安装或不可用时不阻塞研究，SenseNova-Skills-DeepResearch 会切换其他来源。只有用户明确要求时才传入 `--no-camofox-fallback`。

## 确认研究参数

开始前确认研究问题以及三个独立参数：

- 研究深度：`quick`、`normal` 或 `heavy`
- 报告形式：`brief` 或 `formal_report`
- 交付格式：`markdown`、`html`、`pdf` 或 `docx`
- 报告语言：跟随用户的主要语言；用户明确指定语言时优先使用指定值（例如中文使用 `zh-CN`，英文使用 `en-US`）

用户已给出的参数不要重复询问，没给出的参数需要向用户确认。选择 DOCX 时提醒需要 Pandoc；选择 PDF 时提醒需要 Typst。
用户主要语言可从当前对话判断，不要为了语言参数重复询问；只有无法判断且语言会影响交付时才询问。上述参数未确认完成前，不得启动可能长时间运行或产生费用的研究。

## 启动研究

### Query 与标题保持原文

- 用户在本轮提供的研究文本就是 SenseNova-Skills-DeepResearch 的实际 query；去掉仅用于触发 Skill 的前缀（例如“使用
  deepresearch”）后，原文直接传给 SenseNova-Skills-DeepResearch。
- 不要替用户改写、扩展、总结、压缩或重新命名 query，不要另造展示标题，也不要把 query 改成
  “研究 + 主题”的标题。
- 用户写在 query 中的范围、数据源要求、时间范围和交付要求必须原样保留。研究标题由 SenseNova-Skills-DeepResearch/Web
  根据原始 query 展示，Skill 不参与标题生成。
- `mode`、`report_format`、`output_format` 和 `language` 只作为 SenseNova-Skills-DeepResearch 参数传递，不得混入或改写
  query 文本。

Quick 使用前台 SenseNova-Skills-DeepResearch：

```bash
deepresearch "<query>" \
  --mode quick \
  --report-format <brief|formal_report> \
  --output-format <markdown|html|pdf|docx> \
  --harness <hermes|codex|claude-code|openclaw> \
  --language <user-language> \
  --progress tools
```

Normal 和 Heavy 使用 Web 入口。启动前确定端口：优先使用用户明确指定的端口；否则检查默认端口是否可用，必要时选择一个可用端口。不要把端口写死在 Skill 或对用户承诺一个尚未确认的地址。在可持续读取输出、且启动后能将控制权返回给 Agent 的后台或持久终端会话中运行：

```bash
deepresearch web "<query>" \
  --mode <normal|heavy> \
  --report-format <brief|formal_report> \
  --output-format <markdown|html|pdf|docx> \
  --harness <hermes|codex|claude-code|openclaw> \
  --language <user-language> \
  --host 127.0.0.1 \
  --port <selected-port> \
  --progress tools
```

保持该进程运行，不要再启动第二份相同研究。等待 SenseNova-Skills-DeepResearch 日志确认 Web 已在所选端口开始监听后，再把实际地址告诉用户：

```text
研究已经启动，可打开 http://127.0.0.1:<selected-port> 查看实时进度。
```

将 `<selected-port>` 替换为本次运行实际使用的端口。不要等待整个研究完成后才回复用户。如果 Web 启动失败，报告启动错误，不要提供尚不可用的地址。

展示链接不等于强制打开浏览器；需要 GUI 操作时遵循当前环境授权。只有用户明确要求局域网访问时才使用
`--host 0.0.0.0`，并提醒运行轨迹和报告会对同网段可见。

### Harness/SenseNova-Skills-DeepResearch 监控

研究启动后，必须保留本次 Run 所使用的 Harness 和 SenseNova-Skills-DeepResearch 监控进程，持续观察其 stdout/stderr、心跳和
`deepresearch status <run-id> --json` 状态。长时间没有新输出不等于进程已失效：先读取状态和最近日志，
不要因为暂时无输出就重复启动 Harness、启动第二份 SenseNova-Skills-DeepResearch 或终止现有进程。监控会话中断时，优先重新连接
到原进程；只有确认原进程已经退出、Run 已结束，或用户明确要求停止时，才可以结束监控或启动恢复命令。

若监控发现 provider 超时、Harness 退出或 Run 失败，保留原进程输出和 Run 目录，按“模型调用超时与恢复”
流程向用户说明并申请配置修改授权；未经授权不得重启、改配置或并行启动新的 Harness。

## 完成、失败与恢复

- 成功：报告 `run_id`、运行状态和 `output/<run-id>/` 中的最终文件。
- 失败或中断：如实说明失败节点，并保留 `runs/<run-id>/`。
- 恢复：确认原进程已结束后，执行 `deepresearch resume <run-id> --harness <harness>`。

不把搜索命中或中间文件当作最终报告，不伪造完成状态，不在 SenseNova-Skills-DeepResearch 安装目录保存用户运行记录。

## SenseNova-Skills-DeepResearch 诊断

本节只在 SenseNova-Skills-DeepResearch 已安装后使用。正常研究流程不要预先执行整套诊断；仅当用户明确要求诊断，或安装验证失败、
Search 异常、Web 无法访问、Run 停止更新、节点失败、报告未生成时，按当前问题选择最少的只读检查：

```bash
deepresearch --help
deepresearch diagnostics --json
deepresearch doctor --harness <harness> --json
deepresearch sources list --json
deepresearch domains list --json
deepresearch browser status --json
deepresearch status <run-id> --json
deepresearch resume --help
deepresearch web --help
```

参数不确定时先查看对应的 `--help`，不要凭记忆猜测。

- Search 异常：只报告来源可用性和缺失的变量名。
- Camofox 不可用：切换来源继续研究，不让工作流因此阻塞。
- Run 失败：保留运行记录，只在确认原进程已结束后恢复。

出现上述异常时，先执行 `deepresearch diagnostics --json`，再完整读取其 `path` 字段指向的 SenseNova-Skills-DeepResearch 内置诊断手册。不要根据 Skill 所在目录推断 SenseNova-Skills-DeepResearch 的安装位置，也不要读取 Skill 旁边或源码仓库中的相对路径。

正常流程不要加载诊断手册。若命令失败或返回路径不存在，使用本节的最小只读检查并明确说明 SenseNova-Skills-DeepResearch 诊断手册缺失。
诊断手册中的安装、配置修改、服务启动和网络操作仍需遵循当前环境授权；读取手册本身不扩大用户授权范围。
