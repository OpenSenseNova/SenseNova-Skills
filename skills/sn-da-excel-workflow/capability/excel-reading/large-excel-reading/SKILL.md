---
name: large-excel-analysis-and-formatting
description: "用于处理多Sheet大型Excel文件，支持大文件Parquet格式转换提速，并使用openpyxl生成带条件高亮和自定义样式的格式化Excel报告及下载链接。"
---

## Skill Steps

Step1 读取Excel文件，统计所有Sheet的总行数。若数据量过大（如≥1万行），则转换为Parquet格式以显著提升后续读取和分析效率。
```python
import pandas as pd

file_path = "input.xlsx"
xls = pd.ExcelFile(file_path)
total_rows = 0

# 统计所有 sheet 的总行数
for name in xls.sheet_names:
    df_temp = pd.read_excel(file_path, sheet_name=name, header=None)
    total_rows += len(df_temp)

print(f"总行数: {total_rows}")

# 大文件处理：超过阈值转换为 Parquet 提升效率
if total_rows >= 10000:
    parquet_path = "/mnt/data/temp.parquet"
    # 此处以读取第一个sheet为例，实际可根据需求合并多个sheet
    df = pd.read_excel(file_path, sheet_name=0)
    df.to_parquet(engine='pyarrow', path=parquet_path)
    df = pd.read_parquet(parquet_path)
else:
    df = pd.read_excel(file_path, sheet_name=0)
```

Step2 提取目标数据进行分组汇总分析，并识别出最大值及其对应的分类项。
```python
# 占位示例：根据实际数据集替换列名
group_col = '分类列名'  # 如 '控股类型'
target_col = '目标数值列'  # 如 '建筑业总产值'

# 假设 df 已清洗并包含所需列，进行汇总分析
summary = df.groupby(group_col)[target_col].sum().reset_index()

# 识别最大值及其对应的分类
max_idx = summary[target_col].idxmax()
max_type = summary.loc[max_idx, group_col]
print(f"最高产值类型: {max_type}")
```

Step3 使用 openpyxl 将分析结果写入新的Excel文件，配置表头样式、边框、列宽，并对满足特定条件（如最大值）的行进行绿色高亮标注，最后生成下载链接。
```python
from openpyxl import Workbook
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side

wb = Workbook()
ws = wb.active
ws.title = "分析报告"

# 样式定义
header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
header_font = Font(name="微软雅黑", bold=True, color="FFFFFF", size=12)
highlight_fill = PatternFill(start_color="00B050", end_color="00B050", fill_type="solid")
highlight_font = Font(name="微软雅黑", bold=True, color="FFFFFF", size=12)
normal_font = Font(name="微软雅黑", size=11)
center_align = Alignment(horizontal="center", vertical="center")
thin_border = Border(
    left=Side(style="thin"), right=Side(style="thin"),
    top=Side(style="thin"), bottom=Side(style="thin")
)

# 写入表头并应用样式
headers = [group_col, target_col]
for col, header in enumerate(headers, 1):
    cell = ws.cell(row=1, column=col, value=header)
    cell.fill = header_fill
    cell.font = header_font
    cell.alignment = center_align
    cell.border = thin_border

# 写入数据并进行条件高亮
for row_idx, row_data in enumerate(summary.itertuples(index=False), 2):
    type_name, value = row_data[0], row_data[1]
    
    cell_type = ws.cell(row=row_idx, column=1, value=type_name)
    cell_value = ws.cell(row=row_idx, column=2, value=value)
    
    # 基础样式
    for cell in [cell_type, cell_value]:
        cell.alignment = center_align
        cell.border = thin_border
        cell.font = normal_font
    
    # 命中最大值条件时高亮整行
    if type_name == max_type:
        cell_type.fill = highlight_fill
        cell_type.font = highlight_font
        cell_value.fill = highlight_fill
        cell_value.font = highlight_font

# 调整列宽
ws.column_dimensions['A'].width = 18
ws.column_dimensions['B'].width = 25

# 保存文件
output_path = "/mnt/data/formatted_analysis_report.xlsx"
wb.save(output_path)
print(f"文件已保存至: {output_path}")

# 提供下载链接
download_link = f"sandbox:{output_path}"
print(f"下载链接: {download_link}")
```
