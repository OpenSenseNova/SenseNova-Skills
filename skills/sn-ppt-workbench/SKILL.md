---
name: sn-ppt-workbench
description: Use when the user asks to open, preview, inspect, or visually edit an existing SenseNova HTML presentation in the PPT Workbench, using an explicit deck_dir or the latest deck in the current workspace.
metadata:
  project: SenseNova-Skills
  tier: aux
  category: ppt
  user_visible: true
---

# sn-ppt-workbench

Start or reuse the AI PPT editing WebUI for an existing HTML slide deck. The
helper prefers Hermes/canvas/port-forward URLs when available. Without a
forwarded URL, native hosts bind to localhost by default, while Docker/WSL bind
to `0.0.0.0` so remote users can reach the WebUI through the host network.

## Use Cases

- The user already generated a deck and asks to open the WebUI/editor/workbench.
- The user provides a `deck_dir` containing `task_pack.json`,
  `slides/slide_NN.html`, `pages/page_NNN.html`, or a root-level HTML deck.
- The user says to inspect or edit previously generated slides without regenerating them.

## Hard Rules

1. Do not run `sn-ppt-entry`, `sn-ppt-standard`, `page-html`, `batch-page-html`, or `export`.
2. Do not edit slide files directly. The WebUI handles user-visible editing.
3. If `deck_dir` is missing, auto-detect only under `$(pwd)/ppt_decks`.
   Other roots are considered only when the caller explicitly passes
   `--search-root`; never scan home folders by default.
4. If no usable deck is found, ask the user for the absolute `deck_dir`.
5. Workbench startup is best-effort. If it skips or fails, report the reason and do not attempt generation as a fallback.
6. Prefer a forwarded/canvas URL over localhost when the user may be on SSH, IM, or another remote device.
7. When launched from the unified PPT flow, use the exact absolute
   `task_pack.deck_dir`; opening the Workbench must not create or switch tasks.
8. Treat `task_pack.json` as progress/resume state and `outline.md` as the
   user-editable Story. Existing runtime builds may expose only part of these
   artifacts; report compatibility gaps instead of regenerating the deck.

## Invocation

Use the helper directly:

```bash
python3 $SKILL_DIR/scripts/open_workbench.py --deck-dir "<deck_dir>" --agent-session-id "${HERMES_SESSION_KEY:-}"
```

On native Windows where `python3` is unavailable:

```bash
python $SKILL_DIR/scripts/open_workbench.py --deck-dir "<deck_dir>" --agent-session-id "%HERMES_SESSION_KEY%"
```

If the user did not provide a deck path, let the helper auto-detect:

```bash
python3 $SKILL_DIR/scripts/open_workbench.py --agent-session-id "${HERMES_SESSION_KEY:-}"
```

Pass same-session bridge details when available:

```bash
python3 $SKILL_DIR/scripts/open_workbench.py \
  --deck-dir "<deck_dir>" \
  --agent-session-id "${HERMES_SESSION_KEY:-}" \
  --agent-managed 1 \
  --agent-provider hermes \
  --agent-transport gateway \
  --webui-base-url "${HERMES_WEBUI_BASE_URL:-}" \
  --gateway-base-url "${HERMES_GATEWAY_BASE_URL:-}"
```

`--agent-transport` may be omitted: the helper auto-selects `gateway` when the
Hermes Gateway endpoint and key resolve (environment or Hermes `.env` files),
then `webui` / `acp` / `rest` when only those details exist. Explicit flags and
`WORKBENCH_AGENT_TRANSPORT` always win. With no resolvable bridge the bottom
chat stays read-only by design.

For non-Hermes interactive providers, pass structured bridge details instead of
scraping CLI/TUI output:

```bash
python3 $SKILL_DIR/scripts/open_workbench.py \
  --deck-dir "<deck_dir>" \
  --agent-managed 1 \
  --agent-provider openclaw \
  --agent-transport rest \
  --agent-base-url "${WORKBENCH_AGENT_BASE_URL:-}" \
  --agent-api-key "${WORKBENCH_AGENT_API_KEY:-}"

python3 $SKILL_DIR/scripts/open_workbench.py \
  --deck-dir "<deck_dir>" \
  --agent-managed 1 \
  --agent-provider codex \
  --agent-transport acp \
  --acp-command "${WORKBENCH_ACP_COMMAND:-codex-acp}"

python3 $SKILL_DIR/scripts/open_workbench.py \
  --deck-dir "<deck_dir>" \
  --agent-managed 1 \
  --agent-provider box-agent \
  --agent-transport acp \
  --acp-command "${WORKBENCH_ACP_COMMAND:-${BOX_AGENT_ACP_COMMAND:-box-agent-acp}}"
```

When this helper runs inside Box Agent, the exported `BOX_AGENT_PYTHON` or
`BOX_AGENT_SKILL_TOOLS_ROOT` environment automatically selects `box-agent`,
`acp`, and the installed `box-agent-acp` command. Explicit
`WORKBENCH_AGENT_*` flags or environment variables still take precedence.

For WorkBuddy, pass `--agent-provider workbuddy` only as provider identity. Tell
the user clearly that WorkBuddy currently has no supported API or ACP interface
for the interactive workbench bridge, so the WebUI can show WorkBuddy status but
cannot send bottom-chat modification turns back to WorkBuddy.

## CLI Subcommands (direct launch fallback)

When bypassing `open_workbench.py` and invoking the workbench launcher directly, use subcommands:

```bash
node <launcher> start   --deck-dir "<path>" [--port 0] [--agent-managed]
node <launcher> status  --deck-dir "<path>"
node <launcher> stop    --deck-dir "<path>"
```

The old argument-only form (no subcommand) is **deprecated** — it will print a usage error.

