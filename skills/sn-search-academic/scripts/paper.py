#!/usr/bin/env python3
"""Unified academic paper reader with source-specific provider fallback."""

from __future__ import annotations

import argparse
import importlib
import json
import re
import sys
from pathlib import Path
from typing import Any, NamedTuple
from urllib.parse import urlparse


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from search_utils import print_json


class ProviderConfig(NamedTuple):
    module_name: str
    provider: str
    source: str
    full_function: str | None
    section_function: str | None = None
    list_function: str | None = None
    supports_section: bool = False
    custom_full: str | None = None


PROVIDER_GROUPS: dict[str, list[ProviderConfig]] = {
    "arxiv": [
        ProviderConfig(
            module_name="arxiv_paper",
            provider="arxiv_html",
            source="arxiv",
            full_function="cmd_read_full_text",
            section_function="cmd_read_section",
            list_function="cmd_list_sections",
            supports_section=True,
        ),
        ProviderConfig(
            module_name="deepxiv_paper",
            provider="deepxiv",
            source="arxiv",
            full_function="cmd_read_raw",
            section_function="cmd_read_section",
            list_function="cmd_list_sections",
            supports_section=True,
        ),
        ProviderConfig(
            module_name="arxiv_pdf_paper",
            provider="arxiv_pdf",
            source="arxiv",
            full_function="cmd_read_pdf",
            supports_section=False,
        ),
    ],
    "pmc": [
        ProviderConfig(
            module_name="pmc_paper",
            provider="pmc",
            source="pmc",
            full_function=None,
            section_function="cmd_read_section",
            list_function="cmd_list_sections",
            supports_section=True,
            custom_full="pmc_full_text",
        ),
    ],
}


def read_paper(
    paper_id: str,
    source: str = "arxiv",
    section: str | None = None,
    list_section: bool = False,
) -> dict[str, Any]:
    """Read a paper or one section using the configured source fallback chain."""
    clean_source = _normalize_source(source)
    clean_id = _normalize_paper_id(paper_id, clean_source)
    clean_section = section.strip() if section and section.strip() else None
    attempts: list[dict[str, Any]] = []

    for provider in PROVIDER_GROUPS[clean_source]:
        if list_section and not provider.list_function:
            continue
        if clean_section and not provider.supports_section:
            continue

        try:
            if list_section:
                raw_result = _call_provider(provider, clean_id, None, list_section=True)
            else:
                raw_result = _call_provider(provider, clean_id, clean_section)
        except (Exception, SystemExit) as exc:
            attempts.append({"provider": provider.provider, "success": False, "error": _error_message(exc)})
            continue

        success = _provider_succeeded(raw_result, list_section=list_section)
        attempts.append(
            {
                "provider": provider.provider,
                "success": success,
                "error": None if success else _provider_error(raw_result, list_section=list_section),
            }
        )
        if success:
            if list_section:
                return _normalize_list_result(
                    raw_result,
                    clean_id=clean_id,
                    source=clean_source,
                    provider=provider.provider,
                    attempts=attempts,
                )
            return _normalize_success_result(
                raw_result,
                clean_id=clean_id,
                source=clean_source,
                provider=provider.provider,
                requested_section=clean_section,
                attempts=attempts,
            )

    return _failure_result(
        clean_id=clean_id,
        source=clean_source,
        requested_section=clean_section,
        attempts=attempts,
        list_section=list_section,
    )


def _call_provider(
    provider: ProviderConfig,
    paper_id: str,
    section: str | None,
    list_section: bool = False,
) -> dict[str, Any]:
    module = importlib.import_module(provider.module_name)

    if list_section:
        if not provider.list_function:
            raise ValueError(f"{provider.provider} does not support listing sections")
        return getattr(module, provider.list_function)(paper_id)

    if section:
        if not provider.section_function:
            raise ValueError(f"{provider.provider} does not support section reads")
        return getattr(module, provider.section_function)(paper_id, section)

    if provider.custom_full == "pmc_full_text":
        return _call_pmc_full_text(module, paper_id)

    if not provider.full_function:
        raise ValueError(f"{provider.provider} does not support full text reads")
    return getattr(module, provider.full_function)(paper_id)


