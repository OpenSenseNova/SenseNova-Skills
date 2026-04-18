# SenseNova-Skills

[English](README.md) | [简体中文](README_CN.md)

Skills and tooling for **AIGC** in agent runtimes.

## Prerequisites

- **Python** 3.10 or later.
- **U1 API** credentials for image generation and LLM/VLM endpoints (`U1_API_KEY`, `U1_LM_API_KEY`; see Quick Start).

## Skills

### u1-image-base (Tier 0)

Base-layer infrastructure skill providing two low-level tools. See [`skills/u1-image-base/SKILL.md`](skills/u1-image-base/SKILL.md) for full behavior.

- **u1-image-generate** — text-to-image generation
- **u1-text-optimize** — text processing using LLM

All tools are invoked through a unified `openclaw_runner.py` entrypoint.

### u1-infographic (Tier 1)

Scene skill for generating professional infographics, built on `u1-image-base`. See [`skills/u1-infographic/SKILL.md`](skills/u1-infographic/SKILL.md) for full behavior. Sample outputs: [`examples/u1-infographics.md`](examples/u1-infographics.md).

- Automatic prompt quality evaluation
- Content analysis and layout/style selection (87 layouts, 66 styles)
- Multi-round image generation with VLM review
- Quality ranking and best-result output

## Quick Start

Use these skills from [OpenClaw](https://openclaw.ai/). They follow the [Agent Skills](https://agentskills.io/) layout; see [OpenClaw Skills](https://docs.openclaw.ai/skills) for how OpenClaw discovers and loads skill folders. If you have not set up OpenClaw yet, install and configure it from the **[official documentation](https://docs.openclaw.ai/)** (product site: [openclaw.ai](https://openclaw.ai/)).

### 1. Register `u1-image-base` and `u1-infographic`

Clone this repository, then expose **both** skill directories to OpenClaw ([locations and precedence](https://docs.openclaw.ai/skills#locations-and-precedence)). `u1-infographic` depends on `u1-image-base`—install both.

| Approach | What to do |
|----------|------------|
| **Workspace `skills/`** (typical) | Copy or symlink `skills/u1-image-base` and `skills/u1-infographic` into your agent workspace as `./skills/u1-image-base/` and `./skills/u1-infographic/`. |
| **Shared on this machine** | Copy or symlink the same two folders under `~/.openclaw/skills/`. |
| **`openclaw.json`** | Add an absolute path to this repo’s `skills` folder (the parent of both directories) via `skills.load.extraDirs` (example below). |

```json5
{
  skills: {
    load: {
      extraDirs: ["/absolute/path/to/SenseNova-Skills/skills"],
    },
  },
}
```

Replace the path with your clone. Details: [Skills config](https://docs.openclaw.ai/tools/skills-config). Workspace skills win over `extraDirs` if the same name appears twice.

### 2. Python dependencies and API keys

Install packages and export keys in the **Python environment and process** OpenClaw uses when it runs [`skills/u1-image-base/scripts/openclaw_runner.py`](skills/u1-image-base/scripts/openclaw_runner.py) (the unified runner for these tools):

```bash
pip install -r skills/u1-image-base/requirements.txt
export U1_API_KEY="your-image-api-key"
export U1_LM_API_KEY="your-lm-api-key"  # for LLM and VLM
```

Prefer environment variables or a local `.env` file. Do not commit secrets. You can also inject keys through `skills.entries` ([environment injection](https://docs.openclaw.ai/skills#environment-injection-per-agent-run)). Optionally map LLM/VLM endpoints to your OpenClaw providers: [`skills/u1-image-base/SKILL.md`](skills/u1-image-base/SKILL.md) (Agent Configuration Integration).

### 3. Invoke in OpenClaw

Describe the task in chat, for example:

> "Create an infographic explaining the water cycle"

Or call the skill by name:

> /skill u1-infographic "The water cycle"

## License

MIT — see [LICENSE](LICENSE).
