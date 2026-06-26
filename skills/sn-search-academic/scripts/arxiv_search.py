#!/usr/bin/env python3
"""
ArXiv 论文搜索。基于 arxiv Python 包封装，输出 sn-search-academic 的标准 JSON。

支持：
  - 全文 / 标题 / 作者字段搜索
  - 分类过滤、排序
  - 按 ID 列表直接拉取论文元数据

示例：
  python3 arxiv_search.py "attention mechanism"
  python3 arxiv_search.py "transformer" --category cs.CL --sort date
  python3 arxiv_search.py "diffusion model" --author "ho jonathan"
  python3 arxiv_search.py "ViT" --title-only
  python3 arxiv_search.py --id-list 2409.05591,2301.00001
"""

import sys
from pathlib import Path
from typing import Any

try:
    import arxiv
except ImportError as exc:  # pragma: no cover - exercised by CLI users.
    skill_dir = Path(__file__).resolve().parents[1]
    requirements = skill_dir / "requirements.txt"
    raise SystemExit(
        "缺少依赖 arxiv。请安装到当前 Python 环境："
        f"python3 -m pip install -r {requirements}"
    ) from exc


from search_utils import build_parser, make_item, make_result, print_json


class ArxivSearchAssistant:
    """Thin wrapper around arxiv.Client that returns legacy skill items."""

    def __init__(self) -> None:
        self.client = arxiv.Client()

    def search(
        self,
        query: str,
        max_results: int = 10,
        sort_by: str = "relevance",
        category: str | None = None,
        author: str | None = None,
        title_only: bool = False,
    ) -> list[dict[str, Any]]:
        search_query = build_search_query(
            query,
            category=category,
            author=author,
            title_only=title_only,
        )
        request = arxiv.Search(
            query=search_query,
            max_results=max_results,
            sort_by=_sort_criterion(sort_by),
        )
        return [self._paper_to_item(paper) for paper in self.client.results(request)]

    def fetch_by_ids(self, id_list: list[str], max_results: int = 10) -> list[dict[str, Any]]:
        clean_ids = [_clean_arxiv_id(arxiv_id) for arxiv_id in id_list[:max_results]]
        request = arxiv.Search(id_list=clean_ids, max_results=min(len(clean_ids), max_results))
        return [self._paper_to_item(paper, full=True) for paper in self.client.results(request)]

    def download_pdf(self, arxiv_id: str, output_dir: str = "./papers") -> str | None:
        clean_id = _clean_arxiv_id(arxiv_id)
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        request = arxiv.Search(id_list=[clean_id], max_results=1)

        for paper in self.client.results(request):
            filename = f"{clean_id.replace('/', '_')}.pdf"
            paper.download_pdf(dirpath=output_dir, filename=filename)
            return str(Path(output_dir) / filename)

        return None

    def _paper_to_item(self, paper: Any, full: bool = False) -> dict[str, Any]:
        arxiv_id = _clean_arxiv_id(str(paper.entry_id).split("/")[-1])
        title = _normalize_space(str(paper.title))
        summary = _normalize_space(str(paper.summary))
        authors = [str(author) for author in paper.authors]
        url = str(paper.entry_id)

        extra: dict[str, Any] = {
            "arxiv_id": arxiv_id,
            "authors": authors if full else authors[:5],
            "published": _isoformat_or_none(getattr(paper, "published", None)),
            "updated": _isoformat_or_none(getattr(paper, "updated", None)),
            "pdf_url": getattr(paper, "pdf_url", None),
            "html_url": f"https://arxiv.org/html/{arxiv_id}" if arxiv_id else None,
            "categories": getattr(paper, "categories", []),
            "primary_category": getattr(paper, "primary_category", None),
            "comment": getattr(paper, "comment", None),
            "journal_ref": getattr(paper, "journal_ref", None),
            "doi": getattr(paper, "doi", None),
        }
        return make_item(title=title, url=url, snippet=summary, **extra)


def build_search_query(
    query: str,
    category: str | None = None,
    author: str | None = None,
    title_only: bool = False,
) -> str:
    """构建 arXiv 查询字符串。"""
    if _has_arxiv_field_prefix(query):
        parts = [query]
    else:
        field = "ti" if title_only else "all"
        parts = [f"{field}:{query}"]

    if author:
        author_terms = [f"au:{name.strip()}" for name in author.split(",") if name.strip()]
        if author_terms:
            parts.append(f"({' OR '.join(author_terms)})")

    if category:
        parts.append(f"cat:{category}")

    return " AND ".join(parts)


