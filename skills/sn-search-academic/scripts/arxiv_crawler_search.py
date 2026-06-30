#!/usr/bin/env python3
"""arXiv search-result crawler using Camoufox browser disguise.

Usage:
    python3 arxiv_crawler_search.py --query "qwen"
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus


BASE_URL = "https://arxiv.org"
DEFAULT_QUERY = "qwen"


def parse_limit(value: str | None) -> int | None:
    if value is None or value == "":
        return 10
    if value.lower() == "all":
        return None
    try:
        limit = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("--limit must be a positive integer or 'all'") from exc
    if limit <= 0:
        raise argparse.ArgumentTypeError("--limit must be a positive integer or 'all'")
    return limit


def ancestors_from(path: Path) -> list[Path]:
    resolved = path.resolve()
    start = resolved.parent if resolved.is_file() or resolved.suffix else resolved
    return [start, *start.parents]


def has_camoufox_js(directory: Path) -> bool:
    return (directory / "node_modules" / "camoufox-js").exists()


def find_upwards(start: Path) -> Path | None:
    for directory in ancestors_from(start):
        if has_camoufox_js(directory):
            return directory
    return None


def find_camoufox_project_root(
    script_path: Path | None = None,
    env: dict[str, str] | None = None,
    cwd: Path | None = None,
) -> Path:
    env = env or os.environ
    script_path = script_path or Path(__file__)
    cwd = cwd or Path.cwd()

    npm_package_json = env.get("npm_package_json")
    candidates: list[Path] = []
    if npm_package_json:
        candidates.append(Path(npm_package_json))
    candidates.extend([script_path, cwd])

    for candidate in candidates:
        root = find_upwards(candidate)
        if root:
            return root

    raise SystemExit(
        "Could not find node_modules/camoufox-js. Search order:\n"
        "  1. npm_package_json directory and parents\n"
        "  2. crawler script directory and parents\n"
        "  3. current working directory and parents\n"
        "Install camoufox-js in the current or an ancestor npm project, for example: npm install camoufox-js"
    )


def host_os_name() -> str:
    if sys.platform == "darwin":
        return "macos"
    if sys.platform.startswith("linux"):
        return "linux"
    if sys.platform.startswith("win"):
        return "windows"
    return "macos"


def normalize_space(value: str | None) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def camoufox_launch_options_script(headless: bool, os_name: str | None = None) -> str:
    headless_js = "true" if headless else "false"
    os_js = json.dumps(os_name or host_os_name())
    return (
        "import { launchOptions } from 'camoufox-js';\n"
        f"const options = await launchOptions({{headless:{headless_js}, os:{os_js}, humanize:true, enable_cache:true}});\n"
        "console.log(JSON.stringify(options));\n"
    )


def camoufox_launch_options(headless: bool) -> dict[str, Any]:
    project_root = find_camoufox_project_root()
    try:
        raw = subprocess.check_output(
            ["node", "--input-type=module", "-e", camoufox_launch_options_script(headless=headless)],
            cwd=project_root,
            text=True,
            stderr=subprocess.PIPE,
        )
    except FileNotFoundError as exc:
        raise SystemExit("缺少 Node.js。此 crawler 需要 Node.js 和 camoufox-js 来生成浏览器启动参数。") from exc
    except subprocess.CalledProcessError as exc:
        raise SystemExit(
            "Failed to generate Camoufox launch options via camoufox-js.\n"
            f"stderr:\n{exc.stderr}"
        ) from exc
    return json.loads(raw)


async def create_page(headless: bool):
    try:
        from playwright.async_api import async_playwright
    except ModuleNotFoundError as exc:
        skill_dir = Path(__file__).resolve().parents[1]
        requirements = skill_dir / "requirements.txt"
        raise SystemExit(
            "缺少依赖 playwright。请运行：\n"
            f"  python3 -m pip install -r {requirements}\n"
            "  python3 -m playwright install firefox"
        ) from exc

    options = camoufox_launch_options(headless=headless)
    playwright = await async_playwright().start()
    browser = await playwright.firefox.launch(
        executable_path=options["executablePath"],
        headless=options.get("headless", headless),
        args=options.get("args") or [],
        env={**os.environ, **(options.get("env") or {})},
        firefox_user_prefs=options.get("firefoxUserPrefs") or {},
        proxy=options.get("proxy") or None,
    )
    context = await browser.new_context(
        viewport={"width": 1280, "height": 720},
        permissions=["geolocation"],
        locale="en-US",
        timezone_id="America/Los_Angeles",
        geolocation={"latitude": 37.7749, "longitude": -122.4194},
    )
    page = await context.new_page()
    return playwright, browser, context, page


async def dismiss_popups(page) -> None:
    for label in ["Accept", "I agree", "Got it", "Close"]:
        try:
            button = page.get_by_role("button", name=re.compile(rf"^{re.escape(label)}$", re.I))
            if await button.count():
                await button.first.click(timeout=1000)
        except Exception:
            pass


def format_stdout_result(result: dict[str, Any]) -> str:
    return json.dumps(result, ensure_ascii=False, indent=2)


def format_cli_result(result: dict[str, Any], output: Path) -> str:
    cli_result = {**result, "output_path": str(output.resolve())}
    return format_stdout_result(cli_result)


def extract_year(*values: str | None) -> int | None:
    for value in values:
        match = re.search(r"\b(19|20)\d{2}\b", value or "")
        if match:
            return int(match.group(0))
    return None


def extract_primary_category(*values: str | None) -> str | None:
    for value in values:
        match = re.search(r"\[([^\]]+)\]", value or "")
        if match:
            category = match.group(1)
            if re.search(r"\b(pdf|ps|other)\b", category, flags=re.I):
                continue
            return category
    return None


def clean_arxiv_id(arxiv_id: str | None) -> str | None:
    match = re.search(r"(?:arXiv:)?([0-9]{4}\.[0-9]{4,5}(?:v\d+)?|[a-z.-]+/[0-9]{7}(?:v\d+)?)", arxiv_id or "", re.I)
    if match:
        return match.group(1)
    return normalize_space(arxiv_id) or None


def normalize_subject_category(subject: str | None) -> str | None:
    subject = normalize_space(subject)
    paren_match = re.search(r"\(([a-z.-]+\.[A-Z]{2}|[a-z.-]+)\)", subject)
    if paren_match:
        return paren_match.group(1)
    code_match = re.search(r"\b([a-z.-]+\.[A-Z]{2}|[a-z.-]+)\b", subject)
    if code_match:
        return code_match.group(1)
    return subject or None


def format_search_row(row: dict[str, Any]) -> dict[str, Any]:
    title = normalize_space(row.get("title"))
    raw_arxiv_id = normalize_space(row.get("arxiv_id"))
    announced = normalize_space(row.get("announced"))
    abstract = normalize_space(row.get("abstract"))
    comments = normalize_space(row.get("comments"))
    raw_text = normalize_space(row.get("raw_text"))
    subjects = row.get("subjects") or []
    return {
        "title": title,
        "arxiv_id": clean_arxiv_id(raw_arxiv_id),
        "primary_category": normalize_subject_category(subjects[0]) if subjects else extract_primary_category(raw_arxiv_id, raw_text),
        "url": row.get("url"),
        "pdf_url": row.get("pdf_url"),
        "authors": row.get("authors") or [],
        "subjects": subjects,
        "year": extract_year(announced, raw_text),
        "announced": announced or None,
        "abstract": abstract or None,
        "comments": comments or None,
    }


def search_page_size(limit: int | None) -> int:
    if limit is None:
        return 200
    if limit <= 25:
        return 25
    if limit <= 50:
        return 50
    if limit <= 100:
        return 100
    return 200


def build_search_url(query: str, searchtype: str, order: str, limit: int | None) -> str:
    return (
        f"{BASE_URL}/search/?query={quote_plus(query)}"
        f"&searchtype={quote_plus(searchtype)}"
        "&abstracts=show"
        f"&order={quote_plus(order)}"
        f"&size={search_page_size(limit)}"
    )


async def wait_for_search_results(page) -> None:
    await page.wait_for_selector("li.arxiv-result", timeout=30000)


async def extract_search_results(page, limit: int | None) -> list[dict[str, Any]]:
    rows = await page.evaluate(
        """() => {
            const normalize = (s) => (s || '').replace(/\\s+/g, ' ').trim();
            const absolute = (href) => new URL(href, location.origin).href;
            const textOf = (root, selector) => normalize(root.querySelector(selector)?.innerText || root.querySelector(selector)?.textContent);
            const linkHref = (root, selector) => {
                const href = root.querySelector(selector)?.getAttribute('href');
                return href ? absolute(href) : null;
            };
            const sectionText = (root, label) => {
                const paragraph = [...root.querySelectorAll('p')].find((p) => {
                    const text = normalize(p.innerText || p.textContent);
                    return text.toLowerCase().startsWith(label.toLowerCase());
                });
                if (!paragraph) return '';
                return normalize((paragraph.innerText || paragraph.textContent).replace(new RegExp(`^${label}:?`, 'i'), ''));
            };

            return [...document.querySelectorAll('li.arxiv-result')].map((item) => {
                const absLink = item.querySelector('p.list-title a[href*="/abs/"]');
                const pdfLink = [...item.querySelectorAll('a[href*="/pdf/"]')][0];
                const fullAbstract = item.querySelector('span.abstract-full');
                const abstract = fullAbstract
                    ? normalize((fullAbstract.innerText || fullAbstract.textContent).replace(/\\s*△ Less\\s*$/i, ''))
                    : sectionText(item, 'Abstract');
                return {
                    title: textOf(item, 'p.title'),
                    arxiv_id: normalize(item.querySelector('p.list-title')?.innerText || item.querySelector('p.list-title')?.textContent).replace(/^arXiv:\\s*/i, ''),
                    url: absLink ? absolute(absLink.getAttribute('href')) : null,
                    pdf_url: pdfLink ? absolute(pdfLink.getAttribute('href')) : null,
                    authors: [...item.querySelectorAll('p.authors a')].map((a) => normalize(a.innerText || a.textContent)).filter(Boolean),
                    subjects: [...item.querySelectorAll('.tags .tag, span.tag')].map((tag) => normalize(tag.innerText || tag.textContent)).filter(Boolean),
                    announced: textOf(item, 'p.is-size-7'),
                    abstract,
                    comments: sectionText(item, 'Comments'),
                    raw_text: normalize(item.innerText || item.textContent),
                };
            });
        }"""
    )

    results: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for row in rows:
        formatted = format_search_row(row)
        arxiv_id = formatted.get("arxiv_id")
        if not formatted.get("title") or not arxiv_id or arxiv_id in seen_ids:
            continue
        seen_ids.add(arxiv_id)
        results.append(formatted)
        if limit and len(results) >= limit:
            break
    return results


async def crawl_search(
    query: str,
    output: Path,
    headless: bool,
    limit: int | None,
    searchtype: str,
    order: str,
) -> dict[str, Any]:
    playwright, browser, context, page = await create_page(headless=headless)
    try:
        search_url = build_search_url(query, searchtype, order, limit)
        await page.goto(search_url, wait_until="domcontentloaded")
        await page.wait_for_load_state("networkidle", timeout=30000)
        await dismiss_popups(page)
        await wait_for_search_results(page)
        papers = await extract_search_results(page, limit)

        result = {
            "query": query,
            "search_url": search_url,
            "results_count": len(papers),
            "papers": papers,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(format_stdout_result(result), encoding="utf-8")
        return result
    finally:
        await browser.close()
        await playwright.stop()


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Crawl arXiv search results.")
    parser.add_argument("--query", default=DEFAULT_QUERY, help="Search query.")
    parser.add_argument("--output", default="arxiv_search_output.json", help="JSON output path.")
    parser.add_argument("--limit", default="10", help="Maximum papers to collect, or 'all'. Defaults to 10.")
    parser.add_argument(
        "--searchtype",
        default="all",
        choices=["all", "title", "author", "abstract", "comments", "journal_ref", "acm_class", "msc_class", "report_num"],
        help="arXiv search type. Defaults to all.",
    )
    parser.add_argument("--order", default="-announced_date_first", help="arXiv order parameter.")
    parser.add_argument("--headless", choices=["true", "false"], default="true", help="Run Camoufox headless.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    output = Path(args.output)
    result = asyncio.run(
        crawl_search(
            query=args.query,
            output=output,
            headless=args.headless == "true",
            limit=parse_limit(args.limit),
            searchtype=args.searchtype,
            order=args.order,
        )
    )
    print(format_cli_result(result, output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
