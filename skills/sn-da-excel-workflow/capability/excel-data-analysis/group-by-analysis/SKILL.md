---
name: group-by-analysis
description: "对多 Sheet 的 Excel 文件进行行数统计、大文件 Parquet 转换预处理、数据清洗及分组聚合分析，并生成带样式标记的统计表与可视化图表。"
---

Step1 对数据进行清洗与预处理，包括处理合并单元格、正则过滤以及分类映射。
```python
import re

# 1. 处理合并单元格：向前填充
target_col = 'category_column'
df[target_col] = df[target_col].ffill()

# 2. 正则清洗：去除无效字符或筛选特定格式
def clean_text(text):
    if pd.isna(text): return text
    return re.sub(r'[^\w\s]', '', str(text)).strip()

df[target_col] = df[target_col].apply(clean_text)

# 3. 分类映射函数骨架
def map_categories(value):
    mapping = {
        'example_key_1': 'Group_A',
        'example_key_2': 'Group_B'
    }
    return mapping.get(value, 'Others')

df['group_tag'] = df[target_col].apply(map_categories)
```

Step2 执行分组统计，计算频数、占比，并添加总计行。
```python
group_col = 'group_tag'
value_col = 'value_column'

# 分组聚合：计数与求和
summary = df.groupby(group_col)[value_col].agg(['count', 'sum']).reset_index()

# 计算占比
total_sum = summary['sum'].sum()
summary['percentage'] = (summary['sum'] / total_sum).map(lambda x: f"{x:.2%}")

# 添加总计行
total_row = pd.DataFrame({
    group_col: ['Total'],
    'count': [summary['count'].sum()],
    'sum': [total_sum],
    'percentage': ['100.00%']
})
summary_final = pd.concat([summary, total_row], ignore_index=True)

print(summary_final)
```

Step3 生成可视化柱状图，配置中文字体、数值标签及网格美化。
```python
import matplotlib.pyplot as plt

# 配置中文字体支持
plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

plt.figure(figsize=(10, 6), dpi=100)
bars = plt.bar(summary[group_col], summary['sum'], color='#4472C4')

# 添加数值标签
for bar in bars:
    height = bar.get_height()
    plt.text(bar.get_x() + bar.get_width()/2., height,
             f'{height:,.0f}', ha='center', va='bottom', fontsize=10)

plt.title("Distribution Analysis", fontsize=14)
plt.xlabel(group_col)
plt.ylabel("Values")
plt.grid(axis='y', linestyle='--', alpha=0.7)
plt.tight_layout()

chart_path = "analysis_chart.png"
plt.savefig(chart_path)
```

Step4 使用 openpyxl 生成带样式和条件格式的 Excel 报告，并提供下载。
```python
from openpyxl import Workbook
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side

output_path = "analysis_report.xlsx"
wb = Workbook()
ws = wb.active
ws.title = "Summary Report"

# 定义样式
header_style = {
    "fill": PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid"),
    "font": Font(bold=True, color="FFFFFF"),
    "alignment": Alignment(horizontal="center"),
    "border": Border(left=Side(style="thin"), right=Side(style="thin"), top=Side(style="thin"), bottom=Side(style="thin"))
}

highlight_style = PatternFill(start_color="00B050", end_color="00B050", fill_type="solid")

# 写入数据并应用样式
for r_idx, row in enumerate(summary_final.values, 2):
    for c_idx, value in enumerate(row, 1):
        cell = ws.cell(row=r_idx, column=c_idx, value=value)
        # 示例：对最大值所在行进行绿色标记
        if value == summary['sum'].max():
            cell.fill = highlight_style

# 自动调整列宽
for col in ws.columns:
    max_length = max(len(str(cell.value)) for cell in col)
    ws.column_dimensions[col[0].column_letter].width = max_length + 2

wb.save(output_path)
print(f"Download link: {output_path}")
```
