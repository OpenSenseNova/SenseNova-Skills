#!/usr/bin/env python3
"""Search Stack Exchange questions without app keys."""

from __future__ import annotations

import argparse
import html
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from search_utils import get_client, make_item, make_result, print_json
from _filters import CryptoQueryError, filter_crypto_items, reject_crypto_query


API_URL = "https://api.stackexchange.com/2.3/search/advanced"


def _strip_html(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", value or "")
    text = re.sub(r"\s+", " ", text).strip()
    return html.unescape(text)


def search(
    query: str,
    limit: int,
    site: str = "stackoverflow",
    sort: str = "relevance",
    tagged: str | None = None,
) -> list[dict]:
    reject_crypto_query(query)
    params: dict[str, str | int] = {
        "q": query,
        "order": "desc",
        "sort": sort,
        "site": site,
        "pagesize": min(max(limit * 2, limit), 100),
        "filter": "withbody",
    }
    if tagged:
        reject_crypto_query(tagged)
        params["tagged"] = tagged

    with get_client() as client:
        resp = client.get(API_URL, params=params)
        resp.raise_for_status()
        data = resp.json()

    items = []
    for row in data.get("items", []):
        item = make_item(
            title=html.unescape(row.get("title", "")),
            url=row.get("link", ""),
            snippet=_strip_html(row.get("body", ""))[:300],
            score=row.get("score", 0),
            view_count=row.get("view_count", 0),
            answer_count=row.get("answer_count", 0),
            is_answered=row.get("is_answered", False),
            tags=row.get("tags", []),
            creation_date=row.get("creation_date"),
            last_activity_date=row.get("last_activity_date"),
            site=site,
        )
        if filter_crypto_items([item], fields=("title", "snippet", "url", "tags")):
            items.append(item)
        if len(items) >= limit:
            break
    return items


def main() -> None:
    parser = argparse.ArgumentParser(description="搜索 Stack Exchange 问答（免费、免 API key）")
    parser.add_argument("query", help="搜索关键词；加密货币/区块链/Web3 相关查询会被拒绝")
    parser.add_argument("--limit", "-n", type=int, default=10, help="返回结果数量（默认 10）")
    parser.add_argument("--site", default="stackoverflow", help="站点 api_site_parameter，默认 stackoverflow")
    parser.add_argument("--sort", default="relevance", choices=["relevance", "votes", "creation", "activity"], help="排序方式")
    parser.add_argument("--tagged", help="标签过滤，多个用分号分隔")
    args = parser.parse_args()

    try:
        items = search(args.query, args.limit, args.site, args.sort, args.tagged)
        print_json(make_result(True, args.query, "stackexchange", items))
    except CryptoQueryError as exc:
        print_json(make_result(False, args.query, "stackexchange", [], str(exc)))
        sys.exit(2)
    except Exception as exc:
        print_json(make_result(False, args.query, "stackexchange", [], str(exc)))
        sys.exit(1)


if __name__ == "__main__":
    main()
