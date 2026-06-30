#!/usr/bin/env python3
"""DeepXiv 论文章节阅读器，输出 sn-search-academic 标准 JSON。"""

import argparse
import contextlib
import io
import logging
import os
import sys
from pathlib import Path
from typing import Any

try:
    from deepxiv_sdk import Reader
except ImportError as exc:  # pragma: no cover - exercised by CLI users.
    skill_dir = Path(__file__).resolve().parents[1]
    requirements = skill_dir / "requirements.txt"
    raise SystemExit(
        "缺少依赖 deepxiv-sdk。请安装到当前 Python 环境："
        f"python3 -m pip install -r {requirements}"
    ) from exc


from search_utils import print_json


ABS_BASE = "https://arxiv.org/abs"
HTML_BASE = "https://arxiv.org/html"
PDF_BASE = "https://arxiv.org/pdf"

logging.getLogger("deepxiv_sdk").setLevel(logging.CRITICAL)


def cmd_list_sections(
    arxiv_id: str,
    token: str | None = None,
    timeout: int = 120,
    max_retries: int = 3,
) -> dict[str, Any]:
    """列出 DeepXiv 已解析的论文元数据和章节结构。"""
    clean_id = _clean_arxiv_id(arxiv_id)
    reader = _build_reader(token=token, timeout=timeout, max_retries=max_retries)
    head = reader.head(clean_id)
    sections = _sections(head.get("sections"))

    return {
        "success": True,
        "arxiv_id": clean_id,
        "title": head.get("title"),
        "snippet": head.get("abstract") or "",
        "authors": _authors(head.get("authors")),
        "published": head.get("publish_at") or head.get("published") or head.get("date"),
        "categories": head.get("categories") or None,
        "token_count": head.get("token_count"),
        "abs_url": f"{ABS_BASE}/{clean_id}",
        "html_url": f"{HTML_BASE}/{clean_id}",
        "pdf_url": head.get("pdf_url") or head.get("src_url") or f"{PDF_BASE}/{clean_id}",
        "section_count": len(sections),
        "sections": sections,
        "error": None,
    }


def cmd_read_section(
    arxiv_id: str,
    section_name: str,
    token: str | None = None,
    timeout: int = 120,
    max_retries: int = 3,
) -> dict[str, Any]:
    """读取指定章节正文。"""
    clean_id = _clean_arxiv_id(arxiv_id)
    clean_section = section_name.strip()
    reader = _build_reader(token=token, timeout=timeout, max_retries=max_retries)
    content = reader.section(clean_id, clean_section)

    return {
        "success": True,
        "arxiv_id": clean_id,
        "abs_url": f"{ABS_BASE}/{clean_id}",
        "section": clean_section,
        "content": content,
        "char_count": len(content),
        "error": None,
    }


def cmd_read_raw(
    arxiv_id: str,
    token: str | None = None,
    timeout: int = 120,
    max_retries: int = 3,
) -> dict[str, Any]:
    """读取 DeepXiv 返回的整篇 markdown 正文。"""
    clean_id = _clean_arxiv_id(arxiv_id)
    reader = _build_reader(token=token, timeout=timeout, max_retries=max_retries)
    content = reader.raw(clean_id)

    return {
        "success": True,
        "arxiv_id": clean_id,
        "abs_url": f"{ABS_BASE}/{clean_id}",
        "content": content,
        "char_count": len(content),
        "error": None,
    }


def _build_reader(token: str | None, timeout: int, max_retries: int):
    clean_token = _resolve_token(token)
    return Reader(token=clean_token, timeout=timeout, max_retries=max_retries)


def _resolve_token(token: str | None) -> str:
    clean_token = token or os.environ.get("DEEPXIV_TOKEN")
    if clean_token:
        return clean_token

    try:
        from deepxiv_sdk.cli import auto_register_token
    except Exception as exc:
        raise RuntimeError("缺少 DeepXiv token，且无法加载 SDK 自动注册函数") from exc

    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        new_token, _daily_limit = auto_register_token()

    if not new_token:
        message = stderr.getvalue().strip() or stdout.getvalue().strip()
        raise RuntimeError(f"DeepXiv token 自动注册失败：{message or '未返回 token'}")
    return new_token


def _sections(value: Any) -> list[dict[str, Any]]:
    sections = []
    for section in value or []:
        if isinstance(section, str):
            sections.append({"name": section, "level": 1})
            continue
        if isinstance(section, dict):
            name = section.get("name") or section.get("title")
            if not name:
                continue
            item: dict[str, Any] = {
                "name": name,
                "level": section.get("level", 1),
            }
            token_count = section.get("token_count")
            if token_count is not None:
                item["token_count"] = token_count
            sections.append(item)
    return sections


def _authors(value: Any) -> list[str]:
    names = []
    for author in value or []:
        if isinstance(author, str):
            names.append(author)
            continue
        if isinstance(author, dict):
            name = author.get("name")
            if name:
                names.append(name)
    return names


def _clean_arxiv_id(arxiv_id: str) -> str:
    return arxiv_id.strip().replace("arXiv:", "").replace("arxiv:", "")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="DeepXiv 论文章节阅读器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  python3 scripts/deepxiv_paper.py 2308.15022
  python3 scripts/deepxiv_paper.py 2308.15022 --section introduction
  python3 scripts/deepxiv_paper.py 2308.15022 --raw
""",
    )
    parser.add_argument("arxiv_id", help="arXiv 论文 ID（如 2308.15022 或 2308.15022v4）")
    parser.add_argument("--token", help="DeepXiv token（也可用 DEEPXIV_TOKEN；不传则 SDK 可自动注册匿名 token）")
    parser.add_argument(
        "--section",
        "-s",
        metavar="SECTION_NAME",
        help="要读取的章节名（大小写不敏感，支持部分匹配）。不指定则列出所有章节。",
    )
    parser.add_argument("--raw", action="store_true", help="读取整篇 markdown 正文")
    parser.add_argument("--timeout", type=int, default=120, help="请求超时秒数（默认 120）")
    parser.add_argument("--max-retries", type=int, default=3, help="SDK 最大重试次数（默认 3）")
    args = parser.parse_args()

    try:
        if args.raw:
            result = cmd_read_raw(
                args.arxiv_id,
                token=args.token,
                timeout=args.timeout,
                max_retries=args.max_retries,
            )
        elif args.section:
            result = cmd_read_section(
                args.arxiv_id,
                args.section,
                token=args.token,
                timeout=args.timeout,
                max_retries=args.max_retries,
            )
        else:
            result = cmd_list_sections(
                args.arxiv_id,
                token=args.token,
                timeout=args.timeout,
                max_retries=args.max_retries,
            )
        print_json(result)
    except Exception as exc:
        print_json({
            "success": False,
            "arxiv_id": getattr(args, "arxiv_id", ""),
            "error": str(exc),
        })
        sys.exit(1)


if __name__ == "__main__":
    main()
