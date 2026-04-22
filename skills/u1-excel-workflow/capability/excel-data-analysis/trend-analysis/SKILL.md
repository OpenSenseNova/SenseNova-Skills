---
name: trend-analysis
description: "基于多维度数据进行分级评估与趋势预测，通过设定差异化增长率计算预测值，并生成对比可视化图表，适用于绩效评估、目标设定等场景。"
---

Step1 加载数据并配置环境，设置中文字体以确保可视化图表正常显示。
```python
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import warnings
warnings.filterwarnings('ignore')

# 设置中文字体，优先使用 WenQuanYi Zen Hei，备选 SimHei 和 DejaVu Sans
plt.rcParams['font.sans-serif'] = ['WenQuanYi Zen Hei', 'SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

# 加载数据文件
file_path = 'your_data.xlsx'
df = pd.read_excel(file_path)

print(f"数据形状: {df.shape}")
df.head()
```

Step2 基于数据表现划分等级并设定差异化增长率，计算预测结果。
```python
# 定义通用列名
group_col = '分组列名'  # 示例：'部门'、'产品线'
target_col = '目标数值列名'  # 示例：'销售额'、'产量'

# 计算各维度的总值并排序
performance_data = df.groupby(group_col, as_index=False)[target_col].sum().sort_values(by=target_col, ascending=False)

# 划分等级（前30%为高，后30%为低，其余为中等）
n = len(performance_data)
high_perf_threshold = int(0.3 * n)
low_perf_threshold = int(0.7 * n)

performance_data['等级'] = '中等'
performance_data.loc[:high_perf_threshold-1, '等级'] = '高'
performance_data.loc[low_perf_threshold:, '等级'] = '低'

# 设定预测增长率映射字典
growth_rate_map = {
    '高': 0.10,   # 10% 增长率
    '中等': 0.08, # 8% 增长率
    '低': 0.15    # 15% 增长率
}
performance_data['预测增长率'] = performance_data['等级'].map(growth_rate_map)

# 计算预测值 = 当前值 × (1 + 增长率)，保留两位小数
performance_data['预测值'] = (performance_data[target_col] * (1 + performance_data['预测增长率'])).round(2)
performance_data[[group_col, target_col, '预测增长率', '预测值']].head()
```

Step3 综合分析预测结果，计算整体趋势指标并生成结论。
```python
# 计算整体指标
current_total = performance_data[target_col].sum()
forecast_total = performance_data['预测值'].sum()
growth_rate_total = (forecast_total - current_total) / current_total if current_total != 0 else 0

print(f"当前总计: {current_total:,.2f}")
print(f"预测总计: {forecast_total:,.2f}")
print(f"整体增长率: {growth_rate_total:.2%}")

# 输出趋势结论
if growth_rate_total > 0.1:
    conclusion = "整体趋势向好，预计实现显著增长。"
elif growth_rate_total > 0:
    conclusion = "整体呈温和增长态势。"
else:
    conclusion = "整体面临压力，需重点关注低绩效部分。"

print(f"趋势结论：{conclusion}")
```

Step4 可视化展示预测结果，通过横向柱状图对比当前与预测值，并标注等级与数值。
```python
# 设置图形大小与高分辨率
plt.figure(figsize=(12, 8), dpi=100)

# 横向柱状图：当前与预测值对比
x_pos = np.arange(len(performance_data))
width = 0.35

plt.barh(x_pos - width/2, performance_data[target_col], width, label='当前值', color='skyblue', edgecolor='black', alpha=0.8)
plt.barh(x_pos + width/2, performance_data['预测值'], width, label='预测值', color='lightcoral', edgecolor='black', alpha=0.8)

# 添加数值标签
for i, (current, forecast) in enumerate(zip(performance_data[target_col], performance_data['预测值'])):
    plt.text(current, i - width/2, f" {current:,.0f}", va='center', fontsize=9, color='black')
    plt.text(forecast, i + width/2, f" {forecast:,.0f}", va='center', fontsize=9, color='black')

# 添加等级标签到 Y 轴
for i, level in enumerate(performance_data['等级']):
    plt.text(0, i, f"({level}) ", va='center', ha='right', fontsize=9, color='gray', transform=plt.gca().get_yaxis_transform())

# 设置标题与标签
plt.xlabel(f'{target_col}')
plt.ylabel(f'{group_col}')
plt.title(f'各{group_col}当前与预测{target_col}对比', fontsize=14, fontweight='bold')
plt.yticks(x_pos, performance_data[group_col])
plt.legend()
plt.grid(axis='x', linestyle='--', alpha=0.5)

# 调整布局并显示
plt.tight_layout()
plt.show()
```
