#!/usr/bin/env python3
"""Search public GitHub repositories or issues without tokens."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from search_utils import get_client, make_item, make_result, print_json
from _filters import CryptoQueryError, filter_crypto_items, reject_crypto_query


API_BASE = "https://api.github.com/search"


def _truncate(text: str, max_len: int = 240) -> str:
    return text[:max_len] + "..." if len(text) > max_len else text


def search(query: str, limit: int, search_type: str = "repositories", sort: str | None = None, order: str = "desc") -> list[dict]:
    reject_crypto_query(query)
    endpoint = "repositories" if search_type in ("repositories", "repo") else "issues"
    params: dict[str, str | int] = {
        "q": query,
        "per_page": min(max(limit * 2, limit), 100),
        "order": order,
    }
    if sort:
        params["sort"] = sort

    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    with get_client(headers=headers) as client:
        resp = client.get(f"{API_BASE}/{endpoint}", params=params)
        resp.raise_for_status()
        data = resp.json()

    items = []
    for row in data.get("items", []):
        if endpoint == "repositories":
            item = make_item(
                title=row.get("full_name", ""),
                url=row.get("html_url", ""),
                snippet=row.get("description") or "",
                stars=row.get("stargazers_count", 0),
                forks=row.get("forks_count", 0),
                language=row.get("language"),
                open_issues=row.get("open_issues_count"),
                created_at=row.get("created_at"),
                updated_at=row.get("updated_at"),
                pushed_at=row.get("pushed_at"),
            )
        else:
            repo_url = row.get("repository_url", "")
            repo = repo_url.rsplit("/", 2)[-2:] if repo_url else []
            item = make_item(
                title=row.get("title", ""),
                url=row.get("html_url", ""),
                snippet=_truncate(row.get("body") or ""),
                state=row.get("state"),
                comments=row.get("comments", 0),
                created_at=row.get("created_at"),
                updated_at=row.get("updated_at"),
                repository="/".join(repo) if repo else None,
            )
        if filter_crypto_items([item]):
            items.append(item)
        if len(items) >= limit:
            break
    return items


def main() -> None:
    parser = argparse.ArgumentParser(description="搜索 GitHub 公共仓库或 Issue（免费、免 API key；不支持 code search）")
    parser.add_argument("query", help="搜索关键词；加密货币/区块链/Web3 相关查询会被拒绝")
    parser.add_argument("--limit", "-n", type=int, default=10, help="返回结果数量（默认 10）")
    parser.add_argument("--type", "-t", default="repositories", choices=["repositories", "repo", "issues", "issue"], help="搜索类型")
    parser.add_argument("--sort", choices=["stars", "forks", "help-wanted-issues", "updated", "comments", "created"], help="排序字段")
    parser.add_argument("--order", default="desc", choices=["asc", "desc"], help="排序方向")
    args = parser.parse_args()

    try:
        items = search(args.query, args.limit, args.type, args.sort, args.order)
        print_json(make_result(True, args.query, "github-public", items))
    except CryptoQueryError as exc:
        print_json(make_result(False, args.query, "github-public", [], str(exc)))
        sys.exit(2)
    except Exception as exc:
        print_json(make_result(False, args.query, "github-public", [], str(exc)))
        sys.exit(1)


if __name__ == "__main__":
    main()
