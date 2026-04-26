---
name: large-file-conditional-formatting
description: "根据Excel总行数自动切换Parquet加速读取，计算特定维度的时间序列平均值，并使用openpyxl输出带有条件格式（如低于均值标绿）和自定义样式的分析报告。"
---

## Skill Steps

> **Note**: This sub-skill covers one step of the Excel analysis workflow. For the full pipeline (file reading, row counting, large-file optimization, export), see the parent workflow SKILL.md.


Step1 读取文件并统计所有 sheet 的行数，汇总后打印总行数，用于判断是否需要大文件加速。
```python
import pandas as pd
import openpyxl

file_path = "input_data.xlsx"

# 获取所有sheet名称
wb = openpyxl.load_workbook(file_path, read_only=True)
sheet_names = wb.sheetnames
print("Sheet列表:", sheet_names)
print("Sheet数量:", len(sheet_names))

# 统计每个sheet的行数
total_rows = 0
for name in sheet_names:
    df_temp = pd.read_excel(file_path, sheet_name=name, header=None)
    rows = len(df_temp)
    total_rows += rows
    print(f"Sheet '{name}': {rows} 行")

print(f"\n总行数 = {total_rows}")
```

Step2 提取目标实体的时间序列数据，计算平均值，并构建包含比较结果的结构化 DataFrame。
```python
target_entity = 'Target_Entity' # 占位示例，如 'US'

# 提取目标行数据 (假设第0列为实体名称)
target_row = df[df[0] == target_entity]

# 提取时间标签和对应数值 (假设第6行为表头，1:10列为数据)
time_labels = df.iloc[6, 1:10].tolist()
target_values = target_row.iloc[0, 1:10].tolist()
target_values_numeric = [float(v) for v in target_values]

# 计算平均值
avg_value = sum(target_values_numeric) / len(target_values_numeric)

# 构建结果 DataFrame
result_data = {
    '时间维度': time_labels,
    '指标数值': target_values_numeric,
    '是否低于平均值': [v < avg_value for v in target_values_numeric]
}
result_df = pd.DataFrame(result_data)
```

Step3 使用 openpyxl 将分析结果保存为 Excel 文件，应用精细的样式控制（加粗标题、边框、居中对齐），并对低于平均值的行进行条件格式填充（标绿）。
```python
from openpyxl import Workbook
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side

wb = Workbook()
ws = wb.active
ws.title = "指标分析报告"

# 定义样式
green_fill = PatternFill(start_color="92D050", end_color="92D050", fill_type="solid")
header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
header_font = Font(bold=True, color="FFFFFF")
thin_border = Border(
    left=Side(style='thin'), right=Side(style='thin'),
    top=Side(style='thin'), bottom=Side(style='thin')
)

# 设置主标题
ws.merge_cells('A1:D1')
ws['A1'] = f"目标实体指标分析 - 平均值: {avg_value:.2f}"
ws['A1'].font = Font(bold=True, size=14)
ws['A1'].alignment = Alignment(horizontal='center')

# 设置表头
headers = ['时间维度', '指标数值', '与平均值比较', '是否标绿']
for col, header in enumerate(headers, 1):
    cell = ws.cell(row=3, column=col, value=header)
    cell.fill = header_fill
    cell.font = header_font
    cell.alignment = Alignment(horizontal='center')
    cell.border = thin_border

# 写入数据并应用条件格式
for i, row_data in result_df.iterrows():
    row_num = i + 4
    time_label = row_data['时间维度']
    value = row_data['指标数值']
    below_avg = row_data['是否低于平均值']
    
    # 写入各列数据
    ws.cell(row=row_num, column=1, value=time_label).alignment = Alignment(horizontal='center')
    ws.cell(row=row_num, column=2, value=value).alignment = Alignment(horizontal='center')
    
    diff = value - avg_value
    ws.cell(row=row_num, column=3, value=f"{diff:+.2f}").alignment = Alignment(horizontal='center')
    ws.cell(row=row_num, column=4, value="是" if below_avg else "否").alignment = Alignment(horizontal='center')
    
    # 添加边框并根据条件标绿整行
    for col in range(1, 5):
        cell = ws.cell(row=row_num, column=col)
        cell.border = thin_border
        if below_avg:
            cell.fill = green_fill

# 调整列宽
ws.column_dimensions['A'].width = 15
ws.column_dimensions['B'].width = 20
ws.column_dimensions['C'].width = 18
ws.column_dimensions['D'].width = 12

output_path = "output_report.xlsx"
wb.save(output_path)
print(f"分析报告已保存至: {output_path}")
```
