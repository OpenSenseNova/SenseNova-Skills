---
name: excel-conditional-filtering-optimization
description: "根据多维数值条件筛选 Excel 数据并导出结果，支持大规模数据的自动性能优化处理。"
---

# Excel_Conditional_Filtering_Optimization

> **Note**: This sub-skill covers one step of the Excel analysis workflow. For the full pipeline (file reading, row counting, large-file optimization, export), see the parent workflow SKILL.md.


Step1 读取 Excel 文件中所有工作表的数据，统计各表行数并汇总，用于评估数据规模。
```python
import pandas as pd

file_path = "input_data.xlsx"

# 读取所有 sheet，统计行数
xls = pd.ExcelFile(file_path)
print("Sheet names:", xls.sheet_names)

total_rows = 0
sheet_details = []
for sheet in xls.sheet_names:
    df_temp = pd.read_excel(file_path, sheet_name=sheet)
    row_count = len(df_temp)
    sheet_details.append({"sheet": sheet, "rows": row_count})
    total_rows += row_count

print(f"Sheet details: {sheet_details}")
print(f"Total rows across all sheets: {total_rows}")
```

Step2 对目标数据进行清洗，处理表头偏移，并将关键列转换为数值类型以确保计算准确。
```python
# 读取目标数据表
target_sheet = 'Sheet1'
df = pd.read_excel(file_path, sheet_name=target_sheet, header=0)

# 处理可能的子表头或空行偏移（示例：跳过第一行）
# df = df.iloc[1:].reset_index(drop=True)

# 统一设置列名（根据实际业务逻辑调整占位符）
# df.columns = ['col_1', 'col_2', 'col_3', 'target_id', 'val_a', 'val_b', 'val_c']

# 强制转换数值列，处理非数值数据为 NaN
numeric_cols = ['val_a', 'val_b', 'val_c', 'target_id']
for col in numeric_cols:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors='coerce')

# 处理合并单元格（如有）
# df = df.ffill()
```

Step3 执行多维度条件筛选逻辑，提取符合特定数值特征的唯一记录。
```python
# 筛选逻辑：例如 val_a, val_b, val_c 同时满足特定阈值（如均为 0）
mask = (df['val_a'] == 0) & (df['val_b'] == 0) & (df['val_c'] == 0)
filtered_df = df[mask][['target_id', 'val_a', 'val_b', 'val_c']]

# 提取唯一编号并去除空值
result = filtered_df.drop_duplicates().dropna(subset=['target_id']).reset_index(drop=True)
```

Step4 将筛选后的结果保存为新的 Excel 文件，并生成下载链接。
```python
output_path = "filtered_analysis_result.xlsx"

# 格式化输出列名
result.columns = ['Target_Index', 'Value_A', 'Value_B', 'Value_C']

# 导出文件
result.to_excel(output_path, index=False)

# 打印结果摘要与下载路径
print(f"Filtered records count: {len(result)}")
print(f"Result saved to: {output_path}")
```
