# Install & Configure

English | [简体中文](INSTALL_CN.md)

This guide walks you through installing [OpenClaw](https://openclaw.ai/) or [hermes-agent](https://github.com/NousResearch/hermes-agent) on Windows / macOS / Linux, wiring it up to a [SenseNova](https://platform.sensenova.cn/) LLM, and loading the skills in this repository — giving you a fully working skill-driven agent.

> Pick **either** agent. Both OpenClaw and hermes-agent follow the [Agent Skills](https://agentskills.io/) convention, so the skills in this repo work in either runtime without modification.

---

## 0. Prepare your SenseNova API key and endpoint

Both agents below will use the same three values:

| Field      | Value                                                                                                          |
| ---------- | -------------------------------------------------------------------------------------------------------------- |
| Base URL   | `https://token.sensenova.cn/v1`                                                                                |
| API key    | Get one for free at [SenseNova Console · token-plan](https://platform.sensenova.cn/token-plan) and copy it. |
| Model name | `sensenova-6.7-flash-lite`                                                                                     |

> The endpoint speaks the OpenAI-compatible protocol, so it fits any "OpenAI compatible" provider slot.

---

## 0.5. Quick install via Agent Pack (optional)

If you'd rather skip the manual steps below, [Agent Pack](https://github.com/SenseTime-FVG/agent_pack) is a one-click installer that handles everything in this guide for you:

- Installs OpenClaw and/or hermes-agent via each project's official installer
- Configures the LLM provider (pick **Custom** and paste the values from §0)
- We've pre-bundled the SenseNova-Skills under each agent's `skills/` directory — no manual copy needed
- Auto-launches the installed agent(s) in the current window when setup finishes

> Platform-level prerequisites (WSL2 on Windows, Xcode CLT + Homebrew on macOS) are **not** auto-installed — finish §1.1 / §1.2 below for your platform first, then come back here. Linux has no manual prerequisites.

Pre-built installers live on the [GitHub Releases page](https://github.com/SenseTime-FVG/agent_pack/releases/latest):

| Platform | Download | How to use |
|----------|----------|------------|
| Windows | [`-windows-x64.exe` from the latest release](https://github.com/SenseTime-FVG/agent_pack/releases/latest) | Double-click and follow the wizard; installation runs inside WSL2, and the PowerShell window is taken over by the installed agent when setup finishes. |
| macOS | [`-macos-universal.pkg` from the latest release](https://github.com/SenseTime-FVG/agent_pack/releases/latest) | Double-click, then complete the macOS wizard for product selection and LLM configuration; on finish it opens the OpenClaw Gateway Terminal + dashboard, and/or the Hermes Terminal as selected. |
| Linux | [`-linux.sh` from the latest release](https://github.com/SenseTime-FVG/agent_pack/releases/latest), or the one-liner on the right | `chmod +x AgentPack-*-linux.sh && ./AgentPack-*-linux.sh`, or paste `bash <(curl -fsSL https://raw.githubusercontent.com/SenseTime-FVG/agent_pack/main/linux/install.sh)` — either way the shell that ran the installer is handed over to the agent via `exec`. |

When the installer asks for the LLM provider, choose **Custom (OpenAI-compatible)** and feed in the three values from §0 (Base URL, API key, model name). If you're in a China-region network, set `AGENTPACK_CN=1` to enable the GitHub mirror fallbacks.

> **Skills are already bundled** — Agent Pack ships with the SenseNova-Skills committed inside each product's `skills/` directory and installs them as part of the normal install. **You do not need to follow §3 ("Load this repo's skills")** — they're already loaded.

Once setup finishes, jump straight to [§4 End-to-end smoke test](#4-end-to-end-smoke-test) — the manual steps in §1 – §3 are only for users who'd rather install everything themselves.

---

## 1. Platform prep

### 1.1 Windows (WSL2 required)

OpenClaw recommends running under WSL2 on Windows; hermes-agent **only supports** WSL2 on Windows. Either way, install WSL2 first.

Requirements: Windows 10 22H2+ or Windows 11.

1. Open PowerShell **as Administrator**:
   ```powershell
   wsl --install
   ```
   This enables the required Windows features and installs the default Ubuntu distribution.
2. Reboot the machine.
3. After reboot, the Ubuntu terminal launches automatically — set your UNIX username and password as prompted.
4. Verify the WSL version and distribution:
   ```powershell
   wsl -l -v
   ```
   The `VERSION` column should read `2`.

From here on, run every command in the **Ubuntu (WSL2) terminal**, not in PowerShell.

### 1.2 macOS

Requires macOS 12+ and the command line developer tools:

```bash
xcode-select --install   # skip if already installed
```

We also recommend installing Homebrew up front:

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

### 1.3 Linux

Mainstream distributions (Ubuntu 22.04+ / Debian 12+ / Fedora 39+, etc.) work out of the box. Make sure `curl` and `git` are installed:

```bash
# Ubuntu / Debian
sudo apt update && sudo apt install -y curl git

# Fedora
sudo dnf install -y curl git
```

---

## 2. Pick one: install the agent

### Path A: install OpenClaw

OpenClaw needs **Node.js 24 (recommended) or 22.14+**.

#### 2.A.1 Install Node.js

Pick any one option:

- **Official installer**: download the LTS from <https://nodejs.org/>.
- **Homebrew (macOS)**: `brew install node@24`
- **nvm (recommended for Linux/WSL2/macOS)**:
  ```bash
  curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash
  exec $SHELL
  nvm install 24
  ```

#### 2.A.2 Install OpenClaw

macOS / Linux / WSL2:

```bash
curl -fsSL https://openclaw.ai/install.sh | bash
```

Or via npm:

```bash
npm install -g openclaw@latest
openclaw onboard --install-daemon
```

> Windows users: run the commands above **inside WSL2**. OpenClaw also ships a native PowerShell installer (`iwr -useb https://openclaw.ai/install.ps1 | iex`), but the WSL2 path is more stable.

#### 2.A.3 Verify

```bash
openclaw --version
openclaw doctor
```

#### 2.A.4 Configure the SenseNova LLM

Run the three commands below — they register SenseNova as a custom OpenAI-compatible provider and set it as the default model. Replace the placeholder with the API key you generated in §0.

```bash
openclaw config unset models.providers.sensenova
openclaw config set models.providers.custom '{"baseUrl":"https://token.sensenova.cn/v1","api":"openai-completions","apiKey":"<paste your API key here>","models":[{"id":"sensenova-6.7-flash-lite","name":"SenseNova 6.7 Flash Lite"}]}'
openclaw config set agents.defaults.model.primary "custom/sensenova-6.7-flash-lite"
```

> The first `unset` is a safety step — it clears any earlier `sensenova` provider entry so the new `custom` provider is the only one in play.

#### 2.A.5 Verify the LLM connection

```bash
openclaw agent --message "Hi, please introduce yourself" --agent main
```

If you get an English (or Chinese) reply, the LLM is wired up.

> `--agent main` selects the default agent for this one-shot turn. Without it, recent OpenClaw releases error out with `Pass --to <E.164>, --session-id, or --agent to choose a session`.

---

### Path B: install hermes-agent

hermes-agent is maintained by [Nous Research](https://nousresearch.com/). Its installer auto-installs `uv`, Python 3.11, Node 22, `ripgrep`, `ffmpeg`, and other dependencies.

> Windows users: make sure WSL2 is set up (see §1.1). All commands below run inside the WSL2 terminal.

#### 2.B.1 Install

```bash
curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash
```

Reload your shell after install completes:

```bash
source ~/.bashrc          # bash
# or: source ~/.zshrc     # default on macOS
```

Or install from source:

```bash
git clone https://github.com/NousResearch/hermes-agent.git
cd hermes-agent
./setup-hermes.sh
```

#### 2.B.2 Verify

```bash
hermes --version
hermes doctor
```

#### 2.B.3 Configure the SenseNova LLM

Fastest path — use `hermes config set`:

```bash
hermes config set model.provider custom
hermes config set model.base_url https://token.sensenova.cn/v1
hermes config set model.api_key "<your API key>"
hermes config set model.name sensenova-6.7-flash-lite
hermes config set model.default custom/sensenova-6.7-flash-lite
```

> The last line is required — without `model.default`, hermes still routes through whatever was configured at install time (e.g. `anthropic/claude-opus-4.6`) and `hermes -z "..."` fails with `HTTP 404: model is not found`. If you'd rather not run individual commands, use `hermes setup` or `hermes model` (below) instead — both update `model.default` for you.

`hermes config set` automatically writes secrets such as `api_key` into `~/.hermes/.env` and everything else into `~/.hermes/config.yaml`, so you don't have to split them by hand.

You can also run the full wizard:

```bash
hermes setup        # full setup wizard
# or
hermes model        # just the LLM provider step
```

When the wizard asks for a provider, pick `custom (OpenAI-compatible)` and enter:

- Base URL: `https://token.sensenova.cn/v1`
- API key: the one you generated above
- Model name: `sensenova-6.7-flash-lite`

#### 2.B.4 Verify the LLM connection

```bash
hermes
```

In the interactive prompt, type something like "hello" — a coherent reply means everything is wired up.

---

## 3. Load this repo's skills

### 3.1 Clone the repo

```bash
git clone https://github.com/OpenSenseNova/SenseNova-Skills.git
cd SenseNova-Skills
```

### 3.2 Option 1: copy the skill directories manually

OpenClaw:

```bash
mkdir -p ~/.openclaw/skills
cp -r skills/* ~/.openclaw/skills/
```

hermes-agent:

```bash
mkdir -p ~/.hermes/skills
cp -r skills/* ~/.hermes/skills/
```

> Want skills to track this repo? Use symlinks instead of `cp -r`:
> ```bash
> ln -s "$PWD"/skills/* ~/.openclaw/skills/
> ```
> Then `git pull` automatically pulls in skill updates.

### 3.3 Option 2: ask the agent to install them

Once your agent is up, send it the message below. It will use its own shell tool to do the `mkdir` + `cp` + listing for you.

> Copy every subdirectory under `SenseNova-Skills/skills/` (in the current directory) into OpenClaw's skill directory (`~/.openclaw/skills/`). When you're done, list the installed skills.

Swap "OpenClaw" and the path for `hermes-agent` / `~/.hermes/skills/` to use this with hermes.

> This option works well for picking and choosing — e.g., "only copy `sn-image-*` and `sn-deep-research`."

### 3.4 Per-category skill prerequisites

Some skills need extra Python deps, API keys, or runtime tools. Check the relevant guide:

- Image & visualization: [`docs/sn-image-generate_en.md`](docs/sn-image-generate_en.md)
- Presentations: [`docs/ppt-generate_en.md`](docs/ppt-generate_en.md)
- Data analysis: [`docs/data-analysis_en.md`](docs/data-analysis_en.md)
- Deep research / search: [`docs/deep-research_en.md`](docs/deep-research_en.md)

---

## 4. End-to-end smoke test

Start the agent and ask:

> List the available skills, with a one-line description for each.

If the agent enumerates skills like `sn-infographic`, `sn-ppt-entry`, and `sn-deep-research` from this repo, the LLM and skill setup is good to go.

---

## 5. Troubleshooting

- **`wsl --install` not found**: needs Windows 10 22H2+ / Windows 11, run PowerShell as Administrator.
- **Node version too low**: `node -v` must be ≥ 22.14. Switch with nvm: `nvm install 24 && nvm use 24`.
- **`openclaw doctor` / `hermes doctor` complains**: follow the report's hints — install whatever's missing.
- **LLM returns 401 / 403**: double-check the LLM API key stored in your config (`openclaw config get models.providers.custom` for OpenClaw, or `hermes config get model.api_key` for hermes-agent); confirm the key still has free quota in [token-plan](https://platform.sensenova.cn/token-plan).
- **Slow `curl` inside WSL2**: check the WSL2 networking mode (`wsl --status`); switch to `mirrored` networking or use a proxy if needed.
