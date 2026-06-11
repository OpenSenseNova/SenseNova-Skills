#!/usr/bin/env python3
"""Recover a single JSON value from noisy stdin and print it canonically.

LLM and CLI output sometimes wraps JSON in prose ("Here is the result:"),
markdown code fences (```json ... ```), or trailing commentary. This helper
reads stdin, recovers the JSON value, and writes it (compact, UTF-8) to stdout.

Recovery order:
    1. Parse the whole input as-is.
    2. Strip a surrounding markdown code fence, then parse.
    3. Scan each opening bracket to its balanced close (string- and
       escape-aware), trying successive openers until one parses — so a valid
       object/array after some junk is still recovered.

Exit code 0 on success; 1 (with a message on stderr) when no JSON is found.
Usage: some_command | python extract_json.py
"""

from __future__ import annotations

import itertools
import json
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator


def _strip_fence(text: str) -> str:
    """Remove a single surrounding ``` / ```json markdown fence, if present."""
    stripped = text.strip()
    if not stripped.startswith("```"):
        return text
    lines = stripped.splitlines()
    # Drop the opening fence line (``` or ```json) and a trailing fence line.
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines)


def _scan_balanced(text: str, start: int, open_ch: str, close_ch: str) -> int | None:
    """Return the index of the close that balances the opener at ``start``.

    Tracks string literals and escapes so brackets inside strings don't count.
    Returns None when the opener is never balanced.
    """
    depth = 0
    in_str = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == open_ch:
            depth += 1
        elif ch == close_ch:
            depth -= 1
            if depth == 0:
                return i
    return None


def _balanced_spans(text: str) -> Iterator[str]:
    """Yield balanced {...} / [...] substrings in opening-bracket order.

    Scans successive openers so a later valid object/array is still found when
    an earlier bracket region is not valid JSON. Nested openers are included;
    the caller stops at the first span that parses.
    """
    for i, ch in enumerate(text):
        if ch == "{":
            end = _scan_balanced(text, i, "{", "}")
        elif ch == "[":
            end = _scan_balanced(text, i, "[", "]")
        else:
            continue
        if end is not None:
            yield text[i : end + 1]


def extract_json(raw: str):
    """Recover a JSON value from raw text, or raise ValueError if none found."""
    candidates = itertools.chain((raw, _strip_fence(raw)), _balanced_spans(raw))
    for candidate in candidates:
        candidate = candidate.strip()
        if not candidate:
            continue
        try:
            return json.loads(candidate)
        except ValueError:
            continue
    raise ValueError("no valid JSON value found in input")


def main() -> int:
    raw = sys.stdin.read()
    try:
        value = extract_json(raw)
    except ValueError as exc:
        sys.stderr.write(f"extract_json: {exc}\n")
        return 1
    sys.stdout.write(json.dumps(value, ensure_ascii=False))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
