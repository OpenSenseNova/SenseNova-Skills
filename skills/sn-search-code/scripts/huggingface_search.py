#!/usr/bin/env python3
"""HuggingFace 搜索：模型、数据集、Space。通过 HuggingFace Hub API。"""
from __future__ import annotations

import sys

from search_utils import build_parser, get_client, get_key, make_item, make_result, print_json


API_BASE = "https://huggingface.co/api"

SEARCH_TYPES = {
    "models": "models",
    "datasets": "datasets",
    "spaces": "spaces",
    "model": "models",    # 别名
    "dataset": "datasets", # 别名
    "space": "spaces",    # 别名
}

# 过滤掉无信息量的内部 tag（地区、部署、引用文献等）
_TAG_NOISE_PREFIXES = ("region:", "deploy:", "arxiv:", "dataset:", "endpoints_")


def search(query: str, limit: int, search_type: str = "models", token: str | None = None) -> list[dict]:
    """执行 HuggingFace 搜索。"""
    endpoint = SEARCH_TYPES.get(search_type, "models")
    url = f"{API_BASE}/{endpoint}"

    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    params = {
        "search": query,
        "limit": min(limit, 100),
        "full": "true",
    }

    with get_client(headers=headers) as client:
        resp = client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()

    items = []
    for item in data[:limit]:
        if endpoint == "models":
            items.append(_parse_model(item))
        elif endpoint == "datasets":
            items.append(_parse_dataset(item))
        elif endpoint == "spaces":
            items.append(_parse_space(item))
    return items


def _parse_model(item: dict) -> dict:
    model_id = item.get("id", "")
    tags = _filter_tags(item.get("tags", []))
    return make_item(
        title=model_id,
        url=f"https://huggingface.co/{model_id}",
        snippet=_model_snippet(item),
        pipeline_tag=item.get("pipeline_tag"),
        library=item.get("library_name"),
        downloads=item.get("downloads"),
        likes=item.get("likes"),
        tags=tags or None,
        last_modified=item.get("lastModified"),
    )


def _parse_dataset(item: dict) -> dict:
    dataset_id = item.get("id", "")
    description = (item.get("description") or "").strip()
    tags = _filter_tags(item.get("tags", []))
    return make_item(
        title=dataset_id,
        url=f"https://huggingface.co/datasets/{dataset_id}",
        snippet=description,
        downloads=item.get("downloads"),
        likes=item.get("likes"),
        tags=tags or None,
        last_modified=item.get("lastModified"),
    )


def _parse_space(item: dict) -> dict:
    space_id = item.get("id", "")
    tags = _filter_tags(item.get("tags", []))
    return make_item(
        title=space_id,
        url=f"https://huggingface.co/spaces/{space_id}",
        snippet=item.get("shortDescription") or "",
        sdk=item.get("sdk"),
        likes=item.get("likes"),
        tags=tags or None,
        last_modified=item.get("lastModified"),
    )


def _model_snippet(item: dict) -> str:
    """用 pipeline_tag + 关键 tag 拼出简短描述。"""
    parts = []
    if item.get("pipeline_tag"):
        parts.append(item["pipeline_tag"])
    if item.get("library_name"):
        parts.append(item["library_name"])
    # 保留语言 tag（如 en, zh）
    lang_tags = [t for t in (item.get("tags") or []) if len(t) <= 3 and t.isalpha()]
    if lang_tags:
        parts.append("lang:" + ",".join(lang_tags[:3]))
    return " | ".join(parts)


def _filter_tags(tags: list[str]) -> list[str]:
    """过滤掉无信息量的内部 tag。"""
    return [t for t in tags if not any(t.startswith(p) for p in _TAG_NOISE_PREFIXES)]


def main():
    parser = build_parser("搜索 HuggingFace 模型、数据集、Space")
    parser.add_argument("--type", "-t", default="models",
                        choices=list(SEARCH_TYPES.keys()),
                        help="搜索类型（默认 models）")
    parser.add_argument("--token", help="HuggingFace Token（也可通过 HF_TOKEN 环境变量设置，可选，提高限额）")
    args = parser.parse_args()

    token = get_key("HF_TOKEN", args.token)
    try:
        items = search(args.query, args.limit, args.type, token)
        print_json(make_result(True, args.query, "huggingface", items))
    except Exception as e:
        print_json(make_result(False, args.query, "huggingface", [], str(e)))
        sys.exit(1)


if __name__ == "__main__":
    main()
