"""Strip technical metadata (hex colors, rgb/hsl, size units, CSS/JSON-ish
fragments, design-spec labels) from a T2I prompt before it is passed to the
image generation backend.

Rationale: some T2I backends auto-rewrite the prompt server-side and happily
bake "#1e3a8a" / "48px" / "color palette:" into the rendered image when the
prompt mentions them. We control the last mile before the prompt hits the
wire — remove the anchors that cause that failure mode.

Usage:
    # file-in-place mode (Stage 4.1 writes raw prompt to .prompt.txt, then
    # calls this script to clean it):
    python3 sanitize_prompt.py --path <deck_dir>/pages/page_003.prompt.txt

    # stdin/stdout mode (pipe):
    echo "$RAW" | python3 sanitize_prompt.py

Silent by design: no chat notifications, no summary on stdout in file-mode
(only the scrubbed text if stdin/stdout). Debug removals go to stderr so they
end up in the exec log for later inspection, but are never promoted to the
user.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


# Hex color codes: #RGB, #RRGGBB, #RRGGBBAA (with word-boundary on both sides)
_HEX = re.compile(r"(?<![0-9A-Za-z])#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})(?![0-9A-Za-z])")

# rgb(...), rgba(...), hsl(...), hsla(...) — any case, any whitespace
_RGB_HSL = re.compile(r"\b(?:rgba?|hsla?)\s*\([^)]*\)", re.IGNORECASE)

# Size units like 48px, 2rem, 1.2em, 14pt, 100vh, 50vw, 90% — but we only want
# to strip them in font/size contexts, not strip bare "50%" which is common
# elsewhere (e.g. "50% whitespace"). So we require a digit + unit with no
# intervening space, and we only target css-y units.
_SIZE_UNIT = re.compile(r"\b\d+(?:\.\d+)?(?:px|pt|em|rem|vh|vw)\b", re.IGNORECASE)

# Design-spec English labels that commonly appear in a designer's spec sheet
# and, when present, bait the T2I backend into rendering them as visible text.
# We remove the *label* (with trailing colon if present) — surrounding prose
# usually still makes sense.
_SPEC_LABELS = re.compile(
    r"\b(?:color\s*palette|typography|layout\s*annotation|design\s*spec|"
    r"style\s*guide|font\s*stack|css|html|json|yaml|hex\s*code)\s*[:：]?",
    re.IGNORECASE,
)

# CSS-ish key:value fragments like `background: #fff` or `font-size: 48px`
# These often sneak in when an LLM formats style hints like code.
_CSS_KV = re.compile(
    r"\b(?:background(?:-color)?|color|font(?:-size|-family|-weight)?|margin|padding|width|height|opacity)\s*:\s*[^,;\n]{1,60}",
    re.IGNORECASE,
)


def sanitize(text: str) -> tuple[str, list[str]]:
    """Return (cleaned_text, removed_fragments).

    Order matters: strip CSS key:value blocks before standalone hex / units, so
    a fragment like "color: #1e3a8a" is removed as one unit rather than
    leaving "color:" behind.
    """
    removed: list[str] = []

    def _capture(pattern: re.Pattern[str], src: str) -> str:
        def _sub(m: re.Match[str]) -> str:
            removed.append(m.group(0))
            return ""
        return pattern.sub(_sub, src)

    out = text
    out = _capture(_CSS_KV, out)
    out = _capture(_HEX, out)
    out = _capture(_RGB_HSL, out)
    out = _capture(_SIZE_UNIT, out)
    out = _capture(_SPEC_LABELS, out)

    # Collapse whitespace / stray punctuation left behind by removals.
    out = re.sub(r"[ \t]{2,}", " ", out)
    out = re.sub(r"\s+([,.;。，；])", r"\1", out)
    out = re.sub(r"([(（])\s+", r"\1", out)
    out = re.sub(r"\s+([)）])", r"\1", out)
    out = re.sub(r"(?:,\s*){2,}", ", ", out)
    out = re.sub(r"\n{3,}", "\n\n", out)

    return out.strip() + ("\n" if text.endswith("\n") else ""), removed


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--path", type=Path, default=None,
                   help="Sanitize this file in place. If omitted, read stdin, write stdout.")
    args = p.parse_args(argv)

    if args.path is not None:
        path = args.path.expanduser().resolve()
        raw = path.read_text(encoding="utf-8")
        cleaned, removed = sanitize(raw)
        if cleaned != raw:
            path.write_text(cleaned, encoding="utf-8")
        if removed:
            print(f"[sanitize_prompt] {path.name}: removed {len(removed)} fragments: "
                  + "; ".join(repr(r) for r in removed[:10])
                  + (" ..." if len(removed) > 10 else ""),
                  file=sys.stderr)
        return 0

    raw = sys.stdin.read()
    cleaned, removed = sanitize(raw)
    sys.stdout.write(cleaned)
    if removed:
        print(f"[sanitize_prompt] stdin: removed {len(removed)} fragments",
              file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
