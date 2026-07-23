#!/usr/bin/env python3
"""Open the PPT editor WebUI for an existing generated HTML deck.

This helper is intentionally generation-free. It validates or auto-detects a
deck directory, locates the local ppt-editor launcher, starts/reuses the WebUI,
and prints one JSON object for the agent to report to the user.
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


def _json(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False))


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


def _is_html_deck(directory: Path) -> bool:
    if not directory.is_dir():
        return False

    pages_dir = directory / "pages"
    targets = [pages_dir] if pages_dir.is_dir() else [directory]
    return any(
        item.is_file() and item.suffix.lower() in {".html", ".htm"}
        for target in targets
        for item in target.iterdir()
    )


def _deck_mtime(directory: Path) -> float:
    candidates = [directory]
    pages_dir = directory / "pages"
    if pages_dir.is_dir():
        candidates.extend(item for item in pages_dir.iterdir() if item.is_file())

    return max((item.stat().st_mtime for item in candidates if item.exists()), default=0.0)


def _search_roots(args: argparse.Namespace) -> list[Path]:
    roots: list[Path] = []
    roots.extend(Path(item).expanduser() for item in args.search_root)
    roots.append(Path.cwd() / "ppt_decks")
    roots.append(Path.home() / "Downloads" / "ppt_decks")
    roots.append(Path.home() / "Repository" / "ppt_decks")

    seen: set[Path] = set()
    unique: list[Path] = []
    for root in roots:
        resolved = root.resolve()
        if resolved not in seen:
            seen.add(resolved)
            unique.append(resolved)
    return unique


def _detect_deck_dir(args: argparse.Namespace) -> Path | None:
    if args.deck_dir:
        deck_dir = Path(args.deck_dir).expanduser().resolve()
        return deck_dir if _is_html_deck(deck_dir) else None

    candidates: list[Path] = []
    for root in _search_roots(args):
        if not root.is_dir():
            continue
        candidates.extend(child.resolve() for child in root.iterdir() if _is_html_deck(child))

    return max(candidates, key=_deck_mtime, default=None)


def _launcher_candidates() -> Iterable[Path]:
    for env_name in ("SENSENOVA_PPT_WORKBENCH_CLI", "PPT_WORKBENCH_CLI"):
        env_value = os.environ.get(env_name, "").strip()
        if env_value:
            yield Path(env_value).expanduser()

    skill_dir = Path(__file__).resolve().parents[1]
    yield skill_dir / "workbench-runtime" / "bin" / "sensenova-ppt-workbench.mjs"

    home = Path.home()
    yield from _release_launcher_candidates(home / "Repository" / "ppt-editor" / "src" / "ppt-editor")
    yield from _release_launcher_candidates(home / "Repository" / "ppt-editor")
    yield home / "Repository" / "ppt-editor" / "src" / "ppt-editor" / "bin" / "sensenova-ppt-workbench.mjs"
    yield home / "Repository" / "ppt-editor" / "bin" / "sensenova-ppt-workbench.mjs"

    here = Path(__file__).resolve()
    for parent in here.parents:
        yield from _release_launcher_candidates(parent)
        yield from _release_launcher_candidates(parent / "src" / "ppt-editor")
        yield from _release_launcher_candidates(parent / "ppt-editor")
        yield from _release_launcher_candidates(parent / "ppt-editor" / "src" / "ppt-editor")
        yield parent / "src" / "ppt-editor" / "bin" / "sensenova-ppt-workbench.mjs"
        yield parent / "ppt-editor" / "src" / "ppt-editor" / "bin" / "sensenova-ppt-workbench.mjs"
        yield parent.parent / "ppt-editor" / "src" / "ppt-editor" / "bin" / "sensenova-ppt-workbench.mjs"
        yield parent / "ppt-editor" / "bin" / "sensenova-ppt-workbench.mjs"
        yield parent.parent / "ppt-editor" / "bin" / "sensenova-ppt-workbench.mjs"


def _release_launcher_candidates(runtime_root: Path) -> Iterable[Path]:
    for variant in ("workbench-core", "workbench-with-export"):
        yield runtime_root / "release" / variant / "bin" / "sensenova-ppt-workbench.mjs"


def _find_launcher() -> Path | None:
    for candidate in _launcher_candidates():
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


def _env_file_candidates() -> Iterable[Path]:
    """Yield Hermes env files that may contain the Gateway bridge secret."""
    value = _clean_env("HERMES_HOME")
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
        args.agent_session_id.strip()
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


def _ensure_runtime_artifacts(launcher: Path) -> tuple[bool, str]:
    runtime_root = launcher.parents[1]
    missing = [
        str(path.relative_to(runtime_root))
        for path in (
            runtime_root / "dist" / "index.html",
            runtime_root / "dist-server" / "index.mjs",
        )
        if not path.is_file()
    ]
    if missing:
        return False, f"missing packaged runtime artifacts: {', '.join(missing)}"
    return True, "packaged runtime artifacts exist"


def _start_workbench(args: argparse.Namespace, deck_dir: Path, launcher: Path) -> dict:
    public_url = _resolve_public_url(args)
    host = _resolve_host(args, public_url)
    gateway_api_key = _resolve_gateway_api_key(args)
    gateway_base_url = _resolve_gateway_base_url(args, gateway_api_key)
    command = [
        _node_command(),
        str(launcher),
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
        PROGRESS_ROUTE,
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
    if args.agent_session_id:
        command.extend(["--agent-session-id", args.agent_session_id])
    if args.webui_base_url:
        command.extend(["--webui-base-url", args.webui_base_url])
    if gateway_base_url:
        command.extend(["--gateway-base-url", gateway_base_url])
    if gateway_api_key:
        command.extend(["--gateway-api-key", gateway_api_key])

    result = _run(command, launcher.parents[1], timeout=args.launch_timeout)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "launcher failed").strip()
        return {
            "status": "skipped",
            "reason": detail[-1200:],
            "cli": str(launcher),
            "deck_dir": str(deck_dir),
        }

    try:
        workbench = json.loads(result.stdout.strip())
    except json.JSONDecodeError:
        workbench = {"raw": result.stdout.strip()}

    public_workbench_url = workbench.get("url") or public_url
    return {
        "status": "ok",
        "cli": str(launcher),
        "deck_dir": str(deck_dir),
        "bind_host": host,
        "public_url": public_workbench_url,
        "generation_url": _with_workbench_route(workbench.get("generationUrl") or public_workbench_url, PROGRESS_ROUTE),
        "editor_url": workbench.get("editorUrl") or public_workbench_url,
        "workbench": workbench,
    }


def main() -> int:
    _hydrate_hermes_env()
    parser = argparse.ArgumentParser(description="Open PPT editor WebUI for an existing HTML deck.")
    parser.add_argument("--deck-dir", default="")
    parser.add_argument("--search-root", action="append", default=[])
    parser.add_argument("--agent-session-id", default=os.environ.get("HERMES_SESSION_KEY", ""))
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
    parser.add_argument("--no-build", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--build-timeout", type=int, default=180, help=argparse.SUPPRESS)
    parser.add_argument("--launch-timeout", type=int, default=60)
    args = parser.parse_args()

    deck_dir = _detect_deck_dir(args)
    if not deck_dir:
        _json({
            "status": "skipped",
            "reason": "no generated HTML deck found; provide --deck-dir",
            "searched_roots": [str(root) for root in _search_roots(args)],
        })
        return 0

    launcher = _find_launcher()
    if not launcher:
        _json({
            "status": "skipped",
            "reason": "sensenova-ppt-workbench launcher not found; set SENSENOVA_PPT_WORKBENCH_CLI",
            "deck_dir": str(deck_dir),
        })
        return 0

    if args.dry_run:
        public_url = _resolve_public_url(args)
        _json({
            "status": "ok",
            "dry_run": True,
            "deck_dir": str(deck_dir),
            "cli": str(launcher),
            "bind_host": _resolve_host(args, public_url),
            "public_url": public_url,
            "agent_managed": _is_agent_managed(args),
        })
        return 0

    node_ok, node_detail = _probe_command(_node_command())
    if not node_ok:
        _json({
            "status": "skipped",
            "reason": "nodejs_missing",
            "detail": node_detail,
            "install_hint": "NodeJS is required for the PPT editor WebUI. Ask the user whether to install NodeJS/dependencies; if they decline, do not open the WebUI.",
            "cli": str(launcher),
            "deck_dir": str(deck_dir),
        })
        return 0

    ok, detail = _ensure_runtime_artifacts(launcher)
    if not ok:
        _json({
            "status": "skipped",
            "reason": f"workbench runtime incomplete: {detail}; reinstall or rebuild the packaged Workbench runtime",
            "cli": str(launcher),
            "deck_dir": str(deck_dir),
        })
        return 0

    _json(_start_workbench(args, deck_dir, launcher))
    return 0


if __name__ == "__main__":
    sys.exit(main())
