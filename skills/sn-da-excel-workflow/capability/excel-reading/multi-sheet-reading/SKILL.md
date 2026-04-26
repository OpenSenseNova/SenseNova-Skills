---
name: multi-sheet-reading-and-analysis
description: "用于读取多工作表Excel文件，动态评估数据量以启用Parquet大文件优化，并执行正则清洗、分类汇总、线性拟合及生成带格式的图表与结果文件。"
---

Step1 统计多工作表总行数，并根据数据量级（如≥1万行）动态启用Parquet格式转换以优化大文件读取性能。
```python
import pandas as pd
import os
from openpyxl import load_workbook

file_path = "your_excel_file.xlsx"
xls = pd.ExcelFile(file_path)
sheet_names = xls.sheet_names

# 统计所有sheet的数据行数
total_rows = 0
for sheet in sheet_names:
    wb = load_workbook(file_path, read_only=True, data_only=True)
    ws = wb[sheet]
    max_row = ws.max_row
    data_rows = max_row - 1 if max_row > 0 else 0
    total_rows += data_rows
    wb.close()

print(f"总数据行数: {total_rows}")

# 大文件优化：转换为Parquet格式读取
if total_rows >= 10000:
    df = pd.read_excel(file_path, sheet_name=sheet_names[0])
    parquet_path = '/tmp/temp_data.parquet'
    df.to_parquet(parquet_path, engine='pyarrow')
    df = pd.read_parquet(parquet_path)
else:
    df = pd.read_excel(file_path, sheet_name=sheet_names[0])
```

Step2 使用正则表达式对指定文本列进行数据清洗（例如仅保留中文字符）。
```python
import re

def clean_chinese_text(text):
    if pd.isna(text):
        return text
    s = str(text)
    # 提取所有中文字符
    chinese_chars = re.findall(r'[一-鿿]', s)
    cleaned = ''.join(chinese_chars)
    return cleaned if cleaned != '' else ''

target_col = '目标清洗列' # 替换为实际列名
if target_col in df.columns:
    df[target_col] = df[target_col].apply(clean_chinese_text)
```

Step3 提取关键数据进行多维度分析（分类汇总求极值或双变量线性拟合）。
```python
import numpy as np

# 模式1：分类汇总与极值提取
group_col = '分类列'
value_col = '数值列'
# 示例占位数据提取逻辑
summary = pd.DataFrame({
    group_col: ['类别A', '类别B', '类别C'],
    value_col: [100, 500, 200]
})
max_idx = summary[value_col].idxmax()
max_type = summary.loc[max_idx, group_col]

# 模式2：双变量线性关系分析
x_col = 'X轴列'
y_col = 'Y轴列'
if x_col in df.columns and y_col in df.columns:
    x_data = df[x_col].values
    y_data = df[y_col].values
    # 拟合线性趋势线
    coefficients = np.polyfit(x_data, y_data, 1)
    trend_line = np.poly1d(coefficients)(x_data)
```

Step4 生成带条件格式的Excel报告（如高亮最大值）及可视化图表，并提供下载链接。
```python
from openpyxl import Workbook
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
import matplotlib.pyplot as plt

# 1. 生成带样式标记的Excel文件
wb = Workbook()
ws = wb.active
ws.title = "分析结果"

# 定义样式
header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
header_font = Font(name="SimHei", bold=True, color="FFFFFF", size=12)
highlight_fill = PatternFill(start_color="00B050", end_color="00B050", fill_type="solid")
highlight_font = Font(name="SimHei", bold=True, color="FFFFFF", size=12)
normal_font = Font(name="SimHei", size=11)
center_align = Alignment(horizontal="center", vertical="center")
thin_border = Border(left=Side(style="thin"), right=Side(style="thin"), top=Side(style="thin"), bottom=Side(style="thin"))

# 写入表头与数据
headers = [group_col, value_col]
for col, header in enumerate(headers, 1):
    cell = ws.cell(row=1, column=col, value=header)
    cell.fill = header_fill
    cell.font = header_font
    cell.alignment = center_align
    cell.border = thin_border

for row_idx, row in summary.iterrows():
    c_type = ws.cell(row=row_idx+2, column=1, value=row[group_col])
    c_val = ws.cell(row=row_idx+2, column=2, value=row[value_col])
    for cell in [c_type, c_val]:
        cell.alignment = center_align
        cell.border = thin_border
        cell.font = normal_font
    # 高亮最大值行
    if row[group_col] == max_type:
        c_type.fill = highlight_fill
        c_type.font = highlight_font
        c_val.fill = highlight_fill
        c_val.font = highlight_font

output_excel_path = "/mnt/data/analysis_report.xlsx"
wb.save(output_excel_path)

# 2. 生成散点图与趋势线 (如果存在拟合数据)
if 'x_data' in locals():
    plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']
    plt.rcParams['axes.unicode_minus'] = False
    plt.figure(figsize=(10, 6), dpi=100)
    plt.scatter(x_data, y_data, color='blue', s=80, label='数据点')
    plt.plot(x_data, trend_line, color='red', linewidth=2, label=f'趋势线: y={coefficients[0]:.2f}x+{coefficients[1]:.2f}')
    plt.xlabel(x_col)
    plt.ylabel(y_col)
    plt.title(f'{x_col} vs {y_col} 散点图与趋势线')
    plt.legend()
    plt.grid(True)
    output_img_path = '/mnt/data/scatter_plot.png'
    plt.savefig(output_img_path, bbox_inches='tight')
    plt.close()

print(f"文件已生成，下载链接:")
print(f"- 分析报告: {output_excel_path}")
if 'x_data' in locals():
    print(f"- 趋势图表: {output_img_path}")
```
