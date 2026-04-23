#!/usr/bin/env python3
"""GitHub 搜索：仓库、代码、Issue。通过 GitHub REST API。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "_search-common"))

from search_utils import build_parser, get_client, get_key, make_item, make_result, print_json


API_BASE = "https://api.github.com/search"

# 搜索类型 -> API 路径
SEARCH_TYPES = {
    "repositories": "repositories",
    "code": "code",
    "issues": "issues",
    "repo": "repositories",  # 别名
    "issue": "issues",       # 别名
}


def search(query: str, limit: int, search_type: str = "repositories", token: str | None = None) -> list[dict]:
    """执行 GitHub 搜索。"""
    endpoint = SEARCH_TYPES.get(search_type, "repositories")
    url = f"{API_BASE}/{endpoint}"

    headers = {"Accept": "application/vnd.github.v3+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    params = {
        "q": query,
        "per_page": min(limit, 100),
        "sort": "best match",
    }

    with get_client(headers=headers) as client:
        resp = client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()

    items = []
    for item in data.get("items", [])[:limit]:
        if endpoint == "repositories":
            items.append(make_item(
                title=item.get("full_name", ""),
                url=item.get("html_url", ""),
                snippet=item.get("description") or "",
                stars=item.get("stargazers_count", 0),
                language=item.get("language"),
                updated_at=item.get("updated_at"),
            ))
        elif endpoint == "code":
            repo = item.get("repository", {})
            items.append(make_item(
                title=item.get("name", ""),
                url=item.get("html_url", ""),
                snippet=f"{repo.get('full_name', '')} - {item.get('path', '')}",
                repo=repo.get("full_name"),
                path=item.get("path"),
            ))
        elif endpoint == "issues":
            items.append(make_item(
                title=item.get("title", ""),
                url=item.get("html_url", ""),
                snippet=_truncate(item.get("body") or "", 200),
                state=item.get("state"),
                comments=item.get("comments", 0),
                created_at=item.get("created_at"),
            ))
    return items


def _truncate(text: str, max_len: int) -> str:
    return text[:max_len] + "..." if len(text) > max_len else text


def main():
    parser = build_parser("搜索 GitHub 仓库、代码、Issue")
    parser.add_argument("--type", "-t", default="repositories",
                        choices=list(SEARCH_TYPES.keys()),
                        help="搜索类型（默认 repositories）")
    parser.add_argument("--token", help="GitHub Token（也可通过 GITHUB_TOKEN 环境变量设置）")
    args = parser.parse_args()

    token = get_key("GITHUB_TOKEN", args.token)
    try:
        items = search(args.query, args.limit, args.type, token)
        print_json(make_result(True, args.query, "github", items))
    except Exception as e:
        print_json(make_result(False, args.query, "github", [], str(e)))
        sys.exit(1)


if __name__ == "__main__":
    main()
