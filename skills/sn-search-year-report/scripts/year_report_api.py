#!/usr/bin/env python3
"""Search official annual-report APIs that work without API keys."""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request


DEFAULT_UA = os.environ.get(
    "YEAR_REPORT_USER_AGENT",
    "sensenova-sn-search-year-report/1.0 contact@example.com",
)

SEC_UA = os.environ.get("SEC_USER_AGENT", DEFAULT_UA)


def build_url(base: str, params: dict[str, object | None]) -> str:
    clean = {k: v for k, v in params.items() if v not in (None, "", [])}
    if not clean:
        return base
    return f"{base}?{urllib.parse.urlencode(clean, doseq=True)}"


def request(
    url: str,
    *,
    method: str = "GET",
    data: bytes | None = None,
    headers: dict[str, str] | None = None,
    timeout: int = 30,
) -> bytes:
    req_headers = {"User-Agent": DEFAULT_UA, **(headers or {})}
    req = urllib.request.Request(url, data=data, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:1200]
        raise SystemExit(f"HTTP {exc.code} for {url}\n{body}") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise SystemExit(f"Request failed for {url}: {exc}") from exc


def request_json(url: str, **kwargs) -> dict | list:
    body = request(url, **kwargs)
    try:
        return json.loads(body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        snippet = body[:1200].decode("utf-8", errors="replace")
        raise SystemExit(f"Expected JSON from {url}, got:\n{snippet}") from exc


def request_form_json(url: str, form: dict[str, str], headers: dict[str, str] | None = None) -> dict | list:
    data = urllib.parse.urlencode(form).encode("utf-8")
    req_headers = {
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Referer": "https://www.cninfo.com.cn/new/index",
        "Origin": "https://www.cninfo.com.cn",
        **(headers or {}),
    }
    return request_json(url, method="POST", data=data, headers=req_headers)


def emit(source: str, url: str, data: object) -> None:
    print(json.dumps({"source": source, "url": url, "data": data}, ensure_ascii=False, indent=2))


def strip_tags(value: object) -> str:
    text = "" if value is None else str(value)
    text = re.sub(r"<[^>]+>", "", text)
    return html.unescape(text).strip()


def millis_to_date(value: object) -> str | None:
    try:
        return dt.datetime.fromtimestamp(int(value) / 1000, tz=dt.timezone.utc).date().isoformat()
    except Exception:
        return None


def cninfo_year_to_disclosure_range(year: str | None, date_range: str | None) -> str:
    if date_range:
        return date_range
    if year:
        try:
            disclosure_year = int(year) + 1
        except ValueError:
            raise SystemExit("--year must be a four-digit report year, e.g. 2023.")
        return f"{disclosure_year}-01-01~{disclosure_year}-12-31"
    return ""


def cmd_cninfo(args: argparse.Namespace) -> None:
    url = "https://www.cninfo.com.cn/new/hisAnnouncement/query"
    form = {
        "pageNum": str(args.page),
        "pageSize": str(args.page_size),
        "column": args.column,
        "tabName": "fulltext",
        "plate": "",
        "stock": args.stock or "",
        "searchkey": args.query,
        "secid": "",
        "category": args.category,
        "trade": "",
        "seDate": cninfo_year_to_disclosure_range(args.year, args.date_range),
        "sortName": "",
        "sortType": "",
        "isHLtitle": "true",
    }
    data = request_form_json(url, form)
    items = []
    for item in data.get("announcements") or []:
        title = strip_tags(item.get("announcementTitle"))
        pdf_path = item.get("adjunctUrl")
        pdf_url = f"https://static.cninfo.com.cn/{pdf_path}" if pdf_path else None
        items.append(
            {
                "sec_code": item.get("secCode"),
                "sec_name": strip_tags(item.get("secName")),
                "title": title,
                "announcement_date": millis_to_date(item.get("announcementTime")),
                "announcement_id": item.get("announcementId"),
                "pdf_url": pdf_url,
                "adjunct_size_kb": item.get("adjunctSize"),
                "adjunct_type": item.get("adjunctType"),
                "raw_category": item.get("announcementType"),
            }
        )
    emit(
        "CNINFO 巨潮资讯公告接口",
        url,
        {
            "query": args.query,
            "report_year": args.year,
            "announcement_date_range": form["seDate"],
            "total": data.get("totalAnnouncement") or data.get("totalRecordNum"),
            "has_more": data.get("hasMore"),
            "items": items,
        },
    )


def sec_tickers() -> list[dict]:
    url = "https://www.sec.gov/files/company_tickers.json"
    raw = request_json(url, headers={"User-Agent": SEC_UA})
    return list(raw.values()) if isinstance(raw, dict) else []


def find_sec_companies(query: str, limit: int) -> list[dict]:
    q = query.lower()
    matches = []
    for row in sec_tickers():
        ticker = str(row.get("ticker", ""))
        title = str(row.get("title", ""))
        if q == ticker.lower() or q in ticker.lower() or q in title.lower():
            matches.append(
                {
                    "cik": str(row.get("cik_str")).zfill(10),
                    "ticker": ticker,
                    "title": title,
                }
            )
            if len(matches) >= limit:
                break
    return matches


def resolve_cik(cik: str | None, ticker: str | None) -> str:
    if cik:
        digits = "".join(ch for ch in cik if ch.isdigit())
        if not digits:
            raise SystemExit("CIK must contain digits.")
        return digits.zfill(10)
    if not ticker:
        raise SystemExit("Provide --cik or --ticker.")
    matches = [m for m in find_sec_companies(ticker, 10) if m["ticker"].lower() == ticker.lower()]
    if not matches:
        raise SystemExit(f"Could not resolve ticker: {ticker}")
    return matches[0]["cik"]


def cmd_sec_company(args: argparse.Namespace) -> None:
    url = "https://www.sec.gov/files/company_tickers.json"
    emit("SEC EDGAR company_tickers", url, {"query": args.query, "items": find_sec_companies(args.query, args.limit)})


def cmd_sec_filings(args: argparse.Namespace) -> None:
    cik = resolve_cik(args.cik, args.ticker)
    url = f"https://data.sec.gov/submissions/CIK{cik}.json"
    data = request_json(url, headers={"User-Agent": SEC_UA})
    forms = {form.strip().upper() for form in args.forms.split(",") if form.strip()}
    recent = (data.get("filings") or {}).get("recent") or {}
    rows = []
    for i, form in enumerate(recent.get("form") or []):
        if str(form).upper() not in forms:
            continue
        accession = recent.get("accessionNumber", [None])[i]
        primary_doc = recent.get("primaryDocument", [None])[i]
        if accession and primary_doc:
            accession_path = accession.replace("-", "")
            doc_url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession_path}/{primary_doc}"
            filing_url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession_path}/"
        else:
            doc_url = None
            filing_url = None
        rows.append(
            {
                "form": form,
                "filing_date": recent.get("filingDate", [None])[i],
                "report_date": recent.get("reportDate", [None])[i],
                "accession_number": accession,
                "primary_document": primary_doc,
                "document_url": doc_url,
                "filing_directory_url": filing_url,
            }
        )
        if len(rows) >= args.limit:
            break
    emit(
        "SEC EDGAR Submissions API",
        url,
        {
            "cik": cik,
            "entity_name": data.get("name"),
            "tickers": data.get("tickers"),
            "forms": sorted(forms),
            "items": rows,
        },
    )


