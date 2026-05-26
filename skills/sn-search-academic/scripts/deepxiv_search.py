#!/usr/bin/env python3
"""DeepXiv 论文搜索，输出 sn-search-academic 标准 JSON。"""

import os
import sys
import contextlib
import io
import logging
from pathlib import Path
from typing import Any

try:
    from deepxiv_sdk import Reader
except ImportError as exc:  # pragma: no cover - exercised by CLI users.
    skill_dir = Path(__file__).resolve().parents[1]
    requirements = skill_dir / "requirements.txt"
    raise SystemExit(
        "缺少依赖 deepxiv-sdk。请安装到当前 Python 环境："
        f"python3 -m pip install -r {requirements}"
    ) from exc


from search_utils import build_parser, make_item, make_result, print_json


MAX_LIMIT = 100
MAX_OFFSET = 10000
SOURCES = {"arxiv", "biorxiv", "medrxiv"}
logging.getLogger("deepxiv_sdk").setLevel(logging.CRITICAL)


def search(
    query: str,
    limit: int,
    source: str = "arxiv",
    token: str | None = None,
    categories: list[str] | None = None,
    authors: list[str] | None = None,
    orgs: list[str] | None = None,
    min_citation: int | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    date_search_type: str | None = None,
    date_str: str | list[str] | None = None,
    use_fine_rerank: bool = False,
    offset: int = 0,
    timeout: int = 120,
    max_retries: int = 3,
) -> list[dict[str, Any]]:
    """执行 DeepXiv unified retrieve 搜索。"""
    wanted = max(0, min(limit, MAX_LIMIT))
    if wanted == 0:
        return []

    clean_source = _normalize_source(source)
    clean_offset = max(0, min(offset, MAX_OFFSET))
    reader = _build_reader(token=token, timeout=timeout, max_retries=max_retries)
    response = reader.search(
        query,
        size=wanted,
        offset=clean_offset,
        source=clean_source,
        categories=categories,
        authors=authors,
        orgs=orgs,
        min_citation=min_citation,
        date_from=date_from,
        date_to=date_to,
        date_search_type=date_search_type,
        date_str=date_str,
        use_fine_rerank=use_fine_rerank,
    )
    return [_item_from_paper(paper, clean_source) for paper in _extract_results(response)[:wanted]]


def _build_reader(token: str | None, timeout: int, max_retries: int):
    clean_token = _resolve_token(token)
    kwargs: dict[str, Any] = {
        "timeout": timeout,
        "max_retries": max_retries,
    }
    if clean_token:
        kwargs["token"] = clean_token

    try:
        return Reader(**kwargs)
    except TypeError:
        kwargs.pop("token", None)
        reader = Reader(**kwargs)
        if clean_token:
            os.environ["DEEPXIV_TOKEN"] = clean_token
        return reader


def _resolve_token(token: str | None) -> str:
    clean_token = token or os.environ.get("DEEPXIV_TOKEN")
    if clean_token:
        return clean_token

    try:
        from deepxiv_sdk.cli import auto_register_token
    except Exception as exc:
        raise RuntimeError("缺少 DeepXiv token，且无法加载 SDK 自动注册函数") from exc

    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        new_token, _daily_limit = auto_register_token()

    if not new_token:
        message = stderr.getvalue().strip() or stdout.getvalue().strip()
        raise RuntimeError(f"DeepXiv token 自动注册失败：{message or '未返回 token'}")
    return new_token


def _extract_results(response: Any) -> list[dict[str, Any]]:
    if isinstance(response, dict):
        results = response.get("result") or response.get("results") or []
        return results if isinstance(results, list) else []
    results = getattr(response, "result", None) or getattr(response, "results", None) or []
    return results if isinstance(results, list) else []


def _item_from_paper(paper: dict[str, Any], source: str) -> dict[str, Any]:
    paper_id = _paper_id(paper, source)
    title = str(paper.get("title") or "")
    url = paper.get("url") or _source_url(paper_id, source)
    abstract = paper.get("abstract") or ""
    tldr = paper.get("tldr") or ""

    return make_item(
        title=title,
        url=url or "",
        snippet=abstract or tldr,
        tldr=tldr,
        authors=_authors(paper.get("authors")),
        date=paper.get("date"),
        year=_year_from_date(paper.get("date")),
        score=paper.get("score"),
        citation_count=paper.get("citation_count") or paper.get("citation"),
        categories=paper.get("categories"),
        source=source,
        arxiv_id=paper.get("arxiv_id"),
        biorxiv_id=paper.get("biorxiv_id"),
        medrxiv_id=paper.get("medrxiv_id"),
        paper_id=paper_id,
        pdf_url=paper.get("pdf_url"),
        github_url=paper.get("github_url") or paper.get("github"),
        doi=paper.get("doi"),
    )


