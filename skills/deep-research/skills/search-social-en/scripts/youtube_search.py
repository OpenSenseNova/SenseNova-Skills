#!/usr/bin/env python3
"""YouTube 视频搜索。通过 YouTube Data API v3。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "_search-common"))

from search_utils import build_parser, get_client, get_key, make_item, make_result, print_json


API_URL = "https://www.googleapis.com/youtube/v3/search"


def search(query: str, limit: int, api_key: str | None = None, order: str = "relevance") -> list[dict]:
    """执行 YouTube 搜索。"""
    if not api_key:
        raise ValueError("需要 YOUTUBE_API_KEY 环境变量。请到 Google Cloud Console 创建 API key。")

    params = {
        "part": "snippet",
        "q": query,
        "type": "video",
        "maxResults": min(limit, 50),
        "order": order,
        "key": api_key,
    }

    with get_client() as client:
        resp = client.get(API_URL, params=params)
        resp.raise_for_status()
        data = resp.json()

    items = []
    for result in data.get("items", [])[:limit]:
        snippet = result.get("snippet", {})
        video_id = result.get("id", {}).get("videoId", "")

        items.append(make_item(
            title=snippet.get("title", ""),
            url=f"https://www.youtube.com/watch?v={video_id}" if video_id else "",
            snippet=snippet.get("description", ""),
            channel=snippet.get("channelTitle"),
            published_at=snippet.get("publishedAt"),
            thumbnail=snippet.get("thumbnails", {}).get("default", {}).get("url"),
        ))

    return items


def main():
    parser = build_parser("搜索 YouTube 视频")
    parser.add_argument("--api-key", help="YouTube API Key（也可通过 YOUTUBE_API_KEY 环境变量设置）")
    parser.add_argument("--order", default="relevance",
                        choices=["relevance", "date", "viewCount", "rating"],
                        help="排序方式（默认 relevance）")
    args = parser.parse_args()

    api_key = get_key("YOUTUBE_API_KEY", args.api_key)
    try:
        items = search(args.query, args.limit, api_key, args.order)
        print_json(make_result(True, args.query, "youtube", items))
    except Exception as e:
        print_json(make_result(False, args.query, "youtube", [], str(e)))
        sys.exit(1)


if __name__ == "__main__":
    main()
