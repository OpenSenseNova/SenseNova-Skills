#!/usr/bin/env python3
"""Semantic Scholar 引用追溯：查询论文的参考文献（backward）和被引论文（forward）。"""
from __future__ import annotations

import argparse
import sys

from search_utils import get_client, make_item, print_json

API_BASE = "https://api.semanticscholar.org/graph/v1/paper"

# paper-level fields（嵌套在 citedPaper/citingPaper 下）
# 注意: tldr 在 nested 请求中容易触发 rate limit，不请求
PAPER_FIELDS = [
    "title", "abstract", "year", "venue", "publicationDate",
    "authors", "citationCount", "influentialCitationCount",
    "isOpenAccess", "openAccessPdf", "externalIds", "fieldsOfStudy",
]

# edge-level fields（引用关系本身的属性）
EDGE_FIELDS = ["contexts", "intents"]


def resolve_paper_id(identifier: str) -> str:
    """将各种论文标识符转为 Semantic Scholar 可接受的格式。

    支持:
      - Semantic Scholar paper ID (40-char hex)
      - DOI: 10.xxxx/... → DOI:10.xxxx/...
      - ArXiv ID: 2301.07041 → ARXIV:2301.07041
      - PubMed ID: PMID:12345678
      - URL: https://www.semanticscholar.org/paper/... → 提取 ID
    """
    identifier = identifier.strip()

    # S2 URL
    if "semanticscholar.org/paper/" in identifier:
        # URL 末尾的 40-char hex
        parts = identifier.rstrip("/").split("/")
        return parts[-1]

    # DOI
    if identifier.startswith("10."):
        return f"DOI:{identifier}"
    if identifier.lower().startswith("doi:"):
        return identifier

    # ArXiv
    if identifier.lower().startswith("arxiv:"):
        return identifier.upper()
    # 形如 2301.07041 或 2301.07041v2
    if "." in identifier and identifier.replace(".", "").replace("v", "").isdigit():
        return f"ARXIV:{identifier}"

    # PMID
    if identifier.lower().startswith("pmid:"):
        return identifier.upper()

    # 假设是 S2 paper ID
    return identifier


