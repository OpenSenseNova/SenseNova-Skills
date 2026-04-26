---
name: excel-outlier-detection-and-highlighting
description: "识别 Excel 中的超限数值与错误单元格并进行高亮标注。"
---

# Outlier_Coloring

> This sub-skill covers one capability of the Excel workflow. For reading/counting/Parquet optimization, see the parent workflow SKILL.md.

Step1 使用正则表达式提取限值，并结合上下文逻辑识别总传热系数超限的行。
```python
import re

exceed_rows = []
target_col = 0  # 假设特征列在第一列
value_col = 8   # 假设数值列在第九列

for i, row in df.iterrows():
    row_str = str(row.iloc[target_col]) if pd.notna(row.iloc[target_col]) else ""
    
    # 正则表达式精准提取限值，例如 "限值0.5"
    if '限值' in row_str:
        match = re.search(r'限值([\d.]+)', row_str)
        if match:
            current_limit = float(match.group(1))
            
    # 识别计算结果行并进行对比
    if '共计' in row_str:
        try:
            actual_val = float(row.iloc[value_col])
            # 向上回溯寻找结构名称（实战技巧：遍历还原上下文）
            structure_name = "未知结构"
            for j in range(i-1, max(0, i-15), -1):
                prev_val = str(df.iloc[j, 0])
                if any(kw in prev_val for kw in ['系数', '围护']):
                    structure_name = prev_val
                    break
            
            # 提取最近的限值进行对比
            limit_val = None
            for j in range(i-1, max(0, i-15), -1):
                check_str = ' '.join([str(x) for x in df.iloc[j, :] if pd.notna(x)])
                limit_match = re.search(r'限值([\d.]+)', check_str)
                if limit_match:
                    limit_val = float(limit_match.group(1))
                    break
            
            if limit_val and actual_val > limit_val:
                exceed_rows.append({
                    'row_index': i,
                    'name': structure_name,
                    'value': actual_val,
                    'limit': limit_val,
                    'diff': actual_val - limit_val
                })
        except (ValueError, TypeError):
            continue
```

Step2 遍历指定 Sheet 查找包含 '#DIV/' 等异常错误的单元格，并记录坐标。
```python
# 针对特定 Sheet（如 Sheet3）检测公式错误
ws_error = wb['Sheet3']
error_cells = []

for row in ws_error.iter_rows(min_row=1, max_row=ws_error.max_row):
    for cell in row:
        if cell.value is not None:
            val_str = str(cell.value)
            # 识别 Excel 除零错误或其他异常标识
            if '#DIV/' in val_str:
                error_cells.append({
                    'coord': cell.coordinate,
                    'val': cell.value
                })
```

Step3 对识别出的超限行和异常单元格进行红色高亮标注，并保存结果。
```python
from openpyxl.styles import PatternFill

# 定义红色填充样式
red_fill = PatternFill(start_color='FF0000', end_color='FF0000', fill_type='solid')

# 标注超限行（注意：Excel 行号 = pandas 索引 + 1）
# 假设在第一个 Sheet 中标注
ws_main = wb[wb.sheetnames[0]]
for item in exceed_rows:
    excel_row = item['row_index'] + 1
    for col in range(1, ws_main.max_column + 1):
        ws_main.cell(row=excel_row, column=col).fill = red_fill

# 标注异常单元格
for err in error_cells:
    ws_error[err['coord']].fill = red_fill

output_path = "highlighted_report.xlsx"
wb.save(output_path)
```

Step4 汇总超限数据生成分析报告，并提供下载链接。
```python
# 创建汇总 DataFrame
summary_df = pd.DataFrame(exceed_rows)
if not summary_df.empty:
    summary_df['Excel行号'] = summary_df['row_index'] + 1
    summary_df = summary_df[['Excel行号', 'name', 'value', 'limit', 'diff']]
    summary_df.columns = ['行号', '结构名称', '实测值', '限值', '超出值']

summary_path = "outlier_summary.xlsx"
summary_df.to_excel(summary_path, index=False)

# 输出下载链接格式
print(f"处理完成。结果文件：{output_path}")
print(f"汇总报告：{summary_path}")
```
