#!/usr/bin/env python3
"""
ArXiv PDF 全文读取器。

直接下载 https://arxiv.org/pdf/<arxiv_id>，抽取整篇 PDF 文本并输出 JSON。

用法：
  python3 arxiv_pdf_paper.py 2309.16609
  python3 arxiv_pdf_paper.py https://arxiv.org/pdf/2309.16609
"""

import argparse
import io
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


from search_utils import get_client, print_json


ABS_BASE = "https://arxiv.org/abs"
PDF_BASE = "https://arxiv.org/pdf"


def _dependency_hint(package: str) -> str:
    skill_dir = Path(__file__).resolve().parents[1]
    requirements = skill_dir / "requirements.txt"
    return (
        f"缺少依赖 {package}。请安装到当前 Python 环境："
        f"python3 -m pip install -r {requirements}"
    )


def normalize_arxiv_id(value: str) -> str:
    """Accept raw arXiv IDs, arXiv-prefixed IDs, abs URLs, and pdf URLs."""
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


def fetch_pdf_bytes(arxiv_id: str) -> bytes:
    clean_id = normalize_arxiv_id(arxiv_id)
    url = f"{PDF_BASE}/{clean_id}"
    with get_client(timeout=60, headers={"Accept": "application/pdf"}) as client:
        response = client.get(url)
        response.raise_for_status()
    return response.content


def extract_pdf_text(pdf_bytes: bytes) -> tuple[str, int]:
    """Return extracted text and page count, preferring pypdf and falling back to pdftotext."""
    try:
        return _extract_with_pypdf(pdf_bytes)
    except ModuleNotFoundError:
        try:
            return _extract_with_python_pdftotext(pdf_bytes)
        except ModuleNotFoundError:
            return _extract_with_pdftotext_binary(pdf_bytes)


def cmd_read_pdf(arxiv_id: str) -> dict[str, Any]:
    clean_id = normalize_arxiv_id(arxiv_id)
    pdf_bytes = fetch_pdf_bytes(clean_id)
    content, page_count = extract_pdf_text(pdf_bytes)

    return {
        "success": True,
        "arxiv_id": clean_id,
        "abs_url": f"{ABS_BASE}/{clean_id}",
        "pdf_url": f"{PDF_BASE}/{clean_id}",
        "content": content,
        "char_count": len(content),
        "page_count": page_count,
        "error": None,
    }


def _extract_with_pypdf(pdf_bytes: bytes) -> tuple[str, int]:
    reader_cls = _load_pdf_reader()
    reader = reader_cls(io.BytesIO(pdf_bytes))
    page_texts = []
    for page in reader.pages:
        text = page.extract_text() or ""
        if text.strip():
            page_texts.append(_clean_text(text))
    return "\n\n".join(page_texts).strip(), len(reader.pages)


def _extract_with_python_pdftotext(pdf_bytes: bytes) -> tuple[str, int]:
    pdf_cls = _load_pdftotext_pdf()
    pages = list(pdf_cls(io.BytesIO(pdf_bytes)))
    content = _clean_text("\n\n".join(page for page in pages if page.strip()))
    return content, len(pages)


def _extract_with_pdftotext_binary(pdf_bytes: bytes) -> tuple[str, int]:
    binary = shutil.which("pdftotext")
    if not binary:
        raise RuntimeError(
            _dependency_hint("pypdf")
            + "；或安装系统工具 poppler/pdftotext 后重试。"
        )

    proc = subprocess.run(
        [binary, "-layout", "-", "-"],
        input=pdf_bytes,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0:
        message = proc.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"pdftotext 解析 PDF 失败：{message or 'unknown error'}")

    text = proc.stdout.decode("utf-8", errors="replace")
    content = _clean_text(text)
    page_count = max(1, text.count("\f") + 1) if text else 0
    return content, page_count


def _load_pdf_reader():
    from pypdf import PdfReader

    return PdfReader


def _load_pdftotext_pdf():
    from pdftotext import PDF

    return PDF


def _clean_text(value: str) -> str:
    value = value.replace("\r\n", "\n").replace("\r", "\n").replace("\f", "\n\n")
    value = re.sub(r"[ \t]+\n", "\n", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="读取 arXiv PDF 全文",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  python3 scripts/arxiv_pdf_paper.py 2309.16609
  python3 scripts/arxiv_pdf_paper.py https://arxiv.org/pdf/2309.16609
""",
    )
    parser.add_argument("arxiv_id", help="arXiv ID 或 arXiv PDF/abs URL")
    args = parser.parse_args()

    try:
        print_json(cmd_read_pdf(args.arxiv_id))
    except Exception as exc:
        print_json({
            "success": False,
            "arxiv_id": normalize_arxiv_id(getattr(args, "arxiv_id", "")),
            "error": str(exc),
        })
        sys.exit(1)


if __name__ == "__main__":
    main()
