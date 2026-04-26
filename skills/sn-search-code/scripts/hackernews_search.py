#!/usr/bin/env python3
"""Hacker News 搜索。通过 Algolia HN Search API。"""
from __future__ import annotations

import sys

from search_utils import build_parser, get_client, make_item, make_result, print_json


API_URL = "https://hn.algolia.com/api/v1"


def search(query: str, limit: int, sort: str = "relevance", tags: str | None = None) -> list[dict]:
    """执行 Hacker News 搜索。

    sort: "relevance" 或 "date"
    tags: Algolia 标签过滤，如 "story", "comment", "ask_hn", "show_hn"
    """
    # search 按相关性，search_by_date 按时间
    endpoint = "search" if sort == "relevance" else "search_by_date"
    url = f"{API_URL}/{endpoint}"

    params: dict = {
        "query": query,
        "hitsPerPage": min(limit, 100),
    }
    if tags:
        params["tags"] = tags

    with get_client() as client:
        resp = client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()

    items = []
    for hit in data.get("hits", [])[:limit]:
        # 构造 HN 链接
        object_id = hit.get("objectID", "")
        hn_url = f"https://news.ycombinator.com/item?id={object_id}"
        # 原始链接（如果有）
        original_url = hit.get("url") or hn_url

        title = hit.get("title") or hit.get("story_title") or ""
        raw_text = hit.get("comment_text") or hit.get("story_text") or ""
        snippet = _strip_html(raw_text)

        # _tags 形如 ["story", "author_xxx", "story_43998472"]，只保留内容类型标签
        raw_tags = hit.get("_tags") or []
        type_tags = [t for t in raw_tags if t in ("story", "comment", "ask_hn", "show_hn", "job", "poll")]

        items.append(make_item(
            title=title,
            url=original_url,
            snippet=snippet,
            hn_url=hn_url,
            points=hit.get("points"),
            num_comments=hit.get("num_comments"),
            author=hit.get("author"),
            created_at=hit.get("created_at"),
            type=type_tags[0] if type_tags else None,
        ))
    return items


def _strip_html(html: str) -> str:
    import re, html as html_mod
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text).strip()
    return html_mod.unescape(text)


def main():
    parser = build_parser("搜索 Hacker News 新闻和讨论")
    parser.add_argument("--sort", default="relevance",
                        choices=["relevance", "date"],
                        help="排序方式（默认 relevance）")
    parser.add_argument("--tags", help="HN 标签过滤（story, comment, ask_hn, show_hn）")
    args = parser.parse_args()

    try:
        items = search(args.query, args.limit, args.sort, args.tags)
        print_json(make_result(True, args.query, "hackernews", items))
    except Exception as e:
        print_json(make_result(False, args.query, "hackernews", [], str(e)))
        sys.exit(1)


if __name__ == "__main__":
    main()
