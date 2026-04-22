#!/usr/bin/env python3
"""
PMC 论文全文章节阅读器。

通过 NCBI E-utilities 获取 PubMed Central 全文 XML（JATS 格式），支持：
  - 列出论文所有章节结构（含子章节层级）
  - 按章节名称提取正文内容（大小写不敏感，支持部分匹配）
  - 通过 PMID 自动解析到 PMC ID

用法：
  python3 pmc_paper.py PMC11119143                          # 列出章节
  python3 pmc_paper.py 11119143                             # 同上（自动补 PMC 前缀）
  python3 pmc_paper.py PMC11119143 --section introduction   # 读取指定章节
  python3 pmc_paper.py --pmid 38786024 --section method     # 从 PMID 出发
"""
from __future__ import annotations

import argparse
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "_search-common"))

from search_utils import get_client, print_json

EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
ELINK_URL  = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/elink.fcgi"

# ── ID 处理 ───────────────────────────────────────────────────────────────────

def normalize_pmc_id(raw: str) -> str:
    """规范化 PMC ID：去掉 'PMC' 前缀，只保留数字部分。"""
    return re.sub(r"^[Pp][Mm][Cc]", "", raw.strip())


def pmid_to_pmc(pmid: str, api_key: str | None = None) -> str | None:
    """通过 elink 将 PMID 转换为 PMC ID（数字形式）。"""
    params: dict[str, Any] = {
        "dbfrom": "pubmed",
        "db": "pmc",
        "id": pmid,
        "retmode": "json",
    }
    if api_key:
        params["api_key"] = api_key

    with get_client(timeout=20) as client:
        resp = client.get(ELINK_URL, params=params)
        resp.raise_for_status()

    data = resp.json()
    for linkset in data.get("linksets", []):
        for db in linkset.get("linksetdbs", []):
            if db.get("dbto") == "pmc" and db.get("linkname") == "pubmed_pmc":
                links = db.get("links", [])
                if links:
                    return str(links[0])
    return None


# ── XML 拉取 ──────────────────────────────────────────────────────────────────

def fetch_pmc_xml(pmc_num: str, api_key: str | None = None) -> ET.Element:
    """获取 PMC 全文 XML，返回根元素。"""
    params: dict[str, Any] = {
        "db": "pmc",
        "id": pmc_num,
        "rettype": "xml",
        "retmode": "xml",
    }
    if api_key:
        params["api_key"] = api_key

    with get_client(timeout=45) as client:
        resp = client.get(EFETCH_URL, params=params)
        resp.raise_for_status()

    root = ET.fromstring(resp.text)

    # 检查是否找到论文
    article = root.find(".//article")
    if article is None:
        raise ValueError(
            f"PMC{pmc_num} 未找到全文。"
            "可能原因：该论文不在 PMC 开放获取库中，或 ID 有误。"
        )
    return root


# ── JATS XML 文本提取 ─────────────────────────────────────────────────────────

# 跳过这些标签的全部内容（噪音节点）
_SKIP_TAGS = {"ref", "ref-list", "fn", "fn-group", "permissions", "author-notes",
              "glossary", "ack"}  # ack=Acknowledgements，可按需保留

# 转为占位符的标签
_FORMULA_TAGS = {"disp-formula", "inline-formula", "mml:math", "tex-math"}


def _elem_to_text(elem: ET.Element, depth: int = 0) -> str:
    """
    将 JATS XML 元素递归转为可读文本。

    处理规则：
    - <p>: 段落，末尾加换行
    - <title>: 跳过（章节标题在上层已处理）
    - <sec>: 子章节，递归（用缩进区分层级）
    - <list>/<list-item>: 转为 bullet 列表
    - <disp-formula>/<inline-formula>: 替换为 [FORMULA]
    - <fig>: 跳过图像内容，保留 caption
    - <table-wrap>: 保留 label+caption
    - <xref>/<ext-link>: 直接取文本内容
    - <bold>/<italic>/<underline>: 取文本内容
    """
    tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag  # 去 namespace

    if tag in _SKIP_TAGS:
        return ""

    if tag in _FORMULA_TAGS:
        return " [FORMULA] "

    if tag == "title":
        return ""  # 由调用方处理

    if tag == "p":
        text = _collect_text(elem)
        return text.strip() + "\n\n" if text.strip() else ""

    if tag in ("bold", "italic", "underline", "named-content", "styled-content",
               "ext-link", "uri", "xref", "sup", "sub", "monospace"):
        return _collect_text(elem)

    if tag == "list":
        parts = []
        for li in elem.findall("list-item"):
            item_text = "".join(_elem_to_text(c) for c in li).strip()
            if item_text:
                parts.append(f"• {item_text}")
        return "\n".join(parts) + "\n\n" if parts else ""

    if tag == "disp-quote":
        text = "".join(_elem_to_text(c) for c in elem).strip()
        return f"> {text}\n\n" if text else ""

    if tag == "fig":
        # 只保留 caption
        caption = elem.find(".//caption")
        if caption is not None:
            cap_text = "".join(_elem_to_text(c) for c in caption).strip()
            label = elem.findtext("label", "Figure")
            return f"[{label}: {cap_text}]\n\n" if cap_text else ""
        return ""

    if tag == "table-wrap":
        label = elem.findtext("label", "Table")
        caption = elem.find(".//caption")
        cap_text = ""
        if caption is not None:
            cap_text = "".join(_elem_to_text(c) for c in caption).strip()
        return f"[{label}: {cap_text}]\n\n" if cap_text else f"[{label}]\n\n"

    if tag == "sec":
        # 子章节：递归处理，标题加缩进
        sub_title_elem = elem.find("title")
        sub_title = ""
        if sub_title_elem is not None:
            sub_title = _collect_text(sub_title_elem).strip()

        parts = []
        if sub_title:
            indent = "  " * depth
            parts.append(f"\n{indent}### {sub_title}\n\n")
        for child in elem:
            child_tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
            if child_tag == "title":
                continue
            parts.append(_elem_to_text(child, depth + 1))
        return "".join(parts)

    # 默认：递归子节点
    return "".join(_elem_to_text(c, depth) for c in elem)


