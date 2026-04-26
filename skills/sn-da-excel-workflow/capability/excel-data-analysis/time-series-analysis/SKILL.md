---
name: time-series-and-categorical-analysis
description: "对时间序列或分类数据进行多维度趋势分析、百分比清洗、绩效分级建模与预测，并生成高分辨率的可视化综合报告，适用于业务指标监控与预测场景。"
---

## Skill Steps

Step1 加载并检查原始数据，配置中文字体以确保图表正常显示。
```python
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import warnings
warnings.filterwarnings('ignore')

# 设置中文字体，兼容不同操作系统
plt.rcParams['font.sans-serif'] = ['SimHei', 'WenQuanYi Zen Hei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

# 加载Excel文件
file_path = 'data.xlsx'
df = pd.read_excel(file_path)

print(f"数据形状: {df.shape}")
print(f"列名: {list(df.columns)}")
```

Step2 提取时间序列或分类维度数据，处理百分比格式，并计算变化趋势。
```python
def convert_percentage(pct_str):
    """将百分比字符串转换为数值，处理空值和非字符串类型"""
    if pd.isna(pct_str):
        return None
    if isinstance(pct_str, str) and '%' in pct_str:
        try:
            return float(pct_str.replace('%', ''))
        except ValueError:
            return None
    return pct_str

time_col = '时间列'  # 占位示例
target_cols = ['指标1占比', '指标2占比', '指标3占比']  # 占位示例

# 转换百分比字符串为数值并提取数据
ts_df = df[[time_col] + target_cols].copy() if time_col in df.columns else df.copy()
for col in target_cols:
    if col in ts_df.columns:
        ts_df[col] = ts_df[col].apply(convert_percentage)
        
        # 计算变化趋势并识别状态
        diff_col = f'{col}_变化'
        trend_col = f'{col}_趋势'
        ts_df[diff_col] = ts_df[col].diff()
        ts_df[trend_col] = ['上升' if x > 0 else '下降' if x < 0 else '稳定' for x in ts_df[diff_col]]
```

Step3 基于数值进行多维度分级算法建模，映射差异化增长率并计算预测值。
```python
group_col = '分组列'  # 占位示例，如'部门'
value_col = '数值列'  # 占位示例，如'销售额'

# 聚合计算总和并排序
grouped_df = df.groupby(group_col, as_index=False)[value_col].sum()
grouped_df = grouped_df.sort_values(by=value_col, ascending=False).reset_index(drop=True)

# 多维度分级算法结构：前30%为高，中间40%为中，后30%为低
total_rows = len(grouped_df)
high_threshold = int(total_rows * 0.3)
mid_threshold = int(total_rows * 0.7)

grouped_df['等级'] = np.where(
    grouped_df.index < high_threshold, '高',
    np.where(grouped_df.index < mid_threshold, '中', '低')
)

# 分类映射函数骨架：为不同等级设定差异化增长率
growth_rates = {'高': 0.15, '中': 0.08, '低': 0.03}
grouped_df['增长率'] = grouped_df['等级'].map(growth_rates)

# 计算预测值与增长量
grouped_df['预测值'] = grouped_df[value_col] * (1 + grouped_df['增长率'])
grouped_df['增长量'] = grouped_df['预测值'] - grouped_df[value_col]
```

Step4 生成多维度可视化图表（堆叠面积图、柱状图、条形图），并保存为高分辨率图像。
```python
output_path = 'trend_analysis_report.png'
plt.figure(figsize=(14, 10))

# 子图1：堆叠面积图（时间序列占比变化）
plt.subplot(2, 2, 1)
sns.set_style('whitegrid')
if time_col in ts_df.columns and all(c in ts_df.columns for c in target_cols):
    plt.stackplot(ts_df[time_col], 
                  *[ts_df[c] for c in target_cols], 
                  labels=target_cols, alpha=0.8)
    plt.title('各指标占比变化趋势', fontsize=14, fontweight='bold')
    plt.xlabel(time_col)
    plt.ylabel('占比 (%)')
    plt.legend(loc='upper left')
    plt.xticks(rotation=45)

# 子图2：当前 vs 预测对比（柱状图）
plt.subplot(2, 2, 2)
x = np.arange(len(grouped_df))
width = 0.35
plt.bar(x - width/2, grouped_df[value_col], width, label='当前值', alpha=0.8)
plt.bar(x + width/2, grouped_df['预测值'], width, label='预测值', alpha=0.8)
plt.xlabel(group_col)
plt.ylabel('数值')
plt.title('当前与预测值对比')
plt.xticks(x, grouped_df[group_col], rotation=45)
plt.legend()

# 子图3：增长率分布（条形图）
plt.subplot(2, 2, 3)
plt.barh(grouped_df[group_col], grouped_df['增长率'], color='skyblue')
plt.xlabel('增长率')
plt.title('各组增长率分布')
plt.gca().invert_yaxis()

# 子图4：增长量分布（柱状图）
plt.subplot(2, 2, 4)
plt.bar(grouped_df[group_col], grouped_df['增长量'], color='lightcoral')
plt.xlabel(group_col)
plt.ylabel('增长量')
plt.title('各组增长量分析')
plt.xticks(rotation=45)

plt.tight_layout()
# 图表美化与高分辨率保存
plt.savefig(output_path, dpi=300, bbox_inches='tight')
plt.close()
```

Step5 生成综合分析报告，汇总核心指标并输出趋势结论。
```python
# 总体预测汇总
total_current = grouped_df[value_col].sum()
total_forecast = grouped_df['预测值'].sum()
total_growth = grouped_df['增长量'].sum()
overall_growth_rate = (total_forecast - total_current) / total_current if total_current else 0

print("=" * 60)
print("📊 综合趋势分析报告")
print("=" * 60)
print(f"当前总值: {total_current:,.2f}")
print(f"预测总值: {total_forecast:,.2f}")
print(f"总增长量: {total_growth:,.2f}")
print(f"整体增长率: {overall_growth_rate:.2%}")
print("\n📈 分析结论：")
if overall_growth_rate > 0.1:
    print("  - 整体趋势向好，预计实现显著增长。")
elif overall_growth_rate > 0:
    print("  - 呈温和增长态势，建议加强低等级组支持。")
else:
    print("  - 预测下滑，需深入分析原因并制定应对策略。")
print("=" * 60)
```
