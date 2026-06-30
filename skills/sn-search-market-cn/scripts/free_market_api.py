#!/usr/bin/env python3
"""China official free/no-key market research API helper."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


CNINFO_QUERY_URL = "https://www.cninfo.com.cn/new/hisAnnouncement/query"
CNINFO_STATIC_BASE = "https://static.cninfo.com.cn/"
USER_AGENT = "Mozilla/5.0 sensenova-sn-search-market-cn/1.0"


def request_form_json(url: str, form: dict[str, str | int | None], *, timeout: int = 30) -> dict[str, Any]:
    clean = {k: str(v) for k, v in form.items() if v not in (None, "")}
    data = urllib.parse.urlencode(clean).encode("utf-8")
    headers = {
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Origin": "https://www.cninfo.com.cn",
        "Referer": "https://www.cninfo.com.cn/new/commonUrl?url=disclosure/list/notice",
        "User-Agent": USER_AGENT,
        "X-Requested-With": "XMLHttpRequest",
    }
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read()
    except urllib.error.HTTPError as exc:
        snippet = exc.read().decode("utf-8", errors="replace")[:800]
        raise SystemExit(f"HTTP {exc.code} for {url}\n{snippet}") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise SystemExit(f"Request failed for {url}: {exc}") from exc

    try:
        return json.loads(body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        snippet = body[:800].decode("utf-8", errors="replace")
        raise SystemExit(f"Expected JSON from {url}, got:\n{snippet}") from exc


def normalize_date(value: str | None, fallback: str) -> str:
    if not value:
        return fallback
    try:
        dt.date.fromisoformat(value)
    except ValueError as exc:
        raise SystemExit(f"Date must be YYYY-MM-DD, got: {value}") from exc
    return value


def strip_html(value: str | None) -> str | None:
    if value is None:
        return None
    return value.replace("<em>", "").replace("</em>", "")


def with_pdf_url(item: dict[str, Any]) -> dict[str, Any]:
    out = dict(item)
    out["announcementTitle"] = strip_html(out.get("announcementTitle"))
    adjunct_url = out.get("adjunctUrl")
    if adjunct_url:
        out["pdfUrl"] = urllib.parse.urljoin(CNINFO_STATIC_BASE, adjunct_url)
    return out


def emit(source: str, url: str, data: Any) -> None:
    print(json.dumps({"source": source, "url": url, "data": data}, ensure_ascii=False, indent=2))


def cmd_cninfo_announcements(args: argparse.Namespace) -> None:
    today = dt.date.today()
    start = normalize_date(args.start_date, (today - dt.timedelta(days=90)).isoformat())
    end = normalize_date(args.end_date, today.isoformat())
    if start > end:
        raise SystemExit("--start-date must be earlier than or equal to --end-date")

    form = {
        "pageNum": args.page_num,
        "pageSize": args.page_size,
        "column": args.column,
        "tabName": "fulltext",
        "plate": args.plate,
        "stock": args.stock,
        "searchkey": args.keyword,
        "secid": args.secid,
        "category": args.category,
        "trade": args.trade,
        "seDate": f"{start}~{end}",
        "sortName": args.sort_name,
        "sortType": args.sort_type,
        "isHLtitle": "true" if args.highlight else "false",
    }
    data = request_form_json(CNINFO_QUERY_URL, form, timeout=args.timeout)
    if isinstance(data.get("announcements"), list):
        data["announcements"] = [with_pdf_url(item) for item in data["announcements"]]
    emit("巨潮资讯公告查询接口", CNINFO_QUERY_URL, data)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Query China official free/no-key APIs for market and business research."
    )
    sub = parser.add_subparsers(required=True)

    p = sub.add_parser("cninfo-announcements", help="Search CNINFO A-share announcements.")
    p.add_argument("--keyword", default="", help="Title/full-text keyword, e.g. 年报 or 业绩说明会.")
    p.add_argument("--start-date", help="Start date, YYYY-MM-DD. Default: 90 days ago.")
    p.add_argument("--end-date", help="End date, YYYY-MM-DD. Default: today.")
    p.add_argument("--page-num", type=int, default=1)
    p.add_argument("--page-size", type=int, default=10)
    p.add_argument("--column", default="szse", help="CNINFO column code. Default covers common disclosure search.")
    p.add_argument("--plate", default="", help="Optional CNINFO plate filter.")
    p.add_argument("--stock", default="", help="Optional CNINFO stock filter, if known.")
    p.add_argument("--secid", default="", help="Optional CNINFO security id filter.")
    p.add_argument("--category", default="", help="Optional CNINFO announcement category code.")
    p.add_argument("--trade", default="", help="Optional CNINFO industry filter.")
    p.add_argument("--sort-name", default="")
    p.add_argument("--sort-type", default="")
    p.add_argument("--timeout", type=int, default=30)
    p.add_argument("--highlight", action=argparse.BooleanOptionalAction, default=True)
    p.set_defaults(func=cmd_cninfo_announcements)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    try:
        main()
    except BrokenPipeError:
        sys.exit(0)
