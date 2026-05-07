#!/usr/bin/env python3
"""Render a Markdown research report as a comfortable standalone HTML file."""

from __future__ import annotations

import argparse
import base64
import html
import mimetypes
import re
import sys
from pathlib import Path

try:
    import markdown
except ImportError:  # pragma: no cover - environment guidance
    print("Missing dependency: python package 'markdown'. Install it and rerun.", file=sys.stderr)
    raise


MD_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
LIST_ITEM_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")
TOC_HEADING_RE = re.compile(r"^\s{0,3}#{2,6}\s+(?:目录|目錄|contents?|table of contents)\s*$", re.IGNORECASE)
TOC_ITEM_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+\[[^\]]+\]\(#[^)]+\)\s*$")
HR_RE = re.compile(r"^\s{0,3}(?:-{3,}|\*{3,}|_{3,})\s*$")
MERMAID_BLOCK_RE = re.compile(
    r'<pre><code class="(?:[^"]*\s)?language-mermaid(?:\s[^"]*)?">(.*?)</code></pre>',
    re.S,
)
MERMAID_CDN = "https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"


def is_external(src: str) -> bool:
    return bool(re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", src)) or src.startswith("//")


def embed_images(text: str, base_dir: Path) -> str:
    def replace(match: re.Match[str]) -> str:
        alt, src = match.groups()
        if is_external(src):
            return match.group(0)

        image_path = (base_dir / src).resolve()
        if not image_path.exists():
            return match.group(0)

        mime = mimetypes.guess_type(image_path.name)[0] or "application/octet-stream"
        encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
        return f"![{alt}](data:{mime};base64,{encoded})"

    return MD_IMAGE_RE.sub(replace, text)


def normalize_markdown(text: str) -> str:
    """Make common report Markdown patterns parse consistently.

    Many generated reports write "label:" directly followed by a list with no
    blank line. Python-Markdown treats that as a paragraph plus literal hyphens,
    so add the blank line that Markdown parsers expect. Skip fenced code blocks.
    """
    text = text.replace("｜", "|")
    lines = text.splitlines()
    normalized: list[str] = []
    in_fence = False

    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence

        if (
            not in_fence
            and LIST_ITEM_RE.match(line)
            and normalized
            and normalized[-1].strip()
            and not LIST_ITEM_RE.match(normalized[-1])
        ):
            normalized.append("")

        normalized.append(line)

        next_line = lines[i + 1] if i + 1 < len(lines) else ""
        if (
            not in_fence
            and LIST_ITEM_RE.match(line)
            and next_line.strip()
            and not LIST_ITEM_RE.match(next_line)
            and not next_line.startswith((" ", "\t"))
        ):
            normalized.append("")

    return "\n".join(normalized) + ("\n" if text.endswith("\n") else "")


def strip_inline_toc(text: str) -> str:
    """Remove a generated Markdown TOC when a side TOC will be rendered."""
    lines = text.splitlines()
    stripped: list[str] = []
    i = 0
    in_fence = False

    while i < len(lines):
        line = lines[i]
        marker = line.strip()
        if marker.startswith("```") or marker.startswith("~~~"):
            in_fence = not in_fence
            stripped.append(line)
            i += 1
            continue

        if not in_fence and TOC_HEADING_RE.match(line):
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1

            item_count = 0
            while j < len(lines) and TOC_ITEM_RE.match(lines[j]):
                item_count += 1
                j += 1

            if item_count >= 2:
                while j < len(lines) and not lines[j].strip():
                    j += 1
                if j < len(lines) and HR_RE.match(lines[j]):
                    j += 1
                while j < len(lines) and not lines[j].strip():
                    j += 1
                i = j
                continue

        stripped.append(line)
        i += 1

    return "\n".join(stripped) + ("\n" if text.endswith("\n") else "")


def title_from_body(body: str) -> str:
    match = re.search(r"<h1[^>]*>(.*?)</h1>", body, re.S)
    if not match:
        return "Markdown Report"
    return re.sub(r"<.*?>", "", match.group(1)).strip() or "Markdown Report"


def render_mermaid_blocks(body: str) -> tuple[str, int]:
    """Convert fenced mermaid code blocks into Mermaid render targets."""

    def replace(match: re.Match[str]) -> str:
        diagram = html.unescape(match.group(1)).strip()
        return f'<div class="mermaid">{html.escape(diagram)}</div>'

    return MERMAID_BLOCK_RE.subn(replace, body)


def build_mermaid_js(source: str) -> str:
    if source == "none":
        return ""

    if source == "local":
        loader = '<script src="mermaid.min.js"></script>'
    else:
        loader = f'<script src="{MERMAID_CDN}"></script>'

    return f"""
  {loader}
  <script>
    (() => {{
      if (!window.mermaid) return;
      window.mermaid.initialize({{
        startOnLoad: true,
        securityLevel: 'loose',
        theme: 'base',
        themeVariables: {{
          primaryColor: '#eef7f5',
          primaryTextColor: '#1c2430',
          primaryBorderColor: '#0f766e',
          lineColor: '#2563eb',
          secondaryColor: '#eef4f8',
          tertiaryColor: '#ffffff',
          mainBkg: '#ffffff',
          clusterBkg: '#fbfcfe',
          clusterBorder: '#dbe2ea',
          edgeLabelBackground: '#ffffff',
          textColor: '#1c2430',
          titleColor: '#0f172a',
          nodeTextColor: '#1c2430',
          xyChart: {{
            backgroundColor: '#fbfcfe',
            titleColor: '#0f172a',
            xAxisLabelColor: '#475467',
            xAxisTitleColor: '#344054',
            xAxisTickColor: '#dbe2ea',
            xAxisLineColor: '#dbe2ea',
            yAxisLabelColor: '#475467',
            yAxisTitleColor: '#344054',
            yAxisTickColor: '#dbe2ea',
            yAxisLineColor: '#dbe2ea',
            plotColorPalette: '#0f766e, #2563eb, #94a3b8, #c2410c'
          }},
          fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif'
        }}
      }});
    }})();
  </script>
"""


def build_js() -> str:
    return """
  <script>
    (() => {
      const progress = document.querySelector('.progress');
      const topBtn = document.querySelector('.back-top');
      const links = [...document.querySelectorAll('.toc-panel a[href^="#"]')];
      const headings = links
        .map(a => document.getElementById(decodeURIComponent(a.hash.slice(1))))
        .filter(Boolean);

      function onScroll() {
        const max = document.documentElement.scrollHeight - innerHeight;
        if (progress) progress.style.width = max > 0 ? `${scrollY / max * 100}%` : '0%';
        if (topBtn) topBtn.classList.toggle('show', scrollY > innerHeight);

        let current = headings[0];
        for (const h of headings) {
          if (h.getBoundingClientRect().top <= 120) current = h;
        }
        links.forEach(a => a.classList.toggle('active', current && a.hash === `#${current.id}`));
      }

      addEventListener('scroll', onScroll, { passive: true });
      topBtn?.addEventListener('click', () => scrollTo({ top: 0, behavior: 'smooth' }));
      onScroll();
    })();
  </script>
"""


def build_html(title: str, toc: str, body: str, with_js: bool, mermaid_source: str = "none") -> str:
    progress = '<div class="progress"></div>' if with_js else ""
    back_top = '<button class="back-top" type="button" aria-label="返回顶部">↑</button>' if with_js else ""
    js = build_js() if with_js else ""
    mermaid_js = build_mermaid_js(mermaid_source)

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <style>
    :root {{
      --bg: #f7f8fb;
      --paper: #ffffff;
      --ink: #1c2430;
      --muted: #667085;
      --line: #dbe2ea;
      --accent: #0f766e;
      --accent-2: #2563eb;
      --soft: #eef7f5;
      --shadow: 0 18px 45px rgba(15, 23, 42, .08);
      --radius: 8px;
    }}
    * {{ box-sizing: border-box; }}
    html {{ scroll-behavior: smooth; }}
    body {{
      margin: 0;
      color: var(--ink);
      background:
        radial-gradient(circle at 12% 0%, rgba(15, 118, 110, .09), transparent 30%),
        linear-gradient(180deg, #f3f7fa 0%, var(--bg) 360px, var(--bg) 100%);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
      line-height: 1.75;
      letter-spacing: 0;
    }}
    a {{ color: var(--accent-2); text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    .progress {{ position: fixed; inset: 0 auto auto 0; width: 0; height: 3px; z-index: 10; background: linear-gradient(90deg, var(--accent), var(--accent-2)); }}
    .layout {{
      display: grid;
      grid-template-columns: minmax(220px, 280px) minmax(0, 1fr);
      gap: 28px;
      max-width: 1480px;
      margin: 0 auto;
      padding: 28px;
    }}
    .toc-panel {{
      position: sticky;
      top: 20px;
      align-self: start;
      max-height: calc(100vh - 40px);
      overflow: auto;
      padding: 18px 16px;
      background: rgba(255, 255, 255, .86);
      border: 1px solid rgba(219, 226, 234, .9);
      border-radius: var(--radius);
      box-shadow: 0 10px 30px rgba(15, 23, 42, .05);
      backdrop-filter: blur(12px);
    }}
    .toc-title {{
      margin: 0 0 10px;
      font-size: 13px;
      font-weight: 700;
      color: var(--accent);
      text-transform: uppercase;
    }}
    .toc-panel ul {{ list-style: none; padding-left: 0; margin: 0; }}
    .toc-panel li {{ margin: 3px 0; }}
    .toc-panel ul ul {{ padding-left: 14px; margin-top: 3px; border-left: 1px solid var(--line); }}
    .toc-panel a {{
      display: block;
      padding: 5px 6px;
      border-radius: 6px;
      color: #425466;
      font-size: 13px;
      line-height: 1.45;
    }}
    .toc-panel a:hover, .toc-panel a.active {{ background: var(--soft); color: var(--accent); text-decoration: none; }}
    main {{
      min-width: 0;
      background: var(--paper);
      border: 1px solid rgba(219, 226, 234, .9);
      border-radius: var(--radius);
      box-shadow: var(--shadow);
      overflow: hidden;
    }}
    article {{ padding: 46px min(6vw, 76px) 68px; }}
    h1 {{
      margin: -46px min(-6vw, -76px) 34px;
      padding: 58px min(6vw, 76px) 44px;
      color: #fff;
      background: linear-gradient(135deg, #0f766e 0%, #155e75 52%, #1d4ed8 100%);
      font-size: clamp(30px, 4vw, 52px);
      line-height: 1.14;
      font-weight: 800;
    }}
    h2 {{
      margin: 54px 0 18px;
      padding-top: 8px;
      border-top: 1px solid var(--line);
      font-size: clamp(22px, 2.3vw, 30px);
      line-height: 1.35;
      color: #0f172a;
    }}
    h3 {{ margin: 34px 0 12px; font-size: 21px; color: #17324d; }}
    h4 {{ margin: 26px 0 10px; font-size: 17px; color: #344054; }}
    p {{ margin: 12px 0; }}
    strong {{ color: #0f172a; font-weight: 700; }}
    hr {{ border: 0; border-top: 1px solid var(--line); margin: 28px 0; }}
    blockquote {{
      margin: 18px 0 24px;
      padding: 12px 16px;
      color: #475467;
      background: var(--soft);
      border-left: 4px solid var(--accent);
      border-radius: 0 var(--radius) var(--radius) 0;
    }}
    ul, ol {{ padding-left: 1.35em; }}
    li {{ margin: 4px 0; }}
    .table-scroll {{
      width: 100%;
      overflow-x: auto;
      margin: 18px 0 28px;
      border: 1px solid var(--line);
      border-radius: var(--radius);
      background: #fff;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      margin: 0;
      font-size: 14px;
      line-height: 1.55;
      table-layout: auto;
    }}
    th, td {{
      min-width: 112px;
      padding: 11px 13px;
      border-bottom: 1px solid var(--line);
      text-align: left;
      vertical-align: top;
      background: #fff;
    }}
    th {{
      color: #0f172a;
      background: #eef4f8;
      font-weight: 700;
      white-space: nowrap;
    }}
    tr:nth-child(even) td {{ background: #fbfcfe; }}
    tr:last-child td {{ border-bottom: 0; }}
    img {{
      display: block;
      max-width: 100%;
      height: auto;
      margin: 24px auto 8px;
      border: 1px solid var(--line);
      border-radius: var(--radius);
      box-shadow: 0 12px 28px rgba(15, 23, 42, .08);
      background: #fff;
    }}
    code {{
      padding: 2px 5px;
      border-radius: 5px;
      background: #f1f5f9;
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: .92em;
    }}
    pre {{ overflow: auto; padding: 16px; background: #0f172a; color: #e5e7eb; border-radius: var(--radius); }}
    pre code {{ padding: 0; color: inherit; background: transparent; }}
    .mermaid {{
      margin: 26px 0 30px;
      padding: 18px;
      overflow-x: auto;
      text-align: center;
      background: #fbfcfe;
      border: 1px solid var(--line);
      border-radius: var(--radius);
    }}
    .mermaid svg {{ max-width: 100%; height: auto; }}
    .back-top {{
      display: none;
      position: fixed;
      right: 18px;
      bottom: 18px;
      width: 42px;
      height: 42px;
      border: 0;
      border-radius: 999px;
      color: #fff;
      background: var(--accent);
      box-shadow: 0 8px 22px rgba(15, 23, 42, .2);
      cursor: pointer;
    }}
    .back-top.show {{ display: block; }}
    @media (max-width: 1020px) {{
      .layout {{ display: block; padding: 14px; }}
      .toc-panel {{ position: relative; top: 0; max-height: 280px; margin-bottom: 14px; }}
      article {{ padding: 28px 18px 42px; }}
      h1 {{ margin: -28px -18px 28px; padding: 38px 18px 32px; }}
      th, td {{ min-width: 120px; padding: 10px; }}
    }}
    @media print {{
      body {{ background: #fff; }}
      .layout {{ display: block; max-width: none; padding: 0; }}
      .toc-panel, .progress, .back-top {{ display: none !important; }}
      main {{ border: 0; box-shadow: none; }}
      article {{ padding: 0; }}
      h1 {{ margin: 0 0 24px; color: #111827; background: none; padding: 0; }}
      a {{ color: inherit; }}
      .table-scroll, table {{ page-break-inside: avoid; }}
      img, blockquote, pre {{ page-break-inside: avoid; box-shadow: none; }}
    }}
  </style>
</head>
<body>
  {progress}
  <div class="layout">
    <aside class="toc-panel" aria-label="目录">
      <p class="toc-title">目录</p>
      {toc}
    </aside>
    <main>
      <article>
        {body}
      </article>
    </main>
  </div>
  {back_top}
  {mermaid_js}
  {js}
</body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="Input Markdown file")
    parser.add_argument("output", nargs="?", help="Output HTML file")
    parser.add_argument("--embed-images", dest="embed_images", action="store_true", default=True)
    parser.add_argument("--no-embed-images", dest="embed_images", action="store_false")
    parser.add_argument("--with-js", action="store_true", help="Add progress, active TOC, and back-to-top interactions")
    parser.add_argument("--keep-inline-toc", action="store_true", help="Keep an existing Markdown TOC in the article body")
    parser.add_argument(
        "--mermaid-source",
        choices=["auto", "cdn", "local", "none"],
        default="auto",
        help="Render mermaid fences with CDN JS, local mermaid.min.js, or disable rendering",
    )
    parser.add_argument("--title-style", choices=["comfortable"], default="comfortable")
    args = parser.parse_args()

    source = Path(args.input).expanduser().resolve()
    if not source.exists():
        print(f"Input file not found: {source}", file=sys.stderr)
        return 2

    output = Path(args.output).expanduser().resolve() if args.output else source.with_suffix(".html")

    text = normalize_markdown(source.read_text(encoding="utf-8"))
    if not args.keep_inline_toc:
        text = strip_inline_toc(text)
    if args.embed_images:
        text = embed_images(text, source.parent)

    md = markdown.Markdown(
        extensions=["extra", "toc", "sane_lists", "smarty"],
        extension_configs={"toc": {"permalink": False, "separator": "-"}},
    )
    body = md.convert(text)
    body = re.sub(r"(<table>.*?</table>)", r'<div class="table-scroll">\1</div>', body, flags=re.S)
    body, mermaid_count = render_mermaid_blocks(body)
    mermaid_source = "none"
    if mermaid_count and args.mermaid_source != "none":
        mermaid_source = "cdn" if args.mermaid_source == "auto" else args.mermaid_source
    html = build_html(title_from_body(body), md.toc, body, args.with_js, mermaid_source)

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html, encoding="utf-8")
    print(output)
    print(f"tables={html.count('<table')}")
    print(f"images={html.count('<img')}")
    print(f"embedded_images={html.count('data:image/')}")
    print(f"mermaid={mermaid_count}")
    if mermaid_source == "cdn":
        print("mermaid_source=cdn")
    elif mermaid_source == "local":
        print("mermaid_source=local")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
