---
name: dynamic-large-file-parquet-analysis
description: "动态统计Excel总行数，当数据量过大（≥10000行）时自动转换为Parquet格式加速读取，并对指定目标列进行条件筛选、分类汇总与结果导出，适用于超大体积Excel文件的快速读取与统计分析。"
---

# Skill Steps

> This sub-skill covers one capability of the Excel workflow. For reading/counting/Parquet optimization, see the parent workflow SKILL.md.

Step1 动态读取数据（Parquet加速或常规读取）。
```python
# 若已加载 sn-da-large-file-analysis 技能，将 Excel 文件转换为 Parquet 格式加速读取
if 'da_large_file_analysis' in globals():
    # 假设 sn-da-large-file-analysis 转换后生成了 parquet 文件
    parquet_path = 'auto_converted_data.parquet'
    df = pd.read_parquet(parquet_path)
    print("已使用 Parquet 格式加速读取大文件。")
else:
    df = pd.read_excel(file_path, sheet_name='Sheet1', header=0)
    print("文件较小，使用常规方式读取。")
```

Step2 对目标列进行条件筛选，并按分组列进行分类汇总（包含占比与总计）。
```python
target_col = '目标列名'  # 示例：'危险级别'
group_col = '分组列名'   # 示例：'分项工程'
target_value = 'TARGET_VALUE'  # 示例：'★★★★'

# 筛选包含特定值的记录
df_filtered = df[df[target_col].astype(str).str.contains(target_value, na=False)].copy()

# 分类汇总
result = df_filtered[group_col].value_counts()
result_df = pd.DataFrame({
    group_col: result.index,
    '数量': result.values
})

# 计算占比并添加总计行
if not result_df.empty:
    result_df['占比'] = (result_df['数量'] / result_df['数量'].sum()).apply(lambda x: f"{x:.2%}")
    total_row = pd.DataFrame({
        group_col: ['总计'], 
        '数量': [result_df['数量'].sum()], 
        '占比': ['100.00%']
    })
    result_df = pd.concat([result_df, total_row], ignore_index=True)
```

Step3 导出汇总结果并生成下载链接。
```python
output_path = 'filtered_summary_output.xlsx'

# 将分类汇总结果保存为表格文件
result_df.to_excel(output_path, index=False)

# 输出下载链接供用户获取
print("数据处理与分类汇总完成。")
print(f"下载链接: {output_path}")
```
