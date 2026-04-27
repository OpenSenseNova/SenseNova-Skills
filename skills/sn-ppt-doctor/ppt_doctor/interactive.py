"""Interactive .env filler for sn-ppt-doctor.

Prompts only for missing required env vars; skips ones already set.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

REQUIRED = [
    ("SN_CHAT_API_KEY", "shared text/vision chat API key"),
    ("SN_IMAGE_GEN_API_KEY", "Image generation API key"),
]


@dataclass
class FillResult:
    written: bool
    path: Path | None


def interactive_fill_env(env_path: Path, non_interactive: bool = False) -> FillResult:
    missing: list[tuple[str, str]] = [
        (name, desc) for name, desc in REQUIRED if not os.environ.get(name, "").strip()
    ]
    if not missing:
        return FillResult(written=False, path=None)
    if non_interactive:
        return FillResult(written=False, path=None)

    lines: list[str] = []
    for name, desc in missing:
        value = input(f"{name} ({desc}): ").strip()
        if value:
            lines.append(f"{name}={value}")

    if not lines:
        return FillResult(written=False, path=None)

    env_path.parent.mkdir(parents=True, exist_ok=True)
    existing = env_path.read_text() if env_path.exists() else ""
    with env_path.open("w", encoding="utf-8") as f:
        if existing:
            f.write(existing)
            if not existing.endswith("\n"):
                f.write("\n")
        f.write("\n".join(lines) + "\n")
    return FillResult(written=True, path=env_path)
