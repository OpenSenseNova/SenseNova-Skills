#!/usr/bin/env python3
"""Unified academic reference-tree entrypoint with provider fallback."""

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
from urllib.parse import unquote, urlparse


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from search_utils import print_json


DEFAULT_PROVIDER_TIMEOUT_SECONDS = 60
DEFAULT_SOURCES = ["semantic"]
DIRECTIONS = ["references", "citations"]


class ProviderConfig(NamedTuple):
    module_name: str
    provider: str
    source: str
    call_style: str


PROVIDER_GROUPS: dict[str, list[ProviderConfig]] = {
    "semantic": [
        ProviderConfig("semantic_scholar_refTree", "semantic_official", "semantic", "official"),
        ProviderConfig("semantic_scholar_crawler_refTree", "semantic_crawler", "semantic", "crawler"),
    ],
}

IDENTITY_FIELDS: dict[str, tuple[str, ...]] = {
    "semantic": ("paper_id", "doi", "arxiv_id", "url", "title"),
}


def ref_tree(
    paper_id: str,
    title: str,
    sources: Sequence[str] | str | None = None,
    direction: str | None = None,
    limit: int = 10,
    provider_timeout: float = DEFAULT_PROVIDER_TIMEOUT_SECONDS,
    api_key: str | None = None,
) -> dict[str, Any]:
    """Fetch references/citations from selected sources and return one result object."""
    clean_id = _normalize_required_text(paper_id, "paper_id")
    clean_title = _normalize_required_text(title, "title")
    clean_sources = _normalize_sources(sources)
    clean_direction = _normalize_direction(direction)
    clean_limit = _normalize_limit(limit)
    clean_provider_timeout = _normalize_timeout(provider_timeout)

    source_results = _search_sources_concurrently(
        clean_sources,
        clean_id,
        clean_title,
        clean_direction,
        clean_limit,
        clean_provider_timeout,
        api_key,
    )

    errors = [
        {
            "source": result["source"],
            "error": result["error"],
            "attempts": result["attempts"],
        }
        for result in source_results
        if result.get("error")
    ]
    success = any(result.get("success") for result in source_results)

    result: dict[str, Any] = {
        "success": success,
        "id": clean_id,
        "title": clean_title,
        "provider": "refTree.py",
        "sources": clean_sources,
        "direction": clean_direction or "all",
        "source_results": source_results,
        "errors": errors,
        "error": None if success else "All selected sources failed",
    }
    citation_count = _source_paper_citation_count(source_results)
    if citation_count is not None:
        result["citation_count"] = citation_count
    return result


def _search_sources_concurrently(
    sources: list[str],
    paper_id: str,
    title: str,
    direction: str | None,
    limit: int,
    provider_timeout: float,
    api_key: str | None,
) -> list[dict[str, Any]]:
    if not sources:
        return []

    results_by_source: dict[str, dict[str, Any]] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, len(sources)), thread_name_prefix="ref-tree-source") as executor:
        futures = {
            executor.submit(_search_source, source, paper_id, title, direction, limit, provider_timeout, api_key): source
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
                    "provider_rating": None,
                    "citations": [],
                    "references": [],
                    "attempts": [],
                    "error": _error_message(exc),
                }

    return [results_by_source[source] for source in sources]


def _search_source(
    source: str,
    paper_id: str,
    title: str,
    direction: str | None,
    limit: int,
    provider_timeout: float,
    api_key: str | None,
) -> dict[str, Any]:
    if source != "semantic":
        raise ValueError(f"不支持的搜索源：{source}")
    return _search_semantic_source(paper_id, title, direction, limit, provider_timeout, api_key)


