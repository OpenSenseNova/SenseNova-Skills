# SenseNova Proactive Agent

English | [简体中文](sn-proactive-agent_cn.md)

[`sn-proactive-agent`](../skills/sn-proactive-agent/SKILL.md) records progress from
long-running conversations, keeps project state auditable, and presents useful next-step
suggestions in a Web workbench. When a user accepts a suggestion, the corresponding
Connector resumes the original Session so the action remains visible in the same
conversation.

## What it provides

- Creates and updates Projects, Items, and Events from conversations with clear long-term
  goals.
- Suppresses suggestions when a conversation has no meaningful next step.
- Shows suggestions, project progress, and daily summaries in a local Web workbench.
- Resumes an accepted action in the original Hermes or OpenClaw Session and records the result with its
  source suggestion ID.
- Keeps runtime data under the user's Home directory rather than inside the source
  checkout.

## Components and boundaries

| Component | Responsibility |
|---|---|
| Skill | Tells the Agent when to inspect, install, configure, or operate the service. |
| Runtime package | Provides the `sn-proactive-agent` CLI, Core, Web workbench, and diagnostics. |
| Hermes Connector | Captures conversation QA and resumes accepted actions in the original Session. |
| OpenClaw Gateway plugin | Captures text QA from OpenClaw and returns accepted actions to the original Session. |
| User data | Stores Projects, Items, Events, runtime records, and recovery state under `~/.sn-proactive-agent/` by default. |

Installing the Skill does not install the runtime package, configure a Connector, or start
the service. Hermes uses a Web-only bridge; OpenClaw uses a Gateway plugin. Follow the
instructions for the selected Harness rather than substituting its name in Hermes commands.

## Requirements

- Python 3.11 or newer and `pipx`.
- A working, model-configured Hermes CLI for Core's background processing, including when
  only OpenClaw conversations are monitored. OpenClaw-only use does not require the Hermes
  Connector, Hermes TUI source checkout, or Hermes Session diagnostics.
- For Hermes integration: a supported Hermes source checkout, Node.js 22 or newer, and
  the build dependencies required by that Hermes version.
- For OpenClaw integration: a working, model-configured OpenClaw Gateway. The documented
  end-to-end validation baseline is macOS with OpenClaw `2026.6.11`; other versions and
  operating systems require separate validation. Windows instructions are installation
  references, not evidence of a verified end-to-end integration.
- Permission to read the runtime package's GitHub Release repository. Configure models
  through the Harness's own settings; the installation flow does not read or print API keys.

This guide targets runtime version `0.1.4`. Before downloading, confirm that the matching
GitHub Release is published, is not a draft, and contains the wheel and `SHA256SUMS`, plus
`sn-proactive-agent-openclaw-0.1.4.tgz` for OpenClaw. Do not substitute the source checkout, an unverified URL, or the older
`proactive-memory-service` package.

## Install and configure

### 1. Install the Skill

Copy the complete `skills/sn-proactive-agent/` directory into the Harness Skill directory.
The directory must include `SKILL.md` and `references/`; installing the runtime package alone
does not install this Skill.

### 2. Install the runtime package

Use the release checks and download commands from the [shared installation procedure](../skills/sn-proactive-agent/references/install/overview.md):

```text
gh release view v0.1.4 --repo OpenSenseNova/SenseNova-Skills-ProactiveAgent --json tagName,isDraft,isPrerelease,assets
gh release download v0.1.4 --repo OpenSenseNova/SenseNova-Skills-ProactiveAgent --pattern sn_proactive_agent-0.1.4-py3-none-any.whl --pattern SHA256SUMS
```

Verify the wheel against the checksum file before installing it. Then use the Python
interpreter selected for the target environment:

```text
pipx install --python "$SNPA_PYTHON" "$SNPA_PACKAGE"
sn-proactive-agent --version
sn-proactive-agent doctor --json
```

`SNPA_PYTHON` must point to Python 3.11 or newer, and `SNPA_PACKAGE` must be the absolute
path to the verified wheel.

### 3. Configure the Connector

#### Hermes

Set `SNPA_HERMES_ROOT` to the Hermes source checkout that the target instance actually uses.
Preview changes before applying them:

```text
sn-proactive-agent setup --harness hermes --web-only --hermes-root "$SNPA_HERMES_ROOT" --dry-run
sn-proactive-agent setup --harness hermes --web-only --hermes-root "$SNPA_HERMES_ROOT"
```

The installer checks compatibility, backs up the affected TUI and build files, installs
observation resources, and builds the Web-only bridge. It does not copy the Skill, start
Hermes, start the Web service, or send a test message.

#### OpenClaw

Follow the [OpenClaw Connector guide](../skills/sn-proactive-agent/references/connectors/openclaw.md).
In the same verified Release download directory, download the plugin and verify it against
the matching entry in `SHA256SUMS` before installing:

```text
gh release download v0.1.4 --repo OpenSenseNova/SenseNova-Skills-ProactiveAgent --pattern sn-proactive-agent-openclaw-0.1.4.tgz
```

For the intended Gateway instance, install and configure the verified plugin:

```text
openclaw plugins install ./sn-proactive-agent-openclaw-0.1.4.tgz
openclaw plugins enable sn-proactive-agent
openclaw config set plugins.entries.sn-proactive-agent.hooks.allowConversationAccess true
openclaw config set plugins.entries.sn-proactive-agent.config.serviceUrl http://127.0.0.1:8080
```

