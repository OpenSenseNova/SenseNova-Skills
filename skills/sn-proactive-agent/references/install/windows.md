# Windows 安装说明

本文件区分原生 PowerShell 与 WSL，补充 [通用流程](overview.md)中的系统差异。
**当前为安装参考，本项目的 Windows 完整接入尚未验收。** 能打开 Web 不能替代对话采集与续跑测试。

## 先确定运行环境

- **原生 PowerShell**：服务、pipx、Python 和 Harness 都使用 Windows 环境。
- **WSL**：服务、pipx、Python 和 Harness 都安装在同一个 Linux 发行版内；Windows 浏览器可以用于访问工作台。

先跟随用户现有的 Harness 环境，不自行迁移到另一套环境。
不要把 Windows 的可执行文件、PATH 或数据路径混进 WSL，也不要反过来使用。
用户未安装 WSL 时，不能把启用 WSL 当作普通安装步骤自动执行。

## 原生 PowerShell

检查 Python 和 pipx；若 Python 来自其他安装方式，使用实际找到的启动命令：

```powershell
Get-Command py, python, pipx -ErrorAction SilentlyContinue
```

如果存在 `py`，检查当前默认解释器：

```powershell
py --version
```

确认 Python 满足 3.11 或更高要求。若使用该解释器并获准补装 pipx，
按 [pipx 官方安装说明](https://pipx.pypa.io/stable/how-to/install-pipx.html)安装，并通过其模块入口处理 PATH：

```powershell
py -m pip install --user pipx
py -m pipx ensurepath
```

重新打开 PowerShell 后检查 `pipx --version`。若 pipx 本身已可运行、但找不到它安装的应用，
可以按 [pipx 路径说明](https://pipx.pypa.io/latest/how-to/configure-paths.html)更新当前终端的应用搜索路径：

```powershell
$env:Path = "$(pipx environment --value PIPX_BIN_DIR);$env:Path"
```

在实际安装包的同一个 PowerShell 中设置并检查解释器：

```powershell
$SNPA_PYTHON = py -c "import sys; print(sys.executable)"
if ($LASTEXITCODE -ne 0 -or -not $SNPA_PYTHON) { throw "Cannot resolve Python" }
& $SNPA_PYTHON -c "import sys; print(sys.version.split()[0], sys.executable); sys.exit(0 if sys.version_info >= (3, 11) else 'Python 3.11+ required')"
if ($LASTEXITCODE -ne 0) { throw "Python 3.11+ required" }
```

没有 `py` 时使用实际的 Python 命令；默认版本太旧时先选择已有的合格解释器，
例如将 `py` 换成已经确认存在的 `py -3.11`，再执行同样检查。
继续 [通用流程第 2 步](overview.md#2-安装运行包)，把 `SNPA_PYTHON` 显式传给 pipx。
不要复制 Bash 的 `export` 或反斜杠续行写法。

安装已校验的 wheel 或 Connector 前，设置已经确认的实际文件与源码路径。以下仅为写法示例，
执行前替换；`SNPA_HERMES_ROOT` 必须是当前 Hermes 实际使用的源码，不是配置目录：

```powershell
$SNPA_PACKAGE = "C:\path\to\sn_proactive_agent-0.1.3-py3-none-any.whl"
if (-not (Test-Path -LiteralPath $SNPA_PACKAGE -PathType Leaf)) { throw "Package not found" }
$SNPA_HERMES_ROOT = "C:\path\to\hermes-agent"
if (-not (Test-Path -LiteralPath (Join-Path $SNPA_HERMES_ROOT "ui-tui") -PathType Container)) { throw "Hermes source not found" }
```

在线验收时取得目标窗口的真实 Session ID，再设置变量，不能使用示例 ID 验收：

```powershell
$SNPA_SESSION_ID = "actual-session-id"
```

默认数据位置是当前 Windows 用户 Home 下的 `.sn-proactive-agent`，通常为
`%USERPROFILE%\.sn-proactive-agent`。新目录不存在时自动沿用已有的 `.proactive-memory`，不搬迁或合并。
自定义服务地址时，PowerShell 使用以下写法，
将示例值替换为实际服务地址：

```powershell
$env:SN_PROACTIVE_AGENT_SERVICE_URL = "http://127.0.0.1:8080"
```

服务启动后可打开工作台：

```powershell
Start-Process "http://127.0.0.1:8080/"
```

## WSL

在 PowerShell 中只读检查现有 WSL 环境：

```powershell
wsl --status
wsl --list --verbose
```

进入用户选定的发行版后，在 Linux Shell 中检查依赖：

```bash
python3 --version
command -v pipx
```

缺少 pipx 时，按 [pipx 官方 Linux 说明](https://pipx.pypa.io/stable/how-to/install-pipx.html)
选择该发行版对应的安装方式，并确认所需权限；不要在 WSL 中使用 Homebrew 的 macOS 安装步骤。
准备好 pipx 后执行：

```bash
pipx ensurepath
export PATH="$(pipx environment --value PIPX_BIN_DIR):$PATH"
```

完成 PATH 配置后，在实际安装包的 Linux Shell 中选择并检查解释器：

```bash
SNPA_PYTHON="$(python3 -c 'import sys; print(sys.executable)')"
"$SNPA_PYTHON" -c 'import sys; print(sys.version.split()[0], sys.executable); sys.exit(0 if sys.version_info >= (3, 11) else "Python 3.11+ required")'
```

检查失败或变量为空时停止安装；需要切换版本时使用已确认存在的解释器。
在同一个 Linux 环境中继续 [通用流程第 2 步](overview.md#2-安装运行包)。
安装已校验的 wheel 与 Connector 时，使用 WSL 内的实际路径；以下示例必须先替换，检查失败即停止：

```bash
SNPA_PACKAGE="/path/to/sn_proactive_agent-0.1.3-py3-none-any.whl"
test -f "$SNPA_PACKAGE"
SNPA_HERMES_ROOT="/path/to/hermes-agent"
test -d "$SNPA_HERMES_ROOT/ui-tui"
```

在线验收时使用目标窗口的真实 Session ID：

```bash
SNPA_SESSION_ID="actual-session-id"
```

默认数据保存在 WSL 用户的 `~/.sn-proactive-agent/`，不是 Windows 用户目录。
新目录不存在时沿用同一个 WSL 用户已有的 `~/.proactive-memory/`。
先在 WSL 内检查服务，再从 Windows 浏览器验证页面；跨环境访问失败时先核对地址与网络，
不要自动把服务暴露到公网。