def _search_semantic_source(
    paper_id: str,
    title: str,
    direction: str | None,
    limit: int,
    provider_timeout: float,
    api_key: str | None,
) -> dict[str, Any]:
    official, crawler = PROVIDER_GROUPS["semantic"]
    references: list[dict[str, Any]] = []
    citations: list[dict[str, Any]] = []
    attempts: list[dict[str, Any]] = []
    source_papers: list[dict[str, Any]] = []

    if direction:
        success, payload_or_error = _try_provider(official, paper_id, title, direction, limit, provider_timeout, api_key)
        attempts.append(_attempt_from_result(official, direction, success, payload_or_error))
        if success:
            items = _items_for_direction(payload_or_error, direction, official)
            if direction == "references":
                references = items
            else:
                citations = items
            source_papers.extend(_source_papers_from_payload(payload_or_error))
        else:
            success, payload_or_error = _try_provider(crawler, paper_id, title, direction, limit, provider_timeout, api_key)
            attempts.append(_attempt_from_result(crawler, direction, success, payload_or_error))
            if success:
                items = _items_for_direction(payload_or_error, direction, crawler)
                if direction == "references":
                    references = items
                else:
                    citations = items
                source_papers.extend(_source_papers_from_payload(payload_or_error))
        return _source_result("semantic", references, citations, attempts, source_papers)

    official_results = _call_directions_concurrently(
        official,
        paper_id,
        title,
        DIRECTIONS,
        limit,
        provider_timeout,
        api_key,
    )
    failed_directions: list[str] = []
    for current_direction in DIRECTIONS:
        success, payload_or_error = official_results[current_direction]
        attempts.append(_attempt_from_result(official, current_direction, success, payload_or_error))
        if success:
            items = _items_for_direction(payload_or_error, current_direction, official)
            if current_direction == "references":
                references = items
            else:
                citations = items
            source_papers.extend(_source_papers_from_payload(payload_or_error))
        else:
            failed_directions.append(current_direction)

    if len(failed_directions) == len(DIRECTIONS):
        success, payload_or_error = _try_provider(crawler, paper_id, title, None, limit, provider_timeout, api_key)
        attempts.append(_attempt_from_result(crawler, None, success, payload_or_error))
        if success:
            references = _items_for_direction(payload_or_error, "references", crawler)
            citations = _items_for_direction(payload_or_error, "citations", crawler)
            source_papers.extend(_source_papers_from_payload(payload_or_error))
    else:
        for failed_direction in failed_directions:
            success, payload_or_error = _try_provider(crawler, paper_id, title, failed_direction, limit, provider_timeout, api_key)
            attempts.append(_attempt_from_result(crawler, failed_direction, success, payload_or_error))
            if success:
                items = _items_for_direction(payload_or_error, failed_direction, crawler)
                if failed_direction == "references":
                    references = items
                else:
                    citations = items
                source_papers.extend(_source_papers_from_payload(payload_or_error))

    return _source_result("semantic", references, citations, attempts, source_papers)


def _call_directions_concurrently(
    provider: ProviderConfig,
    paper_id: str,
    title: str,
    directions: list[str],
    limit: int,
    provider_timeout: float,
    api_key: str | None,
) -> dict[str, tuple[bool, Any]]:
    results: dict[str, tuple[bool, Any]] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(directions), thread_name_prefix="ref-tree-direction") as executor:
        futures = {
            executor.submit(
                _call_provider_with_timeout,
                provider,
                paper_id,
                title,
                current_direction,
                limit,
                provider_timeout,
                api_key=api_key,
            ): current_direction
            for current_direction in directions
        }
        for future in concurrent.futures.as_completed(futures):
            current_direction = futures[future]
            try:
                payload = future.result()
            except (Exception, SystemExit) as exc:
                results[current_direction] = (False, exc)
                continue
            results[current_direction] = (_provider_succeeded(payload), payload)
    return results


def _try_provider(
    provider: ProviderConfig,
    paper_id: str,
    title: str,
    direction: str | None,
    limit: int,
    provider_timeout: float,
    api_key: str | None,
) -> tuple[bool, Any]:
    try:
        payload = _call_provider_with_timeout(
            provider,
            paper_id,
            title,
            direction,
            limit,
            provider_timeout,
            api_key=api_key,
        )
    except (Exception, SystemExit) as exc:
        return False, exc
    return _provider_succeeded(payload), payload


