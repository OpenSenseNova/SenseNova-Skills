---
name: numeric-extraction-and-distribution-analysis
description: "从带单位的字符串列中提取数值并清洗，生成包含直方图、饼图、条形图和累积分布图的多维度综合分布可视化图表，用于展示数据的集中趋势与分布特征。"
---

# Numeric_Extraction_and_Distribution_Analysis

## Skill Steps

Step1 从原始数据中提取目标列，清理无效和空值数据，并安全地将带单位的字符串转换为数值类型
```python
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# 配置中英文字体，避免图表乱码
plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

item_col = '项目名称'  # 占位示例：分类或名称列
value_col = '带单位的数值'  # 占位示例：需要提取数值的原始列
numeric_col = '提取数值'
unit_str = 'g'  # 占位示例：需要移除的单位字符串

def extract_numeric_value(val_str):
    """从带单位的字符串中提取数值"""
    if pd.isna(val_str):
        return None
    try:
        # 移除单位并转换为浮点数
        return float(str(val_str).replace(unit_str, '').strip())
    except ValueError:
        return None

# 清理缺失值与异常占位符
df_clean = df.dropna(subset=[item_col, value_col]).copy()
df_clean = df_clean[df_clean[item_col] != '...']

# 应用提取函数并过滤转换失败的行
df_clean[numeric_col] = df_clean[value_col].apply(extract_numeric_value)
df_clean = df_clean.dropna(subset=[numeric_col])
```

Step2 创建基础分布直方图，并添加平均值和中位数的参考线以展示数据的集中趋势
```python
plt.figure(figsize=(12, 8))

# 绘制直方图
plt.hist(df_clean[numeric_col], bins=10, alpha=0.7, color='skyblue', edgecolor='black')

# 计算并添加平均值和中位数参考线
mean_val = df_clean[numeric_col].mean()
median_val = df_clean[numeric_col].median()
plt.axvline(mean_val, color='red', linestyle='--', linewidth=2, label=f'平均值: {mean_val:.2f}')
plt.axvline(median_val, color='green', linestyle='--', linewidth=2, label=f'中位数: {median_val:.2f}')

plt.xlabel(f'{numeric_col}', fontsize=12)
plt.ylabel('频数', fontsize=12)
plt.title(f'{numeric_col}分布直方图', fontsize=14, fontweight='bold')
plt.legend()
plt.grid(True, alpha=0.3)
plt.show()
```

Step3 生成包含直方图、饼图、条形图和累积分布图的综合分析面板，全面展示数值的分布特征并保存高分辨率图片
```python
# 创建 2x2 子图布局
fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))

# 1. 直方图
ax1.hist(df_clean[numeric_col], bins=8, alpha=0.7, color='lightblue', edgecolor='black', rwidth=0.8)
ax1.set_xlabel(f'{numeric_col}', fontsize=12)
ax1.set_ylabel('频数', fontsize=12)
ax1.set_title(f'{numeric_col}分布直方图', fontsize=14, fontweight='bold')
ax1.grid(True, alpha=0.3)

# 2. 饼图 (基于 value_counts 统计占比)
val_counts = df_clean[numeric_col].value_counts().sort_index()
colors = plt.cm.Set3(np.linspace(0, 1, len(val_counts)))
ax2.pie(val_counts.values, labels=[f'{x}' for x in val_counts.index], autopct='%1.1f%%', colors=colors, startangle=90)
ax2.set_title(f'{numeric_col}占比分布', fontsize=14, fontweight='bold')

# 3. 条形图
val_counts.plot(kind='bar', ax=ax3, color='lightcoral', alpha=0.8)
ax3.set_xlabel(f'{numeric_col}', fontsize=12)
ax3.set_ylabel('数量', fontsize=12)
ax3.set_title(f'各{numeric_col}对应的数量', fontsize=14, fontweight='bold')
ax3.tick_params(axis='x', rotation=45)
ax3.grid(True, alpha=0.3)

# 4. 累积分布图
sorted_values = np.sort(df_clean[numeric_col])
cumulative_freq = np.arange(1, len(sorted_values) + 1) / len(sorted_values) * 100
ax4.plot(sorted_values, cumulative_freq, marker='o', linewidth=2, markersize=6, color='darkgreen')
ax4.set_xlabel(f'{numeric_col}', fontsize=12)
ax4.set_ylabel('累积百分比 (%)', fontsize=12)
ax4.set_title(f'{numeric_col}累积分布', fontsize=14, fontweight='bold')
ax4.grid(True, alpha=0.3)

# 调整布局并保存
plt.tight_layout()
output_path = 'distribution_dashboard.png'
plt.savefig(output_path, dpi=300, bbox_inches='tight')
plt.show()
```