def _call_pmc_full_text(module: Any, pmc_num: str) -> dict[str, Any]:
    root = module.fetch_pmc_xml(pmc_num)
    sections = module.extract_all_sections(root)
    flat_sections = _flatten_sections(sections)
    content = _join_sections(sections)
    title = _findtext(root, ".//article-title")
    pmid = _findtext(root, ".//article-id[@pub-id-type='pmid']")

    return {
        "success": True,
        "pmc_id": _display_id(pmc_num, "pmc"),
        "pmid": pmid or None,
        "title": title or None,
        "pmc_url": f"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{pmc_num}/",
        "content": content,
        "char_count": len(content),
        "section_count": len(flat_sections),
        "sections": [{"name": s.get("name", ""), "level": s.get("level")} for s in flat_sections],
        "error": None,
    }


def _normalize_success_result(
    raw_result: dict[str, Any],
    clean_id: str,
    source: str,
    provider: str,
    requested_section: str | None,
    attempts: list[dict[str, Any]],
) -> dict[str, Any]:
    content = _as_text(raw_result.get("content")).strip()
    result = dict(raw_result)
    result["success"] = True
    result[_id_key(source)] = _display_id(clean_id, source)
    result["source"] = source
    result["provider"] = provider
    result["provider_rating"] = None
    result["content"] = content
    result.setdefault("char_count", len(content))
    if requested_section is not None:
        result["section"] = result.get("section") or requested_section
    else:
        result.pop("section", None)
    result["attempts"] = list(attempts)
    result["error"] = None
    return result


def _normalize_list_result(
    raw_result: dict[str, Any],
    clean_id: str,
    source: str,
    provider: str,
    attempts: list[dict[str, Any]],
) -> dict[str, Any]:
    result = dict(raw_result)
    sections = result.get("sections")
    if not isinstance(sections, list):
        sections = []
    result["success"] = True
    result[_id_key(source)] = _display_id(clean_id, source)
    result["source"] = source
    result["provider"] = provider
    result["provider_rating"] = None
    result["sections"] = sections
    result["section_count"] = result.get("section_count", len(sections))
    result.pop("content", None)
    result.pop("section", None)
    result["attempts"] = list(attempts)
    result["error"] = None
    return result


def _failure_result(
    clean_id: str,
    source: str,
    requested_section: str | None,
    attempts: list[dict[str, Any]],
    list_section: bool = False,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "success": False,
        _id_key(source): _display_id(clean_id, source),
        "source": source,
        "provider": None,
        "provider_rating": None,
        "content": None,
        "attempts": list(attempts),
        "error": _combined_error(source, attempts),
    }
    if list_section:
        result.pop("content", None)
        result["sections"] = []
        result["section_count"] = 0
    if requested_section is not None:
        result["section"] = requested_section
    return result


def _provider_succeeded(result: dict[str, Any], list_section: bool = False) -> bool:
    if not isinstance(result, dict) or result.get("success") is not True:
        return False
    if list_section:
        sections = result.get("sections")
        return isinstance(sections, list) and bool(sections)
    content = result.get("content")
    return isinstance(content, str) and bool(content.strip())


def _provider_error(result: dict[str, Any], list_section: bool = False) -> str:
    if isinstance(result, dict):
        error = result.get("error")
        if error:
            return str(error)
    if list_section:
        return "provider returned no sections"
    return "provider returned no content"


def _combined_error(source: str, attempts: list[dict[str, Any]]) -> str:
    if not attempts:
        return f"No {source} provider was available"
    parts = [
        f"{attempt.get('provider')}: {attempt.get('error') or 'failed'}"
        for attempt in attempts
        if not attempt.get("success")
    ]
    return "; ".join(parts) or f"All {source} providers failed"


def _normalize_source(source: str | None) -> str:
    clean_source = (source or "arxiv").strip().lower()
    if clean_source not in PROVIDER_GROUPS:
        allowed = ", ".join(PROVIDER_GROUPS)
        raise ValueError(f"不支持的搜索源：{clean_source}；支持：{allowed}")
    return clean_source


def _normalize_paper_id(paper_id: str, source: str) -> str:
    raw = (paper_id or "").strip()
    if not raw:
        raise ValueError("id 不能为空")
    if source == "pmc":
        return _normalize_pmc_id(raw)
    return _normalize_arxiv_id(raw)