def _call_provider_with_timeout(
    provider: ProviderConfig,
    paper_id: str,
    title: str,
    direction: str | None,
    limit: int,
    timeout_seconds: float,
    api_key: str | None = None,
) -> dict[str, Any]:
    if timeout_seconds <= 0:
        return _call_provider(provider, paper_id, title, direction, limit, api_key=api_key)

    result_queue: queue.Queue[tuple[bool, Any]] = queue.Queue(maxsize=1)

    def run_provider() -> None:
        try:
            result_queue.put((True, _call_provider(provider, paper_id, title, direction, limit, api_key=api_key)))
        except BaseException as exc:
            result_queue.put((False, exc))

    thread = threading.Thread(
        target=run_provider,
        name=f"ref-tree-provider-{provider.provider}",
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
    paper_id: str,
    title: str,
    direction: str | None,
    limit: int,
    api_key: str | None = None,
) -> dict[str, Any]:
    module = importlib.import_module(provider.module_name)
    if provider.call_style == "official":
        if direction not in DIRECTIONS:
            raise ValueError("semantic_official requires direction: references or citations")
        return module.fetch_refs(
            paper_id,
            direction,
            limit,
            0,
            None,
            None,
            api_key,
        )

    if provider.call_style == "crawler":
        with tempfile.TemporaryDirectory(prefix=f"{provider.module_name}-") as tmpdir:
            output = Path(tmpdir) / "ref_tree_output.json"
            return _run_coro(
                module.crawl(
                    title=title,
                    output=output,
                    headless=True,
                    limit=limit,
                    max_pages=None,
                    direction=direction,
                )
            )

    raise ValueError(f"Unknown provider call style: {provider.call_style}")


def _run_coro(coro):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    raise RuntimeError("crawler providers cannot run inside an active asyncio event loop")


def _provider_succeeded(payload: Any) -> bool:
    data = _unwrap_provider_payload(payload)
    if not isinstance(data, dict):
        return False
    return data.get("success") is not False


def _attempt_from_result(
    provider: ProviderConfig,
    direction: str | None,
    success: bool,
    payload_or_error: Any,
) -> dict[str, Any]:
    return {
        "provider": provider.provider,
        "direction": direction,
        "success": success,
        "count": _payload_count(payload_or_error, direction) if success else 0,
        "error": None if success else _provider_error(payload_or_error),
    }


def _payload_count(payload: Any, direction: str | None) -> int:
    data = _unwrap_provider_payload(payload)
    if not isinstance(data, dict):
        return 0
    if direction in DIRECTIONS:
        return len(_raw_items_for_direction(data, direction))
    return len(_raw_items_for_direction(data, "references")) + len(_raw_items_for_direction(data, "citations"))


def _items_for_direction(payload: Any, direction: str, provider: ProviderConfig) -> list[dict[str, Any]]:
    data = _unwrap_provider_payload(payload)
    if not isinstance(data, dict):
        return []
    return _dedupe_source_items(
        [_normalize_item(item, provider) for item in _raw_items_for_direction(data, direction)],
        source=provider.source,
        limit=10**9,
    )


def _raw_items_for_direction(data: dict[str, Any], direction: str) -> list[dict[str, Any]]:
    if "items" in data and (data.get("direction") == direction or direction in DIRECTIONS):
        return list(data.get("items") or [])
    return list(data.get(direction) or [])


def _normalize_item(item: dict[str, Any], provider: ProviderConfig) -> dict[str, Any]:
    raw = dict(item or {})
    title = _as_text(raw.get("title")).strip()
    abstract = _as_text(
        raw.get("abstract")
        or raw.get("snippet")
        or raw.get("summary")
        or raw.get("tldr")
        or raw.get("abstract_or_tldr")
    ).strip()
    item_id = _item_id(raw, provider.source)
    citation_count = raw.get("citation_count")
    if citation_count is None:
        citation_count = raw.get("citationCount")

    normalized: dict[str, Any] = {
        "source": provider.source,
        "id": item_id,
        "title": title,
        "provider": provider.provider,
        "provider_rating": None,
        "citation_count": citation_count,
    }
    if abstract:
        normalized["abstract"] = abstract

    for key, value in raw.items():
        if key in normalized:
            if key == "source" and value and value != provider.source:
                normalized["provider_source"] = value
            continue
        if value in (None, "", [], {}):
            continue
        normalized[key] = value

    if provider.source == "semantic" and "paper_id" not in normalized:
        semantic_id = _semantic_id_from_url(raw.get("url"))
        if semantic_id:
            normalized["paper_id"] = semantic_id
    return normalized


