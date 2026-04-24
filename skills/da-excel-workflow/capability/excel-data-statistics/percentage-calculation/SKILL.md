---
name: dynamic-percentage-and-large-file-analysis
description: "根据文件行数动态切换大文件处理策略（Parquet转换），通过逐行扫描或列匹配提取关键指标并计算占比、均值等统计量，最终输出结构化Excel报告及可视化图表。"
---

## Skill Steps

> This sub-skill covers one capability of the Excel workflow. For reading/counting/Parquet optimization, see the parent workflow SKILL.md.

Step1 在数据中动态定位关键字段，通过逐行扫描匹配关键词提取数值，并进行条件筛选与占比计算。
```python
key_values = {}
target_col = None
value_col = 'target_value_col'

# 动态查找目标分类列
for col in df_analysis.columns:
    if 'keyword1' in col.lower() or 'keyword2' in col.lower():
        target_col = col
        break

# 通用字段查找逻辑：逐行扫描匹配关键词并提取首个正数
for idx, row in df_analysis.iterrows():
    row_str = str(row.values)
    if '指标A' in row_str and '指标A' not in key_values:
        for val in row.values:
            if isinstance(val, (int, float)) and val > 0:
                key_values['指标A'] = val
                break
    if '指标B' in row_str and '指标B' not in key_values:
        for val in row.values:
            if isinstance(val, (int, float)) and val > 0:
                key_values['指标B'] = val
                break

# 条件筛选与统计
if target_col and '特定类别' in df_analysis[target_col].unique():
    df_filtered = df_analysis[df_analysis[target_col] == '特定类别']
    if value_col in df_filtered.columns:
        df_filtered[value_col] = pd.to_numeric(df_filtered[value_col], errors='coerce')
        avg_val = df_filtered[value_col].mean()
        print(f"特定类别平均值 = {avg_val:.2f}")

# 计算占比
if '指标A' in key_values and '指标B' in key_values:
    percentage = (key_values['指标A'] / key_values['指标B']) * 100
    print(f"指标A占指标B的百分比: {percentage:.2f}%")
```

Step2 将计算结果保存为结构化表格文件（.xlsx），并在输出中提供可追溯的下载链接。
```python
output_path = "output_analysis_result.xlsx"
os.makedirs(os.path.dirname(output_path), exist_ok=True)

result_data = {
    '项目': ['指标A', '指标B', '占比'],
    '数值': [key_values.get('指标A', 0), key_values.get('指标B', 0), f"{percentage:.2f}%" if 'percentage' in locals() else "N/A"]
}
df_result = pd.DataFrame(result_data)

with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
    df_result.to_excel(writer, sheet_name='汇总结果', index=False)

print(f"结果已保存到: {output_path}")
print(f"下载链接: [点击下载结果表格]({output_path})")
```

Step3 配置中文字体并生成高分辨率的可视化图表（如饼图），展示占比分析结果。
```python
import matplotlib.pyplot as plt
import matplotlib

# 配置中英文字体，防止图表中文乱码
matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans', 'WenQuanYi Zen Hei']
matplotlib.rcParams['axes.unicode_minus'] = False

if 'percentage' in locals():
    # 图表美化与高分辨率设置
    plt.figure(figsize=(8, 6), dpi=120)
    labels = ['指标A', '其他']
    sizes = [percentage, 100 - percentage]
    colors = ['#ff9999', '#66b3ff']
    
    plt.pie(sizes, labels=labels, colors=colors, autopct='%1.1f%%', startangle=90)
    plt.title('核心指标占比分析')
    plt.axis('equal')
    
    chart_path = "percentage_chart.png"
    plt.savefig(chart_path, bbox_inches='tight')
    print(f"图表已保存至: {chart_path}")
    print(f"图表下载链接: [点击下载可视化图表]({chart_path})")
```
