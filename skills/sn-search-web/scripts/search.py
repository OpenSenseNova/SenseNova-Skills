#!/usr/bin/env python3
"""Opt-in anonymous web search and page excerpts through Parallel Search MCP."""

import argparse
import asyncio
import json
import math
import sys
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlsplit

try:
    import httpx
    from mcp import ClientSession
    from mcp.client.streamable_http import streamable_http_client
except ImportError as exc:
    requirements = Path(__file__).resolve().parents[1] / "requirements.txt"
    raise SystemExit(f"Missing dependency: install with python3 -m pip install -r {requirements}") from exc

ENDPOINT = "https://search.parallel.ai/mcp"
USER_AGENT = "SenseNova-Skills/sn-search-web (+https://github.com/OpenSenseNova/SenseNova-Skills)"


def positive_seconds(value):
    seconds = float(value)
    if not math.isfinite(seconds) or seconds <= 0:
        raise argparse.ArgumentTypeError("timeout must be a finite positive number")
    return seconds


def nonempty(value):
    if not value.strip():
        raise argparse.ArgumentTypeError("value must not be empty")
    return value


def http_url(value):
    try:
        parsed = urlsplit(value)
        if parsed.scheme in ("http", "https") and parsed.hostname and not parsed.username and not parsed.password:
            return value
    except ValueError:
        pass
    raise argparse.ArgumentTypeError("use an HTTP(S) URL without embedded credentials")


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    search = commands.add_parser("search", help="Search for current web sources")
    search.add_argument("objective", type=nonempty)
    search.add_argument("--query", action="append", required=True, type=nonempty,
                        help="Keyword query; repeat for related queries")
    fetch = commands.add_parser("fetch", help="Fetch excerpts from known URLs")
    fetch.add_argument("urls", nargs="+", type=http_url)
    fetch.add_argument("--objective", type=nonempty)
    for command in (search, fetch):
        command.add_argument("--timeout", type=positive_seconds, default=60,
                             help="Total operation timeout in seconds (default: 60)")
        command.add_argument("--session-id", type=nonempty,
                             help="Reuse one conversation identifier for related calls (max 100 characters)")
        command.add_argument("--output", type=Path, help="Write JSON to this file instead of stdout")
    args = parser.parse_args(argv)
    if args.session_id and len(args.session_id) > 100:
        parser.error("--session-id must be at most 100 characters")
    if args.command == "fetch":
        if len(args.urls) > 20:
            parser.error("fetch accepts at most 20 URLs")
        if args.objective and len(args.objective) > 200:
            parser.error("fetch --objective must be at most 200 characters")
    return args


async def call(tool, arguments, timeout):
    # No env keys, .env files, saved client credentials, or Authorization header.
    async with asyncio.timeout(timeout):
        async with httpx.AsyncClient(headers={"User-Agent": USER_AGENT}, timeout=timeout) as client:
            async with streamable_http_client(ENDPOINT, http_client=client) as (read, write, _):
                async with ClientSession(read, write, read_timeout_seconds=timedelta(seconds=timeout)) as session:
                    await session.initialize()
                    result = await session.call_tool(tool, arguments)
    return {"success": not result.isError, "provider": "parallel", "tool": tool,
            "result": result.model_dump(mode="json", exclude_none=True)}


def main(argv=None):
    args = parse_args(argv)
    if args.command == "search":
        tool = "web_search"
        arguments = {"objective": args.objective, "search_queries": args.query}
    else:
        tool = "web_fetch"
        arguments = {"urls": args.urls}
        if args.objective:
            arguments["objective"] = args.objective
    if args.session_id:
        arguments["session_id"] = args.session_id
    try:
        output = asyncio.run(call(tool, arguments, args.timeout))
    except TimeoutError:
        output = {"success": False, "provider": "parallel", "tool": tool,
                  "error": f"Operation timed out after {args.timeout:g} seconds"}
    except Exception:
        # Transport exceptions can contain request details. Keep stdout JSON and
        # report a safe action instead of exposing configuration or tracebacks.
        output = {"success": False, "provider": "parallel", "tool": tool,
                  "error": "MCP request failed; check network access and service availability"}
    text = json.dumps(output, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return 0 if output["success"] else 1


if __name__ == "__main__":
    sys.exit(main())
