---
name: stacked-chart-visualization
description: "处理包含百分比字符串的分类占比数据，通过补全缺失维度并生成堆叠柱状图，直观展示多维度构成随时间或分类的变化趋势。"
---

# Stacked_Chart_Visualization

Step1 定义百分比转换函数并提取原始数据。通过正则表达式或字符串处理将百分比格式转换为可计算的浮点数。
```python
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# 配置中文字体，确保图表标签正常显示
plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

def convert_percentage(val):
    """
    将百分比字符串转换为浮点数。
    处理逻辑：去除百分号并转换为 float，若已经是数值则直接返回。
    """
    if isinstance(val, str):
        return float(val.strip('%'))
    return val

# 示例数据提取逻辑（实际应用中替换为从 DataFrame 提取）
time_labels = ['1月', '2月', '3月', '4月', '5月', '6月'] # 泛化时间轴
cat1_raw = ['23.21%', '22.98%', '24.31%', '24.53%', '23.84%', '24.80%']
cat2_raw = ['25.17%', '25.67%', '25.77%', '25.98%', '25.17%', '25.61%']
cat3_raw = ['28.12%', '28.37%', '26.58%', '25.83%', '26.49%', '25.17%']

cat1_ratios = [convert_percentage(x) for x in cat1_raw]
cat2_ratios = [convert_percentage(x) for x in cat2_raw]
cat3_ratios = [convert_percentage(x) for x in cat3_raw]
```

Step2 构建结构化数据表，将清洗后的数值整合进 DataFrame 以便进行向量化计算。
```python
# 构建包含时间维度和各分类占比的结构化数据表
df = pd.DataFrame({
    'group_col': time_labels,
    'cat_1': cat1_ratios,
    'cat_2': cat2_ratios,
    'cat_3': cat3_ratios
})
```

Step3 计算缺失维度的占比。在已知部分维度占比的情况下，通过总和 100% 的约束推算剩余维度的数值，并进行数据校验。
```python
# 计算已知维度的总占比
target_cols = ['cat_1', 'cat_2', 'cat_3']
df['current_total'] = df[target_cols].sum(axis=1)

# 推算剩余维度（如“其他”或特定分类）的占比
df['cat_remainder'] = 100 - df['current_total']

# 验证数据完整性：确保所有维度相加接近 100
df['final_check'] = df[target_cols + ['cat_remainder']].sum(axis=1)
```

Step4 使用堆叠柱状图进行可视化。核心在于利用 `bottom` 参数逐层累加高度，并优化图表美学配置。
```python
# 设置绘图风格与画布
plt.figure(figsize=(12, 6), dpi=100)
sns.set_style('whitegrid')

# 核心堆叠逻辑：每一层的 bottom 是前几层高度的总和
plt.bar(df['group_col'], df['cat_1'], label='分类1', color='#5DADE2')
plt.bar(df['group_col'], df['cat_2'], bottom=df['cat_1'], label='分类2', color='#58D68D')
plt.bar(df['group_col'], df['cat_3'], bottom=df['cat_1'] + df['cat_2'], label='分类3', color='#EC7063')
plt.bar(df['group_col'], df['cat_remainder'], bottom=df['cat_1'] + df['cat_2'] + df['cat_3'], label='其他', color='#F4D03F')

# 图表辅助元素优化
plt.xlabel('统计周期')
plt.ylabel('占比 (%)')
plt.title('多维度占比变化趋势分析')
plt.legend(loc='upper right', bbox_to_anchor=(1.1, 1))
plt.xticks(rotation=45) # 避免标签重叠
plt.tight_layout()
```

Step5 导出分析结果。将生成的图表保存为高分辨率图片，并清理内存。
```python
# 保存图表，设置 dpi 确保清晰度，bbox_inches 确保标签不被截断
output_path = 'stacked_ratio_analysis.png'
plt.savefig(output_path, dpi=300, bbox_inches='tight')
plt.show()
plt.close()
```
