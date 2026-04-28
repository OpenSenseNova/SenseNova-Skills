#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any
from urllib import error, request


DEFAULT_BASE_URL = "https://google.serper.dev"
DEFAULT_TIMEOUT_SECONDS = 30


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Query Serper.dev for image search results.",
    )
    parser.add_argument("query", help="Search query.")
    parser.add_argument("--num", type=int, default=10, help="Maximum number of results to request.")
    parser.add_argument("--gl", default="", help="Two-letter country code bias, for example 'us'.")
    parser.add_argument("--hl", default="", help="Language code bias, for example 'en'.")
    parser.add_argument("--page", type=int, default=1, help="Result page number.")
    parser.add_argument("--json", action="store_true", help="Print raw JSON instead of formatted text.")
    parser.add_argument(
        "--save-json",
        default="",
        help="Optional file path for writing the raw JSON payload without using shell redirection.",
    )
    parser.add_argument(
        "--image-urls-only",
        action="store_true",
        help="Print only direct image URLs, one per line.",
    )
    parser.add_argument(
        "--page-urls-only",
        action="store_true",
        help="Print only source page URLs, one per line.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Maximum number of printed URLs for URL-only output. 0 means no extra truncation.",
    )
    return parser


def _require_search_enabled() -> str:
    api_key = os.environ.get("SERPER_API_KEY", "").strip()
    if api_key:
        return api_key
    raise SystemExit("Serper image search is unavailable in the current environment.")


def _build_payload(args: argparse.Namespace) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "q": args.query,
        "num": max(1, args.num),
        "page": max(1, args.page),
    }
    if args.gl:
        payload["gl"] = args.gl
    if args.hl:
        payload["hl"] = args.hl
    return payload


def _post_json(url: str, payload: dict[str, Any], api_key: str) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "X-API-KEY": api_key,
        },
        method="POST",
    )
    timeout = int(os.environ.get("SERPER_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS)))
    try:
        with request.urlopen(req, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
    except error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace").strip()
        raise SystemExit(f"Serper request failed with HTTP {exc.code}: {details}") from exc
    except error.URLError as exc:
        raise SystemExit(f"Serper request failed: {exc.reason}") from exc

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SystemExit("Serper returned invalid JSON.") from exc
    if not isinstance(data, dict):
        raise SystemExit("Serper returned an unexpected payload shape.")
    return data


def _image_items(data: dict[str, Any]) -> list[dict[str, Any]]:
    items = data.get("images")
    if not isinstance(items, list):
        items = data.get("results")
    if not isinstance(items, list):
        return []
    return [item for item in items if isinstance(item, dict)]


def _format_images(data: dict[str, Any]) -> str:
    items = _image_items(data)
    if not items:
        return "No image results returned."

    lines = ["Image Results"]
    for index, item in enumerate(items, start=1):
        title = str(item.get("title") or "").strip() or f"Image {index}"
        page_link = str(item.get("link") or item.get("url") or "").strip()
        image_url = str(item.get("imageUrl") or item.get("image_url") or "").strip()
        thumbnail_url = str(item.get("thumbnailUrl") or "").strip()
        source = str(item.get("source") or item.get("domain") or "").strip()
        lines.append(f"{index}. {title}")
        if source:
            lines.append(f"   Source: {source}")
        if page_link:
            lines.append(f"   Page: {page_link}")
        if image_url:
            lines.append(f"   Image: {image_url}")
        if thumbnail_url:
            lines.append(f"   Thumbnail: {thumbnail_url}")
    return "\n".join(lines).strip()


def _print_url_only(data: dict[str, Any], *, field: str, limit: int) -> int:
    count = 0
    for item in _image_items(data):
        value = str(item.get(field) or "").strip()
        if not value and field == "link":
            value = str(item.get("url") or "").strip()
        if not value:
            continue
        sys.stdout.write(value + "\n")
        count += 1
        if limit > 0 and count >= limit:
            break
    return 0


def main() -> int:
    args = _build_parser().parse_args()
    api_key = _require_search_enabled()
    base_url = os.environ.get("SERPER_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
    payload = _build_payload(args)
    data = _post_json(f"{base_url}/images", payload, api_key)
    if args.save_json:
        output_path = Path(args.save_json).expanduser()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.json:
        json.dump(data, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
        return 0
    if args.image_urls_only:
        return _print_url_only(data, field="imageUrl", limit=max(0, args.limit))
    if args.page_urls_only:
        return _print_url_only(data, field="link", limit=max(0, args.limit))

    sys.stdout.write(_format_images(data) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
