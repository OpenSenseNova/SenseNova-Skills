---
name: excel-basic-statistics-and-routing
description: "对多Sheet Excel文件进行基础统计与，支持按条件筛选计算均值，以及从指定行区间提取数据去重求和，并生成结果文件与下载链接。"
---

## Skill Steps

> This sub-skill covers one capability of the Excel workflow. For reading/counting/Parquet optimization, see the parent workflow SKILL.md.

Step1 筛选指定分组数据，将目标列转换为数值类型并计算平均值。
```python
group_col = '班级'  # 占位示例
target_group_value = '358'  # 占位示例
target_cols = ['总分', '理数']  # 占位示例

if group_col not in df_analysis.columns:
    raise ValueError(f"数据中缺少'{group_col}'列。")
df_analysis[group_col] = df_analysis[group_col].astype(str)
filtered_df = df_analysis[df_analysis[group_col] == target_group_value]

avg_scores = {}
for col in target_cols:
    if col not in filtered_df.columns:
        raise ValueError(f"数据中缺少'{col}'列。")
    try:
        filtered_df[col] = pd.to_numeric(filtered_df[col], errors='raise')
        avg_scores[f'平均{col}'] = filtered_df[col].mean()
    except Exception as e:
        raise ValueError(f"列'{col}'无法转换为数值类型: {str(e)}")

output("筛选结果统计: " + str(avg_scores))
```

Step2 对于小文件，从特定 Sheet 的指定行区间提取目标字段，去重后计算总和。
```python
unique_components = {}
total_power = 0

if total_rows < 10000:
    target_sheet = 'Sheet2'  # 占位示例
    df_sheet2 = pd.read_excel(file_path, sheet_name=target_sheet)
    extracted_data = []
    
    # 提取区间1 (例如 21-28行)
    for i in range(21, 29):
        if i < len(df_sheet2):
            row = df_sheet2.iloc[i]
            component = row.iloc[0]
            power = row.iloc[6]
            if pd.notna(component) and pd.notna(power):
                try:
                    extracted_data.append({'Component': component, 'Value': float(power)})
                except:
                    pass
    
    # 提取区间2 (例如 51-58行)
    for i in range(51, 59):
        if i < len(df_sheet2):
            row = df_sheet2.iloc[i]
            component = row.iloc[0]
            power = row.iloc[1]
            if pd.notna(component) and pd.notna(power):
                try:
                    extracted_data.append({'Component': component, 'Value': float(power)})
                except:
                    pass
    
    # 合并并去重 (保留首次出现的值)
    for item in extracted_data:
        name = item['Component']
        val = item['Value']
        if name not in unique_components:
            unique_components[name] = val
    
    total_power = sum(unique_components.values())
```

Step3 将计算结果、筛选数据和统计信息保存为Excel文件，并生成本地下载链接。
```python
import os

# 保存区间提取与汇总结果
if total_rows < 10000:
    result_df = pd.DataFrame([
        {'Component Name': name, 'Est. Power (kW)': power} 
        for name, power in unique_components.items()
    ])
    total_row = pd.DataFrame([{'Component Name': '合计', 'Est. Power (kW)': total_power}])
    result_df = pd.concat([result_df, total_row], ignore_index=True)
    
    output_path_power = "output_power_sum.xlsx"
    result_df.to_excel(output_path_power, index=False)
    output(f"功率计算结果已保存。下载链接: file://{os.path.abspath(output_path_power)}")

# 保存筛选与统计结果
output_path_analysis = "output_analysis_result.xlsx"
with pd.ExcelWriter(output_path_analysis, engine='openpyxl') as writer:
    filtered_df.to_excel(writer, sheet_name="筛选数据", index=False)
    pd.DataFrame([avg_scores]).to_excel(writer, sheet_name="统计信息", index=False)

output(f"分析完成，结果已保存。下载链接: file://{os.path.abspath(output_path_analysis)}")
```
