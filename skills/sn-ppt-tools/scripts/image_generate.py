#!/usr/bin/env python3
"""Minimal OpenAI/SenseNova-compatible image-generation fallback for PPT."""

from __future__ import annotations

import argparse
import base64
import binascii
import json
import os
import tempfile
from pathlib import Path
from typing import Any
from urllib import error, parse, request

from env_config import load_ppt_env


DEFAULT_TIMEOUT_SECONDS = 300
DEFAULT_MAX_BYTES = 80 * 1024 * 1024
ENV_LOAD = load_ppt_env()


def _first_env(*names: str) -> str:
    for name in names:
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return ""


def _emit(status: str, **payload: Any) -> None:
    print(json.dumps({"status": status, "provider": "bundled", **payload}, ensure_ascii=False))


def _valid_url(value: str) -> bool:
    parsed = parse.urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _configuration(model_override: str) -> tuple[str, str, str]:
    explicit_url = _first_env("SN_PPT_IMAGE_GEN_URL")
    if explicit_url:
        url = explicit_url
    else:
        base = _first_env("SN_IMAGE_GEN_BASE_URL", "SN_BASE_URL")
        url = f"{base.rstrip('/')}/images/generations" if base else ""
    key = _first_env(
        "SN_PPT_IMAGE_GEN_API_KEY",
        "SN_IMAGE_GEN_API_KEY",
        "SN_API_KEY",
    )
    model = model_override.strip() or _first_env(
        "SN_PPT_IMAGE_GEN_MODEL",
        "SN_IMAGE_GEN_MODEL",
    )
    return url, key, model


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate one image into a PPT deck.")
    prompts = parser.add_mutually_exclusive_group(required=True)
    prompts.add_argument("--prompt", help="Image-generation prompt.")
    prompts.add_argument("--prompt-file", help="UTF-8 file containing the prompt.")
    parser.add_argument("--deck-dir", required=True, help="Absolute existing deck directory.")
    parser.add_argument(
        "--output",
        required=True,
        help="Destination path relative to deck-dir.",
    )
    parser.add_argument("--model", default="", help="Optional non-secret model override.")
    parser.add_argument("--size", default="2752x1536", help="Requested pixel size.")
    parser.add_argument("--negative-prompt", default="", help="Optional negative prompt.")
    return parser


def _destination(deck_dir: str, relative_output: str) -> Path:
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
    return destination


def _read_prompt(args: argparse.Namespace) -> str:
    if args.prompt_file:
        prompt_path = Path(args.prompt_file).expanduser()
        if not prompt_path.is_file():
            raise ValueError("prompt-file does not exist")
        prompt = prompt_path.read_text(encoding="utf-8").strip()
    else:
        prompt = str(args.prompt or "").strip()
    if not prompt:
        raise ValueError("prompt is empty")
    return prompt


def _post(url: str, key: str, payload: dict[str, Any]) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(
        url,
        data=body,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    timeout = float(
        os.environ.get(
            "SN_PPT_IMAGE_GEN_TIMEOUT_SECONDS",
            os.environ.get("SN_PPT_TOOL_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS)),
        )
    )
    with request.urlopen(req, timeout=timeout) as response:
        raw = response.read().decode("utf-8", errors="replace")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("image-generation endpoint returned a non-object response")
    return data


def _download(url: str) -> bytes:
    req = request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; SenseNova-PPT/1.0)",
            "Accept": "image/*,*/*;q=0.8",
        },
    )
    timeout = float(
        os.environ.get(
            "SN_PPT_IMAGE_GEN_TIMEOUT_SECONDS",
            os.environ.get("SN_PPT_TOOL_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS)),
        )
    )
    max_bytes = int(os.environ.get("SN_PPT_MAX_IMAGE_BYTES", str(DEFAULT_MAX_BYTES)))
    with request.urlopen(req, timeout=timeout) as response:
        data = response.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise ValueError(f"generated image exceeds {max_bytes} bytes")
    return data


def _image_bytes(data: dict[str, Any]) -> bytes:
    items = data.get("data")
    if not isinstance(items, list) or not items:
        raise ValueError("image-generation response has no data items")
    item = items[-1]
    if not isinstance(item, dict):
        raise ValueError("image-generation response item is invalid")
    image_url = str(item.get("url") or "").strip()
    if image_url:
        if not _valid_url(image_url):
            raise ValueError("image-generation response URL is invalid")
        return _download(image_url)
    encoded = str(item.get("b64_json") or "").strip()
    if encoded:
        try:
            return base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError("image-generation response contains invalid base64") from exc
    raise ValueError("image-generation response has neither url nor b64_json")


def _looks_like_image(data: bytes) -> bool:
    head = data[:1024].lstrip()
    return bool(
        data.startswith(b"\x89PNG\r\n\x1a\n")
        or data.startswith(b"\xff\xd8\xff")
        or data.startswith((b"GIF87a", b"GIF89a"))
        or (data.startswith(b"RIFF") and data[8:12] == b"WEBP")
        or b"<svg" in head.lower()
    )


def _atomic_write(destination: Path, data: bytes) -> None:
    max_bytes = int(os.environ.get("SN_PPT_MAX_IMAGE_BYTES", str(DEFAULT_MAX_BYTES)))
    if len(data) > max_bytes:
        raise ValueError(f"generated image exceeds {max_bytes} bytes")
    if not data or not _looks_like_image(data):
        raise ValueError("image-generation response is not a recognizable image")
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


def main() -> int:
    args = _parser().parse_args()
    try:
        destination = _destination(args.deck_dir, args.output)
        prompt = _read_prompt(args)
        url, key, model = _configuration(args.model)
        missing = []
        if not _valid_url(url):
            missing.append("url")
        if not key:
            missing.append("api_key")
        if not model:
            missing.append("model")
        if missing:
            _emit("unavailable", reason="missing or invalid configuration", missing=missing)
            return 2

        payload: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "size": args.size,
            # "response_format": "url",
            "output_format": "png",
        }
        if args.negative_prompt:
            payload["negative_prompt"] = args.negative_prompt
        data = _post(url, key, payload)
        image = _image_bytes(data)
        _atomic_write(destination, image)
        _emit("ok", output=str(destination), bytes=len(image), model=model)
        return 0
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        _emit("failed", reason=f"HTTP {exc.code}", detail=detail)
    except (
        error.URLError,
        TimeoutError,
        json.JSONDecodeError,
        ValueError,
        OSError,
    ) as exc:
        _emit("failed", reason=type(exc).__name__, detail=str(exc)[:500])
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
