#!/usr/bin/env python3
"""检查 Markdown 或 HTML 文件中的本地图片引用。"""

from __future__ import annotations

import argparse
import html
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse


MD_IMAGE_RE = re.compile(r"!\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
HTML_IMAGE_RE = re.compile(r"<img\b[^>]*\bsrc=[\"']([^\"']+)[\"']", re.IGNORECASE)


def is_remote_or_data(src: str) -> bool:
    parsed = urlparse(src)
    return parsed.scheme in {"http", "https", "data", "mailto"} or src.startswith("//")


def clean_src(src: str) -> str:
    src = html.unescape(src.strip())
    src = src.split("#", 1)[0].split("?", 1)[0]
    return unquote(src)


def refs_for_text(text: str) -> list[str]:
    refs = []
    refs.extend(match.group(1) for match in MD_IMAGE_RE.finditer(text))
    refs.extend(match.group(1) for match in HTML_IMAGE_RE.finditer(text))
    return refs


def main() -> int:
    parser = argparse.ArgumentParser(description="检查 Markdown 或 HTML 文件中的本地图片引用。")
    parser.add_argument("file", help="要检查的 Markdown 或 HTML 文件")
    args = parser.parse_args()

    target = Path(args.file).expanduser().resolve()
    if not target.exists():
        print(f"错误：文件不存在：{target}", file=sys.stderr)
        return 2

    text = target.read_text(encoding="utf-8", errors="replace")
    base_dir = target.parent
    refs = refs_for_text(text)

    local_refs = []
    missing = []
    for raw in refs:
        src = clean_src(raw)
        if not src or is_remote_or_data(src):
            continue
        ref_path = Path(src)
        if not ref_path.is_absolute():
            ref_path = base_dir / ref_path
        exists = ref_path.exists()
        local_refs.append((src, exists, ref_path))
        if not exists:
            missing.append((src, ref_path))

    print(f"文件：{target}")
    print(f"本地图片引用数：{len(local_refs)}")
    print(f"缺失图片数：{len(missing)}")

    for src, exists, ref_path in local_refs:
        status = "正常" if exists else "缺失"
        print(f"{status}: {src} -> {ref_path}")

    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