`allowConversationAccess` grants access to conversations captured after integration. Keep
the same profile, `OPENCLAW_CONFIG_PATH`, and `OPENCLAW_STATE_DIR` throughout. If `plugins.allow`
is configured, preserve its existing entries and add `sn-proactive-agent`. Check existing
plugin versions and local changes before upgrading; do not overwrite them blindly.

Restart a service-managed Gateway with `openclaw gateway restart`. For a foreground Gateway,
stop and restart the intended instance using its original launch method.
`sn-proactive-agent setup --harness openclaw` is not available.

### 4. Start the Web workbench

For Hermes-only integration, run the service in a separate terminal:

```text
sn-proactive-agent serve --web-only
```

For OpenClaw, including when both Harnesses are connected, use the actual Gateway address:

```text
sn-proactive-agent serve --web-only --openclaw-gateway-url http://127.0.0.1:18789
```

Choose one service command; do not start a second Core instance. If the Gateway uses token
authentication, provide `SN_PROACTIVE_AGENT_OPENCLAW_GATEWAY_TOKEN` in the service environment.
Keep existing authentication enabled and do not put the token in command arguments or logs.
Confirm compatibility before using another authentication mode.

Check the service from another terminal:

```text
sn-proactive-agent doctor --url http://127.0.0.1:8080 --json
```

Open <http://127.0.0.1:8080/> in a browser. If a custom port or data root is used, point
the service, Connector, diagnostic command, and browser to the same values.
For OpenClaw, enable it in the Web settings; disable Hermes monitoring if only OpenClaw is
needed. The monitoring switch does not start the Gateway or remove the Hermes CLI dependency.

### 5. Verify the real Session flow

#### Hermes

Restart the configured Hermes instance, then use an agreed test conversation:

```text
hermes --tui --accept-hooks
```

Verify that the conversation is captured, meaningful suggestions appear only in the Web
workbench, an accepted suggestion runs once in the original Session, and the result returns
with its `source_suggestion_id`. A runtime or static integration check without a real
conversation is not a complete integration acceptance.

For the final diagnostic, use the actual Session ID:

```text
sn-proactive-agent doctor --harness hermes --hermes-root "$SNPA_HERMES_ROOT" \
  --url http://127.0.0.1:8080 --session-id "$SNPA_SESSION_ID" --json
```

#### OpenClaw

Use an agreed test conversation through the user's normal OpenClaw interface:

1. Confirm that a completed text QA appears in the Web workbench with the correct Project,
   Item, Event, and Session association, and that follow-up messages remain associated.
2. When a useful suggestion appears, accept it in the Web workbench and confirm that it
   executes once in the original OpenClaw Session.
3. Check the actual result, updated project state, and the returned Event's
   `source_suggestion_id`; that result should not immediately generate another suggestion.

`doctor --url` checks service health only. There is currently no OpenClaw-specific Session
doctor; Hermes diagnostics and the Web monitoring status do not verify OpenClaw integration.
The plugin captures text QA, not full attachments or tool traces; individual text fields
are truncated beyond 120,000 characters. Gateway restarts clear in-memory continuation
deduplication, so inspect the original Session and logs before retrying an uncertain action.

## Data and lifecycle

The default data root is `~/.sn-proactive-agent/`. It contains:

- `projects/<project-id>/project.md`: project overview and Item index.
- `projects/<project-id>/items/<item-id>/item.md`: latest Item state.
- `projects/<project-id>/items/<item-id>/events.md`: QA and state changes.
- `runtime.jsonl`: ingestion, attribution, suggestion, decision, execution, and daily
  summary records.

Use `--data-root` or `SN_PROACTIVE_AGENT_DATA_ROOT` to choose another location. Existing
users with `~/.proactive-memory/` are handled according to the documented migration rules;
the new service does not merge two data roots automatically.

Stop, upgrade, and uninstall only the intended service and Connector. Follow the
[lifecycle instructions](../skills/sn-proactive-agent/references/install/overview.md) and
the matching [Hermes](../skills/sn-proactive-agent/references/connectors/hermes.md) or
[OpenClaw Connector guide](../skills/sn-proactive-agent/references/connectors/openclaw.md)
for rollback, upgrade, and cleanup behavior.

For OpenClaw, upgrading the runtime wheel does not update the copied Gateway plugin.
Upgrade the verified plugin separately, restart the intended Gateway, and repeat the
conversation checks. To remove the integration, turn off OpenClaw monitoring in the Web
settings, then run against that same Gateway instance:

```text
openclaw plugins disable sn-proactive-agent
openclaw plugins uninstall sn-proactive-agent
```

Restart the Gateway and check for this plugin's remaining configuration and trust-list entries.
`sn-proactive-agent uninstall` currently manages Hermes only; it does not remove the OpenClaw
plugin. Preserve conversations, project data, and other plugins during cleanup.

## Security boundaries

The service handles conversation-derived project state and can submit an accepted action
back to the original Session. Keep the Web service on its intended local interface, do
not expose it publicly without an independent security review, and do not commit API keys,
`.env` files, runtime data, logs, or local Hermes / OpenClaw configuration.
