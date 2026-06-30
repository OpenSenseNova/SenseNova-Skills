#!/usr/bin/env python3
"""Unified academic search entrypoint with source-specific provider fallback."""

from __future__ import annotations

import argparse
import asyncio
import concurrent.futures
import importlib
import json
import queue
import re
import sys
import tempfile
import threading
from pathlib import Path
from typing import Any, NamedTuple, Sequence


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from search_utils import print_json


DEFAULT_PROVIDER_TIMEOUT_SECONDS = 60


class ProviderConfig(NamedTuple):
    module_name: str
    provider: str
    source: str
    category_kwarg: str | None = None
    call_style: str = "search"
    lang_kwarg: str | None = None


DEFAULT_SOURCES = ["arxiv", "semantic", "google_scholar", "pubmed", "wikipedia"]

PROVIDER_GROUPS: dict[str, list[ProviderConfig]] = {
    "arxiv": [
        ProviderConfig("arxiv_search", "arxiv_official", "arxiv", category_kwarg="category"),
        ProviderConfig("deepxiv_search", "deepxiv", "arxiv", category_kwarg="categories"),
        ProviderConfig("openalex_search", "openalex", "arxiv"),
        ProviderConfig("arxiv_crawler_search", "arxiv_crawler", "arxiv", call_style="crawler"),
        ProviderConfig("crossref_search", "crossref", "arxiv"),
        ProviderConfig("arxiv_mirror_search", "arxiv_mirror", "arxiv", category_kwarg="category"),
    ],
    "semantic": [
        ProviderConfig("semantic_scholar_search", "semantic_scholar_official", "semantic"),
        ProviderConfig("semantic_scholar_crawler_search", "semantic_scholar_crawler", "semantic", call_style="crawler"),
    ],
    "google_scholar": [
        ProviderConfig("google_scholar_search", "google_scholar", "google_scholar", lang_kwarg="lang"),
    ],
    "pubmed": [
        ProviderConfig("pubmed_search", "pubmed", "pubmed"),
    ],
    "wikipedia": [
        ProviderConfig("wikipedia_search", "wikipedia", "wikipedia", lang_kwarg="lang"),
    ],
}

IDENTITY_FIELDS: dict[str, tuple[str, ...]] = {
    "arxiv": ("arxiv_id", "doi", "paper_id", "openalex_id", "url", "title"),
    "semantic": ("paper_id", "doi", "arxiv_id", "url", "title"),
    "google_scholar": ("scholar_id", "doi", "url", "title"),
    "pubmed": ("pmid", "doi", "pmc_id", "url", "title"),
    "wikipedia": ("page_id", "url", "title"),
}


def search(
    query: str,
    sources: Sequence[str] | str | None = None,
    limit: int = 10,
    category: str | None = None,
    provider_timeout: float = DEFAULT_PROVIDER_TIMEOUT_SECONDS,
    lang: str | None = None,
) -> dict[str, Any]:
    """Search selected logical sources and return one normalized result object."""
    clean_query = query.strip()
    if not clean_query:
        raise ValueError("query 不能为空")

    clean_sources = _normalize_sources(sources)
    clean_limit = max(0, int(limit))
    clean_provider_timeout = _normalize_timeout(provider_timeout)
    source_results = _search_sources_concurrently(
        clean_sources,
        clean_query,
        clean_limit,
        category,
        clean_provider_timeout,
        lang,
    )

    items: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for result in source_results:
        items.extend(result["items"])
        if result.get("error"):
            errors.append(
                {
                    "source": result["source"],
                    "error": result["error"],
                    "attempts": result["attempts"],
                }
            )

    success = any(result["success"] for result in source_results)
    return {
        "success": success,
        "query": clean_query,
        "provider": "search.py",
        "sources": clean_sources,
        "items": items,
        "source_results": source_results,
        "errors": errors,
        "error": None if success else "All selected sources failed",
    }


def _search_sources_concurrently(
    sources: list[str],
    query: str,
    limit: int,
    category: str | None,
    provider_timeout: float,
    lang: str | None,
) -> list[dict[str, Any]]:
    if not sources:
        return []

    results_by_source: dict[str, dict[str, Any]] = {}
    max_workers = max(1, len(sources))
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="search-source") as executor:
        futures = {
            executor.submit(_search_source, source, query, limit, category, provider_timeout, lang): source
            for source in sources
        }
        for future in concurrent.futures.as_completed(futures):
            source = futures[future]
            try:
                results_by_source[source] = future.result()
            except Exception as exc:
                results_by_source[source] = {
                    "source": source,
                    "success": False,
                    "provider": None,
                    "items": [],
                    "attempts": [],
                    "error": _error_message(exc),
                }

    return [results_by_source[source] for source in sources]


