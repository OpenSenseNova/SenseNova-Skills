---
name: excel-conditional-comparison-and-large-file-processing
description: "对比Excel多表中的特定系数并对异常值进行颜色标记。"
---

# excel-conditional-comparison-and-large-file-processing

> This sub-skill covers one capability of the Excel workflow. For reading/counting/Parquet optimization, see the parent workflow SKILL.md.

Step1 提取不同Sheet中特定维度（如“B1层”）的数值，并进行跨表逻辑对比。
```python
# 定义提取逻辑：定位目标行（如包含'B1'的行）并获取其关联的系数
def extract_target_value(df, target_label='B1', label_col_idx=0, offset_row=1, value_col_idx=2):
    """
    在指定列搜索标签，并返回其相对偏移位置的数值
    """
    extracted_values = []
    for idx, row in df.iterrows():
        if str(row.iloc[label_col_idx]).strip() == target_label:
            # 提取目标行下方或特定偏移位置的数值
            if idx + offset_row < len(df):
                val = df.iloc[idx + offset_row].iloc[value_col_idx]
                extracted_values.append(val)
    return extracted_values

# 分别读取需要对比的Sheet
sheet1_df = pd.read_excel(file_path, sheet_name='Sheet1')
sheet2_df = pd.read_excel(file_path, sheet_name='Sheet2')

# 提取系数（示例：B1层的换算系数）
# 注意：不同Sheet的列索引可能不同，需根据实际结构调整
s1_coeffs = extract_target_value(sheet1_df, target_label='B1', label_col_idx=1, value_col_idx=3)
s2_coeffs = extract_target_value(sheet2_df, target_label='B1', label_col_idx=0, value_col_idx=2)

# 汇总对比数据
comparison_results = []
target_standard = 0.6 # 预设的标准阈值

for val in s1_coeffs:
    comparison_results.append({'source': 'Sheet1', 'value': val, 'is_anomaly': val != target_standard})
for val in s2_coeffs:
    comparison_results.append({'source': 'Sheet2', 'value': val, 'is_anomaly': val != target_standard})
```

Step2 生成对比报告，并使用 openpyxl 对异常值（非标准系数）进行红色高亮标记。
```python
from openpyxl import Workbook
from openpyxl.styles import PatternFill

output_path = 'comparison_report.xlsx'
wb = Workbook()
ws = wb.active
ws.title = "Comparison Analysis"

# 写入表头
headers = ['数据来源', '提取数值', '是否符合标准', '状态标记']
ws.append(headers)

# 定义红色填充样式
red_fill = PatternFill(start_color='FF0000', end_color='FF0000', fill_type='solid')

# 遍历结果并写入，同时应用条件格式
for item in comparison_results:
    status_text = '正常' if not item['is_anomaly'] else '异常(非0.6)'
    row_data = [item['source'], item['value'], '是' if not item['is_anomaly'] else '否', status_text]
    ws.append(row_data)
    
    # 如果是异常值，将该行或特定单元格标红
    if item['is_anomaly']:
        curr_row = ws.max_row
        for col_idx in range(1, len(headers) + 1):
            ws.cell(row=curr_row, column=col_idx).fill = red_fill

# 保存结果并提供下载
wb.save(output_path)
print(f"Analysis complete. Report saved to: {output_path}")
```
