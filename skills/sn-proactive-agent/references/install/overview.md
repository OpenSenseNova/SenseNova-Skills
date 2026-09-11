# 安装与运行

本文件是 Agent 的共用执行流程。系统差异分别见 [macOS](macos.md) 和
[Windows](windows.md)，Hermes 配置见 [接入说明](../connectors/hermes.md)。
只读咨询不触发安装；执行变更前，确认用户已授权相应范围。

## 安装对象与版本

- **Skill**：由 Harness 的 Skill 管理机制安装完整的 `sn-proactive-agent/` 目录，必须包含 `SKILL.md` 和 `references/`，不能只复制入口文件。
- **运行包**：通过 `pipx` 安装 Core、Web 和 Connector 资源。
- **用户数据**：保存在用户 Home 下的 `.sn-proactive-agent/`，不进入安装包。

当前运行包是统一改名后的 `0.1.3`，包含 Web-only Connector 安装和按 Session
的能力探测。`v0.1.3` 已发布到 GitHub Release，但尚未发布到 PyPI；不能直接按包名从索引安装。
后续发布渠道为 [GitHub Releases](https://github.com/OpenSenseNova/SenseNova-Skills-ProactiveAgent/releases)。
已发布的 `v0.1.2` 保持旧包名 `proactive-memory-service`，不改写旧 Tag 或附件，
也不把旧包当成新名称安装失败后的替代。

仅在维护者完成发布后，确认 `v0.1.3` 已发布、不是草稿，并包含以下文件：

- `sn_proactive_agent-0.1.3-py3-none-any.whl`：运行包。
- `SHA256SUMS`：发布文件的 SHA-256 校验值。

Release 不存在、无访问权限或校验失败时停止，报告具体原因，不改用 `main`、旧包或猜测地址。
发布前只可在用户明确要求本地验收时安装本地构建、已校验的 wheel，不执行下面的 Release 下载。
发布后，Skill 源码应位于同一 Tag 下的 `skills/sn-proactive-agent/`；按 Harness 的机制安装完整目录，
不把运行包安装当成 Skill 已安装。预发布与安装检查通过，也不代表所有 Harness 或操作系统已完成验收。

## 1. 检查与授权

先确认操作系统、Shell、Harness 版本、Python 3.11 或更高、pipx、现有服务与端口占用。
Windows 必须先区分原生 PowerShell 与 WSL，保证服务和 Harness 处于同一运行环境。
按相应系统文档准备依赖并设置 `SNPA_PYTHON`，再继续第 2 步；之后的执行顺序由本文件统一组织。

向用户说明下载来源、会修改的 Connector 配置、服务地址和数据目录。
若当前请求已明确授权这些操作，按该范围执行；缺少授权时先询问。
缺少 Python、pipx 或 Harness 时说明缺项，不静默安装新的包管理器或其他 Agent 产品。

不要读取或输出凭据；模型配置由用户在 Harness 提供的配置入口完成。

## 2. 安装运行包

**以下下载命令是发布后的流程，目前不可当作已可用的下载入口。**
已有 GitHub CLI 且账号具有仓库读取权限时，先执行版本检查；确认 Release 与附件存在后，
才在本次下载的空目录中执行下载命令：

```text
gh release view v0.1.3 --repo OpenSenseNova/SenseNova-Skills-ProactiveAgent --json tagName,isDraft,isPrerelease,assets
gh release download v0.1.3 --repo OpenSenseNova/SenseNova-Skills-ProactiveAgent --pattern sn_proactive_agent-0.1.3-py3-none-any.whl --pattern SHA256SUMS
```

不要使用 `--clobber` 覆盖现有文件，也不要把访问令牌写到命令或 URL 中。没有 GitHub CLI 时，
可以让有权限的用户从上述 Release 页面下载相同文件；不因此自动安装新的工具或修改仓库可见性。
用当前系统的 SHA-256 工具核对 wheel 与 `SHA256SUMS` 中同名文件的记录，必须一致才继续。
校验值应来自同一个已确认的 Release；它用于发现内容变化或下载损坏，不替代来源与权限检查。

使用系统说明中已经检查的 `SNPA_PYTHON` 解释器，并把 `SNPA_PACKAGE` 设置为已校验
wheel 的绝对路径。下面是 POSIX Shell 与 PowerShell 通用的单行命令；
两个变量必须在当前终端中已设置且非空，换终端后需要重新设置：

```text
pipx install --python "$SNPA_PYTHON" "$SNPA_PACKAGE"
```

如果已经安装，先确认版本与来源，再判断是否需要升级，不强制覆盖现有环境。
安装后检查：

```text
sn-proactive-agent --version
sn-proactive-agent --help
sn-proactive-agent doctor --help
sn-proactive-agent doctor --json
```

命令不存在时按系统说明检查 PATH；缺少所需子命令时停止接入并报告版本不兼容，
不要拼接源码路径冒充安装包入口。新增检查的 JSON 包含 `scope` 和每项 `status`：

| 检查结果 | 含义 |
|---|---|
| `scope: runtime` | 仅检查运行包、Python、数据目录及显式指定的健康接口 |
| `scope: hermes` | 额外检查指定 Hermes 实例；传入服务地址与 Session ID 后检查该在线窗口的实际回流 |
| `passed` / `failed` / `unverified` | 已通过 / 已发现问题 / 尚无足够证据 |

必需项失败或未验证时，命令返回非零退出码。基础检查通过不等于模型调用或完整接入通过。
若旧包没有这些字段、`setup --hermes-root` 或 `doctor --session-id`，报告为“缺少新版接入检查”，
停止自动接入；可以在用户同意下仅启动 Web 查看已有记录。

## 3. 配置 Connector

按实际 Harness 读取对应文件；当前提供 [Hermes](../connectors/hermes.md)。
本步执行该文件的“接入前提”和“安装 Connector”。安装器只对显式指定且兼容的源码
进行备份、接线和构建；前提不满足时停在这里，不手动强行打补丁或重装 Harness 来绕过。
配置完成后继续第 4 步；仅安装观测资源的环境不能按完整接入验收。

## 4. 启动 Web 并检查

当前使用前台服务，在单独终端执行：

```text
sn-proactive-agent serve --web-only
```

在另一个终端检查服务：

```text
sn-proactive-agent doctor --url http://127.0.0.1:8080 --json
```

然后打开 <http://127.0.0.1:8080/>。如果使用了自定义端口或数据目录，检查、浏览器和
Connector 必须指向同一个实际服务地址，不能遇到占用就停止不明进程。

`--web-only` 关闭终端内建议展示，但不取消对话采集和获批续跑。
没有可用的 Hermes 模型时，网页可能仍能显示已有记录；这不代表新对话能够被整理。
没有兼容桥接时只报告 Web 可用，不尝试接受建议来证明接入成功。

## 5. 对话与原 Session 续跑验收

Web 可用且接入前提已满足后，执行 Connector 说明中的
[真实对话验收](../connectors/hermes.md#真实对话验收)。需要用户同意使用的输入和模型服务，
检查完整 QA、状态更新、Web 决策、获批后原 Session 执行和结果回流。

向用户分别报告安装版本、Harness、Web 地址、数据目录，以及安装、启动、对话采集和续跑各自的验证结果。

## 停止、升级与卸载

这些操作只在用户要求时执行，并先确认当前服务归属以及是否还有正在处理的对话或获批动作。

- **停止**：在本次启动服务的终端按 `Ctrl+C`；若由其他进程管理器启动，使用该实例对应的停止方式。当前命令没有配置开机自启，不把终端前台运行称为常驻服务。
- **升级**：先核对现有环境与来源，确认已验证的目标版本。已安装续跑桥时，先按 Connector 说明恢复旧桥，再更换运行包。下载新版本 Release 的 wheel 并核对该版本校验值，再使用第 2 步命令，把 `SNPA_PACKAGE` 换成新 wheel 并增加 `--force`。固定版本链接不会自动变成新版本，不用移动旧 Tag 或覆盖旧安装包实现升级。保留已检查的 `--python`；原环境有注入包或自定义选项时先确认保留方式，不直接覆盖。

```text
pipx list --json
pipx install --help
```

不使用无版本限制的 `pipx upgrade` 作为固定版本升级方案。完成后重新核对
`--version` 和 `doctor` 输出，再按 Connector 说明刷新已复制的资源、重启并复验。
只更新 pipx 包不会刷新已复制到 Harness 的 Hook、插件或已构建的续跑桥。
`--python` 与 `--force` 的参数含义见 [pipx 官方参考](https://pipx.pypa.io/stable/reference/cli.html)。

- **卸载**：先按 Connector 说明清理接入，再卸载运行包；若用户也要求移除 Skill，使用 Harness 的管理机制单独移除说明文件。

```text
pipx uninstall sn-proactive-agent
```

默认保留实际数据目录的全部用户数据，包括沿用的 `.proactive-memory/`；只有用户明确要求删除数据时，才另行确认目标后处理。
遇到 Connector 清理残留，应报告尚未清理的内容，不宣称完整卸载成功。

### 从旧名称升级

旧包与新包是不同的安装标识，不使用 `--force` 把改名伪装成普通原地升级。
先停止旧服务，用旧包的 `proactive-memory-service uninstall` 清理原 Connector
（有桥接时传入原 `--hermes-root`，自定义配置时传入原 `--hermes-home`），
确认旧接线已恢复，再卸载旧运行包、安装新 wheel 并重新接入。
安装器发现旧 Hook、插件或未恢复的桥接时会停止，不会并行安装导致重复上报。
当前新包的 `uninstall` 只管理新名称的组件，不能替代旧包的卸载命令。

新用户默认使用 `.sn-proactive-agent/`；若新目录不存在且已有 `.proactive-memory/`，自动沿用旧数据。
两者都存在时默认选新目录，不自动合并，可用 `--data-root` 明确选择。
旧 `PROACTIVE_MEMORY_*` 环境变量仍可读；`SN_PROACTIVE_AGENT_*` 同名设置优先，命令行参数优先于环境变量。

## 开发验收

只有用户明确要求在源码仓库验收时，才使用源码入口。不要为解决正式安装问题而悄悄改用
本机仓库路径。开发验收与安装包验收分别记录；本文件重组不代表新增操作系统已通过测试。
