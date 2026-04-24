---
name: formatted-export-with-parquet
description: "从多Sheet Excel文件中识别指定条件的记录，并将筛选结果以整行标红格式导出为Excel文件，适用于数据清洗、条件筛选与可视化标记场景。"
metadata: "{\"nanobot\": {\"requires\": {\"pip\": [\"pandas\", \"pyarrow\", \"openpyxl\"]}}}"  
---

# Formatted_Export

> This sub-skill covers one capability of the Excel workflow. For reading/counting/Parquet optimization, see the parent workflow SKILL.md.

## Skill Steps

Step1 对所有 sheet 进行扫描，通过模糊匹配定位目标列，筛选出符合条件（如空值或无效字符）的记录。
```python
empty_target_rows = []
for sheet_name, sheet_df in all_sheets.items():
    target_col = None
    
    # 优先匹配目标列名（示例：包含特定关键字的列）
    for col in sheet_df.columns:
        if 'keyword1' in str(col).lower() or 'keyword2' in str(col).lower():
            target_col = col
            break
            
    if target_col is None:
        # 尝试次级推断逻辑
        for col in sheet_df.columns:
            if 'keyword3' in str(col) and ('keyword4' in str(col)):
                target_col = col
                break
                
    if target_col is None:
        continue
    
    # 数据清洗：筛选空值和无效字符（如空格、'nan'）行
    mask = sheet_df[target_col].isna() | (sheet_df[target_col].astype(str).str.strip() == '') | (sheet_df[target_col].astype(str).str.strip() == 'nan')
    empty_rows = sheet_df[mask].copy()
    
    if len(empty_rows) > 0:
        empty_rows.insert(0, '来源Sheet', sheet_name)
        empty_target_rows.append(empty_rows)

# 合并结果
result_df = pd.concat(empty_target_rows, ignore_index=True) if empty_target_rows else pd.DataFrame()
```

Step2 将筛选出的记录导出为 Excel 文件，整行标红显示以便于视觉识别，并生成下载链接。
```python
from openpyxl import load_workbook
from openpyxl.styles import PatternFill

output_path = "filtered_results_highlighted.xlsx"

if not result_df.empty:
    # 导出基础数据
    result_df.to_excel(output_path, index=False)

    # 加载工作簿进行格式化
    wb = load_workbook(output_path)
    ws = wb.active
    
    # 定义红色填充样式
    red_fill = PatternFill(start_color="FF0000", end_color="FF0000", fill_type="solid")

    # 遍历所有数据行并标红（跳过表头）
    for row in range(2, ws.max_row + 1):
        for col in range(1, ws.max_column + 1):
            ws.cell(row=row, column=col).fill = red_fill

    wb.save(output_path)
    print(f"结果文件已保存: {output_path}")
    print(f"下载链接: [点击下载标红结果文件]({output_path})")
else:
    print("未找到符合条件的记录，无需导出。")
```
