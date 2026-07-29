#!/usr/bin/env python3
"""Twitter/X 搜索。支持 Xquik 与 TikHub。"""

import sys


from search_utils import build_parser, get_client, get_key, make_item, make_result, print_json


TIKHUB_BASE = "https://api.tikhub.io"
TIKHUB_SEARCH_ENDPOINT = "/api/v1/twitter/web/fetch_search_timeline"
XQUIK_SEARCH_URL = "https://xquik.com/api/v1/x/tweets/search"


def search_tikhub(
    query: str,
    limit: int,
    token: str | None = None,
    client_factory=get_client,
) -> list[dict]:
    """通过 TikHub 执行 Twitter 搜索。"""
    if not token:
        raise ValueError("需要 TIKHUB_TOKEN 环境变量。请到 tikhub.io 注册获取。")

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }

    params = {
        "keyword": query,
        "search_type": "Latest",
    }

    with client_factory(timeout=30, headers=headers) as client:
        resp = client.get(f"{TIKHUB_BASE}{TIKHUB_SEARCH_ENDPOINT}", params=params)
        resp.raise_for_status()
        data = resp.json()

    # 解析 TikHub 返回结构
    items = []
    results = data.get("data", {}).get("data", [])
    if isinstance(results, dict):
        results = results.get("data", [])

    for tweet in results[:limit]:
        content = tweet.get("content", {}) if isinstance(tweet, dict) else {}
        if not content:
            content = tweet

        text = content.get("full_text") or content.get("text") or ""
        user = content.get("user", {}) or {}
        screen_name = user.get("screen_name", "")
        tweet_id = content.get("id_str") or content.get("rest_id") or ""
        url = f"https://x.com/{screen_name}/status/{tweet_id}" if screen_name and tweet_id else ""

        items.append(make_item(
            title=f"@{screen_name}" if screen_name else "",
            url=url,
            snippet=text[:500],
            author=user.get("name"),
            screen_name=screen_name,
            favorite_count=content.get("favorite_count"),
            retweet_count=content.get("retweet_count"),
            created_at=content.get("created_at"),
            source="tikhub",
        ))

    return items


def search_xquik(
    query: str,
    limit: int,
    api_key: str | None = None,
    client_factory=get_client,
) -> list[dict]:
    """通过 Xquik 执行 Twitter 搜索。"""
    if not api_key:
        raise ValueError("需要 XQUIK_API_KEY 环境变量。请在 Xquik 创建 API key。")
    if limit < 1:
        raise ValueError("limit 必须大于 0。")

    headers = {"x-api-key": api_key, "Accept": "application/json"}
    requested_limit = min(limit, 10_000)
    params = {"q": query, "limit": requested_limit, "queryType": "Latest"}

    with client_factory(timeout=30, headers=headers) as client:
        resp = client.get(XQUIK_SEARCH_URL, params=params)
        resp.raise_for_status()
        data = resp.json()

    tweets = data.get("tweets", [])
    if not isinstance(tweets, list):
        raise ValueError("Xquik 返回了无效的 tweets 字段。")

    items = []
    for tweet in tweets[:requested_limit]:
        if not isinstance(tweet, dict):
            continue

        author = tweet.get("author") or {}
        if not isinstance(author, dict):
            author = {}
        username = author.get("username", "")
        tweet_id = tweet.get("id", "")
        url = tweet.get("url") or (
            f"https://x.com/{username}/status/{tweet_id}"
            if username and tweet_id
            else ""
        )

        items.append(
            make_item(
                title=f"@{username}" if username else "",
                url=url,
                snippet=str(tweet.get("text") or "")[:500],
                author=author.get("name"),
                screen_name=username,
                tweet_id=tweet_id,
                favorite_count=tweet.get("likeCount"),
                retweet_count=tweet.get("retweetCount"),
                reply_count=tweet.get("replyCount"),
                view_count=tweet.get("viewCount"),
                created_at=tweet.get("createdAt"),
                source="xquik",
            )
        )

    return items


def search(
    query: str,
    limit: int,
    token: str | None = None,
    provider: str = "tikhub",
    api_key: str | None = None,
    client_factory=get_client,
) -> list[dict]:
    """通过指定提供方执行 Twitter 搜索。"""
    if provider == "xquik":
        return search_xquik(query, limit, api_key, client_factory)
    if provider == "tikhub":
        return search_tikhub(query, limit, token, client_factory)
    raise ValueError(f"不支持的 Twitter 搜索提供方：{provider}")


def main():
    parser = build_parser("搜索 Twitter/X 推文")
    parser.add_argument(
        "--provider",
        choices=["tikhub", "xquik"],
        default="tikhub",
        help="搜索提供方（默认 tikhub）",
    )
    parser.add_argument("--token", help="TikHub Token（也可通过 TIKHUB_TOKEN 环境变量设置）")
    parser.add_argument(
        "--api-key", help="Xquik API Key（也可通过 XQUIK_API_KEY 环境变量设置）"
    )
    args = parser.parse_args()

    token = get_key("TIKHUB_TOKEN", args.token)
    api_key = get_key("XQUIK_API_KEY", args.api_key)
    try:
        items = search(
            args.query,
            args.limit,
            token,
            provider=args.provider,
            api_key=api_key,
        )
        print_json(make_result(True, args.query, "twitter", items))
    except Exception as e:
        print_json(make_result(False, args.query, "twitter", [], str(e)))
        sys.exit(1)


if __name__ == "__main__":
    main()