def _item_id(item: dict[str, Any], source: str) -> str:
    for field in IDENTITY_FIELDS.get(source, ("doi", "url", "title")):
        value = item.get(field)
        if value in (None, "", [], {}):
            continue
        if field == "url" and source == "semantic":
            semantic_id = _semantic_id_from_url(value)
            if semantic_id:
                return semantic_id
        return _as_text(value).strip()
    return _normalize_identifier("title", item.get("title"))


def _dedupe_source_items(items: list[dict[str, Any]], source: str, limit: int) -> list[dict[str, Any]]:
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


def _dedupe_items_by_source(items: list[dict[str, Any]], limit_per_source: int) -> list[dict[str, Any]]:
    buckets: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        buckets.setdefault(_as_text(item.get("source")) or "unknown", []).append(item)

    deduped: list[dict[str, Any]] = []
    for source, source_items in buckets.items():
        deduped.extend(_dedupe_source_items(source_items, source, limit_per_source))
    return deduped


def _identity_key(item: dict[str, Any], source: str) -> str | None:
    fields = IDENTITY_FIELDS.get(source, ("doi", "url", "title"))
    for field in fields:
        value = item.get(field)
        if value in (None, "", [], {}):
            continue
        return f"{field}:{_normalize_identifier(field, value)}"
    fallback = item.get("id")
    if fallback not in (None, "", [], {}):
        return f"id:{_normalize_identifier('id', fallback)}"
    return None


def _normalize_identifier(field: str, value: Any) -> str:
    text = _as_text(value).strip().lower()
    if field == "url":
        return text.rstrip("/")
    if field == "doi":
        return text.removeprefix("https://doi.org/").removeprefix("http://doi.org/").removeprefix("doi:")
    if field == "arxiv_id":
        return re.sub(r"v\d+$", "", text.removeprefix("arxiv:"))
    if field in {"title", "id", "paper_id"}:
        return " ".join(text.split())
    return text


def _semantic_id_from_url(value: Any) -> str | None:
    text = _as_text(value).strip()
    if not text:
        return None
    parsed = urlparse(text)
    segments = [unquote(segment) for segment in parsed.path.split("/") if segment]
    if "paper" not in segments:
        return None
    index = segments.index("paper")
    candidates = segments[index + 1 :]
    if not candidates:
        return None
    return candidates[-1].strip()


def _source_result(
    source: str,
    references: list[dict[str, Any]],
    citations: list[dict[str, Any]],
    attempts: list[dict[str, Any]],
    source_papers: list[dict[str, Any]],
) -> dict[str, Any]:
    references = _dedupe_source_items(references, source=source, limit=10**9)
    citations = _dedupe_source_items(citations, source=source, limit=10**9)
    success = bool(references or citations) or any(attempt.get("success") for attempt in attempts)
    result: dict[str, Any] = {
        "source": source,
        "success": success,
        "provider": _provider_from_items(references + citations, attempts),
        "provider_rating": None,
        "citations": citations,
        "references": references,
        "attempts": attempts,
        "error": None if success else _combined_error(source, attempts),
    }
    citation_count = _source_paper_citation_count_from_papers(source_papers)
    if citation_count is not None:
        result["citation_count"] = citation_count
    return result


def _provider_from_items(items: list[dict[str, Any]], attempts: list[dict[str, Any]]) -> str | None:
    providers = sorted({_as_text(item.get("provider")) for item in items if item.get("provider")})
    if len(providers) == 1:
        return providers[0]
    if len(providers) > 1:
        return "mixed"
    for attempt in attempts:
        if attempt.get("success"):
            return _as_text(attempt.get("provider")) or None
    return None


def _source_papers_from_payload(payload: Any) -> list[dict[str, Any]]:
    data = _unwrap_provider_payload(payload)
    if not isinstance(data, dict):
        return []
    papers = []
    source_paper = data.get("source_paper")
    if isinstance(source_paper, dict):
        papers.append(source_paper)
    matched_paper = data.get("matched_paper")
    if isinstance(matched_paper, dict):
        papers.append(matched_paper)
    return papers


