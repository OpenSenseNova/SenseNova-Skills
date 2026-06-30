#!/usr/bin/env python3
"""Crossref Works 学术论文搜索，输出 sn-search-academic 标准 JSON。"""

import html
import os
import re
import sys
from typing import Any


from search_utils import build_parser, get_client, make_item, make_result, print_json


API_URL = "https://api.crossref.org/works"
MAX_LIMIT = 100


def search(
    query: str,
    limit: int,
    mailto: str | None = None,
    year_min: int | None = None,
    year_max: int | None = None,
) -> list[dict[str, Any]]:
    """执行 Crossref Works 搜索。"""
    wanted = max(0, min(limit, MAX_LIMIT))
    if wanted == 0:
        return []

    polite_mailto = mailto or os.environ.get("CROSSREF_MAILTO") or os.environ.get("CLAWDBOT_EMAIL")
    params = _build_params(query, wanted, polite_mailto, year_min, year_max)
    headers = _build_headers(polite_mailto)

    with get_client(timeout=30, headers=headers) as client:
        response = client.get(API_URL, params=params)
        response.raise_for_status()
        data = response.json()

    items = data.get("message", {}).get("items", [])
    return [_item_from_work(item) for item in items[:wanted]]


def _build_params(
    query: str,
    limit: int,
    mailto: str | None,
    year_min: int | None,
    year_max: int | None,
) -> dict[str, str]:
    params = {
        "query": query,
        "rows": str(limit),
        "sort": "relevance",
        "order": "desc",
    }

    if mailto:
        params["mailto"] = mailto

    filters = []
    if year_min is not None:
        filters.append(f"from-pub-date:{year_min}-01-01")
    if year_max is not None:
        filters.append(f"until-pub-date:{year_max}-12-31")
    if filters:
        params["filter"] = ",".join(filters)

    return params


def _build_headers(mailto: str | None) -> dict[str, str]:
    if not mailto:
        return {}
    return {"User-Agent": f"sensenova sn-search-academic (mailto:{mailto})"}


def _item_from_work(work: dict[str, Any]) -> dict[str, Any]:
    doi = work.get("DOI")
    publication_date = _publication_date(work)
    pdf_url = _pdf_url(work.get("link"))
    url = work.get("URL") or _doi_url(doi)

    return make_item(
        title=_first_text(work.get("title")),
        url=url or "",
        snippet=_clean_abstract(work.get("abstract")),
        authors=_authors(work.get("author")),
        year=_year_from_date(publication_date),
        publication_date=publication_date,
        venue=_first_text(work.get("container-title")),
        publisher=work.get("publisher"),
        work_type=work.get("type"),
        citation_count=work.get("is-referenced-by-count"),
        doi=doi,
        issn=work.get("ISSN"),
        isbn=work.get("ISBN"),
        subjects=work.get("subject"),
        pdf_url=pdf_url,
    )


def _publication_date(work: dict[str, Any]) -> str | None:
    for key in (
        "published-print",
        "published-online",
        "published",
        "issued",
        "created",
    ):
        value = _date_from_parts(work.get(key))
        if value:
            return value
    return None


def _date_from_parts(value: dict[str, Any] | None) -> str | None:
    if not isinstance(value, dict):
        return None

    date_parts = value.get("date-parts")
    if not date_parts or not isinstance(date_parts, list) or not date_parts[0]:
        return None

    parts = date_parts[0]
    if not isinstance(parts, list) or not parts:
        return None

    try:
        year = int(parts[0])
    except (TypeError, ValueError):
        return None

    if len(parts) >= 3 and parts[1] and parts[2]:
        return f"{year:04d}-{int(parts[1]):02d}-{int(parts[2]):02d}"
    if len(parts) >= 2 and parts[1]:
        return f"{year:04d}-{int(parts[1]):02d}"
    return f"{year:04d}"


def _year_from_date(value: str | None) -> int | None:
    if not value:
        return None
    try:
        return int(value[:4])
    except ValueError:
        return None


def _first_text(value: Any) -> str:
    if isinstance(value, list):
        return " ".join(str(part).strip() for part in value if str(part).strip())
    if value is None:
        return ""
    return str(value).strip()


def _authors(authors: list[dict[str, Any]] | None) -> list[str]:
    names = []
    for author in authors or []:
        name = author.get("name")
        if not name:
            name = " ".join(
                part.strip()
                for part in [author.get("given") or "", author.get("family") or ""]
                if part and part.strip()
            )
        if name:
            names.append(name)
    return names


def _clean_abstract(value: str | None) -> str:
    if not value:
        return ""
    text = html.unescape(value)
    text = re.sub(r"<[^>]+>", " ", text)
    return " ".join(text.split())


def _pdf_url(links: list[dict[str, Any]] | None) -> str | None:
    for link in links or []:
        url = link.get("URL")
        content_type = (link.get("content-type") or "").lower()
        if url and ("pdf" in content_type or url.lower().endswith(".pdf")):
            return url
    return None


def _doi_url(doi: str | None) -> str | None:
    if not doi:
        return None
    return f"https://doi.org/{doi}"


def main() -> None:
    parser = build_parser("搜索 Crossref Works 学术论文")
    parser.add_argument("--mailto", help="Crossref polite pool 邮箱（也可用 CROSSREF_MAILTO/CLAWDBOT_EMAIL）")
    parser.add_argument("--year-min", type=int, help="最早发表年份")
    parser.add_argument("--year-max", type=int, help="最晚发表年份")
    args = parser.parse_args()

    try:
        items = search(
            args.query,
            args.limit,
            mailto=args.mailto,
            year_min=args.year_min,
            year_max=args.year_max,
        )
        print_json(make_result(True, args.query, "crossref", items))
    except Exception as e:
        print_json(make_result(False, args.query, "crossref", [], str(e)))
        sys.exit(1)


if __name__ == "__main__":
    main()
