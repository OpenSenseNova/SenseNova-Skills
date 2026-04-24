#!/usr/bin/env python3
"""Twitter/X 搜索。通过 TikHub API。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "_search-common"))

from search_utils import build_parser, get_client, get_key, make_item, make_result, print_json


TIKHUB_BASE = "https://api.tikhub.io"
SEARCH_ENDPOINT = "/api/v1/twitter/web/fetch_search_timeline"


def search(query: str, limit: int, token: str | None = None) -> list[dict]:
    """执行 Twitter 搜索。"""
    if not token:
        raise ValueError("需要 TIKHUB_TOKEN 环境变量。请到 tikhub.io 注册获取。")

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }

    params = {
        "keyword": query,
        "search_type": "Latest",
    }

    with get_client(timeout=30, headers=headers) as client:
        resp = client.get(f"{TIKHUB_BASE}{SEARCH_ENDPOINT}", params=params)
        resp.raise_for_status()
        data = resp.json()

    # 解析 TikHub 返回结构
    items = []
    results = data.get("data", {}).get("data", [])
    if isinstance(results, dict):
        results = results.get("data", [])

    for tweet in results[:limit]:
        content = tweet.get("content", {}) if isinstance(tweet, dict) else {}
        if not content:
            content = tweet

        text = content.get("full_text") or content.get("text") or ""
        user = content.get("user", {}) or {}
        screen_name = user.get("screen_name", "")
        tweet_id = content.get("id_str") or content.get("rest_id") or ""
        url = f"https://x.com/{screen_name}/status/{tweet_id}" if screen_name and tweet_id else ""

        items.append(make_item(
            title=f"@{screen_name}" if screen_name else "",
            url=url,
            snippet=text[:500],
            author=user.get("name"),
            screen_name=screen_name,
            favorite_count=content.get("favorite_count"),
            retweet_count=content.get("retweet_count"),
            created_at=content.get("created_at"),
        ))

    return items


def main():
    parser = build_parser("搜索 Twitter/X 推文")
    parser.add_argument("--token", help="TikHub Token（也可通过 TIKHUB_TOKEN 环境变量设置）")
    args = parser.parse_args()

    token = get_key("TIKHUB_TOKEN", args.token)
    try:
        items = search(args.query, args.limit, token)
        print_json(make_result(True, args.query, "twitter", items))
    except Exception as e:
        print_json(make_result(False, args.query, "twitter", [], str(e)))
        sys.exit(1)


if __name__ == "__main__":
    main()
