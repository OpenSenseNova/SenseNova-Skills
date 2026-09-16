#!/usr/bin/env python3
"""Download one selected image into an explicitly supplied PPT deck directory."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path
from typing import Any
from urllib import error, parse, request

from env_config import load_ppt_env


DEFAULT_TIMEOUT_SECONDS = 30
DEFAULT_MAX_BYTES = 50 * 1024 * 1024
ENV_LOAD = load_ppt_env()


def _emit(status: str, **payload: Any) -> None:
    print(json.dumps({"status": status, "provider": "bundled", **payload}, ensure_ascii=False))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Download an image into a PPT deck.")
    parser.add_argument("url", help="Direct image URL.")
    parser.add_argument("--deck-dir", required=True, help="Absolute existing deck directory.")
    parser.add_argument(
        "--output",
        required=True,
        help="Destination path relative to deck-dir, for example assets/hero.png.",
    )
    parser.add_argument("--referer", default="", help="Optional source-page Referer.")
    return parser


def _destination(deck_dir: str, relative_output: str) -> tuple[Path, Path]:
    deck = Path(deck_dir).expanduser()
    if not deck.is_absolute() or not deck.is_dir():
        raise ValueError("deck-dir must be an absolute existing directory")
    relative = Path(relative_output)
    if relative.is_absolute():
        raise ValueError("output must be relative to deck-dir")
    destination = (deck / relative).resolve()
    try:
        destination.relative_to(deck.resolve())
    except ValueError as exc:
        raise ValueError("output escapes deck-dir") from exc
    if destination == deck.resolve():
        raise ValueError("output must name a file inside deck-dir")
    return deck.resolve(), destination


def _looks_like_image(data: bytes, content_type: str) -> bool:
    head = data[:1024].lstrip()
    binary_image = (
        data.startswith(b"\x89PNG\r\n\x1a\n")
        or data.startswith(b"\xff\xd8\xff")
        or data.startswith((b"GIF87a", b"GIF89a"))
        or (data.startswith(b"RIFF") and data[8:12] == b"WEBP")
    )
    svg_image = content_type.lower().startswith("image/svg") and b"<svg" in head.lower()
    return binary_image or svg_image


def main() -> int:
    args = _parser().parse_args()
    try:
        parsed_url = parse.urlparse(args.url)
        if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
            raise ValueError("url must be an absolute HTTP(S) URL")
        _deck, destination = _destination(args.deck_dir, args.output)
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; SenseNova-PPT/1.0)",
            "Accept": "image/*,*/*;q=0.8",
        }
        if args.referer:
            headers["Referer"] = args.referer
        req = request.Request(args.url, headers=headers)
        timeout = float(
            os.environ.get("SN_PPT_TOOL_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS))
        )
        max_bytes = int(
            os.environ.get("SN_PPT_MAX_IMAGE_BYTES", str(DEFAULT_MAX_BYTES))
        )
        with request.urlopen(req, timeout=timeout) as response:
            content_type = response.headers.get("Content-Type", "")
            data = response.read(max_bytes + 1)
        if len(data) > max_bytes:
            raise ValueError(f"image exceeds {max_bytes} bytes")
        if not data or not _looks_like_image(data, content_type):
            raise ValueError("downloaded content is not a recognizable image")

        destination.parent.mkdir(parents=True, exist_ok=True)
        temp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                dir=destination.parent,
                prefix=f".{destination.name}.",
                suffix=".tmp",
                delete=False,
            ) as temp_file:
                temp_path = Path(temp_file.name)
                temp_file.write(data)
                temp_file.flush()
                os.fsync(temp_file.fileno())
            temp_path.replace(destination)
        finally:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)
        _emit("ok", output=str(destination), bytes=len(data))
        return 0
    except error.HTTPError as exc:
        _emit("failed", reason=f"HTTP {exc.code}")
    except (error.URLError, TimeoutError, ValueError, OSError) as exc:
        _emit("failed", reason=type(exc).__name__, detail=str(exc)[:500])
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
