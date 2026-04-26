---
name: sn-da-large-file-analysis
description: "High-performance analysis for Excel datasets with 10k+ rows. Provides streaming read via openpyxl read_only + iter_rows for 100k+ rows, Parquet conversion, memory optimization, chunked processing, and large-file write patterns. Must load this skill when data >= 10k rows."
---

# Large Scale Excel Analysis Skill

## Mandatory Rules

> **When total rows >= 10,000, you MUST use the methods in this skill.**

| Data Scale | Read Strategy | Reason |
|-----------|---------------|--------|
| < 10k rows | `pd.read_excel()` directly | No memory pressure |
| 10k–100k rows | `pd.read_excel()` → convert to Parquet → `pd.read_parquet()` for analysis | Avoid repeated slow reads |
| 100k–1M rows | **openpyxl `read_only` + `iter_rows` streaming** → Parquet | `pd.read_excel()` will OOM or timeout |
| > 1M rows | Streaming read + **multi-sheet split** (Excel max 1,048,576 rows per sheet) | Must chunk |

**Prohibited:**
- Do NOT use `pd.read_excel()` to fully load 100k+ row files
- Do NOT search for fonts with `fc-list`, `find ... fonts`, or install packages with `pip install`
- Do NOT use `df.iterrows()` on large DataFrames (use `itertuples()` or vectorized ops)
- Do NOT use `df.apply(lambda...)` for operations that can be vectorized

---

## Environment Setup

```python
import pandas as pd
import numpy as np
import os
import gc

pd.options.mode.copy_on_write = True

# CJK font setup (fixed paths — do NOT search for fonts)
# ⚠️ Copy this block as-is. Do NOT use fc-list, find, subprocess, or glob to locate fonts.
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

_FONT_PATHS = [
    '/mnt/afs_agents/SimHei.ttf',
    '/mnt/afs_agents/mnt/data/SimHei.ttf',
    os.path.expanduser('~/.fonts/SimHei.ttf'),
    '/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc',
    '/usr/share/fonts/SimHei.ttf',
]
for _p in _FONT_PATHS:
    if os.path.exists(_p):
        fm.fontManager.addfont(_p)
        matplotlib.rcParams['font.family'] = fm.FontProperties(fname=_p).get_name()
        break
matplotlib.rcParams['axes.unicode_minus'] = False
```

---

## Core Method 1: Inspect File Structure (Without Loading Data)

Before any operation on a large file, inspect sheets and row counts **without loading data into memory**:

```python
import openpyxl

def inspect_excel(file_path):
    """Stream-inspect Excel structure. Returns {sheet_name: {rows, columns}}."""
    wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
    info = {}
    for name in wb.sheetnames:
        ws = wb[name]
        row_count = 0
        header = None
        for i, row in enumerate(ws.iter_rows(values_only=True)):
            if i == 0:
                header = [str(c) if c is not None else f"Col_{j}" for j, c in enumerate(row)]
            else:
                row_count += 1
        info[name] = {"rows": row_count, "columns": header}
    wb.close()
    return info

# Usage
file_info = inspect_excel(file_path)
for sheet, meta in file_info.items():
    print(f"Sheet '{sheet}': {meta['rows']} rows, {len(meta['columns'])} cols")
    print(f"  Columns: {meta['columns'][:10]}...")
total_rows = sum(m['rows'] for m in file_info.values())
print(f"Total rows: {total_rows}")
```

---

## Core Method 2: Streaming Read → Parquet (100k+ Rows)

For 100k+ row files, **never** use `pd.read_excel()`. Use openpyxl streaming → Parquet:

```python
import openpyxl
import pyarrow as pa
import pyarrow.parquet as pq

def stream_excel_to_parquet(excel_path, parquet_path, sheet_name=None, chunk_size=50000):
    """Stream Excel rows to Parquet with constant memory usage.

    All columns are cast to string to avoid cross-chunk schema mismatches
    (Excel mixed-type columns may be all-None in some chunks, causing PyArrow
    to infer null type instead of string). Convert numeric columns after loading
    Parquet with pd.to_numeric() as needed.
    """
    wb = openpyxl.load_workbook(excel_path, read_only=True, data_only=True)
    ws = wb[sheet_name] if sheet_name else wb.active

    header = None
    writer = None
    chunk_rows = []
    total_written = 0

    def _flush(rows):
        nonlocal writer
        table = pa.table({
            col: pa.array(
                [str(r[idx]) if r[idx] is not None else None for r in rows],
                type=pa.string(),
            )
            for idx, col in enumerate(header)
        })
        if writer is None:
            writer = pq.ParquetWriter(parquet_path, table.schema)
        writer.write_table(table)

    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i == 0:
            header = [str(c) if c is not None else f"Col_{j}" for j, c in enumerate(row)]
            continue

        chunk_rows.append(list(row))

        if len(chunk_rows) >= chunk_size:
            _flush(chunk_rows)
            total_written += len(chunk_rows)
            print(f"  Written {total_written:,} rows...")
            chunk_rows = []
            gc.collect()

    if chunk_rows:
        _flush(chunk_rows)
        total_written += len(chunk_rows)

    if writer:
        writer.close()
    wb.close()
    print(f"Done: {total_written:,} rows -> {parquet_path}")
    return total_written
```