def _source_paper_citation_count(source_results: list[dict[str, Any]]) -> Any:
    for result in source_results:
        if result.get("citation_count") is not None:
            return result.get("citation_count")
    return None


def _source_paper_citation_count_from_papers(papers: list[dict[str, Any]]) -> Any:
    for paper in papers:
        for key in ("citation_count", "citationCount", "citations_count"):
            if paper.get(key) is not None:
                return paper.get(key)
    return None


def _unwrap_provider_payload(payload: Any) -> Any:
    if isinstance(payload, dict) and isinstance(payload.get("result"), dict):
        return payload["result"]
    return payload


def _provider_error(payload_or_error: Any) -> str:
    if isinstance(payload_or_error, BaseException):
        return _error_message(payload_or_error)
    data = _unwrap_provider_payload(payload_or_error)
    if isinstance(data, dict):
        error = data.get("error")
        if error:
            return _as_text(error)
    return "provider returned unsuccessful result"


def _combined_error(source: str, attempts: list[dict[str, Any]]) -> str:
    if not attempts:
        return f"No {source} provider was available"
    parts = [
        f"{attempt.get('provider')}[{attempt.get('direction') or 'all'}]: {attempt.get('error') or 'failed'}"
        for attempt in attempts
        if not attempt.get("success")
    ]
    return "; ".join(parts) or f"All {source} providers failed"


def _normalize_required_text(value: str | None, name: str) -> str:
    text = (value or "").strip()
    if not text:
        raise ValueError(f"{name} 不能为空")
    return text


def _normalize_direction(direction: str | None) -> str | None:
    if direction is None:
        return None
    clean_direction = direction.strip().lower()
    if clean_direction in ("", "all"):
        return None
    if clean_direction not in DIRECTIONS:
        raise ValueError("direction 只支持 references 或 citations")
    return clean_direction


def _normalize_limit(value: int | str) -> int:
    try:
        limit = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("limit 必须是正整数") from exc
    if limit <= 0:
        raise ValueError("limit 必须是正整数")
    return limit


def _normalize_timeout(value: float | int | str) -> float:
    try:
        timeout = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("provider_timeout 必须是数字") from exc
    if timeout < 0:
        raise ValueError("provider_timeout 不能小于 0")
    return timeout


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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="统一查询论文 references/citations refTree")
    parser.add_argument("--paper_id", required=True, help="论文 ID：S2 ID、DOI、ArXiv ID、PMID 等")
    parser.add_argument("--title", required=True, help="论文标题；crawler fallback 用于精确匹配")
    parser.add_argument(
        "--source",
        "--sources",
        "-s",
        action="append",
        help="搜索源：all, semantic；可重复或逗号分隔，默认 all",
    )
    parser.add_argument(
        "--direction",
        choices=DIRECTIONS,
        default=None,
        help="references 或 citations；不填则两者都搜",
    )
    parser.add_argument("--limit", "-n", type=int, default=10, help="每个搜索源每个方向返回数量（默认 10）")
    parser.add_argument("--output", "-o", help="将最终 JSON 结果写入指定文件")
    parser.add_argument("--api-key", help="Semantic Scholar API Key（只传给官方 provider）")
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
        result = ref_tree(
            args.paper_id,
            args.title,
            sources=sources,
            direction=args.direction,
            limit=args.limit,
            provider_timeout=args.provider_timeout,
            api_key=args.api_key,
        )
    except Exception as exc:
        result = {
            "success": False,
            "id": args.paper_id,
            "title": getattr(args, "title", ""),
            "provider": "refTree.py",
            "sources": sources,
            "direction": args.direction or "all",
            "source_results": [],
            "errors": [],
            "error": str(exc),
        }

    output_result = dict(result)
    if args.output:
        try:
            _write_output_file(output_result, args.output)
        except Exception as exc:
            output_result = dict(result)
            output_result["success"] = False
            output_result["error"] = f"Failed to write output file: {exc}"
            output_result["output_path"] = str(Path(args.output).expanduser().resolve())

    print_json(output_result)
    if not output_result["success"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
