#!/usr/bin/env python3
"""Stack Overflow 搜索。通过 Stack Exchange API v2.3。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "_search-common"))

from search_utils import build_parser, get_client, get_key, make_item, make_result, print_json


API_URL = "https://api.stackexchange.com/2.3/search/advanced"


def search(query: str, limit: int, sort: str = "relevance", tagged: str | None = None, api_key: str | None = None) -> list[dict]:
    """执行 Stack Overflow 搜索。"""
    params: dict = {
        "q": query,
        "order": "desc",
        "sort": sort,
        "site": "stackoverflow",
        "pagesize": min(limit, 100),
        "filter": "withbody",  # 包含 body 摘要
    }
    if tagged:
        params["tagged"] = tagged
    if api_key:
        params["key"] = api_key

    with get_client() as client:
        resp = client.get(API_URL, params=params)
        resp.raise_for_status()
        data = resp.json()

    items = []
    for item in data.get("items", [])[:limit]:
        body = item.get("body", "")
        snippet = _strip_html(body)

        items.append(make_item(
            title=_unescape(item.get("title", "")),
            url=item.get("link", ""),
            snippet=snippet,
            score=item.get("score", 0),
            answer_count=item.get("answer_count", 0),
            is_answered=item.get("is_answered", False),
            accepted_answer_id=item.get("accepted_answer_id"),
            tags=item.get("tags", []),
            creation_date=item.get("creation_date"),
        ))
    return items


def _strip_html(html: str) -> str:
    """去除 HTML 标签并反转义实体。"""
    import re, html as html_mod
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text).strip()
    return html_mod.unescape(text)


def _unescape(text: str) -> str:
    """反转义 HTML 实体。"""
    import html
    return html.unescape(text)


def main():
    parser = build_parser("搜索 Stack Overflow 问答")
    parser.add_argument("--sort", default="relevance",
                        choices=["relevance", "votes", "creation", "activity"],
                        help="排序方式（默认 relevance）")
    parser.add_argument("--tagged", help="按标签过滤，多个用分号分隔（如 python;asyncio）")
    parser.add_argument("--api-key", help="Stack Exchange API key（可选，提高限额）")
    args = parser.parse_args()

    api_key = get_key("SO_API_KEY", args.api_key)
    try:
        items = search(args.query, args.limit, args.sort, args.tagged, api_key)
        print_json(make_result(True, args.query, "stackoverflow", items))
    except Exception as e:
        print_json(make_result(False, args.query, "stackoverflow", [], str(e)))
        sys.exit(1)


if __name__ == "__main__":
    main()
