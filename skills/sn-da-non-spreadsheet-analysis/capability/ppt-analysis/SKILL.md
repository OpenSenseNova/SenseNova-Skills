---
name: ppt-analysis
description: "PPT (.pptx/.ppt) 全量解析。覆盖：所有 slide 文本/表格/图表提取、嵌入图片 caption、纯图片 slide 渲染识别、数据标签提取。"
---

# PPT Analysis — .pptx / .ppt

## Environment

```python
from pptx import Presentation
from pptx.util import Inches
import os, subprocess, json

# python-pptx is available
# For .ppt (old binary format): convert via libreoffice
def load_pptx(path):
    if path.lower().endswith('.ppt'):
        import subprocess
        out_dir = os.path.dirname(path)
        subprocess.run(
            ['libreoffice', '--headless', '--convert-to', 'pptx', '--outdir', out_dir, path],
            check=True, capture_output=True
        )
        path = path.rsplit('.', 1)[0] + '.pptx'
    return Presentation(path), path
```

---

## Core Method 1: Full Text Extraction (ALL slides)

```python
def extract_all_slides_text(pptx_path):
    """
    Extract text from every slide: text frames, tables, chart titles.
    For slides with no extractable text, flag them for image captioning.
    """
    prs, _ = load_pptx(pptx_path)
    slides_data = []

    for slide_num, slide in enumerate(prs.slides, start=1):
        slide_texts = []
        has_text = False

        for shape in slide.shapes:
            # Text frame (most common)
            if shape.has_text_frame:
                for para in shape.text_frame.paragraphs:
                    text = para.text.strip()
                    if text:
                        slide_texts.append(text)
                        has_text = True

            # Table
            if shape.has_table:
                tbl = shape.table
                for row in tbl.rows:
                    row_text = '\t'.join(cell.text.strip() for cell in row.cells)
                    if row_text.strip():
                        slide_texts.append(row_text)
                        has_text = True

            # Chart title
            if shape.shape_type == 3:  # MSO_SHAPE_TYPE.CHART
                try:
                    if shape.chart.has_title:
                        title = shape.chart.chart_title.text_frame.text
                        slide_texts.append(f"[Chart: {title}]")
                        has_text = True
                except Exception:
                    pass

        slides_data.append({
            'slide': slide_num,
            'text': '\n'.join(slide_texts),
            'has_text': has_text,
            'needs_caption': not has_text  # flag image-only slides
        })

    print(f"Total slides: {len(slides_data)}")
    image_only = sum(1 for s in slides_data if s['needs_caption'])
    print(f"Slides with text: {len(slides_data) - image_only}, image-only: {image_only}")
    return slides_data
```

---

## Core Method 2: Table Extraction (Structured)

```python
import pandas as pd

def extract_pptx_tables(pptx_path):
    """Extract all tables from all slides as DataFrames."""
    prs, _ = load_pptx(pptx_path)
    all_tables = []

    for slide_num, slide in enumerate(prs.slides, start=1):
        for shape in slide.shapes:
            if not shape.has_table:
                continue
            tbl = shape.table
            rows = []
            for row in tbl.rows:
                rows.append([cell.text.strip() for cell in row.cells])

            if not rows:
                continue

            # Use first row as header
            try:
                df = pd.DataFrame(rows[1:], columns=rows[0])
            except Exception:
                df = pd.DataFrame(rows)

            all_tables.append({'slide': slide_num, 'df': df})
            print(f"  Slide {slide_num}: table {df.shape[0]}r × {df.shape[1]}c")
            print(df.head(3).to_string())

    return all_tables
```

---

## Core Method 3: Chart Data Extraction

`python-pptx` can read Chart data when it's stored as embedded Excel data.
If that fails, fall back to captioning the slide image.

```python
def extract_chart_data(pptx_path):
    """
    Extract data series from Chart shapes.
    Returns list of {slide, chart_title, series_name, categories, values}.
    """
    prs, _ = load_pptx(pptx_path)
    charts = []

    for slide_num, slide in enumerate(prs.slides, start=1):
        for shape in slide.shapes:
            if shape.shape_type != 3:  # not a chart
                continue
            try:
                chart = shape.chart
                title = chart.chart_title.text_frame.text if chart.has_title else f"Chart_S{slide_num}"

                for plot in chart.plots:
                    for series in plot.series:
                        try:
                            categories = [str(pt.label) for pt in series.data_labels] if hasattr(series, 'data_labels') else []
                            values = [pt.value for pt in series.values] if hasattr(series, 'values') else []
                            # Alternative: use xChart data
                            if not values:
                                values = list(series.values)
                        except Exception as e:
                            values = []
                            categories = []

                        charts.append({
                            'slide': slide_num,
                            'chart_title': title,
                            'series': getattr(series, 'name', ''),
                            'categories': categories,
                            'values': values
                        })
            except Exception as e:
                print(f"  Slide {slide_num}: chart extraction failed ({e}) — will use caption")

    return charts
```

---

## Core Method 4: Render Image-Only Slides → Caption

When a slide has no extractable text (pure image/screenshot slides):

