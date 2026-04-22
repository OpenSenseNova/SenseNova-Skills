---
name: large-file-kpi-analysis
description: "根据数据量自动选择读取策略（大文件转Parquet），提取关键指标进行单位一致性验证与排序分析，并输出可下载的结果表格。"
---

## Skill Steps

> This sub-skill covers one capability of the Excel workflow. For reading/counting/Parquet optimization, see the parent workflow SKILL.md.

Step1 提取关键指标，进行物理量/指标的单位一致性验证计算，并对核心业务指标进行降序排列。
```python
# 1. 物理量/指标单位一致性验证与计算 (保留公式结构示例)
col_numerator = 'numerator_col'  # 示例：Mx (kN·m)
col_denominator = 'denominator_col' # 示例：Wx (cm³)
col_target = 'target_col' # 示例：sigma (MPa)

if col_numerator in data.columns and col_denominator in data.columns and col_target in data.columns:
    # 单位换算示例：统一到标准单位后计算
    data['den_converted'] = data[col_denominator] * 1e-6
    data['num_converted'] = data[col_numerator] * 1e3
    data['calc_result_pa'] = data['num_converted'] / data['den_converted']
    data['calc_result_mpa'] = data['calc_result_pa'] / 1e6
    
    # 容差验证
    tolerance = 1e-6
    data['is_valid'] = abs(data['calc_result_mpa'] - data[col_target]) < tolerance
    print("单位一致性验证通过率:", data['is_valid'].mean() * 100, "%")

# 2. 提取关键指标并降序排列
group_col = 'group_col' # 示例：开发区名称
metric_col = 'metric_col' # 示例：实际到帐外资额

result_df = pd.DataFrame()
if group_col in data.columns and metric_col in data.columns:
    result_df = data[[group_col, metric_col]].copy()
    result_df = result_df.sort_values(metric_col, ascending=False).reset_index(drop=True)
```

Step2 将分析与验证结果整理为最终的数据框，保存为 Excel 文件，并生成可供下载的链接。
```python
output_path = 'analysis_result.xlsx'

# 确定最终输出的数据框
if not result_df.empty:
    result_df_final = result_df
elif 'calc_result_mpa' in data.columns:
    result_df_final = data[[col_numerator, col_denominator, col_target, 'calc_result_mpa', 'is_valid']].copy()
    result_df_final.columns = ['分子指标', '分母指标', '目标比对值', '计算结果', '是否一致']
else:
    result_df_final = data.head(100) # 默认输出前100行作为示例

# 保存为Excel文件
result_df_final.to_excel(output_path, index=False, engine='openpyxl')
print(f"分析结果已保存至: {output_path}")

# 生成下载链接
print(f"下载链接: [点击下载分析结果](./{output_path})")
```