def _search_source(
    source: str,
    query: str,
    limit: int,
    category: str | None,
    provider_timeout: float,
    lang: str | None,
) -> dict[str, Any]:
    attempts: list[dict[str, Any]] = []
    first_empty_provider: str | None = None

    for provider in PROVIDER_GROUPS[source]:
        try:
            raw_items = _call_provider_with_timeout(provider, query, limit, category, provider_timeout, lang=lang)
        except (Exception, SystemExit) as exc:
            attempts.append(
                {
                    "provider": provider.provider,
                    "success": False,
                    "count": 0,
                    "error": _error_message(exc),
                }
            )
            continue

        normalized_items = _dedupe_source_items(
            [
                _normalize_item(item, provider)
                for item in raw_items
            ],
            source=source,
            limit=limit,
        )
        attempts.append(
            {
                "provider": provider.provider,
                "success": True,
                "count": len(normalized_items),
                "error": None,
            }
        )
        if normalized_items:
            return {
                "source": source,
                "success": True,
                "provider": provider.provider,
                "items": normalized_items,
                "attempts": attempts,
                "error": None,
            }
        if first_empty_provider is None:
            first_empty_provider = provider.provider

    if first_empty_provider is not None:
        return {
            "source": source,
            "success": True,
            "provider": first_empty_provider,
            "items": [],
            "attempts": attempts,
            "error": None,
        }

    error = "; ".join(
        f"{attempt['provider']}: {attempt['error']}"
        for attempt in attempts
        if attempt.get("error")
    ) or "No provider was available"
    return {
        "source": source,
        "success": False,
        "provider": None,
        "items": [],
        "attempts": attempts,
        "error": error,
    }


def _call_provider_with_timeout(
    provider: ProviderConfig,
    query: str,
    limit: int,
    category: str | None,
    timeout_seconds: float,
    lang: str | None = None,
) -> list[dict[str, Any]]:
    if timeout_seconds <= 0:
        return _call_provider(provider, query, limit, category, lang=lang)

    result_queue: queue.Queue[tuple[bool, Any]] = queue.Queue(maxsize=1)

    def run_provider() -> None:
        try:
            result_queue.put((True, _call_provider(provider, query, limit, category, lang=lang)))
        except BaseException as exc:
            result_queue.put((False, exc))

    thread = threading.Thread(
        target=run_provider,
        name=f"search-provider-{provider.provider}",
        daemon=True,
    )
    thread.start()
    thread.join(timeout_seconds)

    if thread.is_alive():
        raise TimeoutError(f"{provider.provider} timed out after {timeout_seconds:g}s")

    success, payload = result_queue.get_nowait()
    if success:
        return payload
    raise payload


def _call_provider(
    provider: ProviderConfig,
    query: str,
    limit: int,
    category: str | None,
    lang: str | None = None,
) -> list[dict[str, Any]]:
    if limit <= 0:
        return []

    module = importlib.import_module(provider.module_name)
    if provider.call_style == "crawler":
        return _call_crawler_provider(module, provider, query, limit)

    kwargs: dict[str, Any] = {}
    if category:
        if provider.category_kwarg == "category":
            kwargs["category"] = category
        elif provider.category_kwarg == "categories":
            kwargs["categories"] = [category]
    if lang and provider.lang_kwarg:
        kwargs[provider.lang_kwarg] = lang

    items = module.search(query, limit, **kwargs)
    return list(items or [])


def _call_crawler_provider(
    module: Any,
    provider: ProviderConfig,
    query: str,
    limit: int,
) -> list[dict[str, Any]]:
    with tempfile.TemporaryDirectory(prefix=f"{provider.module_name}-") as tmpdir:
        output = Path(tmpdir) / "search_output.json"
        result = _run_coro(
            module.crawl_search(
                query=query,
                output=output,
                headless=True,
                limit=limit,
            )
        )
    return list((result or {}).get("papers") or (result or {}).get("items") or [])


def _run_coro(coro):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    raise RuntimeError("crawler providers cannot run inside an active asyncio event loop")


def _normalize_item(item: dict[str, Any], provider: ProviderConfig) -> dict[str, Any]:
    raw = dict(item or {})
    title = _as_text(raw.get("title"))
    abstract = _as_text(
        raw.get("abstract")
        or raw.get("snippet")
        or raw.get("summary")
        or raw.get("tldr")
    )

    normalized: dict[str, Any] = {
        "source": provider.source,
        "provider": provider.provider,
        "provider_rating": None,
        "title": title,
        "abstract": abstract,
        "citation_count": raw.get("citation_count"),
    }

    for key, value in raw.items():
        if key in normalized:
            if key == "source" and value and value != provider.source:
                normalized["provider_source"] = value
            continue
        normalized[key] = value

    return normalized


def _dedupe_source_items(
    items: list[dict[str, Any]],
    source: str,
    limit: int,
) -> list[dict[str, Any]]:
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []

    for item in items:
        identity = _identity_key(item, source)
        if identity and identity in seen:
            continue
        if identity:
            seen.add(identity)
        deduped.append(item)
        if limit and len(deduped) >= limit:
            break

    return deduped


