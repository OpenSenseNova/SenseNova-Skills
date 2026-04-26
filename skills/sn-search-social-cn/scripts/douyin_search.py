#!/usr/bin/env python3
"""抖音搜索。通过抖音 Web API（需要 cookie 认证，稳定性较低）。"""
from __future__ import annotations

import sys

from search_utils import build_parser, get_client, get_key, make_item, make_result, print_json


SEARCH_URL = "https://www.douyin.com/aweme/v1/web/general/search/single/"


def search(query: str, limit: int, cookie: str | None = None) -> list[dict]:
    """执行抖音搜索。

    注意：抖音反爬较严格，此脚本稳定性较低，可能需要频繁更新 cookie。
    """
    if not cookie:
        raise ValueError("需要 DOUYIN_COOKIE 环境变量。请从浏览器开发者工具获取抖音 cookie。")

    headers = {
        "Cookie": cookie,
        "Referer": "https://www.douyin.com/search/" + query,
        "Origin": "https://www.douyin.com",
    }

    params = {
        "keyword": query,
        "search_channel": "aweme_general",
        "sort_type": 0,  # 0=综合, 1=最多点赞, 2=最新发布
        "publish_time": 0,  # 0=不限, 1=一天内, 7=一周内, 182=半年内
        "count": min(limit, 20),
        "offset": 0,
        "need_filter_settings": 0,
        "device_platform": "webapp",
        "aid": 6383,
    }

    with get_client(timeout=20, headers=headers) as client:
        resp = client.get(SEARCH_URL, params=params)
        resp.raise_for_status()
        data = resp.json()

    status_code = data.get("status_code", -1)
    if status_code != 0:
        msg = data.get("status_msg") or f"status_code={status_code}"
        raise RuntimeError(f"抖音 API 错误: {msg}")

    items = []
    for entry in data.get("data", [])[:limit]:
        aweme = entry.get("aweme_info", entry)
        if not aweme:
            continue

        desc = aweme.get("desc", "")
        aweme_id = aweme.get("aweme_id", "")
        author = aweme.get("author", {}) or {}
        stats = aweme.get("statistics", {}) or {}

        items.append(make_item(
            title=desc[:100],
            url=f"https://www.douyin.com/video/{aweme_id}" if aweme_id else "",
            snippet=desc[:300],
            author=author.get("nickname", ""),
            digg_count=stats.get("digg_count", 0),
            comment_count=stats.get("comment_count", 0),
            share_count=stats.get("share_count", 0),
            play_count=stats.get("play_count", 0),
            create_time=aweme.get("create_time"),
        ))

    return items


def main():
    parser = build_parser("搜索抖音视频")
    parser.add_argument("--cookie", help="抖音 Cookie（也可通过 DOUYIN_COOKIE 环境变量设置）")
    args = parser.parse_args()

    cookie = get_key("DOUYIN_COOKIE", args.cookie)
    try:
        items = search(args.query, args.limit, cookie)
        print_json(make_result(True, args.query, "douyin", items))
    except Exception as e:
        print_json(make_result(False, args.query, "douyin", [], str(e)))
        sys.exit(1)


if __name__ == "__main__":
    main()
