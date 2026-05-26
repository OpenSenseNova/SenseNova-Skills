#!/usr/bin/env python3
"""Google Scholar 搜索结果抓取，输出 sn-search-academic 标准 JSON。

Google Scholar 对自动化访问限制严格。本脚本只发送普通低频搜索请求，
遇到验证码或异常流量页面会直接失败，不尝试绕过访问控制。
"""

import re
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

try:
    from bs4 import BeautifulSoup
except ImportError:  # pragma: no cover - exercised by CLI users without project deps.
    BeautifulSoup = None


from search_utils import build_parser, get_client, make_item, make_result, print_json


BASE_URL = "https://scholar.google.com"
SEARCH_URL = f"{BASE_URL}/scholar"
PAGE_SIZE = 10
DEFAULT_SLEEP_SECONDS = 2.0
MAX_LIMIT = 50


def _dependency_hint(package: str) -> str:
    skill_dir = Path(__file__).resolve().parents[1]
    requirements = skill_dir / "requirements.txt"
    return (
        f"缺少依赖 {package}。请安装到当前 Python 环境："
        f"python3 -m pip install -r {requirements}"
    )


class GoogleScholarBlockedError(RuntimeError):
    """Raised when Google Scholar returns a captcha or automated traffic page."""


def parse_results(html: str) -> list[dict[str, Any]]:
    """Parse Google Scholar result HTML into standard search items."""
    if BeautifulSoup is None:
        raise RuntimeError(_dependency_hint("beautifulsoup4"))

    _raise_if_blocked(html)
    soup = BeautifulSoup(html, "html.parser")

    items: list[dict[str, Any]] = []
    for result in soup.select(".gs_r.gs_or.gs_scl"):
        title_node = result.select_one("h3.gs_rt")
        if not title_node:
            continue

        link = title_node.find("a", href=True)
        title = _clean_title(link.get_text(" ", strip=True) if link else title_node.get_text(" ", strip=True))
        url = link["href"] if link else ""

        meta_text = _text(result.select_one(".gs_a"))
        snippet = _text(result.select_one(".gs_rs"))
        authors, venue, year = _parse_meta(meta_text)
        scholar_id = result.get("data-cid") or None

        links = _parse_footer_links(result)
        pdf_url = _extract_pdf_url(result)

        items.append(
            make_item(
                title=title,
                url=url,
                snippet=snippet,
                authors=authors or None,
                year=year,
                venue=venue,
                pdf_url=pdf_url,
                scholar_id=scholar_id,
                **links,
            )
        )

    return items


def search(
    query: str,
    limit: int,
    lang: str = "en",
    year_min: int | None = None,
    year_max: int | None = None,
    include_citations: bool = False,
    sleep_seconds: float = DEFAULT_SLEEP_SECONDS,
) -> list[dict[str, Any]]:
    """Fetch Google Scholar search pages until limit items are collected."""
    wanted = max(0, min(limit, MAX_LIMIT))
    if wanted == 0:
        return []

    items: list[dict[str, Any]] = []
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": _accept_language(lang),
    }

    with get_client(timeout=30, headers=headers) as client:
        start = 0
        while len(items) < wanted:
            params = _build_params(
                query=query,
                start=start,
                lang=lang,
                year_min=year_min,
                year_max=year_max,
                include_citations=include_citations,
            )
            response = client.get(SEARCH_URL, params=params)
            if getattr(response, "status_code", None) in {429, 503}:
                raise GoogleScholarBlockedError("Google Scholar 返回限流/验证码页面，请稍后降低频率重试。")
            response.raise_for_status()

            page_items = parse_results(response.text)
            if not page_items:
                break

            items.extend(page_items)
            if len(items) >= wanted:
                break
            if sleep_seconds > 0:
                time.sleep(sleep_seconds)
            start += PAGE_SIZE

    return items[:wanted]


def _build_params(
    query: str,
    start: int,
    lang: str,
    year_min: int | None,
    year_max: int | None,
    include_citations: bool,
) -> dict[str, str]:
    params = {
        "q": query,
        "hl": lang,
        "start": str(start),
        "num": str(PAGE_SIZE),
        "as_sdt": "0,5",
        "as_vis": "0" if include_citations else "1",
    }
    if year_min is not None:
        params["as_ylo"] = str(year_min)
    if year_max is not None:
        params["as_yhi"] = str(year_max)
    return params


