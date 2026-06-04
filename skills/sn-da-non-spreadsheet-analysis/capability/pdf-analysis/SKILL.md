---
name: pdf-analysis
description: "PDF 文档解析。自动区分文字型 PDF 与扫描型 PDF，覆盖：文本/表格提取、多页全量扫描、嵌入图表 caption、单位感知数值计算。"
---

# PDF Analysis

## Step 0 — Detect PDF type (text vs scanned)

**Critical first step**: determine whether the PDF has extractable text or is a scanned image.
Never skip this — using the wrong parser wastes time and produces empty results.

```python
import fitz  # PyMuPDF

def detect_pdf_type(pdf_path, sample_pages=3):
    """
    Returns 'text' if PDF has extractable text, 'scanned' if image-based.
    Checks first N pages (or all if fewer).
    """
    doc = fitz.open(pdf_path)
    total_chars = 0
    pages_checked = min(sample_pages, len(doc))

    for i in range(pages_checked):
        page = doc[i]
        text = page.get_text("text")
        total_chars += len(text.strip())

    doc.close()
    avg_chars = total_chars / max(pages_checked, 1)
    pdf_type = 'text' if avg_chars > 50 else 'scanned'
    print(f"PDF type: {pdf_type} (avg {avg_chars:.0f} chars/page, checked {pages_checked} pages)")
    return pdf_type
```

---

## Core Method 1: Text PDF — Full Text Extraction (ALL pages)

```python
import fitz

def extract_text_pdf(pdf_path):
    """Extract text from all pages of a text-based PDF."""
    doc = fitz.open(pdf_path)
    total_pages = len(doc)
    print(f"Total pages: {total_pages}")

    all_text = []
    for i, page in enumerate(doc):
        text = page.get_text("text").strip()
        if text:
            all_text.append(f"=== Page {i+1} ===\n{text}")
        else:
            print(f"  Page {i+1}: no text (may be image — will caption later)")

    doc.close()
    return '\n\n'.join(all_text)

# ⚠️ MUST iterate ALL pages — never stop at page 1
full_text = extract_text_pdf(pdf_path)
print(f"Total text length: {len(full_text)} chars")
```

---

## Core Method 2: Text PDF — Table Extraction

For PDFs with tables, `pdfplumber` gives better table structure than `fitz`:

```python
import pdfplumber
import pandas as pd

def extract_tables_pdf(pdf_path):
    """Extract all tables from all pages as DataFrames."""
    all_tables = []
    with pdfplumber.open(pdf_path) as pdf:
        print(f"Total pages: {len(pdf.pages)}")
        for i, page in enumerate(pdf.pages):
            tables = page.extract_tables()
            for j, tbl in enumerate(tables):
                if not tbl:
                    continue
                # First row as header
                df = pd.DataFrame(tbl[1:], columns=tbl[0])
                # Clean: strip whitespace, replace None
                df = df.applymap(lambda x: x.strip() if isinstance(x, str) else x)
                df = df.dropna(how='all').reset_index(drop=True)
                all_tables.append({'page': i+1, 'table_idx': j, 'df': df})
                print(f"  Page {i+1}, Table {j}: {df.shape[0]}r × {df.shape[1]}c")
                print(df.head(3))
    return all_tables

# Verify table alignment after extraction:
# Print column headers and first 3 rows to confirm row/col mapping is correct
```

---

## Core Method 3: Scanned PDF — OCR via Caption

For scanned PDFs (image-based pages), render each page as PNG and caption:

```python
import fitz
import subprocess, json, os

CAPTION = "/path/to/skills/sn-da-image-caption/scripts/caption.py"

def extract_scanned_pdf(pdf_path, prompt=None, dpi=150):
    """Render each page as image, then caption for text extraction."""
    doc = fitz.open(pdf_path)
    total_pages = len(doc)
    print(f"Scanned PDF: {total_pages} pages, captioning each...")

    all_text = []
    for i, page in enumerate(doc):
        # Render page to PNG
        mat = fitz.Matrix(dpi/72, dpi/72)
        pix = page.get_pixmap(matrix=mat)
        img_path = f"/tmp/pdf_page_{i+1}.png"
        pix.save(img_path)

        # Caption the page image
        cmd = ["python3", CAPTION, img_path, "--json"]
        if prompt:
            cmd += ["--prompt", prompt]
        else:
            cmd += ["--prompt", "提取页面中所有文字和表格内容，保持原始结构，Markdown格式输出。"]

        r = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
        if r.returncode == 0:
            desc = json.loads(r.stdout).get("description", "")
            all_text.append(f"=== Page {i+1} ===\n{desc}")
            print(f"  Page {i+1}: {len(desc)} chars extracted")
        else:
            print(f"  Page {i+1}: caption failed — {r.stderr[:100]}")

    doc.close()
    return '\n\n'.join(all_text)

# Usage for scanned invoice PDFs, bank statements, org charts, etc.
text = extract_scanned_pdf(pdf_path)
```

---

## Core Method 4: Hybrid PDF (mixed text + image pages)

