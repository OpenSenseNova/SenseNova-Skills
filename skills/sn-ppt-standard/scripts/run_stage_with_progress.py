#!/usr/bin/env python3
"""Run one SenseNova PPT stage while publishing WebUI progress.

Generation remains in `run_stage.py`. This wrapper only adds deterministic
progress writes before and after the delegated command.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from progress_event import now_iso, write_event


def _configure_stdio_encoding() -> None:
    """Keep captured stage output stable under non-UTF-8 Windows codepages."""
    for stream in (sys.stdout, sys.stderr):
        if not hasattr(stream, "reconfigure"):
            continue
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


_configure_stdio_encoding()


def _background_process_kwargs() -> dict[str, int]:
    if os.name != "nt":
        return {}
    return {"creationflags": subprocess.CREATE_NO_WINDOW}


def _subprocess_env() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("PYTHONUTF8", "1")
    return env


def _arg_value(argv: list[str], name: str) -> str | None:
    """Read a single `--name value` argument without consuming unknown args."""
    for index, value in enumerate(argv):
        if value == name and index + 1 < len(argv):
            return argv[index + 1]
        if value.startswith(f"{name}="):
            return value.split("=", 1)[1]
    return None


def _int_arg(argv: list[str], name: str) -> int | None:
    """Read an integer CLI argument when present."""
    value = _arg_value(argv, name)
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _parse_last_json(stdout: str) -> Any:
    """Parse the last JSON-looking stdout line from run_stage.py."""
    for line in reversed([row.strip() for row in stdout.splitlines() if row.strip()]):
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            continue
    return None


def _write_stage_progress(argv: list[str], status: str, started_at: str, result: Any = None, error: str | None = None) -> None:
    """Publish one progress event without allowing metadata failures to break generation."""
    deck_arg = _arg_value(argv, "--deck-dir")
    if not deck_arg:
        return

    try:
        write_event(
            Path(deck_arg),
            argv[0] if argv else "unknown",
            status,
            page_no=_int_arg(argv, "--page"),
            start_page=_int_arg(argv, "--start-page"),
            end_page=_int_arg(argv, "--end-page"),
            started_at=started_at,
            result=result,
            error=error,
        )
    except Exception as exc:
        print(f"[workbench-progress] failed to write progress: {exc}", file=sys.stderr)


def main() -> int:
    """Delegate to run_stage.py and publish progress around the call."""
    argv = sys.argv[1:]
    if not argv:
        print("usage: run_stage_with_progress.py <stage> --deck-dir <deck> [...]", file=sys.stderr)
        return 2

    deck_arg = _arg_value(argv, "--deck-dir")
    deck = Path(deck_arg).expanduser().resolve() if deck_arg else None
    started_at = now_iso()
    if deck:
        _write_stage_progress(argv, "running", started_at)

    run_stage = Path(__file__).resolve().with_name("run_stage.py")
    completed = subprocess.run(
        [sys.executable, str(run_stage), *argv],
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        env=_subprocess_env(),
        check=False,
        **_background_process_kwargs(),
    )
    if completed.stdout:
        sys.stdout.write(completed.stdout)
    if completed.stderr:
        sys.stderr.write(completed.stderr)

    if deck:
        status = "ok" if completed.returncode == 0 else "failed"
        error = None if completed.returncode == 0 else (completed.stderr or completed.stdout or "stage failed").strip()[-1200:]
        _write_stage_progress(
            argv,
            status,
            started_at,
            result=_parse_last_json(completed.stdout),
            error=error,
        )

    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
