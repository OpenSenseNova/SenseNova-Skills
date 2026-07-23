# Hermes Gateway API Auth Setup for PPT Workbench

When launching the PPT workbench with writable Hermes session bridging, the
workbench Node.js server and the Hermes Gateway API server must authenticate
with matching keys.

## Quick Reference

| Component | Env var | Default | What it does |
|---|---|---|---|
| Gateway | `API_SERVER_KEY` | *required, no default* | Validates inbound requests to the Gateway API |
| Workbench (bridge) | `WORKBENCH_GATEWAY_API_KEY` | falls back to backend-only Gateway settings | Sent as `Authorization: Bearer` to Gateway API chat endpoint |
| Workbench (AI settings) | `AI_GATEWAY_API_KEY` | `ppt-editor-dev` | AI provider BYOK; used only as a backend fallback when no explicit bridge key is set |

**Rule: `API_SERVER_KEY` (gateway) == `WORKBENCH_GATEWAY_API_KEY` (workbench bridge).**
Prefer setting `WORKBENCH_GATEWAY_API_KEY` explicitly. If omitted, the workbench
server falls back to `API_SERVER_KEY`, `HERMES_GATEWAY_API_KEY`, then the
backend-only AI Gateway key (`AI_GATEWAY_API_KEY`, defaulting to
`ppt-editor-dev`). These values are never sent to the browser.

## Gateway API Server

The Gateway API server is a platform adapter inside the Hermes Gateway, just like
Feishu or Discord. It must be explicitly enabled.

### Prerequisites

1. Set `API_SERVER_KEY` in `~/.hermes/.env`:
   ```
   API_SERVER_KEY=ppt-editor-dev
   ```
2. Restart the Hermes Gateway (full restart, not hot reload).
3. Verify: `curl http://127.0.0.1:8642/v1/models -H "Authorization: Bearer ppt-editor-dev"`

### Default port

`8642` — defined in `gateway/platforms/api_server.py`:
```python
DEFAULT_PORT = 8642
```

The port binds to `127.0.0.1` (loopback only). No remote access by default.

### Troubleshooting: "Refusing to start"

Gateway log shows:
```
ERROR gateway.platforms.api_server: [Api_Server] Refusing to start:
API_SERVER_KEY is required for the API server, including loopback-only
binds on 127.0.0.1.
```

**Fix:** Add `API_SERVER_KEY` to `~/.hermes/.env` and restart the gateway.
The gateway checks `os.getenv("API_SERVER_KEY")` — setting it in `.env` works
because the gateway process loads `.env` at startup.

## Workbench Connection

### Step 1: Set matching keys

Ensure the workbench process has `WORKBENCH_GATEWAY_API_KEY` set to the same value
as the gateway's `API_SERVER_KEY`:
```bash
export WORKBENCH_GATEWAY_API_KEY=ppt-editor-dev
```

Or add to `~/.hermes/.env`:
```
API_SERVER_KEY=ppt-editor-dev
WORKBENCH_GATEWAY_API_KEY=ppt-editor-dev
```

### Step 2: Launch workbench with gateway URL

```bash
export HERMES_GATEWAY_BASE_URL="http://127.0.0.1:8642"
python $SKILL_DIR/scripts/open_workbench.py --deck-dir "$DECK"
```

The open_workbench.py script passes `--gateway-base-url` to the Node.js
workbench process via CLI argument. The Node.js process prefers
`WORKBENCH_GATEWAY_API_KEY` from the environment, but can fall back to the local
dev key when the Gateway uses `ppt-editor-dev`.

### Step 3: Verify bridge mode

The health check should show:
```json
{
  "agentBridge": {
    "mode": "gateway-session",
    "writable": true,
    "status": "Connected to Hermes Gateway session."
  }
}
```

If you see `"mode": "mirror-only"` with `"writable": false`, the bridge didn't
establish — check that both keys match and the gateway is running on port 8642.

## Common Pitfalls

### Preferred variable: WORKBENCH_GATEWAY_API_KEY

Set `WORKBENCH_GATEWAY_API_KEY` for bridge auth when the Gateway uses a custom
`API_SERVER_KEY`. `AI_GATEWAY_API_KEY` is only a backend fallback and should not
be relied on for production or shared environments.

**Fix:** Use `WORKBENCH_GATEWAY_API_KEY` for gateway bridge auth.

### "Hermes Gateway chat bridge failed with HTTP 401. Invalid API key"

- The gateway has `API_SERVER_KEY=X` but the workbench sends `WORKBENCH_GATEWAY_API_KEY=*** where X ≠ Y.
- **Fix:** Make them match. Simplest approach: set both to `ppt-editor-dev`.

### Key truncated in shell

Bash heredocs (`<< 'EOF'`) and terminal output may display trun*** values
due to Hermes secret redaction patterns. The actual file content is preserved.
Verify with: `wc -c <.env_file` (should match expected line lengths).

### Shell env vars not reaching Node subprocess

`export FOO=bar; python script.py` — the Python subprocess inherits `FOO`, and
`subprocess.run()` in Python inherits the parent's environment. However, if the
workbench was already running from a previous launch (reused), it retains its
original environment.

**Fix:** Kill the old workbench (`taskkill /PID <pid> /F`) before restarting.

### Old workbench instance reusing stale session.json

The open_workbench.py helper is designed to reuse an existing healthy workbench.
If the workbench was launched without `--gateway-base-url`, its session.json
records `mirror-only` mode. Subsequent invocations will reuse this instance
even if `HERMES_GATEWAY_BASE_URL` is now set.

**Fix:** Kill the old PID first, then launch fresh.

## Health Check Commands

```bash
# Gateway API alive?
curl http://127.0.0.1:8642/health

# Gateway API with auth?
curl http://127.0.0.1:8642/v1/models \
  -H "Authorization: Bearer ppt-editor-dev"

# Chat completion test (validates end-to-end Hermes session routing):
curl http://127.0.0.1:8642/v1/chat/completions \
  -H "Authorization: Bearer ppt-editor-dev" \
  -H "Content-Type: application/json" \
  -d '{"model":"hermes-agent","messages":[{"role":"user","content":"hi"}]}'

# Gateway logs:
tail -f ~/AppData/Local/hermes/logs/gateway.log | grep api_server
```
