from __future__ import annotations

from pathlib import Path


def ensure_output_path(path: Path) -> Path:
    """Ensure the parent directory of the given path exists.

    Args:
        path (Path):
            The file path whose parent directory should be created.

    Returns:
        Path:
            The original path unchanged.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    return path
