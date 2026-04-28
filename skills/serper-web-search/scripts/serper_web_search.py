#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any
from urllib import error, request


DEFAULT_BASE_URL = "https://google.serper.dev"
DEFAULT_TIMEOUT_SECONDS = 30


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Query Serper.dev for ranked web search results.",
    )
    parser.add_argument("query", help="Search query.")
    parser.add_argument("--num", type=int, default=5, help="Maximum number of results to request.")
    parser.add_argument("--gl", default="", help="Two-letter country code bias, for example 'us'.")
    parser.add_argument("--hl", default="", help="Language code bias, for example 'en'.")
    parser.add_argument("--page", type=int, default=1, help="Result page number.")
    parser.add_argument("--json", action="store_true", help="Print raw JSON instead of formatted text.")
    parser.add_argument(
        "--links-only",
        action="store_true",
        help="Print only organic result URLs, one per line.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Maximum number of printed results for links-only output. 0 means no extra truncation.",
    )
    return parser


def _require_search_enabled() -> str:
    api_key = os.environ.get("SERPER_API_KEY", "").strip()
    if api_key:
        return api_key
    raise SystemExit("Serper web search is unavailable in the current environment.")


def _build_payload(args: argparse.Namespace) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "q": args.query,
        "num": max(1, args.num),
        "page": max(1, args.page),
    }
    if args.gl:
        payload["gl"] = args.gl
    if args.hl:
        payload["hl"] = args.hl
    return payload


def _post_json(url: str, payload: dict[str, Any], api_key: str) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "X-API-KEY": api_key,
        },
        method="POST",
    )
    timeout = int(os.environ.get("SERPER_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS)))
    try:
        with request.urlopen(req, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
    except error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace").strip()
        raise SystemExit(f"Serper request failed with HTTP {exc.code}: {details}") from exc
    except error.URLError as exc:
        raise SystemExit(f"Serper request failed: {exc.reason}") from exc

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SystemExit("Serper returned invalid JSON.") from exc
    if not isinstance(data, dict):
        raise SystemExit("Serper returned an unexpected payload shape.")
    return data


def _format_search(data: dict[str, Any]) -> str:
    lines: list[str] = []
    answer_box = data.get("answerBox")
    if isinstance(answer_box, dict):
        title = str(answer_box.get("title") or "").strip()
        answer = str(answer_box.get("answer") or answer_box.get("snippet") or "").strip()
        link = str(answer_box.get("link") or "").strip()
        if title or answer:
            lines.append("Answer Box")
            if title:
                lines.append(f"Title: {title}")
            if answer:
                lines.append(f"Answer: {answer}")
            if link:
                lines.append(f"Link: {link}")
            lines.append("")

    knowledge_graph = data.get("knowledgeGraph")
    if isinstance(knowledge_graph, dict):
        title = str(knowledge_graph.get("title") or "").strip()
        description = str(knowledge_graph.get("description") or "").strip()
        website = str(knowledge_graph.get("website") or "").strip()
        if title or description:
            lines.append("Knowledge Graph")
            if title:
                lines.append(f"Title: {title}")
            if description:
                lines.append(f"Description: {description}")
            if website:
                lines.append(f"Website: {website}")
            lines.append("")

    organic = data.get("organic")
    if isinstance(organic, list) and organic:
        lines.append("Organic Results")
        for index, item in enumerate(organic, start=1):
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "").strip() or f"Result {index}"
            link = str(item.get("link") or "").strip()
            snippet = str(item.get("snippet") or "").strip()
            date = str(item.get("date") or "").strip()
            lines.append(f"{index}. {title}")
            if link:
                lines.append(f"   URL: {link}")
            if snippet:
                lines.append(f"   Snippet: {snippet}")
            if date:
                lines.append(f"   Date: {date}")
        lines.append("")

    people_also_ask = data.get("peopleAlsoAsk")
    if isinstance(people_also_ask, list) and people_also_ask:
        lines.append("People Also Ask")
        for index, item in enumerate(people_also_ask[:5], start=1):
            if not isinstance(item, dict):
                continue
            question = str(item.get("question") or "").strip()
            snippet = str(item.get("snippet") or "").strip()
            if question:
                lines.append(f"{index}. {question}")
                if snippet:
                    lines.append(f"   {snippet}")

    return "\n".join(line for line in lines if line is not None).strip() or "No search results returned."


def _print_links_only(data: dict[str, Any], limit: int) -> int:
    organic = data.get("organic")
    if not isinstance(organic, list):
        organic = []
    count = 0
    for item in organic:
        if not isinstance(item, dict):
            continue
        link = str(item.get("link") or "").strip()
        if not link:
            continue
        sys.stdout.write(link + "\n")
        count += 1
        if limit > 0 and count >= limit:
            break
    return 0


def main() -> int:
    args = _build_parser().parse_args()
    api_key = _require_search_enabled()
    base_url = os.environ.get("SERPER_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
    payload = _build_payload(args)
    data = _post_json(f"{base_url}/search", payload, api_key)

    if args.json:
        json.dump(data, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
        return 0
    if args.links_only:
        return _print_links_only(data, max(0, args.limit))

    sys.stdout.write(_format_search(data) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
