#!/usr/bin/env python3
"""papers.cool ArXiv 镜像搜索，输出 sn-search-academic 标准 JSON。"""

import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

try:
    from bs4 import BeautifulSoup
except ImportError:  # pragma: no cover - exercised by CLI users without project deps.
    BeautifulSoup = None


from search_utils import build_parser, get_client, make_item, make_result, print_json


BASE_URL = "https://papers.cool"
ARXIV_BASE = "https://arxiv.org"
MAX_LIMIT = 100


def _dependency_hint(package: str) -> str:
    skill_dir = Path(__file__).resolve().parents[1]
    requirements = skill_dir / "requirements.txt"
    return (
        f"缺少依赖 {package}。请安装到当前 Python 环境："
        f"python3 -m pip install -r {requirements}"
    )


def parse_results(html: str) -> list[dict[str, Any]]:
    """Parse papers.cool ArXiv HTML into standard sn-search-academic items."""
    if BeautifulSoup is None:
        raise RuntimeError(_dependency_hint("beautifulsoup4"))

    soup = BeautifulSoup(html, "html.parser")
    items: list[dict[str, Any]] = []

    for paper in soup.select("div.panel.paper[id]"):
        arxiv_id = (paper.get("id") or "").strip()
        if not arxiv_id:
            continue

        title_node = paper.select_one(f"#title-{_css_escape(arxiv_id)}") or paper.select_one("a.title-link")
        title = _text(title_node)
        if not title:
            continue

        mirror_path = title_node.get("href") if title_node else f"/arxiv/{arxiv_id}"
        mirror_url = urljoin(BASE_URL, mirror_path)
        abs_url = _abs_url(paper, arxiv_id)
        pdf_url = _pdf_url(paper, arxiv_id)
        categories, subjects = _subjects(paper)

        items.append(
            make_item(
                title=title,
                url=mirror_url,
                snippet=_text(paper.select_one(f"#summary-{_css_escape(arxiv_id)}") or paper.select_one(".summary")),
                arxiv_id=arxiv_id,
                authors=_authors(paper),
                published=_published(paper, arxiv_id),
                pdf_url=pdf_url,
                abs_url=abs_url,
                html_url=f"{ARXIV_BASE}/html/{arxiv_id}",
                mirror_url=mirror_url,
                categories=categories,
                subjects=subjects,
                keywords=_keywords(paper),
            )
        )

    return items


def search(
    query: str,
    limit: int,
    category: str | None = None,
    date: str | None = None,
    id_list: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Fetch papers.cool ArXiv search/category/ID pages and parse papers."""
    wanted = max(0, min(limit, MAX_LIMIT))
    if wanted == 0:
        return []

    url, params = _build_request(query=query, category=category, date=date, id_list=id_list)
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }

    with get_client(timeout=30, headers=headers) as client:
        response = client.get(url, params=params)
        response.raise_for_status()
        return parse_results(response.text)[:wanted]


def _build_request(
    query: str,
    category: str | None,
    date: str | None,
    id_list: list[str] | None,
) -> tuple[str, dict[str, str]]:
    if id_list:
        clean_ids = [_clean_arxiv_id(arxiv_id) for arxiv_id in id_list if arxiv_id.strip()]
        return f"{BASE_URL}/arxiv/{','.join(clean_ids)}", {}

    if category:
        params = {"date": date} if date else {}
        return f"{BASE_URL}/arxiv/{category.strip()}", params

    params = {"query": query, "highlight": "1"}
    return f"{BASE_URL}/arxiv/search", params


def _authors(paper) -> list[str]:
    return [_text(author) for author in paper.select(".authors a.author") if _text(author)]


def _subjects(paper) -> tuple[list[str], list[str]]:
    categories: list[str] = []
    subjects: list[str] = []
    for link in paper.select(".subjects a[href]"):
        href = link.get("href") or ""
        category = href.rstrip("/").split("/")[-1] if href.startswith("/arxiv/") else ""
        subject = _text(link)
        if category:
            categories.append(category)
        if subject:
            subjects.append(subject)
    return categories, subjects


def _published(paper, arxiv_id: str) -> str:
    date_node = paper.select_one(f"#date-{_css_escape(arxiv_id)} .date-data") or paper.select_one(".date .date-data")
    return _text(date_node)


def _abs_url(paper, arxiv_id: str) -> str:
    link = paper.select_one('h2.title a[href^="https://arxiv.org/abs/"]')
    return link.get("href") if link else f"{ARXIV_BASE}/abs/{arxiv_id}"


def _pdf_url(paper, arxiv_id: str) -> str:
    link = paper.select_one(f"#pdf-{_css_escape(arxiv_id)}") or paper.select_one(".title-pdf")
    href = link.get("data") or link.get("href") if link else None
    return href or f"{ARXIV_BASE}/pdf/{arxiv_id}"


def _keywords(paper) -> list[str]:
    raw = paper.get("keywords") or ""
    return [keyword.strip() for keyword in raw.split(",") if keyword.strip()]


def _clean_arxiv_id(arxiv_id: str) -> str:
    return arxiv_id.strip().replace("arXiv:", "").replace("arxiv:", "")


def _text(node) -> str:
    if not node:
        return ""
    return " ".join(node.get_text(" ", strip=True).split())


def _css_escape(value: str) -> str:
    return re.sub(r"([:.])", r"\\\1", value)


def main() -> None:
    parser = build_parser("搜索 papers.cool ArXiv 镜像库")
    parser.prog = "arxiv镜像库搜索.py"
    parser.add_argument("--category", "-c", help="按 ArXiv 分类浏览/搜索最新列表（如 cs.CL, cs.CV）")
    parser.add_argument("--date", help="分类页日期，格式 YYYY-MM-DD（仅配合 --category 使用）")
    parser.add_argument("--id-list", help="直接按 arXiv ID 获取镜像页，逗号分隔")

    for action in parser._positionals._group_actions:
        if action.dest == "query":
            action.nargs = "?"
            action.default = ""
            break

    args = parser.parse_args()

    try:
        id_list = [arxiv_id.strip() for arxiv_id in args.id_list.split(",") if arxiv_id.strip()] if args.id_list else None
        if not args.query and not args.category and not id_list:
            parser.error("请提供搜索关键词，或使用 --category/--id-list")

        items = search(
            args.query,
            args.limit,
            category=args.category,
            date=args.date,
            id_list=id_list,
        )
        query = f"id_list:{','.join(id_list)}" if id_list else (args.category or args.query)
        print_json(make_result(True, query, "papers.cool-arxiv", items))
    except Exception as exc:
        print_json(make_result(False, getattr(args, "query", "") or "", "papers.cool-arxiv", [], str(exc)))
        sys.exit(1)


if __name__ == "__main__":
    main()
