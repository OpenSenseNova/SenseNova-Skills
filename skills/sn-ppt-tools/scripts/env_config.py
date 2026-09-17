"""Load persistent PPT tool settings without evaluating shell code."""

from __future__ import annotations

import os
import re
import shlex
from dataclasses import asdict, dataclass
from pathlib import Path


_ENV_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass(frozen=True)
class EnvLoadResult:
    path: str
    source: str
    exists: bool
    loaded_keys: tuple[str, ...] = ()
    preserved_process_keys: tuple[str, ...] = ()
    invalid_lines: tuple[int, ...] = ()
    error: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def resolve_env_path() -> tuple[Path, str]:
    explicit = os.environ.get("SN_PPT_ENV_FILE", "").strip()
    if explicit:
        return Path(explicit).expanduser().resolve(), "SN_PPT_ENV_FILE"
    if os.environ.get("OPENCLAW_SHELL", "").strip():
        return (Path.home() / ".openclaw" / ".env").resolve(), "openclaw"
    return (Path.home() / ".hermes" / ".env").resolve(), "hermes"


def _parse_value(raw: str) -> str:
    lexer = shlex.shlex(raw, posix=True)
    lexer.whitespace_split = True
    lexer.commenters = "#"
    return " ".join(lexer)


def load_ppt_env() -> EnvLoadResult:
    path, source = resolve_env_path()
    if not path.is_file():
        return EnvLoadResult(path=str(path), source=source, exists=False)

    loaded: list[str] = []
    preserved: list[str] = []
    invalid: list[int] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        return EnvLoadResult(
            path=str(path),
            source=source,
            exists=True,
            error=f"{type(exc).__name__}: {exc}",
        )

    for line_number, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        name, separator, raw_value = line.partition("=")
        name = name.strip()
        if not separator or not _ENV_NAME.fullmatch(name):
            invalid.append(line_number)
            continue
        try:
            value = _parse_value(raw_value.strip())
        except ValueError:
            invalid.append(line_number)
            continue
        if name in os.environ:
            preserved.append(name)
            continue
        os.environ[name] = value
        loaded.append(name)

    return EnvLoadResult(
        path=str(path),
        source=source,
        exists=True,
        loaded_keys=tuple(sorted(loaded)),
        preserved_process_keys=tuple(sorted(preserved)),
        invalid_lines=tuple(invalid),
    )
