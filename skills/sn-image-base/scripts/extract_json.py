#!/usr/bin/env python3
"""Recover a single JSON value from noisy stdin and print it canonically.

LLM and CLI output sometimes wraps JSON in prose ("Here is the result:"),
markdown code fences (```json ... ```), or trailing commentary. This helper
reads stdin, recovers the JSON value, and writes it (compact, UTF-8) to stdout.

Recovery order:
    1. Parse the whole input as-is.
    2. Strip a surrounding markdown code fence, then parse.
    3. Slice from the first opening bracket to its balanced close (string- and
       escape-aware), then parse.

Exit code 0 on success; 1 (with a message on stderr) when no JSON is found.
Usage: some_command | python extract_json.py
"""

from __future__ import annotations

import json
import sys


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


def _balanced_span(text: str) -> str | None:
    """Return the substring from the first { or [ to its matching close.

    Tracks string literals and escapes so braces inside strings don't count.
    Returns None when no balanced span is found.
    """
    starts = [(text.find(o), o, c) for o, c in (("{", "}"), ("[", "]"))]
    starts = [s for s in starts if s[0] != -1]
    if not starts:
        return None
    start, open_ch, close_ch = min(starts, key=lambda t: t[0])

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
                return text[start : i + 1]
    return None


def extract_json(raw: str):
    """Recover a JSON value from raw text, or raise ValueError if none found."""
    candidates = [raw, _strip_fence(raw)]
    span = _balanced_span(raw)
    if span is not None:
        candidates.append(span)
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