def fetch_refs(
    paper_id: str,
    direction: str,
    limit: int,
    min_citations: int,
    year_min: int | None,
    year_max: int | None,
    api_key: str | None = None,
) -> dict:
    """获取论文的 references 或 citations。"""
    resolved = resolve_paper_id(paper_id)
    endpoint = f"{API_BASE}/{resolved}/{direction}"

    headers: dict[str, str] = {}
    if api_key:
        headers["x-api-key"] = api_key

    # S2 API 单次最多 1000，分页用 offset
    # S2 references/citations 端点：paper fields 用 nested 前缀，edge fields 直接列出
    # 格式: fields=contexts,intents,citedPaper.title,citedPaper.year,...
    paper_key_prefix = "citedPaper" if direction == "references" else "citingPaper"
    prefixed_fields = [f"{paper_key_prefix}.{f}" for f in PAPER_FIELDS]
    all_fields = ",".join(EDGE_FIELDS + prefixed_fields)

    params = {
        "fields": all_fields,
        # citations 端点按时间倒序返回，需要多取才能找到高引论文
        # references 通常较少（几十条），多取无害
        "limit": 1000,
    }

    with get_client(timeout=30, headers=headers) as client:
        resp = client.get(endpoint, params=params)
        resp.raise_for_status()
        data = resp.json()

    # 获取论文本体信息（用于输出上下文）
    paper_resp = None
    with get_client(timeout=15, headers=headers) as client:
        try:
            r = client.get(f"{API_BASE}/{resolved}", params={"fields": "title,year,citationCount"})
            r.raise_for_status()
            paper_resp = r.json()
        except Exception:
            pass

    # direction=references 时结构是 {"data": [{"citedPaper": {...}, "contexts": [...], "intents": [...]}]}
    # direction=citations 时结构是 {"data": [{"citingPaper": {...}, "contexts": [...], "intents": [...]}]}
    paper_key = "citedPaper" if direction == "references" else "citingPaper"

    items = []
    for entry in data.get("data", []):
        paper = entry.get(paper_key, {})
        if not paper or not paper.get("title"):
            continue

        year = paper.get("year")
        citation_count = paper.get("citationCount") or 0

        # 过滤
        if citation_count < min_citations:
            continue
        if year_min and year and year < year_min:
            continue
        if year_max and year and year > year_max:
            continue

        authors = [a.get("name", "") for a in paper.get("authors", [])]
        external_ids = paper.get("externalIds") or {}
        doi = external_ids.get("DOI")
        arxiv_id = external_ids.get("ArXiv")
        s2_id = paper.get("paperId", "")

        url = f"https://www.semanticscholar.org/paper/{s2_id}" if s2_id else ""

        abstract = paper.get("abstract") or ""
        snippet = abstract

        open_access_pdf = None
        if paper.get("openAccessPdf"):
            open_access_pdf = paper["openAccessPdf"].get("url")

        # contexts: 引用该论文时的上下文句子（仅 citations 方向有意义）
        contexts = entry.get("contexts") or []
        intents = entry.get("intents") or []

        item = make_item(
            title=paper.get("title", ""),
            url=url,
            snippet=snippet,
            authors=authors,
            year=year,
            venue=paper.get("venue") or None,
            publication_date=paper.get("publicationDate"),
            citation_count=citation_count,
            influential_citation_count=paper.get("influentialCitationCount"),
            is_open_access=paper.get("isOpenAccess"),
            open_access_pdf=open_access_pdf,
            fields_of_study=paper.get("fieldsOfStudy") or None,
            doi=doi,
            arxiv_id=arxiv_id,
            paper_id=s2_id,
            citation_contexts=contexts[:3] if contexts else None,  # 最多 3 条上下文
            citation_intents=intents if intents else None,
        )
        items.append(item)

    # 按引用数排序，取 top-N
    items.sort(key=lambda x: x.get("citation_count", 0), reverse=True)
    items = items[:limit]

    result = {
        "success": True,
        "paper_id": resolved,
        "direction": direction,
        "provider": "semantic_scholar",
        "items": items,
        "total_available": len(data.get("data", [])),
        "returned": len(items),
        "error": None,
    }
    if paper_resp:
        result["source_paper"] = {
            "title": paper_resp.get("title"),
            "year": paper_resp.get("year"),
            "citation_count": paper_resp.get("citationCount"),
        }

    return result


def main():
    parser = argparse.ArgumentParser(
        description="查询论文的参考文献（backward）或被引论文（forward）"
    )
    parser.add_argument(
        "paper_id",
        help="论文标识符：S2 ID、DOI（如 10.1234/...）、ArXiv ID（如 2301.07041）、PMID（如 PMID:12345678）",
    )
    parser.add_argument(
        "direction",
        choices=["references", "citations"],
        help="references=参考文献（backward），citations=被引论文（forward）",
    )
    parser.add_argument("--limit", "-n", type=int, default=20, help="返回结果数量（默认 20）")
    parser.add_argument("--min-citations", type=int, default=0, help="最低引用数过滤（默认 0）")
    parser.add_argument("--year-min", type=int, default=None, help="最早年份过滤")
    parser.add_argument("--year-max", type=int, default=None, help="最晚年份过滤")
    parser.add_argument("--api-key", help="Semantic Scholar API Key（可选）")
    args = parser.parse_args()

    try:
        result = fetch_refs(
            args.paper_id,
            args.direction,
            args.limit,
            args.min_citations,
            args.year_min,
            args.year_max,
            getattr(args, "api_key", None),
        )
        print_json(result)
    except Exception as e:
        print_json({
            "success": False,
            "paper_id": args.paper_id,
            "direction": args.direction,
            "provider": "semantic_scholar",
            "items": [],
            "error": str(e),
        })
        sys.exit(1)


if __name__ == "__main__":
    main()
