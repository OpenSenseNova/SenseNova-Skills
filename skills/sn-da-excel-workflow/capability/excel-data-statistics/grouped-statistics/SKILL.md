---
name: grouped-statistics
description: "对多 Sheet 的 Excel 文件进行行数统计、数据合并与前向填充。"
---

## Skill Steps

> **Note**: This sub-skill covers one step of the Excel analysis workflow. For the full pipeline (file reading, row counting, large-file optimization, export), see the parent workflow SKILL.md.

Step1 提取关键维度与指标信息，处理合并单元格缺失值，并进行多表交叉分析与排序。
```python
import pandas as pd

# 设定目标列名
group_col = '行业名称'
target_val_1 = '企业单位数'
target_val_2 = '工业总产值'

# 读取第一个 Sheet 并清洗
df1 = pd.read_excel(file_path, sheet_name=sheet_names[0], header=None)
# 假设数据从第 21 行开始，提取维度列与数值列
data_1 = df1.iloc[21:63, [0, 2]].copy()
data_1.columns = [group_col, target_val_1]

# 处理合并单元格：前向填充维度列
data_1[group_col] = data_1[group_col].ffill()
data_1[target_val_1] = pd.to_numeric(data_1[target_val_1], errors='coerce')

# 读取第二个 Sheet 并提取补充指标
df2 = pd.read_excel(file_path, sheet_name=sheet_names[1], header=None)
data_2 = df2.iloc[5:47, [0, 1]].copy()
data_2.columns = ['temp_dim', target_val_2]
data_2[target_val_2] = pd.to_numeric(data_2[target_val_2], errors='coerce')

# 交叉分析：基于索引或维度列合并
merged_df = pd.merge(data_1, data_2.reset_index(), left_index=True, right_index=True, how='inner')
merged_df = merged_df[[group_col, target_val_1, target_val_2]].dropna(subset=[target_val_1])

# 筛选 Top N 结果
top5_df = merged_df.nlargest(5, target_val_1).reset_index(drop=True)
top5_df.index = top5_df.index + 1
print(top5_df)
```

Step2 对筛选出的关键数据进行格式化标注（如标红、边框、对齐），生成美化后的 Excel 文件。
```python
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

output_path = 'analysis_report.xlsx'
wb = Workbook()
ws = wb.active
ws.title = 'Top_Analysis'

# 定义样式
header_fill = PatternFill(start_color='4472C4', end_color='4472C4', fill_type='solid')
header_font = Font(bold=True, color='FFFFFF', size=12)
red_font = Font(color='FF0000', bold=True)
thin_border = Border(left=Side(style='thin'), right=Side(style='thin'), 
                    top=Side(style='thin'), bottom=Side(style='thin'))
center_align = Alignment(horizontal='center', vertical='center')

# 写入表头
headers = ['排名'] + list(top5_df.columns)
for col, header in enumerate(headers, 1):
    cell = ws.cell(row=1, column=col, value=header)
    cell.font = header_font
    cell.fill = header_fill
    cell.alignment = center_align
    cell.border = thin_border

# 写入数据并应用条件格式
for idx, row in top5_df.iterrows():
    row_num = idx + 1 # 考虑表头
    # 排名列
    ws.cell(row=row_num, column=1, value=idx).border = thin_border
    # 维度列
    ws.cell(row=row_num, column=2, value=row[group_col]).border = thin_border
    # 数值列 1
    cell_v1 = ws.cell(row=row_num, column=3, value=row[target_val_1])
    cell_v1.border = thin_border
    cell_v1.number_format = '#,##0'
    # 数值列 2（执行标红标注）
    cell_v2 = ws.cell(row=row_num, column=4, value=row[target_val_2])
    cell_v2.font = red_font
    cell_v2.border = thin_border
    cell_v2.number_format = '#,##0.00'

# 调整列宽
ws.column_dimensions['B'].width = 35
ws.column_dimensions['C'].width = 15
ws.column_dimensions['D'].width = 18

wb.save(output_path)
```

Step3 输出最终结果并生成下载链接。
```python
# 确认文件生成并提供下载
import os
if os.path.exists(output_path):
    print(f"分析完成。结果文件已生成，下载链接：{output_path}")
else:
    print("文件生成失败，请检查路径权限。")
```
