# macOS 安装说明

本文件只补充 macOS 的环境和命令差异。完整流程见 [安装与运行](overview.md)，
Hermes 配置见 [接入说明](../connectors/hermes.md)。

## 检查环境

在当前用户的 zsh 或 Bash 中检查：

```bash
uname -s
command -v python3
python3 --version
command -v pipx
```

Python 必须满足运行包的 3.11 或更高要求；若有多个 Python，应确认安装包实际使用的解释器版本。
缺少依赖时说明情况，不修改系统 Python，也不把其他项目的虚拟环境当成本服务的安装位置。

## 准备 pipx

若用户已安装 Homebrew，并授权补装 pipx，可按 [pipx 官方说明](https://pipx.pypa.io/stable/how-to/install-pipx.html)执行：

```bash
brew install pipx
pipx ensurepath
```

如果没有 Homebrew，不顺带安装新的包管理器；先与用户确认依赖安装方式。
`pipx ensurepath` 可能修改 Shell 配置。重新打开终端，或者在 pipx 已可运行时，
按 [pipx 路径说明](https://pipx.pypa.io/latest/how-to/configure-paths.html)使应用命令目录对当前终端生效：

```bash
export PATH="$(pipx environment --value PIPX_BIN_DIR):$PATH"
pipx --version
```

## 指定安装解释器

在完成 PATH 配置后、实际安装包的同一个终端中执行：

```bash
SNPA_PYTHON="$(python3 -c 'import sys; print(sys.executable)')"
"$SNPA_PYTHON" -c 'import sys; print(sys.version.split()[0], sys.executable); sys.exit(0 if sys.version_info >= (3, 11) else "Python 3.11+ required")'
```

检查失败或变量为空时停止安装。若默认 Python 太旧，先定位已有的合格解释器，
用其实际命令替换上面的 `python3` 后重新检查，不修改系统默认 Python。
之后继续 [通用流程第 2 步](overview.md#2-安装运行包)；其中的 `--python "$SNPA_PYTHON"`
确保 pipx 使用刚刚检查的解释器，而不是另一套默认 Python。

## 安装包与 Hermes 目标

以下是路径与变量写法，执行前必须把示例替换为已确认的真实路径。
`SNPA_PACKAGE` 指向按通用流程下载并校验的 wheel；`SNPA_HERMES_ROOT` 指向当前 Hermes 实际使用的源码，
不是配置目录。任一检查失败时停止，不自动新建或下载替代文件：

```bash
SNPA_PACKAGE="/path/to/sn_proactive_agent-0.1.3-py3-none-any.whl"
test -f "$SNPA_PACKAGE"
SNPA_HERMES_ROOT="/path/to/hermes-agent"
test -d "$SNPA_HERMES_ROOT/ui-tui"
```

进行在线验收时，将目标窗口的真实 Session ID 赋给变量，不能用示例 ID 当作验收证据：

```bash
SNPA_SESSION_ID="actual-session-id"
```

## 数据路径与服务地址

默认数据目录为 `~/.sn-proactive-agent/`。不需要预先创建 Project 或 Item。
若新目录不存在而已有 `~/.proactive-memory/`，继续使用旧目录，具体升级规则见通用流程。
用户要求改位置时，通过服务的 `--data-root` 或 `SN_PROACTIVE_AGENT_DATA_ROOT` 指定，
不得覆盖原数据目录。

使用默认地址时，无需额外配置。自定义了服务地址时，在启动 Hermes 的同一个终端中设置
`SN_PROACTIVE_AGENT_SERVICE_URL` 为实际地址。以下仅展示 POSIX Shell 的写法：

```bash
export SN_PROACTIVE_AGENT_SERVICE_URL="http://127.0.0.1:8080"
```

服务启动后可以打开工作台：

```bash
open http://127.0.0.1:8080/
```

停止与升级遵循 [通用流程](overview.md)。不要为了关闭本服务而停止其他 Python 或 Hermes 进程。