def _raise_if_blocked(html: str) -> None:
    lower = html.lower()
    blocked_markers = (
        'id="gs_captcha_f"',
        "our systems have detected unusual traffic",
        "not a robot",
        "captcha",
    )
    if any(marker in lower for marker in blocked_markers):
        raise GoogleScholarBlockedError("Google Scholar 返回验证码或异常流量页面，脚本不会绕过该限制。")


def _parse_footer_links(result) -> dict[str, Any]:
    links: dict[str, Any] = {}
    for anchor in result.select(".gs_fl a[href]"):
        text = anchor.get_text(" ", strip=True)
        href = urljoin(BASE_URL, anchor["href"])
        citation_match = re.search(r"Cited by\s+([\d,]+)", text, flags=re.I)
        if citation_match:
            links["citation_count"] = int(citation_match.group(1).replace(",", ""))
            links["cited_by_url"] = href
        elif "related" in text.lower():
            links["related_url"] = href
        elif "version" in text.lower():
            links["versions_url"] = href
    return links


def _extract_pdf_url(result) -> str | None:
    pdf_link = result.select_one(".gs_or_ggsm a[href]")
    if not pdf_link:
        return None
    href = pdf_link["href"]
    label = pdf_link.get_text(" ", strip=True).lower()
    if "pdf" in label or href.lower().endswith(".pdf"):
        return href
    return None


def _parse_meta(meta_text: str) -> tuple[list[str], str | None, int | None]:
    if not meta_text:
        return [], None, None

    parts = [part.strip() for part in meta_text.split(" - ") if part.strip()]
    authors = _parse_authors(parts[0]) if parts else []
    year = _extract_year(meta_text)
    venue = None

    if len(parts) >= 2:
        venue = parts[1]
        if year:
            venue = re.sub(rf"\b{year}\b", "", venue)
        venue = venue.strip(" ,;-") or None

    return authors, venue, year


def _parse_authors(value: str) -> list[str]:
    if not value:
        return []
    return [author.strip() for author in value.split(",") if author.strip() and author.strip() != "..."]


def _extract_year(value: str) -> int | None:
    matches = re.findall(r"\b(18\d{2}|19\d{2}|20\d{2})\b", value)
    return int(matches[-1]) if matches else None


def _clean_title(value: str) -> str:
    return re.sub(r"^\[(?:HTML|PDF|CITATION|BOOK)\]\s*", "", value, flags=re.I).strip()


def _text(node) -> str:
    return " ".join(node.get_text(" ", strip=True).split()) if node else ""


def _accept_language(lang: str) -> str:
    if lang.startswith("zh"):
        return "zh-CN,zh;q=0.9,en;q=0.7"
    return f"{lang};q=0.9,en;q=0.8"


def main() -> None:
    parser = build_parser("搜索 Google Scholar 学术论文")
    parser.add_argument("--lang", "-l", default="en", help="界面语言/结果语言提示（默认 en）")
    parser.add_argument("--year-min", type=int, help="最早年份过滤")
    parser.add_argument("--year-max", type=int, help="最晚年份过滤")
    parser.add_argument(
        "--include-citations",
        action="store_true",
        help="包含引用条目（默认隐藏引用条目）",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=DEFAULT_SLEEP_SECONDS,
        help="翻页请求间隔秒数（默认 2.0）",
    )
    parser.epilog = "请低频使用；遇到验证码/异常流量页面时脚本会直接失败，不会绕过访问控制。"

    args = parser.parse_args()

    try:
        items = search(
            args.query,
            args.limit,
            lang=args.lang,
            year_min=args.year_min,
            year_max=args.year_max,
            include_citations=args.include_citations,
            sleep_seconds=args.sleep,
        )
        print_json(make_result(True, args.query, "google_scholar", items))
    except Exception as exc:
        print_json(make_result(False, args.query, "google_scholar", [], str(exc)))
        sys.exit(1)


if __name__ == "__main__":
    main()