def _identity_key(item: dict[str, Any], source: str) -> str | None:
    fields = IDENTITY_FIELDS.get(source, ("doi", "url", "title"))
    for field in fields:
        value = item.get(field)
        if value in (None, "", [], {}):
            continue
        return f"{field}:{_normalize_identifier(field, value)}"
    return None


def _normalize_identifier(field: str, value: Any) -> str:
    text = _as_text(value).strip().lower()
    if field == "url":
        return text.rstrip("/")
    if field == "arxiv_id":
        text = text.replace("arxiv:", "")
        return re.sub(r"v\d+$", "", text)
    if field == "doi":
        return text.removeprefix("https://doi.org/").removeprefix("http://doi.org/")
    if field == "title":
        return " ".join(text.split())
    return text


def _normalize_sources(sources: Sequence[str] | str | None) -> list[str]:
    if sources is None:
        return list(DEFAULT_SOURCES)

    values = [sources] if isinstance(sources, str) else list(sources)
    selected: list[str] = []
    for value in values:
        for part in str(value).split(","):
            source = part.strip().lower()
            if not source:
                continue
            if source == "all":
                return list(DEFAULT_SOURCES)
            selected.append(source)

    if not selected:
        return list(DEFAULT_SOURCES)

    invalid = [source for source in selected if source not in PROVIDER_GROUPS]
    if invalid:
        allowed = ", ".join(["all", *DEFAULT_SOURCES])
        raise ValueError(f"不支持的搜索源：{', '.join(invalid)}；支持：{allowed}")

    unique: list[str] = []
    seen: set[str] = set()
    for source in selected:
        if source in seen:
            continue
        unique.append(source)
        seen.add(source)
    return unique


def _normalize_timeout(value: float | int | str) -> float:
    try:
        timeout = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("provider_timeout 必须是数字") from exc
    if timeout < 0:
        raise ValueError("provider_timeout 不能小于 0")
    return timeout


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return " ".join(_as_text(item) for item in value if _as_text(item))
    return str(value)


def _error_message(exc: BaseException) -> str:
    message = str(exc)
    if message:
        return message
    code = getattr(exc, "code", None)
    if code is not None:
        return str(code)
    return exc.__class__.__name__


def _normalize_output_result(result: dict[str, Any]) -> dict[str, Any]:
    output_result = dict(result)
    output_result.pop("items", None)
    return output_result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="统一搜索学术论文/百科源")
    parser.add_argument("query", help="搜索关键词")
    parser.add_argument(
        "--source",
        "--sources",
        "-s",
        action="append",
        help="搜索源：all, arxiv, semantic, google_scholar, pubmed, wikipedia；可重复或逗号分隔，默认 all",
    )
    parser.add_argument("--limit", "-n", type=int, default=10, help="每个搜索源返回数量（默认 10）")
    parser.add_argument("--category", "-c", help="ArXiv 分类过滤（只传给支持该参数的 provider）")
    parser.add_argument("--lang", "-l", help="语言提示；只传给支持 lang 的 provider（Wikipedia/Google Scholar）")
    parser.add_argument("--output", "-o", help="将最终 JSON 结果写入指定文件")
    parser.add_argument(
        "--provider-timeout",
        type=float,
        default=DEFAULT_PROVIDER_TIMEOUT_SECONDS,
        help="每个 provider 调用的超时时间，单位秒（默认 60；设为 0 表示不限制）",
    )
    return parser


def _write_output_file(result: dict[str, Any], output_path: str) -> None:
    path = Path(output_path).expanduser().resolve()
    result["output_path"] = str(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        sources = _normalize_sources(args.source)
    except ValueError as exc:
        parser.error(str(exc))

    try:
        result = search(
            args.query,
            sources=sources,
            limit=args.limit,
            category=args.category,
            provider_timeout=args.provider_timeout,
            lang=args.lang,
        )
    except Exception as exc:
        result = {
            "success": False,
            "query": getattr(args, "query", ""),
            "provider": "search.py",
            "sources": sources,
            "items": [],
            "source_results": [],
            "errors": [],
            "error": str(exc),
        }

    output_result = _normalize_output_result(result)
    write_failed = False
    if args.output:
        try:
            _write_output_file(output_result, args.output)
        except Exception as exc:
            write_failed = True
            output_result = _normalize_output_result({
                "success": False,
                "query": getattr(args, "query", ""),
                "provider": "search.py",
                "sources": sources,
                "items": [],
                "source_results": [],
                "errors": [],
                "error": f"Failed to write output file: {exc}",
                "output_path": str(Path(args.output).expanduser().resolve()),
            })

    print_json(output_result)
    if write_failed or not result["success"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
