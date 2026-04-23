#!/usr/bin/env python3
"""
ArXiv 论文搜索。通过 ArXiv API（返回 Atom XML）。

支持：
  - 全文 / 标题 / 摘要 / 作者字段搜索
  - 分类过滤、排序
  - 按 ID 列表直接拉取论文元数据
  - 布尔组合查询（AND / OR / ANDNOT）

示例：
  python3 arxiv_search.py "attention mechanism"
  python3 arxiv_search.py "transformer" --category cs.CL --sort date
  python3 arxiv_search.py "diffusion model" --author "ho jonathan"
  python3 arxiv_search.py "ViT" --title-only
  python3 arxiv_search.py --id-list 2409.05591,2301.00001
"""
from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "_search-common"))

from search_utils import build_parser, get_client, make_item, make_result, print_json

API_URL = "https://export.arxiv.org/api/query"

# Atom XML 命名空间
NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "arxiv": "http://arxiv.org/schemas/atom",
}


def build_search_query(
    query: str,
    category: str | None = None,
    author: str | None = None,
    title_only: bool = False,
) -> str:
    """
    构建 arXiv 查询字符串。

    字段前缀：
      all:  全字段（默认）
      ti:   仅标题
      au:   作者（支持通配 au:smi*）
      abs:  摘要
      cat:  分类
    布尔运算符必须大写：AND / OR / ANDNOT
    """
    # 主查询字段
    field = "ti" if title_only else "all"
    parts = [f"{field}:{query}"]

    if author:
        # 多个作者用 OR 连接，支持 "lastname firstname" 格式
        author_terms = [f"au:{a.strip()}" for a in author.split(",") if a.strip()]
        if author_terms:
            parts.append(f"({' OR '.join(author_terms)})")

    if category:
        parts.append(f"cat:{category}")

    return " AND ".join(parts)


def fetch_by_ids(id_list: list[str], limit: int) -> list[dict]:
    """通过 ID 列表直接获取论文元数据（不做文本搜索）。"""
    params = {
        "id_list": ",".join(id_list[:limit]),
        "max_results": min(len(id_list), limit, 100),
    }
    with get_client(timeout=30, headers={"Accept": "application/xml"}) as client:
        resp = client.get(API_URL, params=params)
        resp.raise_for_status()
    return _parse_entries(ET.fromstring(resp.text), limit)


def search(
    query: str,
    limit: int,
    category: str | None = None,
    sort_by: str = "relevance",
    author: str | None = None,
    title_only: bool = False,
) -> list[dict]:
    """执行 ArXiv 关键词搜索。"""
    search_query = build_search_query(query, category, author, title_only)

    sort_map = {
        "relevance": "relevance",
        "date": "lastUpdatedDate",
        "submitted": "submittedDate",
    }

    params = {
        "search_query": search_query,
        "start": 0,
        "max_results": min(limit, 100),
        "sortBy": sort_map.get(sort_by, "relevance"),
        "sortOrder": "descending",
    }

    with get_client(timeout=30, headers={"Accept": "application/xml"}) as client:
        resp = client.get(API_URL, params=params)
        resp.raise_for_status()

    return _parse_entries(ET.fromstring(resp.text), limit)


def _parse_entries(root: ET.Element, limit: int) -> list[dict]:
    """从 Atom XML 解析论文条目。"""
    items = []

    for entry in root.findall("atom:entry", NS)[:limit]:
        title = _text(entry, "atom:title").replace("\n", " ").strip()
        summary = _text(entry, "atom:summary").replace("\n", " ").strip()
        published = _text(entry, "atom:published")
        updated = _text(entry, "atom:updated")

        # 获取论文链接（优先 abs 页面）
        url = ""
        pdf_url = ""
        for link in entry.findall("atom:link", NS):
            href = link.get("href", "")
            if link.get("title") == "pdf":
                pdf_url = href
            elif link.get("type") == "text/html" or "/abs/" in href:
                url = href
        if not url:
            url = _text(entry, "atom:id")

        # 从 abs URL 或 id 提取 arxiv_id
        arxiv_id = ""
        raw_id = _text(entry, "atom:id")
        if "/abs/" in raw_id:
            arxiv_id = raw_id.split("/abs/")[-1]
        elif raw_id.startswith("http"):
            arxiv_id = raw_id.split("/")[-1]

        # 获取作者
        authors = [_text(a, "atom:name") for a in entry.findall("atom:author", NS)]

        # 获取分类
        categories = [c.get("term", "") for c in entry.findall("atom:category", NS)]

        comment = _text(entry, "arxiv:comment")
        journal_ref = _text(entry, "arxiv:journal_ref")
        doi = _text(entry, "arxiv:doi")
        primary_category = entry.find("arxiv:primary_category", NS)
        primary_cat = primary_category.get("term", "") if primary_category is not None else ""

        # HTML 版本链接（较新论文有）
        html_url = f"https://arxiv.org/html/{arxiv_id}" if arxiv_id else None

        items.append(make_item(
            title=title,
            url=url,
            snippet=summary,
            arxiv_id=arxiv_id if arxiv_id else None,
            authors=authors,
            published=published,
            updated=updated,
            pdf_url=pdf_url,
            html_url=html_url,
            categories=categories,
            primary_category=primary_cat if primary_cat else None,
            comment=comment if comment else None,
            journal_ref=journal_ref if journal_ref else None,
            doi=doi if doi else None,
        ))

    return items


def _text(elem: ET.Element, tag: str) -> str:
    """安全获取子元素文本。"""
    child = elem.find(tag, NS)
    return child.text.strip() if child is not None and child.text else ""


def main():
    parser = build_parser("搜索 ArXiv 学术论文")
    parser.add_argument("--category", "-c", help="ArXiv 分类过滤（如 cs.AI, cs.CL, math.CO）")
    parser.add_argument(
        "--sort", default="relevance",
        choices=["relevance", "date", "submitted"],
        help="排序方式（默认 relevance）",
    )
    parser.add_argument(
        "--author", "-a",
        help="按作者过滤（如 'hinton'，多个作者用逗号分隔）",
    )
    parser.add_argument(
        "--title-only", action="store_true",
        help="仅在标题中搜索（默认搜索全字段）",
    )
    parser.add_argument(
        "--id-list",
        help="直接按 arXiv ID 获取元数据，逗号分隔（如 2409.05591,2301.00001）。指定此项时 query 参数可留空。",
    )
    # 当使用 --id-list 时 query 可选
    parser.prog = "arxiv_search.py"

    # 为了支持 --id-list 时 query 可省略，临时让 query 可选
    for action in parser._positionals._group_actions:
        if action.dest == "query":
            action.nargs = "?"
            action.default = ""
            break

    args = parser.parse_args()

    try:
        if args.id_list:
            id_list = [i.strip() for i in args.id_list.split(",") if i.strip()]
            items = fetch_by_ids(id_list, args.limit)
            query_str = f"id_list:{args.id_list}"
        else:
            if not args.query:
                parser.error("请提供搜索关键词，或使用 --id-list 按 ID 查询")
            items = search(
                args.query,
                args.limit,
                category=args.category,
                sort_by=args.sort,
                author=args.author,
                title_only=args.title_only,
            )
            query_str = args.query

        print_json(make_result(True, query_str, "arxiv", items))
    except Exception as e:
        print_json(make_result(False, getattr(args, "query", "") or "", "arxiv", [], str(e)))
        sys.exit(1)


if __name__ == "__main__":
    main()