---

## Core Method 3: Medium File Parquet Conversion (10k–100k Rows)

For 10k–100k rows, `pd.read_excel()` won't OOM, but Parquet is much faster for repeated analysis:

```python
def convert_excel_to_parquet(excel_path, parquet_path, sheet_name=0):
    """Medium file: pd.read_excel -> Parquet cache."""
    if os.path.exists(parquet_path):
        print(f"Cache exists: {parquet_path}")
        return
    df = pd.read_excel(excel_path, sheet_name=sheet_name)
    df.columns = df.columns.astype(str)
    df.to_parquet(parquet_path, engine='pyarrow', compression='snappy')
    row_count = len(df)
    del df
    gc.collect()
    print(f"Converted {row_count:,} rows -> {parquet_path}")
```

---

## Core Method 4: Memory Optimization (Type Downcasting)

After loading Parquet, further reduce memory footprint:

```python
def optimize_dtypes(df):
    """Auto-downcast numeric types + convert low-cardinality strings to Category.
    Typically saves 50-80% memory."""
    start_mb = df.memory_usage(deep=True).sum() / 1024**2

    for col in df.select_dtypes(include=['int64', 'int32']).columns:
        c_min, c_max = df[col].min(), df[col].max()
        if c_min >= np.iinfo(np.int8).min and c_max <= np.iinfo(np.int8).max:
            df[col] = df[col].astype(np.int8)
        elif c_min >= np.iinfo(np.int16).min and c_max <= np.iinfo(np.int16).max:
            df[col] = df[col].astype(np.int16)
        elif c_min >= np.iinfo(np.int32).min and c_max <= np.iinfo(np.int32).max:
            df[col] = df[col].astype(np.int32)

    for col in df.select_dtypes(include=['float64']).columns:
        df[col] = df[col].astype(np.float32)

    for col in df.select_dtypes(include=['object', 'string']).columns:
        if df[col].nunique() / max(len(df), 1) < 0.5:
            df[col] = df[col].astype('category')

    end_mb = df.memory_usage(deep=True).sum() / 1024**2
    print(f"Memory: {start_mb:.1f} MB -> {end_mb:.1f} MB (saved {(1 - end_mb/start_mb)*100:.0f}%)")
    return df
```

---

## Core Method 5: Large File Writing

```python
def write_large_excel(df, output_path, sheet_name="Sheet1"):
    """Auto-select write strategy based on data size."""
    total_cells = len(df) * len(df.columns)

    if len(df) > 1_000_000:
        csv_path = output_path.rsplit('.', 1)[0] + '.csv'
        df.to_csv(csv_path, index=False)
        print(f"Over 1M rows — exported as CSV: {csv_path}")
        return csv_path

    if total_cells > 50_000:
        from openpyxl import Workbook
        from openpyxl.cell import WriteOnlyCell

        wb = Workbook(write_only=True)
        ws = wb.create_sheet(title=sheet_name)
        ws.append(list(df.columns))
        for idx, row in enumerate(df.itertuples(index=False)):
            ws.append([None if pd.isna(v) else v for v in row])
            if (idx + 1) % 100_000 == 0:
                print(f"  Written {idx + 1:,} rows...")
        wb.save(output_path)
        wb.close()
        print(f"write_only mode: {len(df):,} rows -> {output_path}")
    else:
        df.to_excel(output_path, index=False, sheet_name=sheet_name)
        print(f"Standard write: {len(df):,} rows -> {output_path}")
    return output_path
```

---

## Example 1: 100k-Row Table — Column Distribution + Chart

**Scenario**: User has a 100k-row sales Excel file and wants regional sales distribution with a bar chart.