```python
def extract_hybrid_pdf(pdf_path, text_prompt=None, image_prompt=None):
    """Handle PDFs where some pages have text, others are scanned."""
    doc_fitz = fitz.open(pdf_path)
    all_text = []

    for i, page in enumerate(doc_fitz):
        raw_text = page.get_text("text").strip()

        if len(raw_text) > 50:
            # Text page — use directly
            all_text.append(f"=== Page {i+1} (text) ===\n{raw_text}")
        else:
            # Image page — render and caption
            mat = fitz.Matrix(150/72, 150/72)
            pix = page.get_pixmap(matrix=mat)
            img_path = f"/tmp/hybrid_page_{i+1}.png"
            pix.save(img_path)

            cmd = ["python3", CAPTION, img_path, "--json"]
            prompt = image_prompt or "提取页面中所有文字和表格内容，Markdown格式输出。"
            cmd += ["--prompt", prompt]

            r = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
            if r.returncode == 0:
                desc = json.loads(r.stdout).get("description", "")
                all_text.append(f"=== Page {i+1} (image→caption) ===\n{desc}")
            else:
                all_text.append(f"=== Page {i+1} (caption failed) ===")

    doc_fitz.close()
    return '\n\n'.join(all_text)
```

---

## Core Method 5: Extract Embedded Images / Charts from PDF

```python
import fitz

def extract_pdf_images(pdf_path, min_width=100, min_height=100):
    """Extract all embedded images from a PDF (charts, diagrams, photos)."""
    doc = fitz.open(pdf_path)
    image_paths = []

    for page_num, page in enumerate(doc):
        for img_idx, img in enumerate(page.get_images(full=True)):
            xref = img[0]
            base = doc.extract_image(xref)
            img_bytes = base["image"]
            ext = base["ext"]

            img_path = f"/tmp/pdf_img_p{page_num+1}_{img_idx}.{ext}"
            with open(img_path, 'wb') as f:
                f.write(img_bytes)

            # Only keep images above size threshold (skip icons/logos)
            from PIL import Image
            with Image.open(img_path) as im:
                w, h = im.size
            if w >= min_width and h >= min_height:
                image_paths.append({'page': page_num+1, 'path': img_path, 'size': (w, h)})
                print(f"  Page {page_num+1}, img {img_idx}: {w}×{h} → {img_path}")

    doc.close()
    return image_paths

# After extracting, caption each image:
# for img_info in image_paths:
#     caption_image(img_info['path'], prompt="提取图表数据，Markdown 表格输出。")
```

---

## Common Patterns

### Multi-invoice / multi-document PDF (发票汇总)

```python
# When PDF contains multiple invoices (one per page):
tables_by_page = extract_tables_pdf(pdf_path)
invoices = []
for item in tables_by_page:
    df = item['df']
    # Find key fields (flexible column name matching)
    for col in df.columns:
        if '金额' in str(col) or 'amount' in str(col).lower():
            invoices.append({'page': item['page'], 'amount_col': col, 'data': df})
            break
print(f"Found {len(invoices)} pages with amount data")
```

### Numeric extraction with unit awareness

```python
import re

def extract_number_with_unit(text_snippet):
    """
    Extract value and unit from text like '1,760 千港元' or '95,975,196,217.52元'.
    Returns (numeric_value, unit_string).
    """
    # Remove thousands separator
    text_snippet = text_snippet.replace(',', '')
    match = re.search(r'([\d\.]+)\s*(千|万|亿|百万)?\s*(元|港元|美元|人民币|%|percent)?', text_snippet)
    if not match:
        return None, None
    value = float(match.group(1))
    multiplier_map = {'千': 1000, '万': 10000, '亿': 1e8, '百万': 1e6}
    mult = multiplier_map.get(match.group(2), 1)
    unit = match.group(3) or ''
    return value * mult, f"{match.group(2) or ''}{unit}"

# Always verify unit matches what the question asks:
# "多几多" in HKD → answer in 千港元 if source says 千港元
```

### Long document keyword search

```python
def find_in_pdf(pdf_path, keyword, context_chars=200):
    """Search for keyword across all pages, return context snippets."""
    text = extract_text_pdf(pdf_path)
    results = []
    start = 0
    while True:
        idx = text.find(keyword, start)
        if idx < 0:
            break
        snippet = text[max(0, idx-context_chars//2): idx+context_chars]
        results.append({'pos': idx, 'context': snippet})
        start = idx + 1
    print(f"Found '{keyword}' {len(results)} times")
    return results
```

---

## Pitfalls

| Pitfall | Fix |
|---------|-----|
| Use `pdfplumber` on scanned PDF → empty result | Detect type first (Method 0); use OCR path for scanned |
| Only read page 1, miss remaining invoices/data | Always `for page in doc` — never index `[0]` only |
| Table columns misaligned after extraction | Print headers + first 3 rows to verify before computing |
| Report number as % when question asks absolute value | Read question carefully; `extract_number_with_unit()` preserves context |
| Chart data embedded as image → pdfplumber returns nothing | Extract images (Method 5), then caption each |
| Long doc loses cross-page context | Use `find_in_pdf()` for keyword search across full text |
| `.pdf` contains multiple scanned docs (zip of PDFs) | Check if input is dir or archive; unzip first |