def _collect_text(elem: ET.Element) -> str:
    """收集元素的所有文本（含子节点，跳过公式）。"""
    parts = []
    if elem.text:
        parts.append(elem.text)
    for child in elem:
        child_tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
        if child_tag in _FORMULA_TAGS:
            parts.append("[FORMULA]")
        elif child_tag in _SKIP_TAGS:
            pass
        else:
            parts.append(_collect_text(child))
        if child.tail:
            parts.append(child.tail)
    return "".join(parts)


# ── 章节提取 ──────────────────────────────────────────────────────────────────

def _extract_sections_from(container: ET.Element, level: int = 1) -> list[dict[str, Any]]:
    """递归提取 sec 节点，返回扁平章节列表。"""
    sections: list[dict[str, Any]] = []
    for sec in container.findall("sec"):
        title_elem = sec.find("title")
        title = _collect_text(title_elem).strip() if title_elem is not None else f"Section {len(sections)+1}"

        # 正文：本 sec 的直接子节点（排除 sec 和 title）
        text_parts = []
        for child in sec:
            child_tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
            if child_tag in ("title", "sec"):
                continue
            text_parts.append(_elem_to_text(child))

        text = "".join(text_parts).strip()

        # 子章节递归
        subsections = _extract_sections_from(sec, level + 1)

        sections.append({
            "name": title,
            "level": level,
            "text": text,
            "subsections": subsections,
        })
    return sections


def extract_all_sections(root: ET.Element) -> list[dict[str, Any]]:
    """
    从 PMC JATS XML 提取所有章节。
    顺序：Abstract → Body sections（含子章节）
    """
    sections: list[dict[str, Any]] = []

    article = root.find(".//article")
    if article is None:
        return sections

    # ── 摘要 ──
    abstract = article.find(".//abstract")
    if abstract is not None:
        # 结构化摘要（含 sec）
        if abstract.findall("sec"):
            abs_parts = []
            for sec in abstract.findall("sec"):
                sec_title = sec.findtext("title", "")
                sec_text_parts = []
                for child in sec:
                    if child.tag != "title":
                        sec_text_parts.append(_elem_to_text(child))
                part = "".join(sec_text_parts).strip()
                if sec_title:
                    abs_parts.append(f"{sec_title}: {part}")
                else:
                    abs_parts.append(part)
            abs_text = "\n\n".join(abs_parts)
        else:
            abs_text = "".join(_elem_to_text(c) for c in abstract).strip()

        if abs_text:
            sections.append({"name": "Abstract", "level": 0, "text": abs_text, "subsections": []})

    # ── Body ──
    body = article.find(".//body")
    if body is not None:
        sections.extend(_extract_sections_from(body, level=1))

    return sections


# ── 章节匹配 ──────────────────────────────────────────────────────────────────

def _flatten_sections(sections: list[dict], result: list | None = None) -> list[dict]:
    """将嵌套章节扁平化，便于搜索。"""
    if result is None:
        result = []
    for s in sections:
        result.append(s)
        _flatten_sections(s.get("subsections", []), result)
    return result


def match_section(sections: list[dict], query: str) -> dict | None:
    """大小写不敏感 + 去数字前缀的模糊匹配（搜索所有层级）。"""
    q = query.lower().strip()
    flat = _flatten_sections(sections)

    def clean(name: str) -> str:
        return re.sub(r"^\d+[\.\s]+", "", name).lower().strip()

    # 精确匹配
    for s in flat:
        if s["name"].lower() == q or clean(s["name"]) == q:
            return s

    # 包含/前缀匹配
    for s in flat:
        c = clean(s["name"])
        if c.startswith(q) or q in c:
            return s

    return None