def _normalize_arxiv_id(value: str) -> str:
    raw = value.strip()
    parsed = urlparse(raw)
    if parsed.scheme and parsed.netloc:
        path = parsed.path.strip("/")
        if path.startswith("pdf/"):
            raw = path[len("pdf/") :]
        elif path.startswith("abs/"):
            raw = path[len("abs/") :]
        else:
            raw = path.rsplit("/", 1)[-1]

    raw = raw.replace("arXiv:", "").replace("arxiv:", "").strip()
    return re.sub(r"\.pdf$", "", raw, flags=re.I)


def _normalize_pmc_id(value: str) -> str:
    raw = value.strip()
    parsed = urlparse(raw)
    if parsed.scheme and parsed.netloc:
        match = re.search(r"PMC(\d+)", parsed.path, flags=re.I)
        if match:
            raw = match.group(1)
        else:
            raw = parsed.path.rsplit("/", 1)[-1]
    raw = re.sub(r"^[Pp][Mm][Cc]", "", raw).strip().strip("/")
    if not raw:
        raise ValueError("pmc id 不能为空")
    return raw


def _display_id(clean_id: str, source: str) -> str:
    if source == "pmc":
        return f"PMC{clean_id}"
    return clean_id


def _id_key(source: str) -> str:
    return "pmc_id" if source == "pmc" else "arxiv_id"


def _join_sections(sections: list[dict[str, Any]]) -> str:
    blocks: list[str] = []

    def visit(section: dict[str, Any]) -> None:
        name = _as_text(section.get("name")).strip()
        text = _as_text(section.get("text")).strip()
        if name and text:
            blocks.append(f"{name}\n{text}")
        elif name:
            blocks.append(name)
        elif text:
            blocks.append(text)
        for child in section.get("subsections") or []:
            if isinstance(child, dict):
                visit(child)

    for section in sections:
        visit(section)
    return "\n\n".join(blocks).strip()


def _flatten_sections(sections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    flat: list[dict[str, Any]] = []

    def visit(section: dict[str, Any]) -> None:
        flat.append(section)
        for child in section.get("subsections") or []:
            if isinstance(child, dict):
                visit(child)

    for section in sections:
        visit(section)
    return flat


def _findtext(root: Any, path: str) -> str:
    try:
        value = root.findtext(path, "")
    except TypeError:
        value = root.findtext(path)
    except AttributeError:
        return ""
    return _as_text(value).strip()


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return " ".join(_as_text(item) for item in value if _as_text(item))
    return str(value)


def _error_message(exc: BaseException) -> str:
    message = str(exc)
    if message:
        return message
    code = getattr(exc, "code", None)
    if code is not None:
        return str(code)
    return exc.__class__.__name__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="统一读取 arXiv/PMC 论文全文或章节")
    parser.add_argument("paper_id", metavar="id", help="论文 ID，如 arXiv:2603.00729 或 PMC11119143")
    parser.add_argument("--source", choices=sorted(PROVIDER_GROUPS), default="arxiv", help="搜索源：arxiv 或 pmc（默认 arxiv）")
    parser.add_argument("--section", "-s", help="要读取的章节；不填则返回全文")
    parser.add_argument("--list_section", "--list-section", action="store_true", help="列出论文可用章节，不返回正文")
    parser.add_argument("--output", "-o", help="将最终 JSON 结果写入指定文件")
    return parser


def _write_output_file(result: dict[str, Any], output_path: str) -> None:
    path = Path(output_path).expanduser().resolve()
    result["output_path"] = str(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.list_section and args.section:
        parser.error("--list_section 不能和 --section 同时使用")

    try:
        if args.list_section:
            result = read_paper(args.paper_id, source=args.source, list_section=True)
        else:
            result = read_paper(args.paper_id, source=args.source, section=args.section)
    except Exception as exc:
        source = getattr(args, "source", "arxiv")
        paper_id = getattr(args, "paper_id", "")
        clean_source = source if source in PROVIDER_GROUPS else "arxiv"
        result = {
            "success": False,
            _id_key(clean_source): _display_id(paper_id, clean_source),
            "source": source,
            "provider": None,
            "provider_rating": None,
            "content": None,
            "error": str(exc),
        }
        if getattr(args, "section", None):
            result["section"] = args.section

    output_result = dict(result)
    if args.output:
        try:
            _write_output_file(output_result, args.output)
        except Exception as exc:
            output_result = dict(result)
            output_result["success"] = False
            output_result["error"] = f"Failed to write output file: {exc}"
            output_result["output_path"] = str(Path(args.output).expanduser().resolve())

    print_json(output_result)
    if not output_result["success"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