def cmd_download(args: argparse.Namespace) -> None:
    body = request(args.url, headers={"User-Agent": DEFAULT_UA}, timeout=60)
    with open(args.output, "wb") as f:
        f.write(body)
    emit("Direct public file download", args.url, {"output": args.output, "bytes": len(body)})


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Search free official annual-report sources.")
    sub = parser.add_subparsers(required=True)

    p = sub.add_parser("cninfo", help="Search CNINFO A-share annual reports and disclosure PDFs.")
    p.add_argument("query", help="Company name, stock code, or keyword.")
    p.add_argument("--year", help="Report year, e.g. 2023; CNINFO is searched in the next-year disclosure window.")
    p.add_argument("--date-range", help="Override CNINFO announcement date range, e.g. 2024-01-01~2024-12-31.")
    p.add_argument("--stock", help="Optional CNINFO stock parameter if known.")
    p.add_argument("--category", default="category_ndbg_szsh", help="CNINFO category; default annual reports.")
    p.add_argument("--column", default="szse")
    p.add_argument("--page", type=int, default=1)
    p.add_argument("--page-size", type=int, default=10)
    p.set_defaults(func=cmd_cninfo)

    p = sub.add_parser("sec-company", help="Resolve SEC CIK by ticker or company name.")
    p.add_argument("query")
    p.add_argument("--limit", type=int, default=10)
    p.set_defaults(func=cmd_sec_company)

    p = sub.add_parser("sec-filings", help="Search SEC annual filing documents by CIK or ticker.")
    p.add_argument("--cik")
    p.add_argument("--ticker")
    p.add_argument("--forms", default="10-K,10-K/A,20-F,20-F/A,40-F,40-F/A")
    p.add_argument("--limit", type=int, default=10)
    p.set_defaults(func=cmd_sec_filings)

    p = sub.add_parser("download", help="Download a public annual-report PDF URL returned by a source.")
    p.add_argument("url")
    p.add_argument("--output", required=True)
    p.set_defaults(func=cmd_download)

    return parser


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    try:
        main()
    except BrokenPipeError:
        sys.exit(0)
