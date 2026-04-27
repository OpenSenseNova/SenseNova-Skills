---
name: categorical-comparison-analysis
description: "对两类分类数据进行对比分析，统计数量差异与比例关系并生成可视化图表。"
---

# categorical-comparison-analysis

> This sub-skill covers one capability of the Excel workflow. For reading/counting/Parquet optimization, see the parent workflow SKILL.md.

Step1 读取文件并统计所有 sheet 的总行数，评估是否需要进行大文件优化处理。
```python
import pandas as pd
from pandas import read_excel
from pathlib import Path

# 统计所有 sheet 的行数以决定处理策略
file_path = "input_data.xlsx"
sheet_names = pd.ExcelFile(file_path).sheet_names
total_rows = 0
for sheet in sheet_names:
    # 仅读取行索引以快速计数
    df_tmp = read_excel(file_path, sheet_name=sheet, usecols=[0])
    total_rows += len(df_tmp)

print(f"Total rows across all sheets: {total_rows}")
```

Step2 提取对比维度的分类信息，执行数据清洗，包括去除空值、处理合并单元格填充以及排除非数据行。
```python
# 定义目标列名
target_col_a = "category_a_column"
target_col_b = "category_b_column"

# 处理合并单元格（ffill）并清洗数据
df[target_col_a] = df[target_col_a].ffill()
df[target_col_b] = df[target_col_b].ffill()

# 排除标题行占位符（如 '代码'、'名称'）及空值
exclude_val = "代码" 
data_a = df[target_col_a].dropna()
data_a = data_a[data_a != exclude_val]

data_b = df[target_col_b].dropna()
data_b = data_b[data_b != exclude_val]
```

Step3 统计分类数量，计算差异值与占比，生成多维度对比统计表。
```python
count_a = len(data_a)
count_b = len(data_b)
total_count = count_a + count_b
difference = abs(count_a - count_b)

# 计算占比
ratio_a = (count_a / total_count) * 100 if total_count > 0 else 0
ratio_b = (count_b / total_count) * 100 if total_count > 0 else 0

# 构建统计摘要
summary_df = pd.DataFrame({
    "分类名称": ["类别A", "类别B"],
    "数量": [count_a, count_b],
    "占比": [f"{ratio_a:.2f}%", f"{ratio_b:.2f}%"]
})
print(summary_df)
print(f"数量差异: {difference}")
```

Step4 配置中文字体并生成可视化图表（柱状图与饼图），美化输出效果。
```python
import matplotlib.pyplot as plt

# 中文字体配置
plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
labels = ['类别A', '类别B']
counts = [count_a, count_b]
colors = ['#3498db', '#e74c3c']

# 柱状图美化
bars = ax1.bar(labels, counts, color=colors, alpha=0.8, edgecolor='black')
ax1.set_title('分类数量对比', fontsize=14)
ax1.grid(axis='y', linestyle='--', alpha=0.6)
for bar in bars:
    height = bar.get_height()
    ax1.text(bar.get_x() + bar.get_width()/2., height + 0.1, f'{int(height)}', 
             ha='center', va='bottom', fontweight='bold')

# 饼图美化
ax2.pie(counts, labels=labels, colors=colors, autopct='%1.1f%%', startangle=140, explode=(0.05, 0))
ax2.set_title('分类比例分布', fontsize=14)

output_img = "/mnt/data/comparison_analysis_chart.png"
plt.tight_layout()
plt.savefig(output_img, dpi=300, bbox_inches='tight')
plt.show()
```

Step5 将分析结果导出为 Excel 文件，并生成可供下载的链接。
```python
from IPython.display import FileLink

output_path = "/mnt/data/analysis_report.xlsx"
with pd.ExcelWriter(output_path) as writer:
    summary_df.to_excel(writer, sheet_name='统计摘要', index=False)
    # 如果有明细数据也可在此导出

print(f"分析报告已生成")
display(FileLink(output_path, result_html_prefix="下载分析报告: "))
```