# ── 对外接口 ──────────────────────────────────────────────────────────────────

def _section_outline(sections: list[dict], depth: int = 0) -> list[dict]:
    """生成章节目录（只含 name 和 level，递归）。"""
    outline = []
    for s in sections:
        outline.append({"name": s["name"], "level": s["level"]})
        if s.get("subsections"):
            outline.extend(_section_outline(s["subsections"], depth + 1))
    return outline


def cmd_list_sections(pmc_num: str, api_key: str | None = None) -> dict[str, Any]:
    """列出 PMC 论文所有章节目录。"""
    root = fetch_pmc_xml(pmc_num, api_key)
    sections = extract_all_sections(root)

    # 从 XML 拿标题
    title = root.findtext(".//article-title", "")
    pmid = root.findtext(".//article-id[@pub-id-type='pmid']", "")

    return {
        "success": True,
        "pmc_id": f"PMC{pmc_num}",
        "pmid": pmid or None,
        "title": title,
        "pmc_url": f"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{pmc_num}/",
        "section_count": len(_flatten_sections(sections)),
        "sections": _section_outline(sections),
        "error": None,
    }


def cmd_read_section(pmc_num: str, section_name: str, api_key: str | None = None) -> dict[str, Any]:
    """读取指定章节的正文内容（含子章节文本）。"""
    root = fetch_pmc_xml(pmc_num, api_key)
    sections = extract_all_sections(root)
    matched = match_section(sections, section_name)

    if matched is None:
        flat = _flatten_sections(sections)
        available = [s["name"] for s in flat]
        return {
            "success": False,
            "pmc_id": f"PMC{pmc_num}",
            "section": section_name,
            "content": None,
            "error": f"未找到章节 '{section_name}'，可用章节：{available}",
        }

    # 合并本节文本 + 子章节文本
    def collect_text(s: dict) -> str:
        parts = [s["text"]]
        for sub in s.get("subsections", []):
            sub_text = collect_text(sub)
            if sub_text.strip():
                parts.append(f"\n### {sub['name']}\n\n{sub_text}")
        return "\n\n".join(p for p in parts if p.strip())

    content = collect_text(matched)

    return {
        "success": True,
        "pmc_id": f"PMC{pmc_num}",
        "pmc_url": f"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{pmc_num}/",
        "section": matched["name"],
        "level": matched["level"],
        "content": content,
        "char_count": len(content),
        "error": None,
    }


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="PMC 论文全文章节阅读器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  python3 pmc_paper.py PMC11119143                           列出所有章节
  python3 pmc_paper.py 11119143                              同上（自动补前缀）
  python3 pmc_paper.py PMC11119143 --section introduction    读取 Introduction
  python3 pmc_paper.py PMC11119143 --section method          读取 Methods
  python3 pmc_paper.py --pmid 38786024                       从 PMID 列章节
  python3 pmc_paper.py --pmid 38786024 --section conclusion  从 PMID 读章节
""",
    )
    parser.add_argument(
        "pmc_id", nargs="?",
        help="PMC ID（如 PMC11119143 或 11119143）。与 --pmid 二选一。",
    )
    parser.add_argument(
        "--pmid",
        help="PubMed ID，自动转换为 PMC ID（需要论文在 PMC 开放获取库中）",
    )
    parser.add_argument(
        "--section", "-s",
        metavar="SECTION_NAME",
        help="要读取的章节名（大小写不敏感，支持部分匹配）。不指定则列出所有章节。",
    )
    parser.add_argument(
        "--api-key",
        help="NCBI API Key（可选，提升限额从 3 req/s 到 10 req/s）",
    )
    args = parser.parse_args()

    api_key = getattr(args, "api_key", None)

    try:
        # 解析 PMC 数字 ID
        if args.pmid:
            pmc_num = pmid_to_pmc(args.pmid, api_key)
            if not pmc_num:
                print_json({
                    "success": False,
                    "pmid": args.pmid,
                    "error": f"PMID {args.pmid} 在 PMC 中无对应全文。该论文可能未开放获取。",
                })
                sys.exit(1)
        elif args.pmc_id:
            pmc_num = normalize_pmc_id(args.pmc_id)
        else:
            parser.error("请提供 PMC ID 或使用 --pmid 指定 PubMed ID")

        if args.section:
            result = cmd_read_section(pmc_num, args.section.strip(), api_key)
        else:
            result = cmd_list_sections(pmc_num, api_key)

        print_json(result)

    except Exception as e:
        print_json({
            "success": False,
            "pmc_id": f"PMC{pmc_num}" if "pmc_num" in dir() else None,
            "error": str(e),
        })
        sys.exit(1)


if __name__ == "__main__":
    main()
