---
name: excel-statistical-viz-large-file
description: "对 Excel 数据进行多维度统计分析与可视化。"
---

# excel_statistical_visualization

> This sub-skill covers one capability of the Excel workflow. For reading/counting/Parquet optimization, see the parent workflow SKILL.md.

Step1 数据清洗与标准化。提取目标分析列，处理合并单元格（ffill），并利用正则表达式或类型转换清理数值字段，确保分析数据集的准确性。
```python
import re

# 假设 target_col_x 和 target_col_y 是分析目标
# 处理合并单元格导致的缺失值
df['group_col'] = df['group_col'].fillna(method='ffill')

def clean_numeric_string(value):
    if pd.isna(value): return None
    # 保留数字、小数点和负号，移除空格及非法字符
    cleaned = re.sub(r'[^\d\.\-]', '', str(value))
    try:
        return float(cleaned)
    except ValueError:
        return None

df['x_val'] = df['target_col_x'].apply(clean_numeric_string)
df['y_val'] = df['target_col_y'].apply(clean_numeric_string)

# 过滤无效数据
df_clean = df.dropna(subset=['x_val', 'y_val']).copy()
```

Step2 执行多维度统计分析。计算分类占比、均值、标准差，并构建交叉分析表（crosstab/pivot），为可视化提供数据支撑。
```python
# 分类统计与占比
stats_summary = df_clean.groupby('group_col')['y_val'].agg(['count', 'mean', 'std', 'min', 'max'])
stats_summary['percentage'] = (stats_summary['count'] / stats_summary['count'].sum()) * 100

# 添加总计行
total_row = pd.DataFrame(df_clean[['y_val']].agg(['count', 'mean']).T)
total_row.index = ['Total']

# 交叉分析示例
pivot_table = pd.pivot_table(df_clean, values='y_val', index='group_col', columns='category_col', aggfunc='count', fill_value=0)
```

Step3 生成高分辨率可视化图表。包含散点图、线性趋势线（R²、p值）、箱线图或柱状图组合，并配置中文字体与美化参数。
```python
import matplotlib.pyplot as plt
import matplotlib
from scipy import stats
import numpy as np

# 字体配置：优先使用 SimHei 或 DejaVu Sans 确保中文显示
matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'WenQuanYi Zen Hei', 'DejaVu Sans']
matplotlib.rcParams['axes.unicode_minus'] = False

x = df_clean['x_val'].values
y = df_clean['y_val'].values

# 线性回归计算
slope, intercept, r_value, p_value, std_err = stats.linregress(x, y)
line = slope * x + intercept

plt.figure(figsize=(12, 8), dpi=300)

# 散点图：添加随机抖动 (jitter) 避免点重叠
jitter_x = x + np.random.normal(0, 0.01, size=len(x))
plt.scatter(jitter_x, y, alpha=0.6, edgecolors='w', label='Data Points')

# 趋势线
plt.plot(x, line, color='red', linestyle='--', linewidth=2, 
         label=f'Trend: y={slope:.4f}x+{intercept:.4f}\n$R^2$={r_value**2:.4f}, p={p_value:.4e}')

# 数据点标注 (实战技巧：仅标注极值或特定点)
for i, (xi, yi) in enumerate(zip(x, y)):
    if i % (len(x)//5 or 1) == 0: # 抽样标注避免拥挤
        plt.annotate(f'({xi:.2f}, {yi:.2f})', (xi, yi), textcoords="offset points", xytext=(5,5), fontsize=8)

plt.xlabel('Dimension X')
plt.ylabel('Dimension Y')
plt.title('Statistical Distribution & Trend Analysis')
plt.grid(True, linestyle=':', alpha=0.6)
plt.legend()

output_img = 'analysis_plot.png'
plt.savefig(output_img, bbox_inches='tight')
plt.show()
```

Step4 导出分析结果并生成下载链接。将清洗后的数据及统计摘要保存为 CSV 或 Excel 文件。
```python
output_csv = 'cleaned_analysis_data.csv'
# 使用 utf-8-sig 确保 Excel 打开中文不乱码
df_clean.to_csv(output_csv, index=False, encoding='utf-8-sig')

print(f"Visualization saved to: {output_img}")
print(f"Data exported to: {output_csv}")
# 打印回归关键指标供快速参考
print(f"R-squared: {r_value**2:.6f}, P-value: {p_value:.6f}")
```
