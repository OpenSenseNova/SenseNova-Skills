#!/usr/bin/env python3
"""Semantic Scholar 论文搜索。优先使用 semanticscholar SDK，失败时回退 Graph API HTTP。"""

import sys
import time
from datetime import date, datetime
from pathlib import Path


from search_utils import build_parser, get_client, make_item, make_result, print_json

try:
    from semanticscholar import SemanticScholar
except ImportError:  # SDK 是优先路径；缺失时仍可使用 HTTP fallback。
    SemanticScholar = None

API_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
MAX_429_ATTEMPTS = 4
BASE_429_DELAY_SECONDS = 1.0


def _dependency_hint(package: str) -> str:
    skill_dir = Path(__file__).resolve().parents[1]
    requirements = skill_dir / "requirements.txt"
    return (
        f"缺少依赖 {package}。请安装到当前 Python 环境："
        f"python3 -m pip install -r {requirements}"
    )

FIELDS = ",".join([
    "title", "abstract", "tldr", "year", "venue", "publicationVenue", "publicationDate",
    "authors", "citationCount", "influentialCitationCount",
    "referenceCount", "isOpenAccess", "openAccessPdf",
    "externalIds", "fieldsOfStudy", "publicationTypes", "journal",
])
SDK_FIELDS = FIELDS.split(",")


def _retry_after_delay(response, attempt: int) -> float:
    retry_after = response.headers.get("Retry-After")
    if retry_after:
        try:
            return max(0.0, float(retry_after))
        except ValueError:
            pass
    return BASE_429_DELAY_SECONDS * (2 ** attempt)


def _get_with_429_retry(client, url: str, *, params: dict) -> object:
    for attempt in range(MAX_429_ATTEMPTS):
        resp = client.get(url, params=params)
        if getattr(resp, "status_code", None) != 429:
            resp.raise_for_status()
            return resp
        if attempt == MAX_429_ATTEMPTS - 1:
            resp.raise_for_status()
            return resp
        time.sleep(_retry_after_delay(resp, attempt))
    raise RuntimeError("unreachable")


def _value(obj, key: str, default=None):
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _names(items) -> list[str]:
    names = []
    for item in items or []:
        name = _value(item, "name")
        if name:
            names.append(name)
        elif isinstance(item, str):
            names.append(item)
    return names


def _text(obj) -> str | None:
    if obj is None:
        return None
    if isinstance(obj, str):
        return obj
    return _value(obj, "text")


def _date_string(value):
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return value


def _open_access_pdf_url(paper) -> str | None:
    pdf = _value(paper, "openAccessPdf")
    return _value(pdf, "url")


def _publication_venue(paper) -> dict | None:
    pub_venue = _value(paper, "publicationVenue") or {}
    publication_venue = {
        k: _value(pub_venue, k)
        for k in ("id", "name", "type", "url")
        if _value(pub_venue, k)
    }
    return publication_venue or None


def _external_ids(paper) -> dict:
    external_ids = _value(paper, "externalIds") or {}
    return external_ids if isinstance(external_ids, dict) else {}


def _item_from_paper(paper, fallback_paper_id: str = "") -> dict:
    authors = _names(_value(paper, "authors"))
    external_ids = _external_ids(paper)

    paper_id = _value(paper, "paperId") or fallback_paper_id
    url = _value(paper, "url") or (f"https://www.semanticscholar.org/paper/{paper_id}" if paper_id else "")

    abstract = _value(paper, "abstract") or ""
    tldr = _text(_value(paper, "tldr"))
    snippet = abstract or tldr or ""

    journal = _value(paper, "journal") or {}
    venue = _value(paper, "venue") or _value(journal, "name")

    return make_item(
        title=_value(paper, "title") or "",
        url=url,
        snippet=snippet,
        tldr=tldr,
        authors=authors,
        year=_value(paper, "year"),
        venue=venue if venue else None,
        publication_venue=_publication_venue(paper),
        publication_date=_date_string(_value(paper, "publicationDate")),
        citation_count=_value(paper, "citationCount"),
        influential_citation_count=_value(paper, "influentialCitationCount"),
        reference_count=_value(paper, "referenceCount"),
        is_open_access=_value(paper, "isOpenAccess"),
        open_access_pdf=_open_access_pdf_url(paper),
        fields_of_study=_names(_value(paper, "fieldsOfStudy")) or None,
        publication_types=_value(paper, "publicationTypes") or None,
        doi=_value(paper, "doi") or external_ids.get("DOI"),
        arxiv_id=external_ids.get("ArXiv"),
        paper_id=paper_id,
    )


def _build_sdk_client(api_key: str | None):
    if SemanticScholar is None:
        raise ImportError(_dependency_hint("semanticscholar"))
    if api_key:
        return SemanticScholar(api_key=api_key)
    return SemanticScholar()


def _search_with_sdk(query: str, limit: int, api_key: str | None = None) -> list[dict]:
    sch = _build_sdk_client(api_key)
    results = sch.search_paper(query, limit=min(limit, 100))

    items = []
    for paper in results:
        paper_id = _value(paper, "paperId")
        details = sch.get_paper(paper_id, fields=SDK_FIELDS) if paper_id else paper
        items.append(_item_from_paper(details, fallback_paper_id=paper_id))
        if len(items) >= limit:
            break
    return items


def _search_with_http(query: str, limit: int, api_key: str | None = None) -> list[dict]:
    headers: dict[str, str] = {}
    if api_key:
        headers["x-api-key"] = api_key

    params = {
        "query": query,
        "limit": min(limit, 100),
        "fields": FIELDS,
    }

    with get_client(timeout=30, headers=headers) as client:
        resp = _get_with_429_retry(client, API_URL, params=params)
        data = resp.json()

    items = []
    for paper in data.get("data", [])[:limit]:
        items.append(_item_from_paper(paper))

    return items


def search(query: str, limit: int, api_key: str | None = None) -> list[dict]:
    """执行 Semantic Scholar 搜索：SDK 优先，失败时使用原 HTTP Graph API。"""
    try:
        return _search_with_sdk(query, limit, api_key)
    except Exception:
        return _search_with_http(query, limit, api_key)


def main():
    parser = build_parser("搜索 Semantic Scholar 学术论文")
    parser.add_argument("--api-key", help="Semantic Scholar API Key（可选，提高限额）")
    args = parser.parse_args()

    try:
        items = search(args.query, args.limit, getattr(args, "api_key", None))
        print_json(make_result(True, args.query, "semantic_scholar", items))
    except Exception as e:
        print_json(make_result(False, args.query, "semantic_scholar", [], str(e)))
        sys.exit(1)


if __name__ == "__main__":
    main()
