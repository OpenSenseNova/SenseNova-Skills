---
name: sn-da-image-caption
description: "Use this skill when image files (.png, .jpg, .jpeg, .gif, .webp, .bmp) are the primary input and the user needs to understand, extract data from, or analyze image content. Provides a pre-configured caption script (scripts/caption.py) that converts images to text descriptions via a vision model — no API key setup needed. Covers: (1) captioning charts/tables/screenshots/diagrams via scripts/caption.py, (2) parsing caption text into structured DataFrames, (3) re-creating visualizations from extracted data, (4) exporting to Excel/CSV. Trigger when user uploads images and wants: data extraction, table OCR, chart analysis, UI description, or diagram understanding. Do NOT trigger for image editing (resize, crop, filter) or image generation."
---

# Image Caption Analysis — 图片描述与数据提取

## Overview

Analyze, extract data from, or understand image files (.png, .jpg, .jpeg, .gif, .webp, .bmp). The core workflow:

1. Run `scripts/caption.py` to get a text description of the image
2. Parse the description into structured data (DataFrame, etc.)
3. Analyze, visualize, or export

## scripts/caption.py — Image Caption

The script converts images to text descriptions via a vision model. Set `VISION_API_KEY` and `VISION_API_BASE` environment variables before running.

### Usage

```bash
# Basic — get text description
python3 scripts/caption.py /mnt/data/image.png

# Custom prompt — guide what to extract
python3 scripts/caption.py /mnt/data/chart.png --prompt "提取所有数值，Markdown 表格格式"

# JSON output — includes detected type, usage stats, cache info
python3 scripts/caption.py /mnt/data/image.png --json

# Batch — process all images in a directory
python3 scripts/caption.py /mnt/data/images/ --batch --output /mnt/data/captions.json

# Override model (optional)
python3 scripts/caption.py /mnt/data/image.png --model gemini-3.1-flash-lite-preview
```

### Options

| Option | Description |
|--------|------------|
| `--prompt, -p` | Custom prompt (overrides auto-detection) |
| `--model, -m` | Vision model (default: gpt-4o) |
| `--json` | Output structured JSON instead of plain text |
| `--batch` | Process all images in a directory |
| `--output, -o` | Output file for batch results |
| `--no-cache` | Skip MD5 cache |

### What it does automatically

- **Type detection**: Detects image type from filename (chart/table/UI/diagram/general) and picks the best prompt
- **Compression**: Images >5MB or >2048px are compressed before sending
- **Caching**: Same image + same prompt → instant cached result, no API cost
- **Error handling**: Retries on failure, returns error message on permanent failure

### JSON output format

```json
{
  "file": "/mnt/data/image.png",
  "type": "chart",
  "description": "这是一张柱状图...",
  "usage": {"prompt_tokens": 1100, "completion_tokens": 400},
  "cached": false
}
```

## Calling from Python

```python
import subprocess, json

CAPTION = "/path/to/skills/sn-da-image-caption/scripts/caption.py"

# Single image
result = subprocess.run(
    ["python3", CAPTION, "/mnt/data/chart.png", "--json",
     "--prompt", "提取图表数据，Markdown 表格输出"],
    capture_output=True, text=True, timeout=60
)
data = json.loads(result.stdout)
description = data["description"]

# Batch
result = subprocess.run(
    ["python3", CAPTION, "/mnt/data/images/", "--batch",
     "--output", "/mnt/data/captions.json"],
    capture_output=True, text=True, timeout=300
)
with open("/mnt/data/captions.json") as f:
    all_captions = json.load(f)
```

## Prompt Strategy

Different image types need different prompts. The script auto-detects, but specifying `--prompt` gives better results.

| Image Type | When | Recommended --prompt |
|-----------|------|---------------------|
| Data chart | 柱状图/折线图/饼图 | `"提取图表标题、坐标轴、每个数据点数值、图例。Markdown 表格输出。"` |
| Table screenshot | 表格截图 | `"提取表格所有内容，Markdown 表格格式，保持行列结构，数值不四舍五入。"` |
| UI screenshot | 界面截图 | `"以前端开发者视角描述：布局、组件、文字、颜色。"` |
| Diagram | 流程图/架构图 | `"描述所有节点、连接关系（A→B）、分支条件。"` |
| General | 照片、其他 | 不传 --prompt，用默认 |

