#!/usr/bin/env python3
"""Start the SenseNova generation progress WebUI for a generated deck.

The PPT pipeline remains responsible for generation. This helper only starts
the local WebUI so users can watch JSON artifacts and pages appear in real
time. It is intentionally best-effort: missing workbench code must not block
PPT generation.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Iterable

EDITOR_ROUTE = "/editor"
PROGRESS_ROUTE = "/progress"
LEGACY_EDITOR_ROUTE = "/ppt-editor"
LEGACY_PROGRESS_ROUTE = "/ppt-progress"


def _background_process_kwargs() -> dict[str, int]:
    if os.name != "nt":
        return {}
    return {"creationflags": subprocess.CREATE_NO_WINDOW}


def _repo_candidates() -> Iterable[Path]:
    binary_name = "sensenova-ppt-workbench.mjs"
    env_cli = os.environ.get("SENSENOVA_PPT_WORKBENCH_CLI") or os.environ.get("PPT_WORKBENCH_CLI")
    if env_cli:
        yield Path(env_cli).expanduser()

    here = Path(__file__).resolve()
    skill_dir = here.parents[1]
    skills_root = skill_dir.parent
    yield skills_root / "sn-ppt-workbench" / "workbench-runtime" / "bin" / binary_name
    yield skill_dir / "workbench-runtime" / "bin" / binary_name

    home = Path.home()
    yield home / "Repository" / "ppt-editor" / "src" / "ppt-editor" / "bin" / binary_name
    yield home / "Repository" / "ppt-editor" / "bin" / binary_name

    # Common layout during local development:
    #   ~/Repository/SenseNova-Skills/skills/sn-ppt-standard/scripts/launch_workbench.py
    #   ~/Repository/ppt-editor/src/ppt-editor/bin/sensenova-ppt-workbench.mjs
    for parent in here.parents:
        yield parent / "src" / "ppt-editor" / "bin" / binary_name
        yield parent / "ppt-editor" / "src" / "ppt-editor" / "bin" / binary_name
        yield parent.parent / "ppt-editor" / "src" / "ppt-editor" / "bin" / binary_name
        yield parent / "ppt-editor" / "bin" / binary_name
        yield parent.parent / "ppt-editor" / "bin" / binary_name


def _find_cli() -> Path | None:
    for candidate in _repo_candidates():
        if candidate.is_file():
            return candidate.resolve()
    return None


def _run(command: list[str], cwd: Path, timeout: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=str(cwd),
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
        **_background_process_kwargs(),
    )


def _npm_command() -> str:
    return "npm.cmd" if os.name == "nt" else "npm"


def _node_command() -> str:
    return "node.exe" if os.name == "nt" else "node"


def _probe_command(command: str) -> tuple[bool, str]:
    """Return whether a local command is runnable, plus version/error detail."""
    try:
        result = subprocess.run(
            [command, "--version"],
            text=True,
            capture_output=True,
            timeout=10,
            check=False,
            **_background_process_kwargs(),
        )
    except (FileNotFoundError, OSError) as exc:
        return False, str(exc)
    except subprocess.TimeoutExpired:
        return False, f"{command} --version timed out"

    detail = (result.stdout or result.stderr or "").strip()
    return result.returncode == 0, detail


def _clean_env(name: str) -> str:
    return os.environ.get(name, "").strip()


def _with_workbench_route(url: str, route: str) -> str:
    if not url:
        return ""

    parts = urllib.parse.urlsplit(url)
    path = parts.path.rstrip("/")
    for known_route in (EDITOR_ROUTE, PROGRESS_ROUTE, LEGACY_EDITOR_ROUTE, LEGACY_PROGRESS_ROUTE):
        if path.endswith(known_route):
            path = path[: -len(known_route)].rstrip("/")
            break

    path = f"{path}{route}" if path else route
    query = parts.query
    if route == PROGRESS_ROUTE and query:
        query = urllib.parse.urlencode([
            (key, value)
            for key, value in urllib.parse.parse_qsl(query, keep_blank_values=True)
            if not (key == "view" and value == "generation")
        ])

    return urllib.parse.urlunsplit((parts.scheme, parts.netloc, path, query, parts.fragment))


def _normalize_progress_route(value: str) -> str:
    route = (value or PROGRESS_ROUTE).strip().replace("\\", "/")
    if route in {PROGRESS_ROUTE, LEGACY_PROGRESS_ROUTE}:
        return PROGRESS_ROUTE
    if route.rstrip("/").endswith(PROGRESS_ROUTE) or route.rstrip("/").endswith(LEGACY_PROGRESS_ROUTE):
        return PROGRESS_ROUTE
    raise ValueError(f"--progress-route must be {PROGRESS_ROUTE}")


def _env_file_candidates() -> Iterable[Path]:
    """Yield Hermes env files that may contain the Gateway bridge secret."""
    for name in ("HERMES_HOME",):
        value = _clean_env(name)
        if value:
            yield Path(value).expanduser() / ".env"
    if os.name == "nt":
        local_app_data = os.environ.get("LOCALAPPDATA", "").strip()
        if local_app_data:
            yield Path(local_app_data) / "hermes" / ".env"
    yield Path.home() / ".hermes" / ".env"


def _load_env_file(file_path: Path) -> dict[str, str]:
    """Parse a simple KEY=VALUE env file without printing secret values."""
    if not file_path.is_file():
        return {}

    values: dict[str, str] = {}
    for line in file_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, raw_value = stripped.split("=", 1)
        values[key.strip()] = raw_value.strip().strip("\"'")
    return values


def _hydrate_hermes_env() -> None:
    """Load missing bridge values from Hermes env files into this process."""
    for file_path in _env_file_candidates():
        values = _load_env_file(file_path)
        for key in (
            "API_SERVER_KEY",
            "WORKBENCH_GATEWAY_API_KEY",
            "HERMES_GATEWAY_API_KEY",
            "AI_GATEWAY_API_KEY",
            "HERMES_GATEWAY_BASE_URL",
        ):
            if key in values and not _clean_env(key):
                os.environ[key] = values[key]


def _resolve_gateway_api_key(args: argparse.Namespace) -> str:
    """Resolve the server-only Gateway bridge key for the Node child process."""
    return (
        args.gateway_api_key.strip()
        or _clean_env("WORKBENCH_GATEWAY_API_KEY")
        or _clean_env("API_SERVER_KEY")
        or _clean_env("HERMES_GATEWAY_API_KEY")
        or _clean_env("AI_GATEWAY_API_KEY")
    )


def _gateway_models_url(base_url: str) -> str:
    """Build a models URL while accepting bases with or without /v1."""
    normalized = base_url.rstrip("/")
    return f"{normalized}/models" if normalized.endswith("/v1") else f"{normalized}/v1/models"


def _is_hermes_gateway_base(base_url: str, api_key: str) -> bool:
    """Return true when a base URL looks like the Hermes Gateway API."""
    if not base_url or not api_key:
        return False

    request = urllib.request.Request(
        _gateway_models_url(base_url),
        headers={"Authorization": f"Bearer {api_key}"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=4) as response:
            body = response.read(10000).decode("utf-8", errors="replace")
            return response.status == 200 and "hermes-agent" in body
    except (OSError, urllib.error.URLError, urllib.error.HTTPError):
        return False


def _resolve_gateway_base_url(args: argparse.Namespace, api_key: str) -> str:
    """Resolve a Hermes Gateway URL and avoid direct model endpoints."""
    configured = args.gateway_base_url.strip() or _clean_env("HERMES_GATEWAY_BASE_URL")
    if _is_hermes_gateway_base(configured, api_key):
        return configured

    for candidate in ("http://127.0.0.1:8642", "http://localhost:8642", "http://127.0.0.1:8643"):
        if _is_hermes_gateway_base(candidate, api_key):
            return candidate

    return configured


def _discover_forwarded_public_url() -> str:
    """Prefer Hermes/canvas/port-forward URLs over direct host exposure."""
    for name in (
        "WORKBENCH_PUBLIC_URL",
        "HERMES_WORKBENCH_PUBLIC_URL",
        "HERMES_CANVAS_URL",
        "HERMES_CANVAS_PUBLIC_URL",
        "HERMES_PORT_FORWARD_URL",
        "HERMES_PORT_FORWARD_PUBLIC_URL",
        "HERMES_FORWARD_URL",
        "HERMES_PUBLIC_URL",
        "CANVAS_URL",
        "CANVAS_PUBLIC_URL",
        "PORT_FORWARD_URL",
        "PUBLIC_URL",
        "EXTERNAL_URL",
        "TUNNEL_URL",
    ):
        value = _clean_env(name)
        if value:
            return value

    codespace = _clean_env("CODESPACE_NAME")
    codespace_domain = _clean_env("GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN")
    if codespace and codespace_domain:
        return f"https://{codespace}-{{port}}.{codespace_domain}"

    gitpod_url = _clean_env("GITPOD_WORKSPACE_URL")
    if gitpod_url:
        return f"https://{{port}}-{gitpod_url.removeprefix('https://').removeprefix('http://')}"

    return ""


def _resolve_public_url(args: argparse.Namespace) -> str:
    return args.public_url.strip() or _discover_forwarded_public_url()


def _looks_like_docker_or_wsl() -> bool:
    """Return true when localhost would not be reachable from the user side."""
    env_markers = (
        "WSL_DISTRO_NAME",
        "WSL_INTEROP",
        "DOCKER_CONTAINER",
        "KUBERNETES_SERVICE_HOST",
    )
    if any(_clean_env(name) for name in env_markers):
        return True
    if _clean_env("container"):
        return True
    if Path("/.dockerenv").exists():
        return True

    for file_path in (Path("/proc/1/cgroup"), Path("/proc/version")):
        try:
            text = file_path.read_text(encoding="utf-8", errors="ignore").lower()
        except OSError:
            continue
        if any(marker in text for marker in ("docker", "containerd", "kubepods", "microsoft", "wsl")):
            return True

    return False


def _resolve_host(args: argparse.Namespace, public_url: str) -> str:
    if args.host.strip():
        return args.host.strip()

    env_host = _clean_env("WORKBENCH_HOST")
    if env_host:
        return env_host

    # Forwarding/canvas URLs usually proxy from localhost. Without one, expose
    # all interfaces only in container-like environments where localhost points
    # at the wrong network namespace for the user.
    if public_url:
        return "127.0.0.1"
    return "0.0.0.0" if _looks_like_docker_or_wsl() else "127.0.0.1"


def _is_agent_managed(args: argparse.Namespace) -> bool:
    return args.agent_managed.strip() == "1" or bool(
        args.source_session_id.strip()
        or args.agent_session_id.strip()
        or args.agent_base_url.strip()
        or args.acp_command.strip()
        or args.agent_provider.strip()
    )


def _default_agent_provider() -> str:
    return (
        os.environ.get("WORKBENCH_AGENT_PROVIDER")
        or os.environ.get("WORKBENCH_AGENT_RUNTIME")
        or "hermes"
    )


def _ensure_built(cli: Path, timeout: int) -> tuple[bool, str]:
    repo = cli.parents[1]
    if (repo / "dist" / "index.html").is_file():
        return True, "dist/index.html exists"

    npm_ok, npm_detail = _probe_command(_npm_command())
    if not npm_ok:
        return False, f"npm is unavailable: {npm_detail}"

    result = _run([_npm_command(), "run", "build"], repo, timeout)
    if result.returncode == 0 and (repo / "dist" / "index.html").is_file():
        return True, "built workbench"

    detail = (result.stderr or result.stdout or "npm run build failed").strip()
    return False, detail[-1000:]


def main() -> int:
    _hydrate_hermes_env()
    parser = argparse.ArgumentParser(description="Start SenseNova PPT workbench.")
    parser.add_argument("--deck-dir", required=True)
    parser.add_argument("--source-session-id", default=os.environ.get("WORKBENCH_AGENT_SOURCE_SESSION_ID", os.environ.get("HERMES_SESSION_KEY", "")))
    parser.add_argument("--agent-session-id", default="")
    parser.add_argument("--agent-managed", default=os.environ.get("WORKBENCH_AGENT_MANAGED", ""))
    parser.add_argument("--agent-provider", default=_default_agent_provider())
    parser.add_argument("--agent-transport", default=os.environ.get("WORKBENCH_AGENT_TRANSPORT", ""))
    parser.add_argument("--agent-runtime", default=os.environ.get("WORKBENCH_AGENT_RUNTIME", _default_agent_provider()))
    parser.add_argument("--agent-base-url", default=os.environ.get("WORKBENCH_AGENT_BASE_URL", os.environ.get("OPENCLAW_GATEWAY_BASE_URL", os.environ.get("OPENCLAW_BASE_URL", ""))))
    parser.add_argument("--agent-api-key", default=os.environ.get("WORKBENCH_AGENT_API_KEY", os.environ.get("OPENCLAW_API_KEY", "")))
    parser.add_argument("--acp-command", default=os.environ.get("WORKBENCH_ACP_COMMAND", os.environ.get("CODEX_ACP_COMMAND", os.environ.get("CLAUDE_ACP_COMMAND", ""))))
    parser.add_argument("--webui-base-url", default=os.environ.get("HERMES_WEBUI_BASE_URL", ""))
    parser.add_argument("--gateway-base-url", default=os.environ.get("HERMES_GATEWAY_BASE_URL", ""))
    parser.add_argument("--gateway-api-key", default=os.environ.get("WORKBENCH_GATEWAY_API_KEY", ""))
    parser.add_argument("--public-url", default="")
    parser.add_argument("--host", default="")
    parser.add_argument("--port", default="0")
    parser.add_argument("--progress-route", default=os.environ.get("WORKBENCH_PROGRESS_ROUTE", PROGRESS_ROUTE))
    parser.add_argument("--no-build", action="store_true")
    parser.add_argument("--require-webui", action="store_true")
    args = parser.parse_args()

    def unavailable(payload: dict[str, object]) -> int:
        print(json.dumps({
            "status": "failed" if args.require_webui else "skipped",
            **payload,
        }, ensure_ascii=False))
        return 2 if args.require_webui else 0

    deck_dir = Path(args.deck_dir).expanduser().resolve()
    if not deck_dir.is_dir():
        return unavailable({
            "reason": f"deck dir not found: {deck_dir}",
        })

    cli = _find_cli()
    if not cli:
        return unavailable({
            "reason": "sensenova-ppt-workbench launcher not found; set SENSENOVA_PPT_WORKBENCH_CLI",
        })

    node_ok, node_detail = _probe_command(_node_command())
    if not node_ok:
        return unavailable({
            "reason": "nodejs_missing",
            "detail": node_detail,
            "install_hint": "NodeJS is required for the generation progress WebUI. Ask the user whether to install NodeJS/dependencies; if they decline, continue PPT generation without the WebUI.",
            "cli": str(cli),
        })

    if not args.no_build:
        ok, detail = _ensure_built(cli, timeout=180)
        if not ok:
            return unavailable({
                "reason": f"workbench build failed: {detail}",
                "cli": str(cli),
            })

    public_url = _resolve_public_url(args)
    host = _resolve_host(args, public_url)
    try:
        progress_route = _normalize_progress_route(args.progress_route)
    except ValueError as exc:
        return unavailable({
            "reason": str(exc),
            "cli": str(cli),
        })
    gateway_api_key = _resolve_gateway_api_key(args)
    gateway_base_url = _resolve_gateway_base_url(args, gateway_api_key)
    command = [
        _node_command(),
        str(cli),
        "start",
        "--deck-dir",
        str(deck_dir),
        "--port",
        str(args.port),
        "--host",
        host,
        "--product",
        "ppt",
        "--progress-route",
        progress_route,
        "--agent-provider",
        args.agent_provider,
        "--agent-runtime",
        args.agent_runtime,
    ]
    if args.agent_transport:
        command.extend(["--agent-transport", args.agent_transport])
    if args.agent_base_url:
        command.extend(["--agent-base-url", args.agent_base_url])
    if args.agent_api_key:
        command.extend(["--agent-api-key", args.agent_api_key])
    if args.acp_command:
        command.extend(["--acp-command", args.acp_command])
    if public_url:
        command.extend(["--public-url", public_url])
    if _is_agent_managed(args):
        command.extend(["--agent-managed", "1"])
    source_session_id = args.source_session_id.strip() or args.agent_session_id.strip()
    if source_session_id:
        command.extend(["--source-session-id", source_session_id])
    if args.webui_base_url:
        command.extend(["--webui-base-url", args.webui_base_url])
    if gateway_base_url:
        command.extend(["--gateway-base-url", gateway_base_url])
    if gateway_api_key:
        command.extend(["--gateway-api-key", gateway_api_key])

    result = _run(command, cli.parents[1], timeout=60)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "launcher failed").strip()
        return unavailable({
            "reason": detail[-1000:],
            "cli": str(cli),
        })

    try:
        payload = json.loads(result.stdout.strip())
    except json.JSONDecodeError:
        payload = {"raw": result.stdout.strip()}

    workbench_url = payload.get("url") or public_url
    generation_url = _with_workbench_route(payload.get("generationUrl") or workbench_url, progress_route)
    print(json.dumps({
        "status": "ok",
        "cli": str(cli),
        "product": "ppt",
        "deck_dir": str(deck_dir),
        "bind_host": host,
        "agent_managed": _is_agent_managed(args),
        "public_url": workbench_url,
        "progress_route": progress_route,
        "generation_url": generation_url,
        "editor_url": payload.get("editorUrl") or workbench_url,
        "workbench": payload,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