def _has_arxiv_field_prefix(query: str) -> bool:
    fields = ("all", "ti", "au", "abs", "co", "jr", "cat", "rn", "id")
    return query.lstrip().lower().startswith(tuple(f"{field}:" for field in fields))


def fetch_by_ids(id_list: list[str], limit: int) -> list[dict[str, Any]]:
    """通过 ID 列表直接获取论文元数据（不做文本搜索）。"""
    return ArxivSearchAssistant().fetch_by_ids(id_list, max_results=min(limit, 100))


def download_pdf(arxiv_id: str, output_dir: str = "./papers") -> str | None:
    """下载论文 PDF。隐藏兼容接口，不在 skill 使用说明中公开。"""
    return ArxivSearchAssistant().download_pdf(arxiv_id, output_dir=output_dir)


def search(
    query: str,
    limit: int,
    category: str | None = None,
    sort_by: str = "relevance",
    author: str | None = None,
    title_only: bool = False,
) -> list[dict[str, Any]]:
    """执行 ArXiv 关键词搜索。"""
    return ArxivSearchAssistant().search(
        query,
        max_results=min(limit, 100),
        sort_by=sort_by,
        category=category,
        author=author,
        title_only=title_only,
    )


def _sort_criterion(sort_by: str):
    if sort_by == "relevance":
        return arxiv.SortCriterion.Relevance
    if sort_by in {"date", "submitted"}:
        return arxiv.SortCriterion.SubmittedDate
    return arxiv.SortCriterion.Relevance


def _clean_arxiv_id(arxiv_id: str) -> str:
    return arxiv_id.strip().replace("arXiv:", "").replace("arxiv:", "")


def _normalize_space(value: str) -> str:
    return " ".join(value.split())


def _isoformat_or_none(value: Any) -> str | None:
    return value.isoformat() if value else None


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "download":
        _main_download()
        return

    parser = build_parser("搜索 ArXiv 学术论文")
    parser.add_argument("--category", "-c", help="ArXiv 分类过滤（如 cs.AI, cs.CL, math.CO）")
    parser.add_argument(
        "--sort",
        default="relevance",
        choices=["relevance", "date", "submitted"],
        help="排序方式（默认 relevance；date/submitted 按提交日期倒序）",
    )
    parser.add_argument(
        "--author",
        "-a",
        help="按作者过滤（如 'hinton'，多个作者用逗号分隔）",
    )
    parser.add_argument(
        "--title-only",
        action="store_true",
        help="仅在标题中搜索（默认搜索全字段）",
    )
    parser.add_argument(
        "--id-list",
        help="直接按 arXiv ID 获取元数据，逗号分隔（如 2409.05591,2301.00001）。指定此项时 query 参数可留空。",
    )
    parser.prog = "arxiv_search.py"

    for action in parser._positionals._group_actions:
        if action.dest == "query":
            action.nargs = "?"
            action.default = ""
            break

    args = parser.parse_args()

    try:
        if args.id_list:
            id_list = [arxiv_id.strip() for arxiv_id in args.id_list.split(",") if arxiv_id.strip()]
            items = fetch_by_ids(id_list, args.limit)
            query_str = f"id_list:{','.join(id_list)}"
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
    except Exception as exc:
        print_json(make_result(False, getattr(args, "query", "") or "", "arxiv", [], str(exc)))
        sys.exit(1)


def _main_download() -> None:
    parser = build_parser("下载 ArXiv PDF")
    parser.prog = "arxiv_search.py download"
    for action in parser._positionals._group_actions:
        if action.dest == "query":
            action.dest = "arxiv_id"
            action.metavar = "arxiv_id"
            action.help = "arXiv 论文 ID"
            break
    parser.add_argument("--output", default="./papers", help="输出目录")

    args = parser.parse_args(sys.argv[2:])
    clean_id = _clean_arxiv_id(args.arxiv_id)

    try:
        filepath = download_pdf(clean_id, args.output)
        if filepath is None:
            print_json({
                "success": False,
                "arxiv_id": clean_id,
                "output_path": None,
                "error": f"Paper {clean_id} not found",
            })
            sys.exit(1)

        print_json({
            "success": True,
            "arxiv_id": clean_id,
            "output_path": filepath,
            "error": None,
        })
    except Exception as exc:
        print_json({
            "success": False,
            "arxiv_id": clean_id,
            "output_path": None,
            "error": str(exc),
        })
        sys.exit(1)


if __name__ == "__main__":
    main()
