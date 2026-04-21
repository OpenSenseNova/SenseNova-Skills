#!/usr/bin/env python3
"""B站搜索。通过 Bilibili Web API（无需认证即可搜索）。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "_search-common"))

from search_utils import build_parser, get_client, get_key, make_item, make_result, print_json


SEARCH_URL = "https://api.bilibili.com/x/web-interface/search/all/v2"


def search(query: str, limit: int, cookie: str | None = None, order: str = "") -> list[dict]:
    """执行 B站搜索。"""
    headers = {
        "Referer": "https://www.bilibili.com",
        "Origin": "https://www.bilibili.com",
    }
    if cookie:
        headers["Cookie"] = cookie

    params = {
        "keyword": query,
        "page": 1,
        "page_size": min(limit, 50),
    }
    if order:
        params["order"] = order

    with get_client(headers=headers) as client:
        resp = client.get(SEARCH_URL, params=params)
        resp.raise_for_status()
        data = resp.json()

    if data.get("code") != 0:
        msg = data.get("message", "未知错误")
        raise RuntimeError(f"B站 API 返回错误: {msg}")

    items = []
    # 结果在 data.data.result 中，按类型分组
    result_groups = data.get("data", {}).get("result", [])
    for group in result_groups:
        result_type = group.get("result_type", "")
        if result_type not in ("video", "media_bangumi", "media_ft", "article"):
            continue
        for entry in group.get("data", []):
            title = _strip_html(entry.get("title", ""))
            if result_type == "video":
                bvid = entry.get("bvid", "")
                url = f"https://www.bilibili.com/video/{bvid}" if bvid else entry.get("arcurl", "")
                items.append(make_item(
                    title=title,
                    url=url,
                    snippet=entry.get("description", "")[:300],
                    author=entry.get("author", ""),
                    play=entry.get("play", 0),
                    like=entry.get("like", 0),
                    pubdate=entry.get("pubdate"),
                    type="video",
                ))
            elif result_type == "article":
                url = f"https://www.bilibili.com/read/cv{entry.get('id', '')}"
                items.append(make_item(
                    title=title,
                    url=url,
                    snippet=entry.get("desc", "")[:300],
                    author=entry.get("author_name", ""),
                    view=entry.get("view", 0),
                    type="article",
                ))

            if len(items) >= limit:
                break
        if len(items) >= limit:
            break

    return items[:limit]


def _strip_html(html: str) -> str:
    import re
    return re.sub(r"<[^>]+>", "", html).strip()


def main():
    parser = build_parser("搜索 B站视频和文章")
    parser.add_argument("--cookie", help="B站 Cookie（也可通过 BILIBILI_COOKIE 环境变量设置，可选）")
    parser.add_argument("--order", default="",
                        choices=["", "totalrank", "click", "pubdate", "dm", "stow"],
                        help="排序：空=综合, totalrank=最佳匹配, click=播放, pubdate=最新, dm=弹幕, stow=收藏")
    args = parser.parse_args()

    cookie = get_key("BILIBILI_COOKIE", args.cookie)
    try:
        items = search(args.query, args.limit, cookie, args.order)
        print_json(make_result(True, args.query, "bilibili", items))
    except Exception as e:
        print_json(make_result(False, args.query, "bilibili", [], str(e)))
        sys.exit(1)


if __name__ == "__main__":
    main()