```python
import pandas as pd
import os, gc

excel_path = "sales_100k.xlsx"
parquet_path = "sales_100k.parquet"

# === Step 1: Inspect structure ===
file_info = inspect_excel(excel_path)
total_rows = sum(m['rows'] for m in file_info.values())
print(f"Total rows: {total_rows}")

# === Step 2: Choose read strategy by row count ===
if total_rows >= 100_000:
    stream_excel_to_parquet(excel_path, parquet_path)
else:
    convert_excel_to_parquet(excel_path, parquet_path)

# === Step 3: Load Parquet + optimize memory ===
df = pd.read_parquet(parquet_path)
df = optimize_dtypes(df)
print(f"Shape: {df.shape}")
print(df.head(3))

# === Step 4: Analysis ===
region_sales = df.groupby('Region')['Sales'].sum().sort_values(ascending=False)
print(region_sales)

# === Step 5: Visualization ===
fig, ax = plt.subplots(figsize=(10, 6))
region_sales.plot(kind='bar', ax=ax, color='#4C72B0')
ax.set_title('Sales by Region')
ax.set_ylabel('Sales')
plt.tight_layout()
plt.savefig('region_sales.png', dpi=150, bbox_inches='tight')
plt.show()

# === Step 6: Cleanup ===
del df
gc.collect()
```

---

## Example 2: 1M-Row Table — Streaming Read + Filter + Export

**Scenario**: User has a 1M-row transaction log and wants records with amount > 10,000 exported.

```python
import pandas as pd
import os, gc

excel_path = "transactions_1m.xlsx"
parquet_path = "transactions_1m.parquet"

# === Step 1: Stream to Parquet (1M rows — MUST use streaming, never pd.read_excel) ===
stream_excel_to_parquet(excel_path, parquet_path, chunk_size=50000)

# === Step 2: Load only needed columns (saves memory) ===
df = pd.read_parquet(parquet_path, columns=['TransactionID', 'Amount', 'Date', 'Type'])
df = optimize_dtypes(df)
print(f"Shape: {df.shape}, Memory: {df.memory_usage(deep=True).sum()/1024**2:.1f} MB")

# === Step 3: Vectorized filtering (never use apply/iterrows) ===
mask = df['Amount'] > 10000
high_value = df[mask].copy()
print(f"Filtered: {len(high_value):,} / {len(df):,} rows")

# === Step 4: Export ===
output_path = write_large_excel(high_value, 'high_value_transactions.xlsx')

# === Step 5: Cleanup ===
del df, high_value
gc.collect()
```

---

## Vectorized Operations Cheat Sheet

On large files, **never use slow operations** — use vectorized alternatives:

| Slow (Prohibited) | Fast (Use This) |
|-------------------|-----------------|
| `df.apply(lambda x: x*2)` | `df['col'] * 2` |
| `df.iterrows()` | `df.itertuples(index=False)` |
| `for i in range(len(df)): df.iloc[i]` | Vectorized boolean indexing `df[mask]` |
| `df['a'].map(lambda x: 'Y' if x>0 else 'N')` | `np.where(df['a']>0, 'Y', 'N')` |
| `df.groupby('a').apply(custom_func)` | `df.groupby('a').agg({'b':'sum','c':'mean'})` |

---

## Memory Estimation

Estimate memory before loading to avoid OOM:

```
Estimated MB ≈ rows × cols × 8 / 1024² (numeric columns)
Estimated MB ≈ rows × cols × 50 / 1024² (with text columns)
```

| Rows | 20 cols (numeric) | 20 cols (with text) |
|------|-------------------|---------------------|
| 100k | ~15 MB | ~95 MB |
| 500k | ~76 MB | ~477 MB |
| 1M | ~153 MB | ~953 MB |

When estimated memory exceeds 80% of available RAM, use **column-selective loading** (`pd.read_parquet(columns=[...])`) or chunked processing.

---

## Best Practices

1. **Parquet is king**: For any file >= 10k rows, convert to Parquet before analysis. Parquet supports columnar reads, compressed storage, and loads 10-50x faster than xlsx.
2. **Streaming is the safety net**: For 100k+ rows, always use openpyxl `read_only` + `iter_rows`. Never `pd.read_excel()` for full load.
3. **Release memory promptly**: `del df; gc.collect()` after every intermediate DataFrame.
4. **Excel row limit**: Max 1,048,576 rows per sheet. Auto-split to multiple sheets or export as CSV when exceeded.
5. **Use write_only for output**: Files with >50k cells must use `openpyxl Workbook(write_only=True)`.
