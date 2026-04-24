#!/usr/bin/env python3
"""知乎搜索。通过知乎内部 API（需要 cookie 认证）。"""
from __future__ import annotations

import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "_search-common"))

from search_utils import build_parser, get_client, get_key, make_item, make_result, print_json

# 正文内联截断长度（超出部分存文件）
_CONTENT_INLINE_LIMIT = 2000


SEARCH_URL = "https://www.zhihu.com/api/v4/search_v3"

# 广告类型，对研究无价值，直接过滤
_AD_TYPES = {"education", "knowledge_ad"}


def search(query: str, limit: int, cookie: str | None = None, search_type: str = "general") -> list[dict]:
    """执行知乎搜索。"""
    if not cookie:
        raise ValueError("需要 ZHIHU_COOKIE 环境变量。请从浏览器开发者工具获取知乎 cookie。")

    headers = {
        "Cookie": cookie,
        "Referer": "https://www.zhihu.com/search",
        "Origin": "https://www.zhihu.com",
        "Accept": "application/json",
    }

    params = {
        "q": query,
        "t": search_type,
        "offset": 0,
        # 多请求一些以弥补过滤掉广告条目的损失
        "limit": min(limit * 2, 20),
    }

    with get_client(headers=headers) as client:
        resp = client.get(SEARCH_URL, params=params)
        resp.raise_for_status()
        data = resp.json()

    items = []
    for entry in data.get("data", []):
        if len(items) >= limit:
            break
        if entry.get("type") in _AD_TYPES:
            continue

        obj = entry.get("object", {}) or entry
        obj_type = obj.get("type", "")

        item = _parse_object(obj, obj_type)
        if item:
            items.append(item)

    return items


def _parse_object(obj: dict, obj_type: str) -> dict | None:
    """将 API 返回的 object 解析为标准条目。"""
    title = _strip_html(obj.get("title") or obj.get("name") or "")
    snippet = _strip_html(obj.get("excerpt") or obj.get("description") or "")[:300]
    full_content = _strip_html(obj.get("content") or "")
    content, content_file = _maybe_save_content(full_content, obj_type, obj.get("id", ""))

    url = _build_url(obj, obj_type)

    # 作者信息
    author_obj = obj.get("author", {})
    author_name = author_obj.get("name", "") if isinstance(author_obj, dict) else ""
    author_headline = author_obj.get("headline", "") if isinstance(author_obj, dict) else ""
    author_followers = author_obj.get("follower_count") if isinstance(author_obj, dict) else None

    # 互动数据
    voteup = obj.get("voteup_count") or 0
    comment = obj.get("comment_count") or 0
    favorites = obj.get("favorites_count") or obj.get("zfav_count") or 0
    visits = obj.get("visits_count")  # answer 特有

    # 时间（转为 ISO 8601，方便 agent 判断时效性）
    created_at = _ts_to_iso(obj.get("created_time"))
    updated_at = _ts_to_iso(obj.get("updated_time"))

    # answer 专属：所属问题的标题和链接
    question_title = ""
    question_url = ""
    answer_count = None
    if obj_type == "answer":
        q = obj.get("question", {})
        question_title = _strip_html(q.get("name") or q.get("title") or "")
        qid = q.get("id", "")
        question_url = f"https://www.zhihu.com/question/{qid}" if qid else ""
        answer_count = obj.get("answer_count")
        # answer 没有独立 title，用问题标题补充
        if not title:
            title = question_title

    # question 专属
    if obj_type == "question":
        answer_count = obj.get("answer_count")

    if not title and not snippet:
        return None

    return make_item(
        title=title,
        url=url,
        snippet=snippet,
        content=content,
        content_file=content_file,
        content_type=obj_type,
        author=author_name,
        author_headline=author_headline,
        author_followers=author_followers,
        voteup_count=voteup,
        comment_count=comment,
        favorites_count=favorites if favorites else None,
        visits_count=visits,
        answer_count=answer_count,
        question_title=question_title if obj_type == "answer" else None,
        question_url=question_url if obj_type == "answer" else None,
        created_at=created_at,
        updated_at=updated_at,
    )


def _maybe_save_content(full_content: str, obj_type: str, obj_id: str) -> tuple[str, str | None]:
    """处理正文：短内容直接返回，长内容截断并将完整版存为临时文件。

    返回 (inline_content, file_path)，file_path 为 None 表示未截断。
    """
    if not full_content:
        return "", None

    if len(full_content) <= _CONTENT_INLINE_LIMIT:
        return full_content, None

    # 超出截断限制，写入临时文件
    suffix = f"_zhihu_{obj_type}_{obj_id}.txt"
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", suffix=suffix, delete=False
    ) as f:
        f.write(full_content)
        fpath = f.name

    inline = (
        full_content[:_CONTENT_INLINE_LIMIT]
        + f"\n\n[内容已截断，共 {len(full_content)} 字，完整内容见: {fpath}]"
    )
    return inline, fpath


def _build_url(obj: dict, obj_type: str) -> str:
    """构造面向用户的 Web URL（而非 API URL）。"""
    oid = obj.get("id", "")
    if obj_type == "article":
        return f"https://zhuanlan.zhihu.com/p/{oid}" if oid else ""
    if obj_type == "answer":
        q = obj.get("question", {})
        qid = q.get("id", "")
        return f"https://www.zhihu.com/question/{qid}/answer/{oid}" if qid and oid else ""
    if obj_type == "question":
        return f"https://www.zhihu.com/question/{oid}" if oid else ""
    # 其他类型直接返回 obj 里的 url（若有）
    raw = obj.get("url", "")
    # 将 api.zhihu.com 替换为 www.zhihu.com
    return raw.replace("https://api.zhihu.com/", "https://www.zhihu.com/")


def _strip_html(html: str) -> str:
    return re.sub(r"<[^>]+>", "", html).strip()


def _ts_to_iso(ts: int | None) -> str | None:
    if not ts:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main():
    parser = build_parser("搜索知乎问答和文章")
    parser.add_argument("--cookie", help="知乎 Cookie（也可通过 ZHIHU_COOKIE 环境变量设置）")
    parser.add_argument("--type", default="general",
                        choices=["general", "topic", "people", "zvideo"],
                        help="搜索类型（默认 general）")
    args = parser.parse_args()

    cookie = get_key("ZHIHU_COOKIE", args.cookie)
    try:
        items = search(args.query, args.limit, cookie, args.type)
        print_json(make_result(True, args.query, "zhihu", items))
    except Exception as e:
        print_json(make_result(False, args.query, "zhihu", [], str(e)))
        sys.exit(1)


if __name__ == "__main__":
    main()
