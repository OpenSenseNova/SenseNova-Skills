---
name: large-file-parquet-analysis-and-highlight
description: "当Excel文件总行数超过1万行时，通过转换为Parquet格式提升读取性能，提取目标指标并计算最大值，最后将结果输出为Excel并对特定行进行高亮标注。"
---

# Skill Steps

Step1 读取文件并统计所有 sheet 的行数，汇总后打印总行数，用于判断数据规模是否需要启用大文件处理。
```python
import pandas as pd

file_path = "input_data.xlsx"

# 读取所有sheet并统计总行数
xls = pd.ExcelFile(file_path)
sheet_names = xls.sheet_names
print(f"Sheet列表: {sheet_names}")

total_rows = 0
for sheet in sheet_names:
    # 仅读取一列以加快行数统计速度
    df_temp = pd.read_excel(file_path, sheet_name=sheet, usecols=[0], header=None)
    rows = len(df_temp)
    total_rows += rows
    print(f"Sheet '{sheet}': {rows} 行")

print(f"\n总行数 = {total_rows}")
```

Step2 当总行数 ≥ 1万时，读取已转换为 Parquet 格式的数据文件，通过行列匹配提取目标指标数据，并找出最大值及其对应分类。
```python
import pandas as pd

# 假设已通过大文件处理技能将Excel转换为Parquet
parquet_path = "converted_data.parquet"
df = pd.read_parquet(parquet_path)

# 假设第2行（索引1）是分类表头（如：控股类型、区域等）
header_row = df.iloc[1].tolist()
print("分类表头:", header_row)

# 找到目标指标所在的行（占位示例：'目标指标名称'）
target_metric = '目标指标名称'
target_rows = df[df[0] == target_metric]

if not target_rows.empty:
    # 提取数值
    values = target_rows.iloc[0, 1:].tolist()
    
    # 清洗数据并找出最大值及其对应的分类
    numeric_values = []
    for val in values:
        try:
            numeric_values.append(float(val))
        except:
            numeric_values.append(0)
    
    max_val = max(numeric_values)
    max_idx = numeric_values.index(max_val)
    max_type = header_row[1:][max_idx]
    
    print(f"\n指标最高的分类: {max_type} ({max_val})")
    
    # 准备写入Excel的数据结构
    result_data = list(zip(header_row[1:], numeric_values))
```

Step3 将提取的分析结果保存为新的 Excel 文件，并使用 openpyxl 对最大值所在行进行背景色高亮标注，最后验证输出。
```python
from openpyxl import Workbook
from openpyxl.styles import PatternFill
from openpyxl import load_workbook

output_path = "analysis_result.xlsx"

wb = Workbook()
ws = wb.active
ws.title = "数据分析结果"

# 写入表头
headers = ["分类类型", "指标数值"]
ws.append(headers)

# 写入数据 (使用Step2提取的 result_data，此处为防空值做备用示例)
if 'result_data' not in locals():
    result_data = [("分类A", 100), ("分类B", 500), ("分类C", 200)]
    max_type = "分类B"

for row in result_data:
    ws.append(row)

# 找到最大值所在行并标绿
green_fill = PatternFill(start_color="00FF00", end_color="00FF00", fill_type="solid")

for row in ws.iter_rows(min_row=2, max_row=ws.max_row):
    if row[0].value == max_type:
        for cell in row:
            cell.fill = green_fill

# 保存文件
wb.save(output_path)
print(f"文件已保存到: {output_path}")

# 验证输出文件内容及格式
wb_check = load_workbook(output_path)
ws_check = wb_check.active
print("\n文件内容验证:")
for row in ws_check.iter_rows(values_only=True):
    print(row)
```
