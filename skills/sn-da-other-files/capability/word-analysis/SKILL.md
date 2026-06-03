---
name: word-analysis
description: "Word (.docx/.doc) 文档全量解析。覆盖：正文/段落文本提取、表格数据提取、高亮/颜色格式读取、多文件汇总对比、嵌入图片转 caption。"
---

# Word Analysis — .docx / .doc

## Environment

```python
from docx import Document
import os

# python-docx is available; for .doc (old format) convert via libreoffice first
def load_doc(path):
    """Load .docx directly; convert .doc to .docx first if needed."""
    if path.lower().endswith('.doc'):
        import subprocess
        out_dir = os.path.dirname(path)
        subprocess.run(
            ['libreoffice', '--headless', '--convert-to', 'docx', '--outdir', out_dir, path],
            check=True, capture_output=True
        )
        path = path.rsplit('.', 1)[0] + '.docx'
    return Document(path)
```

---

## Core Method 1: Full Text Extraction

```python
def extract_full_text(doc_path):
    """Extract all text: paragraphs + table cells, in document order."""
    doc = load_doc(doc_path)
    lines = []

    # Iterate paragraphs and tables in body order
    from docx.oxml.ns import qn
    for block in doc.element.body:
        tag = block.tag.split('}')[-1]
        if tag == 'p':
            # Paragraph
            from docx.text.paragraph import Paragraph
            para = Paragraph(block, doc)
            text = para.text.strip()
            if text:
                lines.append(text)
        elif tag == 'tbl':
            # Table
            from docx.table import Table
            tbl = Table(block, doc)
            for row in tbl.rows:
                row_text = '\t'.join(cell.text.strip() for cell in row.cells)
                if row_text.strip():
                    lines.append(row_text)

    return '\n'.join(lines)

# Usage
text = extract_full_text("/mnt/data/doc.docx")
print(text[:2000])  # preview first 2000 chars
```

---

## Core Method 2: Table Extraction (Structured)

```python
import pandas as pd

def extract_all_tables(doc_path):
    """Extract all tables from a Word document as list of DataFrames."""
    doc = load_doc(doc_path)
    tables = []

    for i, tbl in enumerate(doc.tables):
        rows = []
        for row in tbl.rows:
            rows.append([cell.text.strip() for cell in row.cells])
        if not rows:
            continue
        # Use first row as header if it looks like a header
        df = pd.DataFrame(rows[1:], columns=rows[0]) if rows else pd.DataFrame()
        tables.append((i, df))
        print(f"Table {i}: {df.shape[0]} rows × {df.shape[1]} cols")
        print(df.head(3))

    return tables

# Usage
tables = extract_all_tables("/mnt/data/doc.docx")
```

---

## Core Method 3: Format-Aware Extraction (Color / Highlight)

Some questions require reading cell background color or text highlight color
(e.g., "标黄的行", "红色文字"). Use XML-level access:

```python
from docx import Document
from docx.oxml.ns import qn
from lxml import etree

def get_paragraph_highlight(para):
    """Return highlight color name of first run, or None."""
    for run in para.runs:
        rPr = run._r.find(qn('w:rPr'))
        if rPr is not None:
            hl = rPr.find(qn('w:highlight'))
            if hl is not None:
                return hl.get(qn('w:val'))  # e.g. 'yellow', 'cyan', 'red'
    return None

def get_table_cell_shading(cell):
    """Return background color hex of a table cell, or None."""
    tcPr = cell._tc.find(qn('w:tcPr'))
    if tcPr is not None:
        shd = tcPr.find(qn('w:shd'))
        if shd is not None:
            return shd.get(qn('w:fill'))  # hex color, e.g. 'FFFF00'
    return None

# Example: find all highlighted paragraphs
def find_highlighted_rows(doc_path, color='yellow'):
    doc = load_doc(doc_path)
    highlighted = []
    for i, para in enumerate(doc.paragraphs):
        hl = get_paragraph_highlight(para)
        if hl == color or (color == 'yellow' and hl in ('yellow', 'FFFF00')):
            highlighted.append((i, para.text))
    return highlighted

# For table cells with yellow background:
def find_highlighted_table_cells(doc_path, fill_colors=('FFFF00', 'FFD700')):
    doc = load_doc(doc_path)
    results = []
    for t_idx, tbl in enumerate(doc.tables):
        for r_idx, row in enumerate(tbl.rows):
            for c_idx, cell in enumerate(row.cells):
                color = get_table_cell_shading(cell)
                if color and color.upper() in fill_colors:
                    results.append({
                        'table': t_idx, 'row': r_idx, 'col': c_idx,
                        'color': color, 'text': cell.text.strip()
                    })
    return results
```

