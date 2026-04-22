---
name: line-chart-visualization
description: "提取结构化数据并进行特征清洗与聚类分析，生成包含趋势对比、分布特征与参数敏感性的多维度综合可视化图表，适用于各类趋势预测与多维对比场景。"
---

Step1 数据加载与预处理（支持大文件Parquet转换与动态表头识别）。
```python
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
import os
import re

# 设置中英文字体与图表美化
plt.rcParams['font.sans-serif'] = ['SimHei', 'WenQuanYi Zen Hei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

file_path = 'input_data.xlsx'

# 处理大型Excel文件：统计总行数，若≥1万则转换为Parquet格式提升效率
xls = pd.ExcelFile(file_path)
total_rows = sum(pd.read_excel(xls, sheet_name=s, header=None).shape[0] for s in xls.sheet_names)

if total_rows >= 10000:
    parquet_path = "temp_converted_file.parquet"
    with pd.ExcelWriter(parquet_path, engine='pyarrow') as writer:
        for sheet in xls.sheet_names:
            df_sheet = pd.read_excel(xls, sheet_name=sheet, header=None)
            df_sheet.to_excel(writer, sheet_name=sheet, index=False, header=False)
    df = pd.read_excel(parquet_path, sheet_name='Sheet1', header=None)
else:
    df = pd.read_excel(file_path, sheet_name='Sheet1', header=None)

# 动态识别表头并提取数据
header_row_idx = None
target_cols = ['group_col', 'value_col1', 'value_col2'] # 占位示例列名
for idx, row in df.iterrows():
    row_vals = row.astype(str).tolist()
    if all(col in row_vals for col in target_cols):
        header_row_idx = idx
        break

if header_row_idx is not None:
    df.columns = df.iloc[header_row_idx].tolist()
    df_clean = df.iloc[header_row_idx + 1:].reset_index(drop=True)
else:
    df_clean = df.copy()
```

Step2 数据清洗与特征工程（包含正则提取、缺失值处理与合并单元格还原）。
```python
# 合并单元格处理 (ffill + 遍历还原)
if 'group_col' in df_clean.columns:
    df_clean['group_col'] = df_clean['group_col'].ffill()

# 数据清洗正则表达式：提取数值
if 'value_col1' in df_clean.columns:
    df_clean['value_col1'] = df_clean['value_col1'].astype(str).str.replace(r'[^\d.]', '', regex=True)
    df_clean['value_col1'] = pd.to_numeric(df_clean['value_col1'], errors='coerce')

df_clean = df_clean.dropna(subset=['value_col1']).reset_index(drop=True)

# 分类映射函数骨架
def map_category(val):
    if pd.isna(val): return 'Unknown'
    if val > 100: return 'High' # 占位示例
    elif val > 50: return 'Medium'
    return 'Low'

if 'value_col1' in df_clean.columns:
    df_clean['level'] = df_clean['value_col1'].apply(map_category)

# 多维度评分/分级算法结构
def calculate_score(row):
    score = 0
    if pd.notna(row.get('value_col1')) and float(row['value_col1']) > 50: # 占位示例
        score += 50
    if pd.notna(row.get('value_col2')) and float(row['value_col2']) < 10: # 占位示例
        score += 50
    return score

df_clean['comprehensive_score'] = df_clean.apply(calculate_score, axis=1)
```

