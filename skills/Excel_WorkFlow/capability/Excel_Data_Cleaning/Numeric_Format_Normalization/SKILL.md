---
name: numeric-format-normalization
description: "对 Excel 数据进行数值格式标准化与清洗，支持大规模数据的 Parquet 转换流程，并完成关键指标的合计核对与结果文件导出。"
---

## Skill Steps

> This sub-skill covers one capability of the Excel workflow. For reading/counting/Parquet optimization, see the parent workflow SKILL.md.

Step1 对目标列进行数据清洗（去除空值、标准化数值格式），计算合计值，并与指定汇总 Sheet 中的合计行进行精确核对。
```python
target_col = '目标数值列'  # 示例：'建筑面积'
summary_sheet_name = 'Summary' # 示例汇总Sheet名
summary_item_col = '项目'
summary_value_col = '数值'

# 数据清洗：去除空值、强制转换为数值格式
df_cleaned = df_processed.dropna(subset=[target_col]).copy()
df_cleaned[target_col] = pd.to_numeric(df_cleaned[target_col], errors='coerce')

# 计算合计
total_calculated = df_cleaned[target_col].sum()

# 从指定 Sheet 中读取“合 计”行数值进行核对
try:
    summary_sheet = pd.read_excel(file_path, sheet_name=summary_sheet_name)
    expected_total = summary_sheet.loc[summary_sheet[summary_item_col] == '合 计', summary_value_col].values[0]
    
    # 核对一致性 (处理浮点数精度问题)
    if abs(total_calculated - expected_total) < 1e-6:
        consistency = "一致"
        difference = 0
    else:
        consistency = "不一致"
        difference = abs(total_calculated - expected_total)
    
    print(f"计算合计: {total_calculated}, 指定合计: {expected_total}, 一致性: {consistency}")
except Exception as e:
    print(f"核对失败: {e}")
    expected_total = None
    consistency = "未知"
    difference = None
```

Step2 将分析与核对结果保存为表格文件，并生成可供下载的文件链接。
```python
output_path_xlsx = 'analysis_result.xlsx'
output_path_csv = 'analysis_result.csv'

# 构建结果表格
result_data = {
    '统计项': ['总行数', f'{target_col}合计（计算值）', f'{target_col}合计（指定值）', '一致性', '差异值'],
    '数值': [total_rows, total_calculated, expected_total, consistency, difference]
}
result_df = pd.DataFrame(result_data)

# 保存为多种格式
result_df.to_excel(output_path_xlsx, index=False)
result_df.to_csv(output_path_csv, index=False, encoding='utf-8-sig')

# 输出下载链接（在报告中展示）
print("分析结果已保存，可下载：")
print(f"- [{output_path_xlsx}](sandbox:/{output_path_xlsx})")
print(f"- [{output_path_csv}](sandbox:/{output_path_csv})")
```
