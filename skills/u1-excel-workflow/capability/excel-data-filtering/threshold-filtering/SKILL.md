---
name: excel-threshold-analysis-and-styling
description: "根据 Excel 数据量级自动判断处理策略，执行数值列清洗、条件过滤，并使用 openpyxl 对符合条件的单元格进行样式标记与导出。"
---

# Excel Threshold Analysis and Styling

> **Note**: This sub-skill covers one step of the Excel analysis workflow. For the full pipeline (file reading, row counting, large-file optimization, export), see the parent workflow SKILL.md.


Step1 读取 Excel 文件中所有工作表的行数并汇总，用于评估数据规模。
```python
import pandas as pd

file_path = 'input_file.xlsx'

# 读取所有 sheet 名称并统计总行数
xls = pd.ExcelFile(file_path)
sheet_names = xls.sheet_names
total_rows = 0

for sheet in sheet_names:
    # header=None 用于快速统计包含表头的总行数
    df_tmp = pd.read_excel(file_path, sheet_name=sheet, header=None)
    rows = len(df_tmp)
    total_rows += rows
    print(f"Sheet '{sheet}': {rows} 行")

print(f"\n总行数汇总: {total_rows}")
```

Step2 对目标数据表进行清洗，将指定列的非数值内容转换为缺失值并剔除，确保数据类型为数值型。
```python
target_sheet = 'Sheet1'
target_col = '数量' # 待处理的目标列名
header_idx = 1     # 表头所在行索引（0开始计数）

df = pd.read_excel(file_path, sheet_name=target_sheet, header=header_idx)

# 强制转换数值类型，无法转换的内容变为 NaN 并删除
df[target_col] = pd.to_numeric(df[target_col], errors='coerce')
df_cleaned = df.dropna(subset=[target_col])

print(f"清洗完成，有效数据行数: {len(df_cleaned)}")
```

Step3 筛选符合特定数值条件的记录并进行统计。
```python
filter_threshold = 10 
df_filtered = df_cleaned[df_cleaned[target_col] > filter_threshold]

print(f"{target_col} 大于 {filter_threshold} 的记录共有 {len(df_filtered)} 条")
```

Step4 使用 openpyxl 对原始文件中
