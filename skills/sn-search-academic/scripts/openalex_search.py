#!/usr/bin/env python3
"""OpenAlex 学术论文搜索，输出 sn-search-academic 标准 JSON。"""

import os
import sys
from typing import Any


from search_utils import build_parser, get_client, make_item, make_result, print_json


API_URL = "https://api.openalex.org/works"
MAX_LIMIT = 200
SELECT_FIELDS = ",".join(
    [
        "id",
        "doi",
        "title",
        "display_name",
        "publication_year",
        "publication_date",
        "cited_by_count",
        "type",
        "authorships",
        "abstract_inverted_index",
        "primary_location",
        "open_access",
        "concepts",
    ]
)


def search(
    query: str,
    limit: int,
    api_key: str | None = None,
    mailto: str | None = None,
    year_min: int | None = None,
    year_max: int | None = None,
) -> list[dict[str, Any]]:
    """执行 OpenAlex Works 搜索。"""
    wanted = max(0, min(limit, MAX_LIMIT))
    if wanted == 0:
        return []

    params = _build_params(
        query=query,
        limit=wanted,
        api_key=api_key,
        mailto=mailto,
        year_min=year_min,
        year_max=year_max,
    )

    with get_client(timeout=30) as client:
        response = client.get(API_URL, params=params)
        response.raise_for_status()
        data = response.json()

    return [_item_from_work(work) for work in data.get("results", [])[:wanted]]


def _build_params(
    query: str,
    limit: int,
    api_key: str | None,
    mailto: str | None,
    year_min: int | None,
    year_max: int | None,
) -> dict[str, str]:
    params = {
        "search": query,
        "per-page": str(limit),
        "sort": "relevance_score:desc",
        "select": SELECT_FIELDS,
    }

    if api_key:
        params["api_key"] = api_key

    polite_mailto = mailto or os.environ.get("OPENALEX_MAILTO") or os.environ.get("CLAWDBOT_EMAIL")
    if polite_mailto:
        params["mailto"] = polite_mailto

    filters = []
    if year_min is not None:
        filters.append(f"from_publication_date:{year_min}-01-01")
    if year_max is not None:
        filters.append(f"to_publication_date:{year_max}-12-31")
    if filters:
        params["filter"] = ",".join(filters)

    return params


def _item_from_work(work: dict[str, Any]) -> dict[str, Any]:
    primary_location = work.get("primary_location") or {}
    source = primary_location.get("source") or {}
    open_access = work.get("open_access") or {}

    url = (
        primary_location.get("landing_page_url")
        or open_access.get("oa_url")
        or work.get("doi")
        or work.get("id")
        or ""
    )

    return make_item(
        title=work.get("title") or work.get("display_name") or "",
        url=url,
        snippet=_abstract_from_inverted_index(work.get("abstract_inverted_index")),
        authors=_authors(work.get("authorships")),
        year=work.get("publication_year"),
        publication_date=work.get("publication_date"),
        venue=source.get("display_name"),
        source_type=source.get("type"),
        citation_count=work.get("cited_by_count"),
        is_open_access=open_access.get("is_oa"),
        open_access_url=open_access.get("oa_url"),
        pdf_url=primary_location.get("pdf_url"),
        doi=_normalize_doi(work.get("doi")),
        openalex_id=_openalex_id(work.get("id")),
        work_type=work.get("type"),
        concepts=_concepts(work.get("concepts")),
    )


def _abstract_from_inverted_index(index: dict[str, list[int]] | None) -> str:
    if not index:
        return ""

    words_by_position = {}
    for word, positions in index.items():
        for position in positions or []:
            words_by_position[position] = word

    return " ".join(words_by_position[position] for position in sorted(words_by_position))


def _authors(authorships: list[dict[str, Any]] | None) -> list[str]:
    names = []
    for authorship in authorships or []:
        author = authorship.get("author") or {}
        name = author.get("display_name")
        if name:
            names.append(name)
    return names


def _concepts(concepts: list[dict[str, Any]] | None) -> list[str]:
    names = []
    for concept in concepts or []:
        name = concept.get("display_name")
        if name:
            names.append(name)
    return names


def _normalize_doi(value: str | None) -> str | None:
    if not value:
        return None
    return value.removeprefix("https://doi.org/").removeprefix("http://doi.org/")


def _openalex_id(value: str | None) -> str | None:
    if not value:
        return None
    return value.rstrip("/").split("/")[-1]


def main():
    parser = build_parser("搜索 OpenAlex 学术论文")
    parser.add_argument("--api-key", help="OpenAlex API Key（可选）")
    parser.add_argument("--mailto", help="OpenAlex polite pool 邮箱（也可用 OPENALEX_MAILTO/CLAWDBOT_EMAIL）")
    parser.add_argument("--year-min", type=int, help="最早发表年份")
    parser.add_argument("--year-max", type=int, help="最晚发表年份")
    args = parser.parse_args()

    try:
        items = search(
            args.query,
            args.limit,
            api_key=args.api_key or os.environ.get("OPENALEX_API_KEY"),
            mailto=args.mailto,
            year_min=args.year_min,
            year_max=args.year_max,
        )
        print_json(make_result(True, args.query, "openalex", items))
    except Exception as e:
        print_json(make_result(False, args.query, "openalex", [], str(e)))
        sys.exit(1)


if __name__ == "__main__":
    main()
