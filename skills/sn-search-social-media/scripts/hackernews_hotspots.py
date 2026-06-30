#!/usr/bin/env python3
"""Fetch Hacker News hot lists through the official Firebase API."""

from __future__ import annotations

import argparse
import datetime as dt
import html
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from search_utils import get_client, make_item, make_result, print_json
from _filters import CryptoQueryError, contains_crypto, filter_crypto_items, reject_crypto_query


API_BASE = "https://hacker-news.firebaseio.com/v0"
LISTS = {
    "top": "topstories",
    "new": "newstories",
    "best": "beststories",
    "ask": "askstories",
    "show": "showstories",
    "job": "jobstories",
}


def _strip_html(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", value or "")
    text = re.sub(r"\s+", " ", text).strip()
    return html.unescape(text)


def _matches_query(item: dict, query: str | None) -> bool:
    if not query:
        return True
    haystack = " ".join(str(item.get(field, "")) for field in ("title", "snippet", "url", "author")).lower()
    return all(part.lower() in haystack for part in query.split())


def fetch(kind: str, limit: int, query: str | None = None, scan: int = 80) -> list[dict]:
    if query:
        reject_crypto_query(query)
    list_name = LISTS[kind]
    with get_client(timeout=20) as client:
        ids_resp = client.get(f"{API_BASE}/{list_name}.json")
        ids_resp.raise_for_status()
        ids = ids_resp.json()[:max(scan, limit)]

        items = []
        for item_id in ids:
            item_resp = client.get(f"{API_BASE}/item/{item_id}.json")
            item_resp.raise_for_status()
            row = item_resp.json() or {}
            title = html.unescape(row.get("title", ""))
            text = _strip_html(row.get("text", ""))
            url = row.get("url") or f"https://news.ycombinator.com/item?id={item_id}"
            item = make_item(
                title=title,
                url=url,
                snippet=text,
                hn_url=f"https://news.ycombinator.com/item?id={item_id}",
                id=item_id,
                type=row.get("type"),
                score=row.get("score"),
                comments=row.get("descendants"),
                author=row.get("by"),
                created_at=dt.datetime.fromtimestamp(row.get("time", 0), tz=dt.UTC).isoformat() if row.get("time") else None,
            )
            if contains_crypto(" ".join(str(item.get(field, "")) for field in ("title", "snippet", "url"))):
                continue
            if not _matches_query(item, query):
                continue
            if filter_crypto_items([item]):
                items.append(item)
            if len(items) >= limit:
                break
    return items


def main() -> None:
    parser = argparse.ArgumentParser(description="获取 Hacker News 热门列表（官方 API，免费、免 API key）")
    parser.add_argument("--kind", default="top", choices=list(LISTS.keys()), help="列表类型（默认 top）")
    parser.add_argument("--query", help="可选关键词；官方 API 不支持服务端搜索，此参数在拉取热榜后本地过滤")
    parser.add_argument("--limit", "-n", type=int, default=10, help="返回结果数量（默认 10）")
    parser.add_argument("--scan", type=int, default=80, help="扫描前 N 条热榜记录再过滤（默认 80）")
    args = parser.parse_args()

    try:
        items = fetch(args.kind, args.limit, args.query, args.scan)
        print_json(make_result(True, args.query or args.kind, "hackernews", items))
    except CryptoQueryError as exc:
        print_json(make_result(False, args.query or args.kind, "hackernews", [], str(exc)))
        sys.exit(2)
    except Exception as exc:
        print_json(make_result(False, args.query or args.kind, "hackernews", [], str(exc)))
        sys.exit(1)


if __name__ == "__main__":
    main()
