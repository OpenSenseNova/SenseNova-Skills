#!/usr/bin/env python3
"""
ArXiv 论文章节阅读器。

通过解析 arXiv HTML 版本（LaTeXML 转换），支持：
  - 列出论文所有章节结构
  - 按章节名称提取正文内容（大小写不敏感，支持部分匹配）

用法：
  python3 arxiv_paper.py 2409.05591                        # 列出章节
  python3 arxiv_paper.py 2409.05591 --section introduction  # 读取指定章节
  python3 arxiv_paper.py 2409.05591 --section method
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "_search-common"))

from search_utils import get_client, print_json

try:
    from bs4 import BeautifulSoup, NavigableString, Tag
except ImportError:
    print('{"success": false, "error": "需要 beautifulsoup4，请在项目环境中运行（uv run）"}')
    sys.exit(1)

HTML_BASE = "https://arxiv.org/html"
ABS_BASE = "https://arxiv.org/abs"
PDF_BASE = "https://arxiv.org/pdf"

# ── HTML 获取 ─────────────────────────────────────────────────────────────────

def fetch_html(arxiv_id: str) -> str:
    """获取 arXiv HTML 版本，不存在时抛出有意义的错误。"""
    url = f"{HTML_BASE}/{arxiv_id}"
    with get_client(timeout=45, headers={"Accept": "text/html,application/xhtml+xml"}) as client:
        resp = client.get(url)

    if resp.status_code == 404:
        raise ValueError(
            f"论文 {arxiv_id} 暂无 HTML 版本。"
            "可能原因：论文较老（2018 年前）、非 LaTeX 来源或尚未转换。"
            f"请直接阅读 PDF：{PDF_BASE}/{arxiv_id}"
        )
    resp.raise_for_status()
    return resp.text


# ── 文本清洗 ──────────────────────────────────────────────────────────────────

def _elem_to_text(elem: Tag) -> str:
    """
    将 HTML 元素转为可读文本。
    - math 元素：优先用 LaTeX 注解，否则用 alttext，再降级为 [MATH]
    - 图表标题：保留
    - 跳过 .ltx_note（脚注编号）等噪音节点
    """
    parts: list[str] = []

    for node in elem.descendants:
        if not isinstance(node, NavigableString):
            continue

        parent = node.parent
        if parent is None:
            continue

        tag = parent.name

        # 跳过脚注编号、引用上标等噪音
        parent_classes = parent.get("class") or []
        if any(c in parent_classes for c in ("ltx_note_mark", "ltx_ref_tag", "ltx_tag")):
            continue

        # math 元素：取 LaTeX 注解
        if tag == "annotation":
            encoding = parent.get("encoding", "")
            if "tex" in encoding.lower() or "latex" in encoding.lower():
                latex = node.strip()
                if latex:
                    parts.append(f"${latex}$")
            continue

        # 跳过 math 内部的非注解文本（MathML 结构文本很乱）
        in_math = False
        for ancestor in parent.parents:
            if ancestor.name == "math":
                in_math = True
                break
        if in_math:
            continue

        text = str(node)
        if text.strip():
            parts.append(text)

    raw = "".join(parts)
    # 合并多余空白，保留段落换行
    raw = re.sub(r"[ \t]+", " ", raw)
    raw = re.sub(r"\n{3,}", "\n\n", raw)
    return raw.strip()


# ── 章节提取 ──────────────────────────────────────────────────────────────────

def extract_sections(html: str) -> list[dict[str, Any]]:
    """
    从 arXiv HTML 提取所有章节（含摘要）。

    返回列表，每项：
      name   - 章节标题（含编号，如 "1 Introduction"）
      level  - 层级（0=摘要, 1=h2, 2=h3）
      text   - 正文文本
    """
    soup = BeautifulSoup(html, "html.parser")
    sections: list[dict[str, Any]] = []

    # ── 摘要 ──
    abstract_elem = soup.find(class_=re.compile(r"\bltx_abstract\b"))
    if abstract_elem:
        # 去掉 "Abstract" 标题行
        for h in abstract_elem.find_all(["h2", "h6"], class_=re.compile(r"ltx_title")):
            h.decompose()
        abstract_text = _elem_to_text(abstract_elem)
        if abstract_text:
            sections.append({"name": "Abstract", "level": 0, "text": abstract_text})

    # ── 正文各 section ──
    for sec in soup.find_all("section", class_=re.compile(r"\bltx_section\b|\bltx_appendix\b")):
        # 找本层标题（不要子 section 的标题）
        heading: Tag | None = None
        for h_tag in ["h2", "h3", "h4"]:
            candidate = sec.find(h_tag, class_=re.compile(r"\bltx_title\b"), recursive=False)
            if candidate:
                heading = candidate
                break

        if heading is None:
            # 有些 section 标题在首个 div 里
            for h_tag in ["h2", "h3", "h4"]:
                candidate = sec.find(h_tag, class_=re.compile(r"\bltx_title\b"))
                if candidate:
                    heading = candidate
                    break

        if heading is None:
            continue

        # 清理标题（去尾部 ¶ permalink、多余空白）
        heading_text = heading.get_text(" ", strip=True).rstrip("¶").strip()
        heading_text = re.sub(r"\s+", " ", heading_text)
        level = {"h2": 1, "h3": 2, "h4": 3}.get(heading.name, 1)

        # 提取本 section 的文本（排除子 section，避免重复）
        sec_copy = BeautifulSoup(str(sec), "html.parser").find("section")
        # 移除子 section
        for child_sec in sec_copy.find_all("section", recursive=False):
            child_sec.decompose()
        # 移除标题自身
        for h in sec_copy.find_all(["h2", "h3", "h4"], class_=re.compile(r"\bltx_title\b"), recursive=False):
            h.decompose()

        text = _elem_to_text(sec_copy)

        if not text.strip():
            continue

        sections.append({"name": heading_text, "level": level, "text": text})

    return sections


# ── 匹配章节名 ────────────────────────────────────────────────────────────────

def _match_section(sections: list[dict], query: str) -> dict | None:
    """大小写不敏感 + 去数字前缀的模糊匹配。"""
    q = query.lower().strip()

    def clean(name: str) -> str:
        """去掉 '1 ' / '1. ' 等数字前缀。"""
        return re.sub(r"^\d+[\.\s]+", "", name).lower().strip()

    # 精确匹配
    for s in sections:
        if s["name"].lower() == q or clean(s["name"]) == q:
            return s

    # 前缀 / 包含匹配
    for s in sections:
        if clean(s["name"]).startswith(q) or q in clean(s["name"]):
            return s

    return None


# ── 对外接口 ──────────────────────────────────────────────────────────────────

def cmd_list_sections(arxiv_id: str) -> dict[str, Any]:
    """列出论文所有章节（不含正文）。"""
    html = fetch_html(arxiv_id)
    sections = extract_sections(html)
    return {
        "success": True,
        "arxiv_id": arxiv_id,
        "abs_url": f"{ABS_BASE}/{arxiv_id}",
        "html_url": f"{HTML_BASE}/{arxiv_id}",
        "pdf_url": f"{PDF_BASE}/{arxiv_id}",
        "section_count": len(sections),
        "sections": [{"name": s["name"], "level": s["level"]} for s in sections],
        "error": None,
    }


def cmd_read_section(arxiv_id: str, section_name: str) -> dict[str, Any]:
    """读取指定章节的正文内容。"""
    html = fetch_html(arxiv_id)
    sections = extract_sections(html)
    matched = _match_section(sections, section_name)

    if matched is None:
        available = [s["name"] for s in sections]
        return {
            "success": False,
            "arxiv_id": arxiv_id,
            "section": section_name,
            "content": None,
            "error": f"未找到章节 '{section_name}'，可用章节：{available}",
        }

    return {
        "success": True,
        "arxiv_id": arxiv_id,
        "abs_url": f"{ABS_BASE}/{arxiv_id}",
        "section": matched["name"],
        "level": matched["level"],
        "content": matched["text"],
        "char_count": len(matched["text"]),
        "error": None,
    }


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="ArXiv 论文章节阅读器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  python3 arxiv_paper.py 2409.05591                          列出所有章节
  python3 arxiv_paper.py 2409.05591 --section introduction   读取 Introduction
  python3 arxiv_paper.py 2409.05591 --section method         读取 Method/Methods
  python3 arxiv_paper.py 2409.05591 --section conclusion     读取 Conclusion
""",
    )
    parser.add_argument("arxiv_id", help="arXiv 论文 ID（如 2409.05591 或 2409.05591v2）")
    parser.add_argument(
        "--section", "-s",
        metavar="SECTION_NAME",
        help="要读取的章节名（大小写不敏感，支持部分匹配）。不指定则列出所有章节。",
    )
    args = parser.parse_args()

    try:
        if args.section:
            result = cmd_read_section(args.arxiv_id.strip(), args.section.strip())
        else:
            result = cmd_list_sections(args.arxiv_id.strip())
        print_json(result)
    except Exception as e:
        print_json({
            "success": False,
            "arxiv_id": args.arxiv_id,
            "error": str(e),
        })
        sys.exit(1)


if __name__ == "__main__":
    main()