---

## Core Method 4: Multi-File Aggregation

When the user asks about "these files" or the input is a directory:

```python
def process_all_docs(file_list, extractor_fn):
    """Apply extractor to all files and aggregate results."""
    all_results = []
    for path in file_list:
        print(f"\n=== Processing: {os.path.basename(path)} ===")
        try:
            result = extractor_fn(path)
            all_results.append({'file': os.path.basename(path), 'data': result})
        except Exception as e:
            print(f"  ERROR: {e}")
    return all_results

# Example: extract text from all .docx in a directory
doc_files = [f for f in all_files if f.lower().endswith(('.docx', '.doc'))]
results = process_all_docs(doc_files, extract_full_text)
```

---

## Core Method 5: Embedded Images → Caption

When a Word doc contains embedded images (charts, screenshots):

```python
import zipfile, io, subprocess, json

CAPTION = "/path/to/skills/sn-da-image-caption/scripts/caption.py"

def extract_and_caption_images(doc_path, prompt=None):
    """Extract all images from .docx and caption each one."""
    # .docx is a ZIP archive; images are in word/media/
    results = []
    with zipfile.ZipFile(doc_path, 'r') as z:
        media_files = [n for n in z.namelist() if n.startswith('word/media/')]
        for media in media_files:
            ext = os.path.splitext(media)[-1].lower()
            if ext not in ('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.wmf', '.emf'):
                continue
            # Save to temp
            tmp_path = f"/tmp/{os.path.basename(media)}"
            with z.open(media) as src, open(tmp_path, 'wb') as dst:
                dst.write(src.read())
            # Caption
            cmd = ["python3", CAPTION, tmp_path, "--json"]
            if prompt:
                cmd += ["--prompt", prompt]
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if r.returncode == 0:
                desc = json.loads(r.stdout).get("description", "")
                results.append({'image': media, 'caption': desc})
                print(f"  {media}: {desc[:100]}...")
            else:
                print(f"  {media}: caption failed — {r.stderr[:80]}")
    return results
```

---

## Common Patterns

### Font/size check (字号检查)
```python
from docx.shared import Pt

def check_font_sizes(doc_path):
    doc = load_doc(doc_path)
    issues = []
    for i, para in enumerate(doc.paragraphs):
        for run in para.runs:
            size = run.font.size
            size_pt = size.pt if size else None
            # Also check style-level font
            if size_pt is None:
                style_size = run.style.font.size if run.style else None
                size_pt = style_size.pt if style_size else None
            issues.append({'para': i, 'text': run.text[:30], 'size_pt': size_pt})
    return issues
```

### Spell/grammar check (错别字)
- Use full-text extraction, then search with string matching or pass to LLM for proofreading
- Do NOT try to install hunspell or other spell-check tools

### Keyword search (全文定位)
```python
def find_keyword(doc_path, keyword):
    text = extract_full_text(doc_path)
    idx = text.find(keyword)
    if idx >= 0:
        context = text[max(0, idx-100):idx+200]
        print(f"Found '{keyword}' at pos {idx}:\n{context}")
    else:
        print(f"'{keyword}' not found. Try broader search.")
        # Try case-insensitive or partial match
        for kw in keyword.split():
            if kw in text:
                print(f"  Partial match for '{kw}'")
```

---

## Pitfalls

| Pitfall | Fix |
|---------|-----|
| Only read `doc.paragraphs`, miss tables | Use the body-order iterator in Method 1 |
| Single file when input is multi-file | Check `os.path.isdir()`, iterate all |
| Highlighted cells not detected | Use XML-level `w:shd` / `w:highlight` (Method 3) |
| `.doc` format fails to open | Convert to `.docx` via libreoffice (Method 0) |
| Embedded charts look empty | Extract images from ZIP, caption each (Method 5) |
| Font size is None | Check both run-level and style-level (Method for font check) |
