#!/usr/bin/env python3
"""Reddit 搜索。通过 Reddit 公开 JSON API（无需认证）。"""
from __future__ import annotations

import sys

from search_utils import build_parser, get_client, make_item, make_result, print_json


SEARCH_URL = "https://www.reddit.com/search.json"


def search(
    query: str,
    limit: int,
    subreddit: str | None = None,
    sort: str = "relevance",
    time_filter: str = "all",
) -> list[dict]:
    """执行 Reddit 搜索。"""
    if subreddit:
        url = f"https://www.reddit.com/r/{subreddit}/search.json"
        params = {"q": query, "limit": min(limit, 100), "sort": sort, "t": time_filter, "restrict_sr": "on"}
    else:
        url = SEARCH_URL
        params = {"q": query, "limit": min(limit, 100), "sort": sort, "t": time_filter}

    # Reddit 要求有意义的 User-Agent
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; search-skill/1.0; +https://github.com)",
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.9",
    }

    with get_client(headers=headers) as client:
        resp = client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()

    items = []
    for child in data.get("data", {}).get("children", [])[:limit]:
        post = child.get("data", {})
        items.append(make_item(
            title=post.get("title", ""),
            url=f"https://reddit.com{post.get('permalink', '')}",
            snippet=_truncate(post.get("selftext", ""), 300),
            subreddit=post.get("subreddit", ""),
            score=post.get("score", 0),
            num_comments=post.get("num_comments", 0),
            author=post.get("author"),
            created_utc=post.get("created_utc"),
            external_url=post.get("url_overridden_by_dest"),
        ))

    return items


def _truncate(text: str, max_len: int) -> str:
    return text[:max_len] + "..." if len(text) > max_len else text


def main():
    parser = build_parser("搜索 Reddit 帖子和讨论")
    parser.add_argument("--subreddit", "-r", help="限定子版块（如 python, machinelearning）")
    parser.add_argument("--sort", default="relevance",
                        choices=["relevance", "hot", "top", "new", "comments"],
                        help="排序方式（默认 relevance）")
    parser.add_argument("--time", "-t", default="all",
                        choices=["hour", "day", "week", "month", "year", "all"],
                        help="时间范围（默认 all）")
    args = parser.parse_args()

    try:
        items = search(args.query, args.limit, args.subreddit, args.sort, args.time)
        print_json(make_result(True, args.query, "reddit", items))
    except Exception as e:
        print_json(make_result(False, args.query, "reddit", [], str(e)))
        sys.exit(1)


if __name__ == "__main__":
    main()
