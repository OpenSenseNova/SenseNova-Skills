# ACP runtime

Studio is an ACP v1 client. One implementation (`scripts/agent_bridge.py`) handles stdio, session creation, images, file/terminal callbacks, permission requests and task cancellation. The three profiles only select launch commands.

## Install and select

Use Python 3.10+ and install `requirements.txt`. The Python SDK is pinned to `agent-client-protocol==0.12.1`.

Install the ACP server for the chosen harness, then authenticate using that harness's normal setup. These are separately maintained adapters, not a claim that every harness exposes ACP natively:

| Selection | Default launch argv | Installation |
| --- | --- | --- |
| `codex` | `codex-acp` | `npm install -g @agentclientprotocol/codex-acp@2.5.0` |
| `claude` | `claude-agent-acp` | `npm install -g @agentclientprotocol/claude-agent-acp@0.100.0` |
| `hermes` | `hermes acp` | Install Hermes and its ACP dependencies per the official guide; verify `hermes acp --check` |

Upstream sources: [Codex adapter](https://github.com/agentclientprotocol/codex-acp), [Claude adapter](https://github.com/agentclientprotocol/claude-agent-acp), [Hermes ACP](https://hermes-agent.nousresearch.com/docs/user-guide/features/acp/), [ACP Python SDK](https://agentclientprotocol.com/libraries/python).

```bash
python3 scripts/studio.py doctor --harness codex
python3 scripts/studio.py serve --background --harness codex
```

Use the same selected harness for both commands. `--acp-command` overrides launch argv with a JSON string array, for example `--acp-command '["/opt/tools/codex-acp"]'`. It is a trusted startup option, never a command accepted from the webpage. `--agent-timeout` bounds the entire Agent prompt turn, including waiting for image execution (default 1800 seconds). Keep custom values long enough to cover rewriting plus the 1260-second task-receipt wait; a shorter value can end the Agent session before the image result is available. Handshake and session creation retain separate 30/60-second bounds. Multiple installed harnesses do not trigger automatic selection or fallback.

The launching chat and the Studio Agent are distinct sessions. Each task creates a fresh ACP session with an isolated working directory. Its complete snapshot carries prior manual edits and image roles, so it does not need the launching chat's history. The page shows the configured harness and the task records the actual handshake identity/version/session ID. Executable presence means ready to attempt connection, not verified login.

## Task contract

1. Studio persists the request and dispatches it without browser polling or a host command.
2. The job directory receives `SKILL.md`, `task-input.json`, ordered image files, `execute_task.py` and a private `job-access.json` capability. The Agent receives image blocks when inputs are present; an Agent without negotiated image support fails explicitly.
3. The Agent reads the skill's execution branch, writes `rewrite-result.json`, and calls the supplied Python command.
4. The script atomically publishes `execution-request.json` in the job directory. Studio watches that mailbox and writes `execution-receipt.json`; the Agent script requires no localhost/network permission. Studio validates it, durably records the generation boundary, and invokes `images.py` using the saved settings/assets. Image credentials are not in the task snapshot or ACP prompt.
5. The script returns the receipt. ACP prose/turn completion alone never marks a task successful. A failed image call preserves the rewrite.

`generate_after_rewrite=false` saves only the rewrite; `true` owns both steps on the backend. Browser changes after submission belong to the next task; stale rewrites are candidates instead of overwriting a newer draft. Reloading the page retrieves results without dispatching another image request.

## Permissions and failures

Client-provided file callbacks are scoped to the job directory; writes are restricted to `rewrite-result.json`. Client terminals run only the supplied task script, with argv matching rather than arbitrary shell evaluation. ACP permission callbacks grant one-time access for in-scope file operations and the exact task command; other requests are rejected and reported as task failures. Native Agent tools still use that harness's own sandbox and configuration; ACP client path checks are not a sandbox around native tools.

Authentication/connection failures, missing capabilities, denied operations and missing receipts become visible failures. Raw provider exceptions, thoughts, stderr and tool arguments are not copied to public task data. Cancellation is supported before generation. Once the paid image call starts, Studio keeps observing that original call; it does not cancel and resubmit it.

Repeated submission IDs and repeated task-script callbacks are idempotent. A different payload with the same ID conflicts. A lost response, timeout or service restart never automatically replays a paid image request. On restart, unfinished tasks are marked failed with an uncertainty notice; inspect their existing files before explicitly creating a new task.