Step3 聚类分析与交叉统计（包含标准化、KMeans与多维度交叉分析）。
```python
numeric_cols = ['value_col1', 'comprehensive_score']
existing_num_cols = [c for c in numeric_cols if c in df_clean.columns]

if existing_num_cols:
    # 数值特征标准化
    scaler = StandardScaler()
    numeric_scaled = scaler.fit_transform(df_clean[existing_num_cols].fillna(0))
    
    # 聚类分析识别潜在数据群组结构
    kmeans = KMeans(n_clusters=3, random_state=42)
    df_clean['cluster_label'] = kmeans.fit_predict(numeric_scaled)

# value_counts + 占比计算
if 'level' in df_clean.columns:
    level_counts = df_clean['level'].value_counts()
    level_ratio = df_clean['level'].value_counts(normalize=True) * 100
    summary_df = pd.DataFrame({'频次': level_counts, '占比(%)': level_ratio.round(2)})
    summary_df.loc['总计'] = summary_df.sum()
    print("分类统计汇总:\n", summary_df)

# 交叉分析 crosstab/pivot
if 'cluster_label' in df_clean.columns and 'level' in df_clean.columns:
    cross_tb = pd.crosstab(df_clean['cluster_label'], df_clean['level'], margins=True, margins_name='总计')
    print("\n聚类与等级交叉分析:\n", cross_tb)
```

Step4 多维度可视化与结果输出（包含趋势、分布、占比与敏感性分析图表）。
```python
# 创建多维度综合可视化图表
fig, axes = plt.subplots(2, 2, figsize=(16, 12), dpi=150)
fig.suptitle('综合数据分析图表', fontsize=16)

group_col = 'group_col' if 'group_col' in df_clean.columns else df_clean.columns[0]

# 1. 趋势对比折线图
if 'value_col1' in df_clean.columns:
    axes[0, 0].plot(df_clean[group_col].astype(str).str[:10], df_clean['value_col1'], marker='o', label='指标1', color='#1f77b4')
    if 'comprehensive_score' in df_clean.columns:
        axes[0, 0].plot(df_clean[group_col].astype(str).str[:10], df_clean['comprehensive_score'], marker='s', label='综合评分', color='#ff7f0e')
    axes[0, 0].set_title('多指标趋势对比')
    axes[0, 0].set_xlabel('分组维度')
    axes[0, 0].set_ylabel('数值')
    axes[0, 0].legend(loc='upper right')
    axes[0, 0].grid(True, alpha=0.3)
    axes[0, 0].tick_params(axis='x', rotation=45)

# 2. 分布特征直方图
if 'value_col1' in df_clean.columns:
    axes[0, 1].hist(df_clean['value_col1'].dropna(), bins=15, alpha=0.7, color='skyblue', edgecolor='black')
    axes[0, 1].set_title('数值分布特征')
    axes[0, 1].set_xlabel('数值区间')
    axes[0, 1].set_ylabel('频次')
    axes[0, 1].grid(True, alpha=0.3)

# 3. 市场份额/占比饼图
if 'level' in df_clean.columns:
    level_counts = df_clean['level'].value_counts()
    colors_pie = plt.cm.Set3(np.linspace(0, 1, len(level_counts)))
    axes[1, 0].pie(level_counts, labels=level_counts.index, autopct='%1.1f%%', colors=colors_pie, startangle=90)
    axes[1, 0].set_title('分类占比分布')

# 4. 参数敏感性分析/聚类结果散点图
if 'cluster_label' in df_clean.columns and 'value_col1' in df_clean.columns:
    sns.scatterplot(data=df_clean, x=group_col, y='value_col1', hue='cluster_label', ax=axes[1, 1], palette='Set1', s=80)
    axes[1, 1].set_title('聚类分组散点图')
    axes[1, 1].tick_params(axis='x', rotation=45)
    axes[1, 1].grid(True, alpha=0.3)

plt.tight_layout(rect=[0, 0.03, 1, 0.95])

# 保存图表与清洗后的数据
chart_path = "output_chart.png"
output_path = "output_table.xlsx"

plt.savefig(chart_path, dpi=300, bbox_inches='tight')
plt.close()

df_clean.to_excel(output_path, index=False)

# 生成下载链接
print(f"分析完成。")
print(f"图表下载链接: file:///{os.path.abspath(chart_path)}")
print(f"数据下载链接: file:///{os.path.abspath(output_path)}")
```