```python
import fitz  # PyMuPDF can also render PPTX via LibreOffice conversion

CAPTION = "/path/to/skills/sn-da-image-caption/scripts/caption.py"

def caption_image_slides(pptx_path, slides_data, prompt=None):
    """
    For slides flagged as 'needs_caption', render to PNG and caption.
    Uses LibreOffice to convert PPTX to PDF first, then renders pages.
    """
    image_slides = [s for s in slides_data if s['needs_caption']]
    if not image_slides:
        print("No image-only slides to caption.")
        return slides_data

    # Convert PPTX → PDF (preserves slide visuals)
    out_dir = "/tmp"
    r = subprocess.run(
        ['libreoffice', '--headless', '--convert-to', 'pdf', '--outdir', out_dir, pptx_path],
        capture_output=True, text=True
    )
    pdf_name = os.path.basename(pptx_path).rsplit('.', 1)[0] + '.pdf'
    pdf_path = os.path.join(out_dir, pdf_name)

    if not os.path.exists(pdf_path):
        print(f"LibreOffice conversion failed: {r.stderr[:200]}")
        return slides_data

    # Render each image-only slide
    doc = fitz.open(pdf_path)
    for s in image_slides:
        page_idx = s['slide'] - 1  # 0-indexed
        if page_idx >= len(doc):
            continue
        page = doc[page_idx]
        mat = fitz.Matrix(150/72, 150/72)
        pix = page.get_pixmap(matrix=mat)
        img_path = f"/tmp/slide_{s['slide']}.png"
        pix.save(img_path)

        # Caption the slide image
        cmd = ["python3", CAPTION, img_path, "--json"]
        p = prompt or "提取幻灯片中所有文字、数值和表格内容，保持结构，Markdown格式输出。"
        cmd += ["--prompt", p]
        cr = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
        if cr.returncode == 0:
            desc = json.loads(cr.stdout).get("description", "")
            s['text'] = desc
            s['needs_caption'] = False
            print(f"  Slide {s['slide']}: captioned ({len(desc)} chars)")
        else:
            print(f"  Slide {s['slide']}: caption failed — {cr.stderr[:80]}")

    doc.close()
    return slides_data
```

---

## Common Patterns

### Keyword search across all slides

```python
def find_in_pptx(pptx_path, keyword, slides_data=None):
    """Find keyword across all slides (after text extraction + captioning)."""
    if slides_data is None:
        slides_data = extract_all_slides_text(pptx_path)

    results = []
    for s in slides_data:
        if keyword in s.get('text', ''):
            idx = s['text'].find(keyword)
            context = s['text'][max(0, idx-100):idx+200]
            results.append({'slide': s['slide'], 'context': context})

    print(f"'{keyword}' found in {len(results)} slides: {[r['slide'] for r in results]}")
    return results
```

### Time-line / process extraction from PPT

```python
def extract_timeline(pptx_path, date_pattern=r'\d{4}[年/\-]\d{1,2}'):
    """Extract date-tagged events from slide text."""
    import re
    slides_data = extract_all_slides_text(pptx_path)
    events = []
    for s in slides_data:
        for line in s['text'].split('\n'):
            if re.search(date_pattern, line):
                events.append({'slide': s['slide'], 'event': line.strip()})
    return events
```

### Statistics from PPT tables (e.g., 录用占比)

```python
def compute_ratio_from_pptx_table(pptx_path, numerator_col, denominator_col):
    """Example: compute ratio = col_A / col_B for all rows."""
    tables = extract_pptx_tables(pptx_path)
    for item in tables:
        df = item['df']
        # Try to find columns (flexible matching)
        num_col = next((c for c in df.columns if numerator_col in c), None)
        den_col = next((c for c in df.columns if denominator_col in c), None)
        if num_col and den_col:
            df[num_col] = pd.to_numeric(df[num_col].str.replace('人', '').str.strip(), errors='coerce')
            df[den_col] = pd.to_numeric(df[den_col].str.replace('人', '').str.strip(), errors='coerce')
            df['ratio'] = (df[num_col] / df[den_col] * 100).round(0).astype(str) + '%'
            print(df[['slide' if 'slide' in df.columns else df.columns[0], num_col, den_col, 'ratio']].to_string())
```

---

## Full Workflow Example

```python
pptx_path = "/mnt/data/report.pptx"

# 1. Extract text from all slides
slides_data = extract_all_slides_text(pptx_path)

# 2. Caption image-only slides
slides_data = caption_image_slides(pptx_path, slides_data)

# 3. Combine all text for analysis
all_text = '\n\n'.join(
    f"[Slide {s['slide']}]\n{s['text']}"
    for s in slides_data if s.get('text')
)

# 4. Search or analyze
results = find_in_pptx(pptx_path, '录用占比', slides_data)

# 5. Extract tables if needed
tables = extract_pptx_tables(pptx_path)
```

---

## Pitfalls

| Pitfall | Fix |
|---------|-----|
| Skip slides with no text → miss chart data | Flag `needs_caption`, render & caption (Method 4) |
| `shape.chart.plots[0].series` fails → no data | Catch exception, fall back to captioning the slide |
| Table columns misread (企业名 vs 岗位名) | Print headers + first 3 rows before computing; verify column meaning |
| Only read first N slides | Always `for slide in prs.slides` — no index limit |
| `.ppt` format → `python-pptx` can't open | Convert to `.pptx` via libreoffice first |
| PPT has overlapping text boxes → garbled order | Sort shapes by top-left position: `sorted(slide.shapes, key=lambda s: (s.top, s.left))` |
