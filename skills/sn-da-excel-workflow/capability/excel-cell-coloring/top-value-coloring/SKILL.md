---
name: top-value-coloring
description: "根据数据规模动态选择处理策略，对多表数据进行合并、统计筛选，并利用 openpyxl 实现关键指标的自动化样式高亮与格式化导出。"
---

Step1 提取并合并多个 Sheet 中的关键维度数据，进行数据清洗、类型转换及 Top-N 筛选。
```python
# 示例：合并两个 Sheet 的数据
# 读取 Sheet1 并清洗
df1 = pd.read_excel(file_path, sheet_name='Sheet1', header=None)
# 假设 group_col 在第0列，value_col 在第2列
data1 = df1.iloc[20:, [0, 2]].copy()
data1.columns = ['group_col', 'value_col_1']
data1['value_col_1'] = pd.to_numeric(data1['value_col_1'], errors='coerce')
data1['group_col'] = data1['group_col'].ffill() # 处理合并单元格产生的缺失

# 读取 Sheet2 并清洗
df2 = pd.read_excel(file_path, sheet_name='Sheet2', header=None)
data2 = df2.iloc[5:, [0, 1]].copy()
data2.columns = ['value_col_2', 'value_col_3']

# 合并数据
merged_df = pd.concat([data1.reset_index(drop=True), data2.reset_index(drop=True)], axis=1)
merged_df = merged_df.dropna(subset=['value_col_1'])

# 筛选关键指标前五的数据
top_results = merged_df.nlargest(5, 'value_col_1').copy()

# 占位示例：修正特定缺失值
# top_results.loc[top_results['group_col'].isna(), 'group_col'] = 'Default_Value'
```

Step2 使用 openpyxl 创建格式化表格，应用条件样式（如特定列标红、最大值高亮）并设置边框与对齐方式。
```python
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

output_path = 'analysis_report.xlsx'

# 创建工作簿
wb = Workbook()
ws = wb.active
ws.title = 'Analysis_Results'

# 定义样式
header_fill = PatternFill(start_color='4472C4', end_color='4472C4', fill_type='solid')
header_font = Font(bold=True, color='FFFFFF', size=12)
red_font = Font(color='FF0000', bold=True) # 用于高亮异常或关键值
green_fill = PatternFill(start_color='C6EFCE', end_color='C6EFCE', fill_type='solid') # 用于高亮最大值
thin_border = Border(left=Side(style='thin'), right=Side(style='thin'), 
                     top=Side(style='thin'), bottom=Side(style='thin'))
center_align = Alignment(horizontal='center', vertical='center')

# 写入表头
headers = ['Rank'] + list(top_results.columns)
for col, header in enumerate(headers, 1):
    cell = ws.cell(row=1, column=col, value=header)
    cell.font = header_font
    cell.fill = header_fill
    cell.alignment = center_align
    cell.border = thin_border

# 写入数据并应用样式
for idx, (_, row) in enumerate(top_results.iterrows(), 2):
    # 写入排名
    ws.cell(row=idx, column=1, value=idx-1).border = thin_border
    
    # 写入各列数据
    for col_idx, value in enumerate(row, 2):
        cell = ws.cell(row=idx, column=col_idx, value=value)
        cell.border = thin_border
        
        # 逻辑高亮示例：对特定列（如第4列）应用红色字体
        if col_idx == 4:
            cell.font = red_font
        
        # 逻辑高亮示例：对超过阈值的值应用绿色填充
        # if isinstance(value, (int, float)) and value > threshold_val:
        #     cell.fill = green_fill

# 自动调整列宽
column_widths = {'A': 8, 'B': 30, 'C': 15, 'D': 15, 'E': 18}
for col, width in column_widths.items():
    ws.column_dimensions[col].width = width

# 设置数字格式
for row in range(2, ws.max_row + 1):
    ws.cell(row=row, column=3).number_format = '#,##0'
    ws.cell(row=row, column=4).number_format = '#,##0.00'

wb.save(output_path)
print(f"Formatted file saved to: {output_path}")
```

Step3 生成并输出结果文件的下载链接。
```python
# 必须使用 sandbox:/ 前缀生成下载链接
print(f"[下载分析结果]({f'sandbox:{output_path}'})")
```
