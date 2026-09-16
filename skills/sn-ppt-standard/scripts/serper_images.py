#!/usr/bin/env python3
"""Search Serper Images or localize one result with provenance."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

import requests
from PIL import Image

SEARCH_ENDPOINT = "https://google.serper.dev/images"
MAX_DOWNLOAD_BYTES = 24 * 1024 * 1024


def _search(query: str, limit: int) -> int:
    key = os.environ.get("SERPER_API_KEY", "").strip()
    if not key:
        raise SystemExit("SERPER_API_KEY is not configured")
    response = requests.post(
        SEARCH_ENDPOINT,
        headers={"X-API-KEY": key, "Content-Type": "application/json"},
        json={"q": query, "num": min(max(limit, 1), 10)},
        timeout=30,
    )
    response.raise_for_status()
    rows = []
    for item in response.json().get("images", [])[:limit]:
        url = item.get("imageUrl") or item.get("link")
        if not isinstance(url, str) or not url.startswith(("http://", "https://")):
            continue
        rows.append(
            {
                "url": url,
                "title": str(item.get("title") or ""),
                "source": str(item.get("source") or ""),
                "source_page": str(item.get("link") or ""),
            }
        )
    print(json.dumps({"query": query, "results": rows}, ensure_ascii=False, indent=2))
    return 0


def _fetch(url: str, root: Path) -> int:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise SystemExit("fetch requires an absolute HTTP(S) image URL")
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 Chrome/124.0 Safari/537.36"
        ),
        "Referer": f"{parsed.scheme}://{parsed.netloc}/",
        "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
    }
    response = requests.get(url, headers=headers, timeout=30, stream=True)
    response.raise_for_status()
    chunks = []
    total = 0
    for chunk in response.iter_content(64 * 1024):
        if not chunk:
            continue
        total += len(chunk)
        if total > MAX_DOWNLOAD_BYTES:
            raise SystemExit("image exceeds the 24 MiB download limit")
        chunks.append(chunk)
    data = b"".join(chunks)
    try:
        with Image.open(io.BytesIO(data)) as image:
            image.verify()
            image_format = (image.format or "JPEG").lower()
    except Exception as exc:
        raise SystemExit(f"downloaded content is not a valid image: {type(exc).__name__}") from exc
    extension = {"jpeg": ".jpg", "png": ".png", "webp": ".webp", "gif": ".gif"}.get(
        image_format, ".jpg"
    )
    relative = Path("assets") / f"web_{hashlib.sha1(url.encode('utf-8')).hexdigest()[:12]}{extension}"
    target = (root / relative).resolve()
    assets_root = (root / "assets").resolve()
    if target.parent != assets_root:
        raise SystemExit("resolved asset path escaped the assets directory")
    assets_root.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)

    deck = Path(__file__).with_name("deck.py")
    subprocess.run(
        [
            sys.executable,
            str(deck),
            "asset-register",
            str(root),
            "--path",
            relative.as_posix(),
            "--origin",
            "downloaded",
            "--source-url",
            url,
        ],
        check=True,
    )
    print(relative.as_posix())
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    search = commands.add_parser("search")
    search.add_argument("--query", required=True)
    search.add_argument("--limit", type=int, default=6, choices=range(1, 11), metavar="1..10")
    fetch = commands.add_parser("fetch")
    fetch.add_argument("--url", required=True)
    fetch.add_argument("--root", type=Path, default=Path("."))
    args = parser.parse_args()
    if args.command == "search":
        return _search(args.query, args.limit)
    return _fetch(args.url, args.root.resolve())


if __name__ == "__main__":
    raise SystemExit(main())
