#!/usr/bin/env python3
"""Semantic Scholar 论文搜索。通过 Semantic Scholar Graph API。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "_search-common"))

from search_utils import build_parser, get_client, make_item, make_result, print_json

API_URL = "https://api.semanticscholar.org/graph/v1/paper/search"

FIELDS = ",".join([
    "title", "abstract", "tldr", "year", "venue", "publicationVenue", "publicationDate",
    "authors", "citationCount", "influentialCitationCount",
    "referenceCount", "isOpenAccess", "openAccessPdf",
    "externalIds", "fieldsOfStudy", "publicationTypes", "journal",
])


def search(query: str, limit: int, api_key: str | None = None) -> list[dict]:
    """执行 Semantic Scholar 搜索。"""
    headers: dict[str, str] = {}
    if api_key:
        headers["x-api-key"] = api_key

    params = {
        "query": query,
        "limit": min(limit, 100),
        "fields": FIELDS,
    }

    with get_client(timeout=30, headers=headers) as client:
        resp = client.get(API_URL, params=params)
        resp.raise_for_status()
        data = resp.json()

    items = []
    for paper in data.get("data", [])[:limit]:
        authors = [a.get("name", "") for a in paper.get("authors", [])]

        open_access_pdf = None
        if paper.get("openAccessPdf"):
            open_access_pdf = paper["openAccessPdf"].get("url")

        external_ids = paper.get("externalIds") or {}
        doi = external_ids.get("DOI")
        arxiv_id = external_ids.get("ArXiv")

        paper_id = paper.get("paperId", "")
        url = f"https://www.semanticscholar.org/paper/{paper_id}"

        # 摘要：优先用 abstract，缺失时降级用 tldr
        abstract = paper.get("abstract") or ""
        tldr = (paper.get("tldr") or {}).get("text")
        snippet = abstract or tldr or ""

        # 期刊/会议：venue（脏字符串）+ publicationVenue（结构化）
        venue = paper.get("venue") or (paper.get("journal") or {}).get("name")
        pub_venue = paper.get("publicationVenue") or {}
        publication_venue = {
            k: pub_venue[k]
            for k in ("id", "name", "type", "url")
            if pub_venue.get(k)
        } or None

        items.append(make_item(
            title=paper.get("title") or "",
            url=url,
            snippet=snippet,
            tldr=tldr,
            authors=authors,
            year=paper.get("year"),
            venue=venue if venue else None,
            publication_venue=publication_venue,
            publication_date=paper.get("publicationDate"),
            citation_count=paper.get("citationCount"),
            influential_citation_count=paper.get("influentialCitationCount"),
            reference_count=paper.get("referenceCount"),
            is_open_access=paper.get("isOpenAccess"),
            open_access_pdf=open_access_pdf,
            fields_of_study=paper.get("fieldsOfStudy") or None,
            publication_types=paper.get("publicationTypes") or None,
            doi=doi,
            arxiv_id=arxiv_id,
            paper_id=paper_id,
        ))

    return items


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
