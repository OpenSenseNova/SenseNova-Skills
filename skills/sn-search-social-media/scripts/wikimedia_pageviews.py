#!/usr/bin/env python3
"""Query Wikimedia Pageviews API for public-attention trend signals."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parent))

from search_utils import make_item, make_result, print_json
from _filters import CryptoQueryError, filter_crypto_items, reject_crypto_query


API_BASE = "https://wikimedia.org/api/rest_v1/metrics/pageviews"
USER_AGENT = os.environ.get(
    "WIKIMEDIA_USER_AGENT",
    "sensenova-sn-search-social-media/0.1 (https://github.com/SenseTime-FVG/sensenova)",
)
SKIP_TOP_PREFIXES = ("Main_Page", "Special:", "Wikipedia:", "File:", "Help:", "Portal:", "Category:", "Template:")


def _compact_date(value: str) -> str:
    if len(value) == 8 and value.isdigit():
        return f"{value}00"
    if len(value) == 10:
        parsed = dt.date.fromisoformat(value)
        return parsed.strftime("%Y%m%d00")
    return value


def _article_slug(title: str) -> str:
    return quote(title.replace(" ", "_"), safe="")


def _get_json(url: str) -> dict:
    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def article_views(
    article: str,
    start: str,
    end: str,
    project: str = "en.wikipedia.org",
    granularity: str = "daily",
    access: str = "all-access",
    agent: str = "user",
) -> list[dict]:
    reject_crypto_query(article)
    url = (
        f"{API_BASE}/per-article/{project}/{access}/{agent}/"
        f"{_article_slug(article)}/{granularity}/{_compact_date(start)}/{_compact_date(end)}"
    )
    data = _get_json(url)

    items = []
    for row in data.get("items", []):
        timestamp = row.get("timestamp", "")
        title = row.get("article", article).replace("_", " ")
        views = row.get("views", 0)
        items.append(make_item(
            title=f"{title} - {timestamp}",
            url=f"https://{project}/wiki/{quote(row.get('article', article), safe='/_')}",
            snippet=f"{views} pageviews",
            article=row.get("article"),
            timestamp=timestamp,
            views=views,
            project=project,
            granularity=row.get("granularity"),
            access=row.get("access"),
            agent=row.get("agent"),
        ))
    return filter_crypto_items(items, fields=("title", "url"))


def top_pages(
    date_value: str,
    limit: int,
    project: str = "en.wikipedia.org",
    access: str = "all-access",
) -> list[dict]:
    parsed = dt.date.fromisoformat(date_value)
    url = f"{API_BASE}/top/{project}/{access}/{parsed.year}/{parsed.month:02d}/{parsed.day:02d}"
    data = _get_json(url)

    articles = []
    for block in data.get("items", []):
        articles.extend(block.get("articles", []))

    items = []
    for row in articles:
        article = row.get("article", "")
        if article == "Main_Page" or article.startswith(SKIP_TOP_PREFIXES):
            continue
        title = article.replace("_", " ")
        item = make_item(
            title=title,
            url=f"https://{project}/wiki/{quote(article, safe='/_')}",
            snippet=f"{row.get('views', 0)} pageviews; rank {row.get('rank')}",
            article=article,
            views=row.get("views"),
            rank=row.get("rank"),
            project=project,
            date=date_value,
        )
        if not filter_crypto_items([item], fields=("title", "url")):
            continue
        items.append(item)
        if len(items) >= limit:
            break
    return items


def main() -> None:
    parser = argparse.ArgumentParser(description="查询 Wikimedia Pageviews 热度信号（免费、免 API key）")
    sub = parser.add_subparsers(dest="mode", required=True)

    article_parser = sub.add_parser("article", help="查询单个百科页面浏览量")
    article_parser.add_argument("article", help="页面标题，如 Artificial intelligence")
    article_parser.add_argument("--start", required=True, help="开始日期：YYYY-MM-DD 或 YYYYMMDD")
    article_parser.add_argument("--end", required=True, help="结束日期：YYYY-MM-DD 或 YYYYMMDD")
    article_parser.add_argument("--project", default="en.wikipedia.org", help="项目，如 en.wikipedia.org、zh.wikipedia.org")
    article_parser.add_argument("--granularity", default="daily", choices=["daily", "monthly"])
    article_parser.add_argument("--access", default="all-access")
    article_parser.add_argument("--agent", default="user")

    top_parser = sub.add_parser("top", help="查询某天最受关注页面")
    top_parser.add_argument("--date", required=True, help="日期：YYYY-MM-DD")
    top_parser.add_argument("--project", default="en.wikipedia.org", help="项目，如 en.wikipedia.org、zh.wikipedia.org")
    top_parser.add_argument("--access", default="all-access")
    top_parser.add_argument("--limit", "-n", type=int, default=20, help="返回结果数量（默认 20）")

    args = parser.parse_args()
    try:
        if args.mode == "article":
            items = article_views(args.article, args.start, args.end, args.project, args.granularity, args.access, args.agent)
            print_json(make_result(True, args.article, "wikimedia-pageviews", items))
        else:
            items = top_pages(args.date, args.limit, args.project, args.access)
            print_json(make_result(True, args.date, "wikimedia-pageviews", items))
    except CryptoQueryError as exc:
        query = getattr(args, "article", getattr(args, "date", ""))
        print_json(make_result(False, query, "wikimedia-pageviews", [], str(exc)))
        sys.exit(2)
    except Exception as exc:
        query = getattr(args, "article", getattr(args, "date", ""))
        print_json(make_result(False, query, "wikimedia-pageviews", [], str(exc)))
        sys.exit(1)


if __name__ == "__main__":
    main()