## Parsing Caption Results

Caption 通常返回 Markdown 表格，解析为 DataFrame：

```python
import pandas as pd

def parse_markdown_table(text):
    lines = text.strip().split('\n')
    table_lines = []
    in_table = False
    for line in lines:
        stripped = line.strip()
        if '|' in stripped:
            in_table = True
            table_lines.append(stripped)
        elif in_table:
            break

    data_lines = []
    for l in table_lines:
        cells = [c.strip() for c in l.split('|') if c.strip()]
        if cells and not all(set(c) <= set('-: ') for c in cells):
            data_lines.append(cells)

    if len(data_lines) < 2:
        return None

    header = data_lines[0]
    rows = [r for r in data_lines[1:] if len(r) == len(header)]
    df = pd.DataFrame(rows, columns=header)

    # Auto numeric conversion
    for col in df.columns:
        try:
            cleaned = df[col].str.replace(',', '').str.strip()
            if cleaned.str.endswith('%').any():
                df[col] = pd.to_numeric(cleaned.str.rstrip('%'), errors='coerce')
            else:
                converted = pd.to_numeric(cleaned, errors='coerce')
                if converted.notna().sum() > len(df) * 0.5:
                    df[col] = converted
        except Exception:
            pass
    return df
```

## Visualization

### Chinese Font Setup (MANDATORY)

```python
import matplotlib.pyplot as plt
import matplotlib
import os

font_path = '/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc'
if os.path.exists(font_path):
    matplotlib.rcParams['font.family'] = 'WenQuanYi Zen Hei'
matplotlib.rcParams['axes.unicode_minus'] = False
```

### Color Palette

```python
COLORS = ['#4C72B0', '#55A868', '#C44E52', '#8172B2', '#CCB974', '#64B5CD']
```

### Save & Display

```python
plt.savefig('/mnt/data/chart.png', dpi=150, bbox_inches='tight')
plt.show()
print("![图表](sandbox:/mnt/data/chart.png)")
```

## Export to Excel

```python
from openpyxl.styles import Font, PatternFill, Alignment

output_path = "/mnt/data/result.xlsx"
with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
    df.to_excel(writer, index=False, sheet_name='提取数据')
    ws = writer.sheets['提取数据']
    fill = PatternFill(start_color='4472C4', end_color='4472C4', fill_type='solid')
    for cell in ws[1]:
        cell.font = Font(bold=True, color='FFFFFF')
        cell.fill = fill
        cell.alignment = Alignment(horizontal='center')
    for i, col in enumerate(df.columns, 1):
        w = max(df[col].astype(str).str.len().max(), len(str(col))) + 2
        ws.column_dimensions[chr(64 + i)].width = min(w * 1.2, 40)

print(f"[下载](sandbox:{output_path})")
```

## Multi-Image Processing

```python
import glob

image_files = sorted(glob.glob("/mnt/data/*.png"))
all_dfs = []

for img in image_files:
    r = subprocess.run(
        ["python3", CAPTION, img, "--json", "--prompt", "提取数据，Markdown 表格"],
        capture_output=True, text=True, timeout=60
    )
    desc = json.loads(r.stdout)["description"]
    df = parse_markdown_table(desc)
    if df is not None:
        all_dfs.append(df)

combined = pd.concat(all_dfs, ignore_index=True) if all_dfs else None
```

Or batch mode:

```bash
python3 scripts/caption.py /mnt/data/images/ --batch --output /mnt/data/captions.json
```

## Common Pitfalls

- **Always caption first** — don't guess image content from filenames
- **Use --prompt for precision** — auto-detect is OK, explicit prompt is better
- **Verify extracted data** — check sums, percentages, row counts after parsing
- **Large tables truncate** — caption in two passes: `"提取前半部分"` + `"提取后半部分"`
- **Chinese font** — must set before any matplotlib call, or output is garbled
- **Timeout** — single image ~10-30s, batch set timeout accordingly
