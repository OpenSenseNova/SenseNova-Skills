---
name: excel-sheet-filter-export
description: "动态统计多Sheet Excel文件行数以判断大文件处理逻辑，并根据特定条件筛选数据、重命名字段后导出为包含下载链接的新Excel文件，适用于多Sheet数据探查与条件过滤导出场景。"
---

## Skill Steps

> This sub-skill covers one capability of the Excel workflow. For reading/counting/Parquet optimization, see the parent workflow SKILL.md.

Step1 读取目标Sheet，清理字段格式并根据特定条件筛选记录，统计关键指标。
```python
target_sheet = 'Sheet1' # 替换为实际sheet名
df_target = pd.read_excel(file_path, sheet_name=target_sheet)

# 清理目标列的字符串格式（去除首尾空格）
filter_col = 'group_col'
if filter_col in df_target.columns:
    df_target[filter_col] = df_target[filter_col].astype(str).str.strip()

# 筛选符合条件的记录
target_value = 'target_value_example'
mask = df_target[filter_col] == target_value
df_filtered = df_target[mask]

# 统计特定范围的种类数量
target_col = 'target_col'
if target_col in df_filtered.columns:
    specific_ranges = df_filtered[target_col].dropna().unique()
    print(f"{target_col} 种类数量:", len(specific_ranges))
    
    # 统计各分类数量与占比
    value_counts_df = df_filtered[target_col].value_counts().reset_index()
    value_counts_df.columns = [target_col, '数量']
    value_counts_df['占比'] = (value_counts_df['数量'] / value_counts_df['数量'].sum()).map('{:.2%}'.format)
    
    # 添加总计行
    total_row = pd.DataFrame({
        target_col: ['总计'], 
        '数量': [value_counts_df['数量'].sum()], 
        '占比': ['100.00%']
    })
    value_counts_df = pd.concat([value_counts_df, total_row], ignore_index=True)
    print(f"\n{target_col} 分布情况:\n", value_counts_df.head())
```

Step2 提取所需字段，对结果进行字段重命名与格式化处理，保存为新的Excel文件并生成下载链接。
```python
# 提取需要的列并重命名
selected_cols = ['col1', 'col2', filter_col, target_col]
# 确保列存在
existing_cols = [col for col in selected_cols if col in df_filtered.columns]
result_df = df_filtered[existing_cols].copy()

# 字段重命名映射字典
rename_mapping = {
    'col1': '重命名列1',
    'col2': '重命名列2',
    filter_col: '筛选维度',
    target_col: '分析维度'
}
result_df = result_df.rename(columns=rename_mapping)

# 保存结果并提供下载链接
output_path = "filtered_result_output.xlsx"
result_df.to_excel(output_path, index=False)
print("结果已保存至:", output_path)
print(f"[下载结果文件](sandbox:{output_path})")
```