def _authors(value: Any) -> list[str]:
    names = []
    for author in value or []:
        if isinstance(author, str):
            names.append(author)
            continue
        if isinstance(author, dict):
            name = author.get("name")
            if name:
                names.append(name)
    return names


def _paper_id(paper: dict[str, Any], source: str) -> str | None:
    if source == "biorxiv":
        return paper.get("biorxiv_id") or paper.get("doi") or paper.get("arxiv_id")
    if source == "medrxiv":
        return paper.get("medrxiv_id") or paper.get("doi") or paper.get("arxiv_id")
    return paper.get("arxiv_id") or paper.get("id") or paper.get("doi")


def _source_url(paper_id: str | None, source: str) -> str | None:
    if not paper_id:
        return None
    if source == "arxiv":
        return f"https://arxiv.org/abs/{paper_id}"
    if paper_id.startswith("10."):
        return f"https://doi.org/{paper_id}"
    return None


def _year_from_date(value: Any) -> int | None:
    if not value:
        return None
    try:
        return int(str(value)[:4])
    except ValueError:
        return None


def _normalize_source(source: str) -> str:
    clean_source = source.lower().strip()
    if clean_source not in SOURCES:
        raise ValueError(f"source 必须是 {', '.join(sorted(SOURCES))} 之一")
    return clean_source


def _split_csv(value: str | None) -> list[str] | None:
    if not value:
        return None
    items = [item.strip() for item in value.split(",") if item.strip()]
    return items or None


def _date_str_arg(values: list[str] | None) -> str | list[str] | None:
    if not values:
        return None
    if len(values) == 1:
        return values[0]
    return values


def main() -> None:
    parser = build_parser("搜索 DeepXiv 学术论文")
    parser.add_argument("--token", help="DeepXiv token（也可用 DEEPXIV_TOKEN；不传则 SDK 可自动注册匿名 token）")
    parser.add_argument("--source", choices=sorted(SOURCES), default="arxiv", help="搜索来源（默认 arxiv）")
    parser.add_argument("--biorxiv", action="store_true", help="等价于 --source biorxiv")
    parser.add_argument("--medrxiv", action="store_true", help="等价于 --source medrxiv")
    parser.add_argument("--categories", "-c", help="分类过滤，多个用逗号分隔（如 cs.CV,cs.CL）")
    parser.add_argument("--authors", "-a", help="作者过滤/排序提示，多个用逗号分隔")
    parser.add_argument("--orgs", help="机构过滤/排序提示，多个用逗号分隔")
    parser.add_argument("--min-citation", "--min-citations", type=int, dest="min_citation", help="最低引用数")
    parser.add_argument("--date-from", help="起始日期，支持 YYYY / YYYY-MM / YYYY-MM-DD")
    parser.add_argument("--date-to", help="结束日期，支持 YYYY / YYYY-MM / YYYY-MM-DD")
    parser.add_argument(
        "--date-search-type",
        choices=["between", "exact", "after", "before"],
        help="高级日期过滤类型",
    )
    parser.add_argument(
        "--date-str",
        action="append",
        help="高级日期过滤值；between 可传两次，或直接使用 --date-from/--date-to",
    )
    parser.add_argument("--use-fine-rerank", action="store_true", help="启用 DeepXiv 精排")
    parser.add_argument("--offset", type=int, default=0, help="分页偏移（0~10000，默认 0）")
    parser.add_argument("--timeout", type=int, default=120, help="请求超时秒数（默认 120）")
    parser.add_argument("--max-retries", type=int, default=3, help="SDK 最大重试次数（默认 3）")
    args = parser.parse_args()

    source = args.source
    if args.biorxiv:
        source = "biorxiv"
    if args.medrxiv:
        source = "medrxiv"

    try:
        items = search(
            args.query,
            args.limit,
            source=source,
            token=args.token,
            categories=_split_csv(args.categories),
            authors=_split_csv(args.authors),
            orgs=_split_csv(args.orgs),
            min_citation=args.min_citation,
            date_from=args.date_from,
            date_to=args.date_to,
            date_search_type=args.date_search_type,
            date_str=_date_str_arg(args.date_str),
            use_fine_rerank=args.use_fine_rerank,
            offset=args.offset,
            timeout=args.timeout,
            max_retries=args.max_retries,
        )
        print_json(make_result(True, args.query, "deepxiv", items))
    except Exception as exc:
        print_json(make_result(False, args.query, "deepxiv", [], str(exc)))
        sys.exit(1)


if __name__ == "__main__":
    main()
