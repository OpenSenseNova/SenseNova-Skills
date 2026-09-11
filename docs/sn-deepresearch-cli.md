# SenseNova Deep Research CLI

English | [简体中文](sn-deepresearch-cli_cn.md)

`sn-deepresearch-cli` is the repository skill for installing and operating the standalone
[`sensenova-skills-deepresearch`](https://www.npmjs.com/package/sensenova-skills-deepresearch)
CLI. It is designed for multi-source research, progress tracking, resumable runs, and
brief or formal report delivery through a selected Harness or Agent.

Use [`sn-deep-research`](../skills/sn-deep-research/SKILL.md) when you want the
repository-native integrated controller. Use this CLI entry point when you need an
independently installed command with explicit Harness selection and run monitoring.

## Requirements

- Node.js 22 or later, Python 3.10 or later, and npm.
- One supported Harness: Hermes, Codex, Claude Code, or OpenClaw.
- Search credentials only for the optional source families you intend to use.
- Pandoc for DOCX output and Typst for PDF output.

The CLI can use public sources without optional API keys. Never put tokens, cookies, or
Harness profiles in prompts, reports, logs, or commits.

## Install

Install the published package rather than cloning or building the source repository:

```bash
npm install --global sensenova-skills-deepresearch
deepresearch --help
deepresearch sources init
deepresearch sources list --json
```

The source repository is maintained separately at
[`OpenSenseNova/SenseNova-Skills-DeepResearch`](https://github.com/OpenSenseNova/SenseNova-Skills-DeepResearch).
The user-level search configuration is stored under `~/.deepresearch-cli/search/.env`.

## Prepare a Harness

Reuse the existing login and model configuration where possible:

- Hermes: verify the existing Hermes installation and login.
- Codex: verify `codex` is available and run `codex login` when needed.
- Claude Code: verify `claude-agent-acp`; the regular `claude` command is not a substitute
  for this adapter.
- OpenClaw: verify the active Agent, Gateway health, workspace write access, and the
  required `read`, `write`, `edit`, `apply_patch`, `exec`, and `process` tools.

For OpenClaw, run the write smoke test before starting a real research run:

```bash
deepresearch doctor --harness openclaw --json
```

Do not silently change a Harness provider, model, timeout, or global workspace permission.
Explain the impact and obtain authorization before making such changes.

## Run Research

Before starting, confirm the depth (`quick`, `normal`, or `heavy`), report form (`brief` or
`formal_report`), output format (`markdown`, `html`, `pdf`, or `docx`), and language.

Quick runs use the foreground command:

```bash
deepresearch "<query>" \
  --mode quick \
  --report-format <brief|formal_report> \
  --output-format <markdown|html|pdf|docx> \
  --harness <hermes|codex|claude-code|openclaw> \
  --language <user-language> \
  --progress tools
```

Normal and heavy runs use the Web entry point. Choose an available local port and keep the
process running while the Agent monitors it:

```bash
deepresearch web "<query>" \
  --mode <normal|heavy> \
  --report-format <brief|formal_report> \
  --output-format <markdown|html|pdf|docx> \
  --harness <hermes|codex|claude-code|openclaw> \
  --language <user-language> \
  --host 127.0.0.1 \
  --port <available-port> \
  --progress tools
```

Do not rewrite the user's query into a new title or silently start a second copy of the
same run. Report the actual progress URL only after the Web server is listening.

## Monitor and Recover

Keep the Harness and CLI monitor alive. A quiet log does not prove that a run is dead:
inspect the run status first.

```bash
deepresearch status <run-id> --json
deepresearch diagnostics --json
```

For a failed or interrupted run, preserve its run directory and resume only after the
original process has ended:

```bash
deepresearch resume <run-id> --harness <harness>
```

The final handoff should include the `run_id`, final status, and the generated output path.
Do not treat search hits or intermediate files as the completed report.
