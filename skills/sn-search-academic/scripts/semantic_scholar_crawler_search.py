#!/usr/bin/env python3
"""Semantic Scholar search-result crawler.

Usage:
    python3 semantic_scholar_crawler_search.py --query "qwen"
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from semantic_scholar_crawler_refTree import (
    BASE_URL,
    create_page,
    dismiss_popups,
    extract_quote_count,
    parse_card_text,
    parse_limit,
    strip_raw_text,
)


DEFAULT_QUERY = "qwen"


def format_stdout_result(result: dict[str, Any]) -> str:
    return json.dumps(result, ensure_ascii=False, indent=2)


def format_cli_stdout(result: dict[str, Any], output_path: str) -> str:
    return json.dumps(
        {
            "output": str(Path(output_path).resolve()),
            "result": result,
        },
        ensure_ascii=False,
        indent=2,
    )


def extract_search_citation_count(raw_text: str) -> int | None:
    quoted = extract_quote_count(raw_text)
    if quoted is not None:
        return quoted
    match = re.search(r"\bExpand\s+([0-9][0-9,]*)\s+(?:\[PDF\]|PDF|arXiv|Save|Cite)(?=\s|$)", raw_text or "", flags=re.I)
    if match:
        return int(match.group(1).replace(",", ""))
    return None


def format_search_row(row: dict[str, Any]) -> dict[str, Any]:
    raw_text = row.get("raw_text") or ""
    title = row.get("title") or ""
    parsed = parse_card_text(raw_text, title)
    return {
        "title": title,
        "url": row.get("url"),
        "citation_count": extract_search_citation_count(raw_text),
        **parsed,
        "raw_text": raw_text,
    }


async def wait_for_search_results(page) -> None:
    await page.wait_for_selector('a[href*="/paper/"]', timeout=30000)


async def settle_search_results(page, limit: int | None, max_rounds: int = 40) -> None:
    previous = -1
    stable_rounds = 0
    for _ in range(max_rounds):
        count = await page.locator('a[href*="/paper/"]').count()
        if limit and count >= limit:
            return
        if count == previous:
            stable_rounds += 1
        else:
            stable_rounds = 0
            previous = count
        if stable_rounds >= 4:
            return
        await page.mouse.wheel(0, 1800)
        await page.wait_for_timeout(1000)


async def extract_search_results(page, limit: int | None) -> list[dict[str, Any]]:
    rows = await page.evaluate(
        """() => {
            const normalize = (s) => (s || '').replace(/\\s+/g, ' ').trim();
            const absolute = (href) => new URL(href, location.origin).href;
            const chooseCard = (anchor) => {
                let best = anchor;
                let node = anchor;
                for (let i = 0; node && i < 8; i += 1, node = node.parentElement) {
                    const text = normalize(node.innerText || node.textContent);
                    if (!text.includes(normalize(anchor.innerText || anchor.textContent))) continue;
                    if (text.length > 80 && text.length < 5000) best = node;
                    if (/TLDR|Save|Cite|PDF|arXiv|Excerpts?/i.test(text) && text.length < 5000) {
                        best = node;
                    }
                }
                return best;
            };

            const seen = new Set();
            const papers = [];
            for (const a of [...document.querySelectorAll('a[href*="/paper/"]')]) {
                const href = a.getAttribute('href');
                const title = normalize(a.innerText || a.textContent);
                if (!href || !title || href.includes('/figure/')) continue;
                if (/^[0-9][0-9,]*$/.test(title)) continue;
                if (/^(PDF|arXiv|Save|Cite)$/i.test(title)) continue;
                const url = absolute(href).split('#')[0];
                if (seen.has(url)) continue;
                seen.add(url);
                const card = chooseCard(a);
                papers.push({
                    title,
                    url,
                    raw_text: normalize(card.innerText || card.textContent)
                });
            }
            return papers;
        }"""
    )

    results: list[dict[str, Any]] = []
    for row in rows:
        results.append(format_search_row(row))
        if limit and len(results) >= limit:
            break
    return results


async def crawl_search(query: str, output: Path, headless: bool, limit: int | None) -> dict[str, Any]:
    playwright, browser, context, page = await create_page(headless=headless)
    try:
        search_url = f"{BASE_URL}/search?q={quote_plus(query)}&sort=relevance"
        await page.goto(search_url, wait_until="domcontentloaded")
        await page.wait_for_load_state("networkidle", timeout=30000)
        await dismiss_popups(page)
        await wait_for_search_results(page)
        await settle_search_results(page, limit)
        papers = await extract_search_results(page, limit)

        result = {
            "query": query,
            "search_url": search_url,
            "results_count": len(papers),
            "papers": papers,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        cleaned_result = strip_raw_text(result)
        output.write_text(format_stdout_result(cleaned_result), encoding="utf-8")
        return cleaned_result
    finally:
        await browser.close()
        await playwright.stop()


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Crawl Semantic Scholar search results.")
    parser.add_argument("--query", default=DEFAULT_QUERY, help="Search query.")
    parser.add_argument("--output", default="semantic_scholar_search_output.json", help="JSON output path.")
    parser.add_argument("--limit", default="10", help="Maximum papers to collect, or 'all'. Defaults to 10.")
    parser.add_argument("--headless", choices=["true", "false"], default="true", help="Run Camoufox headless.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    result = asyncio.run(
        crawl_search(
            query=args.query,
            output=Path(args.output),
            headless=args.headless == "true",
            limit=parse_limit(args.limit),
        )
    )
    print(format_cli_stdout(result, args.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
