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
- Resumes an accepted action in the original Hermes Session and records the result with its
  source suggestion ID.
- Keeps runtime data under the user's Home directory rather than inside the source
  checkout.

## Components and boundaries

| Component | Responsibility |
|---|---|
| Skill | Tells the Agent when to inspect, install, configure, or operate the service. |
| Runtime package | Provides the `sn-proactive-agent` CLI, Core, Web workbench, and diagnostics. |
| Hermes Connector | Captures conversation QA and resumes accepted actions in the original Session. |
| User data | Stores Projects, Items, Events, runtime records, and recovery state under `~/.sn-proactive-agent/` by default. |

Installing the Skill does not install the runtime package, configure Hermes, or start the
service. The current installation entry point supports Hermes; other Harnesses must not
reuse the Hermes commands.

## Requirements

- A working Hermes installation and a supported Hermes source checkout.
- Python 3.11 or newer and `pipx`.
- Node.js 22 or newer plus the build dependencies required by the selected Hermes version.
- Permission to read the private GitHub Release repository when installing the published
  runtime package.
- A model configured in Hermes. The installation flow does not read or print API keys.

The current workspace documents the unified `0.1.3` candidate. Before downloading, confirm
that the matching GitHub Release is published, is not a draft, and contains both the wheel
and `SHA256SUMS`. Do not substitute the source checkout, an unverified URL, or the older
`proactive-memory-service` package.

## Install and configure

### 1. Install the Skill

Copy the complete `skills/sn-proactive-agent/` directory into the Harness Skill directory.
The directory must include `SKILL.md` and `references/`; installing the runtime package alone
does not install this Skill.

### 2. Install the runtime package

Use the release checks and download commands from the [shared installation procedure](../skills/sn-proactive-agent/references/install/overview.md):

```text
gh release view v0.1.3 --repo OpenSenseNova/SenseNova-Skills-ProactiveAgent --json tagName,isDraft,isPrerelease,assets
gh release download v0.1.3 --repo OpenSenseNova/SenseNova-Skills-ProactiveAgent --pattern sn_proactive_agent-0.1.3-py3-none-any.whl --pattern SHA256SUMS
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

### 3. Configure the Hermes Connector

Set `SNPA_HERMES_ROOT` to the Hermes source checkout that the target instance actually uses.
Preview changes before applying them:

```text
sn-proactive-agent setup --harness hermes --web-only --hermes-root "$SNPA_HERMES_ROOT" --dry-run
sn-proactive-agent setup --harness hermes --web-only --hermes-root "$SNPA_HERMES_ROOT"
```

The installer checks compatibility, backs up the affected TUI and build files, installs
observation resources, and builds the Web-only bridge. It does not copy the Skill, start
Hermes, start the Web service, or send a test message.

### 4. Start the Web workbench

Run the service in a separate terminal:

```text
sn-proactive-agent serve --web-only
sn-proactive-agent doctor --url http://127.0.0.1:8080 --json
```

Open <http://127.0.0.1:8080/> in a browser. If a custom port or data root is used, point
the service, Connector, diagnostic command, and browser to the same values.

### 5. Verify the real Session flow

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
the [Hermes Connector guide](../skills/sn-proactive-agent/references/connectors/hermes.md)
for rollback, upgrade, and cleanup behavior.

## Security boundaries

The service handles conversation-derived project state and can submit an accepted action
back to the original Session. Keep the Web service on its intended local interface, do
not expose it publicly without an independent security review, and do not commit API keys,
`.env` files, runtime data, logs, or local Hermes configuration.