**Restart pitfall:** `start` silently **reuses** an existing server instance for the same `deck-dir` (response contains `"reused": true`). If you updated the workbench code, you MUST run `stop` first, then `start` — otherwise the old process keeps serving stale code:

```bash
node <launcher> stop  --deck-dir "<path>"
node <launcher> start --deck-dir "<path>" --port 0
```

## Bind Host

The workbench resolves its bind address from `--host` CLI flag → `WORKBENCH_HOST` env var → default `127.0.0.1`. When the user needs remote/LAN access, set `WORKBENCH_HOST=0.0.0.0`:

```bash
export WORKBENCH_HOST=0.0.0.0
node <launcher> start --deck-dir "<path>" --port 0
```

The response `url` field will then show the LAN IP instead of `127.0.0.1`.

## Output Handling

Parse the single JSON line from stdout.

When `status == "ok"`, echo the returned `editor_url`, `public_url`, or `workbench.editorUrl` for existing-deck editing requests. The helper may also return `generation_url`; that URL is the generation progress page at `/progress`, while the editor is `/editor`.

```text
PPT 编辑工作台已启动：<editor_url>
```

If `workbench.reused == true`, say it reused the existing server.

If `bind_host` is `0.0.0.0`, the URL is a Docker/WSL LAN fallback. Tell the user it must be reachable from their device/network; if not, ask them to provide a Hermes/canvas/port-forward URL and rerun with `--public-url`, or an explicit bind host with `--host`.

When `status == "skipped"` or `status == "failed"`, echo the `reason` field. If `reason == "nodejs_missing"`, ask whether the user wants NodeJS/dependencies installed; if they decline, do not open the WebUI. Ask for a valid `deck_dir` only if the reason says no deck was found.

## Environment

The helper locates the editor launcher in this order:

1. `SENSENOVA_PPT_WORKBENCH_CLI`
2. `PPT_WORKBENCH_CLI`
3. The runtime packaged beside this Skill
4. The nearest `src/ppt-editor` source checkout or packaged release in the current worktree
5. Common `~/Repository/ppt-editor` fallbacks

The helper does not build the editor during an end-user launch. Packaged Skills
must include `workbench-runtime`; source checkouts must build `src/ppt-editor`
explicitly before using its launcher. The repository-level `webui/` directory
is a separate product and is not a launcher fallback for this Skill.

Remote URL discovery order:

1. Explicit `--public-url`
2. `WORKBENCH_PUBLIC_URL`, `HERMES_WORKBENCH_PUBLIC_URL`
3. Hermes/canvas/forwarding env vars such as `HERMES_CANVAS_URL`, `HERMES_PORT_FORWARD_URL`, `CANVAS_URL`, `PORT_FORWARD_URL`, `TUNNEL_URL`
4. Codespaces/Gitpod URL patterns
5. Localhost on native hosts, or LAN fallback from the machine's non-loopback IPv4 address on Docker/WSL

## Gateway Auth Setup

For writable interactive agent bridging (chat panel in workbench), Hermes keeps
using the existing WebUI/Gateway protocol. OpenClaw should be exposed through a
Gateway/REST-compatible HTTP endpoint. Codex, Claude Code, and Box Agent should
use ACP JSON-RPC adapters, configured with `--acp-command` or
`WORKBENCH_ACP_COMMAND`. Box Agent defaults to its installed `box-agent-acp`
entry point.
Never parse provider CLI/TUI output for chat synchronization.

For writable Hermes Gateway bridging, the Gateway API server and workbench must
authenticate with matching API keys.

Key env vars:

| Variable | Set By | Value |
|----------|--------|-------|
| `API_SERVER_KEY` | Gateway (.env) | Shared secret |
| `WORKBENCH_GATEWAY_API_KEY` | Workbench env | Same as `API_SERVER_KEY`; preferred explicit bridge key |
| `HERMES_GATEWAY_BASE_URL` | Workbench env | `http://127.0.0.1:8642` |
| `WORKBENCH_AGENT_PROVIDER` | Workbench env | `hermes`, `openclaw`, `codex`, `claude-code`, `box-agent`, or `workbuddy` |
| `WORKBENCH_AGENT_TRANSPORT` | Workbench env | `webui`, `gateway`, `rest`, or `acp` |
| `WORKBENCH_AGENT_BASE_URL` | Workbench env | OpenClaw/Gateway REST endpoint |
| `WORKBENCH_AGENT_API_KEY` | Workbench env | REST provider bearer token |
| `WORKBENCH_ACP_COMMAND` | Workbench env | ACP adapter command, e.g. `codex-acp` |
| `BOX_AGENT_ACP_COMMAND` | Box Agent / Workbench env | Optional override for the default `box-agent-acp` adapter command |

Quick steps:
- Gateway: set `API_SERVER_KEY` in `.env`, restart gateway
- Workbench: set `WORKBENCH_GATEWAY_API_KEY` to same value, set `HERMES_GATEWAY_BASE_URL=http://127.0.0.1:8642`
- If no explicit bridge key is set, the Node relay falls back to `API_SERVER_KEY`, `HERMES_GATEWAY_API_KEY`, then backend-only `AI_GATEWAY_API_KEY` (`ppt-editor-dev` by default). Prefer the explicit bridge key for custom/shared gateways.

## Progress Echo

Always send a short progress message before and after the helper:

| When | Example |
|---|---|
| Before helper | `正在启动 PPT 预览工作台，不会重新生成幻灯片...` |
| Success | `PPT 编辑工作台已启动：http://127.0.0.1:18087` |
| Generation progress URL available | `生成进度工作台：http://127.0.0.1:18087/progress` |
| Skip/failure | `PPT 工作台未启动：<reason>` |
