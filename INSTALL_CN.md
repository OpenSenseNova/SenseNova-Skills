# 安装与配置

简体中文 | [English](INSTALL.md)

本文档引导你在 Windows / macOS / Linux 上安装 [OpenClaw](https://openclaw.ai/) 或 [hermes-agent](https://github.com/NousResearch/hermes-agent)，对接 [SenseNova](https://platform.sensenova.cn/) 大模型，并加载 `SenseNova-Skills` 中的技能，得到完整可用的 skill-driven agent。

> 两个 agent 任选其一。OpenClaw 与 hermes-agent 均遵循 [Agent Skills](https://agentskills.io/) 规范，本仓库的 skill 在两边都能直接使用。

---

## 0. 先准备 SenseNova API Key 与端点

后续两种 agent 都会用到下面这组配置：

| 字段       | 值                                                                                                |
| -------- | ------------------------------------------------------------------------------------------------ |
| Base URL | `https://token.sensenova.cn/v1`                                                                  |
| API Key  | 在 [SenseNova 控制台 · token-plan](https://platform.sensenova.cn/token-plan) 免费申请并复制。 |
| 模型名      | `sensenova-6.7-flash-lite`                                                                       |

> 端点是 OpenAI 兼容协议，可在任何"OpenAI compatible"配置位填写。

---

## 0.5. 一键安装：Agent Pack（可选）

如果不想手动跟着下面的步骤一路装下来，可以直接用 [Agent Pack](https://github.com/SenseTime-FVG/agent_pack) —— 一个跨平台一键安装器，把本文档里的所有步骤都帮你处理好：

- 调用 OpenClaw 和/或 hermes-agent 的官方安装脚本完成安装
- 配置 LLM 供应商（选 **Custom**，把 §0 里的三个值填进去即可）
- 我们已经把 SenseNova-Skills 直接预置在各产品的 `skills/` 目录中 —— 无需再手动复制
- 安装结束后直接在当前窗口拉起 agent，省去重启 shell 的步骤

> 平台级前提（Windows 上的 WSL2、macOS 上的 Xcode CLT + Homebrew）**不会**被自动安装 —— 请先按照下面 §1.1 / §1.2 完成你所在平台的前置准备，然后回到这一节继续。Linux 无需手动准备。

预编译的安装器发布在 [GitHub Releases 页面](https://github.com/SenseTime-FVG/agent_pack/releases/latest)：

| 平台 | 下载 | 使用方式 |
|------|------|---------|
| Windows | [去最新 release 下载 `-windows-x64.exe`](https://github.com/SenseTime-FVG/agent_pack/releases/latest) | 双击运行向导；安装过程在 WSL2 中执行，安装完成后当前 PowerShell 窗口会被接管，直接拉起 agent。 |
| macOS | [去最新 release 下载 `-macos-universal.pkg`](https://github.com/SenseTime-FVG/agent_pack/releases/latest) | 双击后按图形向导完成产品选择和 LLM 配置；安装完成后会按所选产品自动打开 OpenClaw Gateway Terminal 与 dashboard，并打开 Hermes Terminal。 |
| Linux | [去最新 release 下载 `-linux.sh`](https://github.com/SenseTime-FVG/agent_pack/releases/latest)，或使用右侧一行命令 | `chmod +x AgentPack-*-linux.sh && ./AgentPack-*-linux.sh`，或直接粘贴 `bash <(curl -fsSL https://raw.githubusercontent.com/SenseTime-FVG/agent_pack/main/linux/install.sh)` —— 两种方式都会在安装结束后用 `exec` 在当前 shell 里拉起 agent。 |

安装器询问 LLM 供应商时，选 **Custom (OpenAI-compatible)**，把 §0 里的三个值填进去（Base URL、API Key、模型名）。如果你处在国内网络，可以设置环境变量 `AGENTPACK_CN=1` 启用 GitHub 镜像回退。

> **Skills 已内置** —— Agent Pack 直接把 SenseNova-Skills 提交在各产品的 `skills/` 目录中，并随产品一起安装。**走这条路线无需再执行 §3（"加载本仓库的 Skill"）** —— 技能已经加载完毕。

安装结束后请直接跳到 [§4 验证整体可用](#4-验证整体可用) —— §1 至 §3 的手动步骤只服务于希望自己一步步装到底的用户。

---

## 1. 平台准备

### 1.1 Windows（必须使用 WSL2）

OpenClaw 在 Windows 上推荐 WSL2，hermes-agent 在 Windows 上**仅支持** WSL2，两者都先把 WSL2 装好。

要求：Windows 10 22H2+ 或 Windows 11。

1. 以**管理员身份**打开 PowerShell：
   ```powershell
   wsl --install
   ```
   该命令会启用所需的 Windows 功能并安装默认的 Ubuntu 发行版。
2. 重启电脑。
3. 重启后会自动启动 Ubuntu 终端，按提示设置 UNIX 用户名与密码。
4. 检查 WSL 版本与发行版：
   ```powershell
   wsl -l -v
   ```
   `VERSION` 一列应为 `2`。

之后所有命令都在 **Ubuntu (WSL2) 终端**里执行，而不是 PowerShell。

### 1.2 macOS

需要 macOS 12+ 与命令行工具：

```bash
xcode-select --install   # 若已安装可忽略
```

建议预先装好 Homebrew：

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

### 1.3 Linux

主流发行版（Ubuntu 22.04+ / Debian 12+ / Fedora 39+ 等）原生支持。确保已安装 `curl`、`git`：

```bash
# Ubuntu / Debian
sudo apt update && sudo apt install -y curl git

# Fedora
sudo dnf install -y curl git
```

---

## 2. 二选一：安装 Agent

### 路线 A：安装 OpenClaw

OpenClaw 需要 **Node.js 24（推荐）或 22.14+**。

#### 2.A.1 安装 Node.js

任选其一：

- **官方安装包**：从 <https://nodejs.org/> 下载 LTS。
- **Homebrew（macOS）**：`brew install node@24`
- **nvm（推荐 Linux/WSL2/macOS）**：
  ```bash
  curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash
  exec $SHELL
  nvm install 24
  ```

#### 2.A.2 安装 OpenClaw

macOS / Linux / WSL2：

```bash
curl -fsSL https://openclaw.ai/install.sh | bash
```

或通过 npm：

```bash
npm install -g openclaw@latest
openclaw onboard --install-daemon
```

> Windows 用户请在 **WSL2 内**执行上述命令。OpenClaw 文档也提供了原生 PowerShell 安装脚本（`iwr -useb https://openclaw.ai/install.ps1 | iex`），但 WSL2 路线运行更稳定。

#### 2.A.3 验证

```bash
openclaw --version
openclaw doctor
```

#### 2.A.4 配置 SenseNova LLM

OpenClaw 安装脚本会自动触发 onboarding 向导。如果你跳过了或想重新运行，执行：

```bash
openclaw onboard --install-daemon
```

按照下面的交互流程依次填写。`API Key` 使用 §0 中申请到的密钥；至少配置一个搜索 API（下文以 Brave Search 为例）。

```text
◇  I understand this is personal-by-default and shared/multi-user use requires lock-down. Continue?
│  Yes
│
◇  Setup mode
│  QuickStart
│
◇  Model/auth provider
│  Custom Provider
│
◇  API Base URL
│  https://token.sensenova.cn/v1
│
◇  How do you want to provide this API key?
│  Paste API key now
│
◇  API Key (leave blank if not required)
│  填写上面申请到的 api_key
│
◇  Endpoint compatibility
│  OpenAI-compatible
│
◇  Model ID
│  sensenova-6.7-flash-lite
│
◇  Verification successful.
│
◇  Endpoint ID
│  custom-token-sensenova-cn
│
◇  Select channel (QuickStart)
│  Skip for now
│
◇  Web search
│
◇  Search provider
│  Brave Search
│
◇  Brave Search API key
│  BSA-xxxxx  填写你的 Brave Search API key
│
◇  Configure skills now? (recommended)
│  No
│
◇  Enable hooks?
│  Skip for now
```

#### 2.A.5 验证 LLM 通路

```bash
openclaw agent --message "你好，自我介绍一下"
```

能返回中文回答即配置成功。

#### 2.A.6 打开网页 Dashboard

```bash
openclaw dashboard
```

执行后终端会输出形如 `http://localhost:18789/#token=xxx` 的登录链接，复制到浏览器打开即可进入网页端，与 agent 进行对话和配置。

#### 2.A.7 调大模型 token 上限

`~/.openclaw/openclaw.json` 的默认值偏保守。打开该文件，把下面这两项改成 SenseNova 6.7 的全量上限：

```json
"contextWindow": 262144,
"maxTokens": 32768,
```

---

### 路线 B：安装 hermes-agent

hermes-agent 由 [Nous Research](https://nousresearch.com/) 维护，安装脚本会自动准备 `uv`、Python 3.11、Node 22、`ripgrep`、`ffmpeg` 等依赖。

> Windows 用户请确保前面已装好 WSL2，所有命令都在 WSL2 终端中运行。

#### 2.B.1 安装

```bash
curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash
```

完成后重新加载 shell：

```bash
source ~/.bashrc          # bash
# 或：source ~/.zshrc     # macOS 默认 zsh
```

或者从源码安装：

```bash
git clone https://github.com/NousResearch/hermes-agent.git
cd hermes-agent
./setup-hermes.sh
```

#### 2.B.2 验证

```bash
hermes --version
hermes doctor
```

#### 2.B.3 配置 SenseNova LLM

最快方式 — 用 `hermes config set`：

```bash
hermes config set model.provider custom
hermes config set model.base_url https://token.sensenova.cn/v1
hermes config set model.api_key "<你的 API Key>"
hermes config set model.name sensenova-6.7-flash-lite
```

`hermes config set` 会自动把 `api_key` 这类秘钥写到 `~/.hermes/.env`，把其它配置写到 `~/.hermes/config.yaml`，无需手动区分。

也可以一步走完整向导：

```bash
hermes setup        # 全量向导
# 或
hermes model        # 仅交互式选择/配置 LLM
```

向导询问 provider 时选 `custom (OpenAI-compatible)`，然后依次填入：

- Base URL：`https://token.sensenova.cn/v1`
- API Key：上面申请到的 key
- Model name：`sensenova-6.7-flash-lite`

#### 2.B.4 验证 LLM 通路

```bash
hermes
```

进入交互界面后随便问一句"你好"，能返回中文回答即配置成功。

---

## 3. 加载本仓库的 Skill

### 3.1 先克隆仓库

```bash
git clone https://github.com/OpenSenseNova/SenseNova-Skills.git
cd SenseNova-Skills
```

### 3.2 安装方式一：手动复制 skill 目录

OpenClaw：

```bash
mkdir -p ~/.openclaw/skills
cp -r skills/* ~/.openclaw/skills/
```

hermes-agent：

```bash
mkdir -p ~/.hermes/skills
cp -r skills/* ~/.hermes/skills/
```

> 想保持与仓库同步可以用软链接代替 `cp -r`，例如：
> ```bash
> ln -s "$PWD"/skills/* ~/.openclaw/skills/
> ```
> 之后 `git pull` 就能自动获得 skill 更新。

### 3.3 安装方式二：直接交给 agent 安装

启动 agent 后，把下面这条消息发给它：

> 把当前目录 `SenseNova-Skills/skills/` 下所有子目录复制到 OpenClaw 的 skill 目录（`~/.openclaw/skills/`）。完成后列出已安装的 skill 名称。

把"OpenClaw"和路径换成 `hermes-agent` / `~/.hermes/skills/` 即可用于 hermes。Agent 会通过自己的 shell 工具完成 `mkdir` + `cp` + 列目录的动作，并把结果回报给你。

> 这种方式适合按需挑选 skill，例如："只把 `sn-image-*` 和 `sn-deep-research` 这几个 skill 复制过去"。

### 3.4 各分类 skill 的额外依赖

部分 skill 有自己的 Python 依赖、API key 或运行时要求，请按需查阅对应的使用指南：

- 图像与可视化：[`docs/sn-image-generate.md`](docs/sn-image-generate.md)
- 演示文稿：[`docs/ppt-generate.md`](docs/ppt-generate.md)
- 数据分析：[`docs/data-analysis.md`](docs/data-analysis.md)
- 深度研究 / 搜索：[`docs/deep-research.md`](docs/deep-research.md)

---

## 4. 验证整体可用

启动 agent，发送：

> 列出当前可用的 skill，并给出每个 skill 的一句话说明。

如果 agent 能列出 `sn-infographic`、`sn-ppt-entry`、`sn-deep-research` 等本仓库的 skill，说明 LLM 与 skill 都已就绪。

---

## 5. 常见问题

- **`wsl --install` 提示找不到命令**：需要 Windows 10 22H2+ / Windows 11，并以管理员身份打开 PowerShell。
- **Node 版本太低**：`node -v` 必须 ≥ 22.14。用 nvm 切换：`nvm install 24 && nvm use 24`。
- **`openclaw doctor` / `hermes doctor` 报错**：按报告中的提示逐项修复，缺什么装什么。
- **LLM 调用 401 / 403**：检查配置中的 LLM API Key（OpenClaw 用 `openclaw config get models.providers.custom`，hermes-agent 用 `hermes config get model.api_key`）；确认 [token-plan](https://platform.sensenova.cn/token-plan) 中 key 仍在有效额度内。
- **WSL2 中 `curl` 慢/卡**：确认 WSL2 网络模式（`wsl --status`），必要时切到 `mirrored` 网络模式或使用代理。
