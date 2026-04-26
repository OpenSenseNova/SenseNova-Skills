#!/usr/bin/env python3
"""Wikipedia 搜索。通过 MediaWiki API。"""
from __future__ import annotations

import sys

from search_utils import build_parser, get_client, make_item, make_result, print_json


def _api_url(lang: str) -> str:
    return f"https://{lang}.wikipedia.org/w/api.php"


def search(query: str, limit: int, lang: str = "en") -> list[dict]:
    """执行 Wikipedia 搜索。"""
    params = {
        "action": "query",
        "list": "search",
        "srsearch": query,
        "srlimit": min(limit, 50),
        "srprop": "snippet|timestamp|wordcount|size|sectiontitle|sectionsnippet",
        "format": "json",
        "utf8": 1,
    }

    with get_client() as client:
        resp = client.get(_api_url(lang), params=params)
        resp.raise_for_status()
        data = resp.json()

    items = []
    for result in data.get("query", {}).get("search", [])[:limit]:
        title = result.get("title", "")
        # snippet 是 HTML 片段，简单去标签
        snippet = _strip_html(result.get("snippet", ""))
        page_id = result.get("pageid", "")
        url = f"https://{lang}.wikipedia.org/wiki/{title.replace(' ', '_')}"

        section_title = result.get("sectiontitle", "")
        section_snippet = _strip_html(result.get("sectionsnippet", ""))

        items.append(make_item(
            title=title,
            url=url,
            snippet=snippet,
            word_count=result.get("wordcount"),
            size=result.get("size"),
            timestamp=result.get("timestamp"),
            page_id=page_id,
            section_title=section_title if section_title else None,
            section_snippet=section_snippet if section_snippet else None,
        ))

    return items


def _strip_html(html: str) -> str:
    import re
    text = re.sub(r"<[^>]+>", "", html)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def main():
    parser = build_parser("搜索 Wikipedia 百科文章")
    parser.add_argument("--lang", "-l", default="en",
                        help="语言版本（默认 en，可选 zh, ja, de 等）")
    args = parser.parse_args()

    try:
        items = search(args.query, args.limit, args.lang)
        print_json(make_result(True, args.query, "wikipedia", items))
    except Exception as e:
        print_json(make_result(False, args.query, "wikipedia", [], str(e)))
        sys.exit(1)


if __name__ == "__main__":
    main()
