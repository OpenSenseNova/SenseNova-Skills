---
name: chart-embedded-export
description: "从结构化数据中提取分类分布执行清洗与统计，生成多维度交叉分析、高分辨率对比图表及包含下载链接的完整分析报告，适用于大文件处理与嵌入式可视化场景。"
---

## Skill Steps

> This sub-skill covers one capability of the Excel workflow. For reading/counting/Parquet optimization, see the parent workflow SKILL.md.

Step1 执行数据清洗，处理合并单元格，使用正则表达式清理文本，并建立分类映射函数骨架。
```python
target_col = '分类字段'
value_col = '数值字段'

# 合并单元格处理 (向下填充还原)
df[target_col] = df[target_col].ffill()

# 数据清洗：正则去除特殊字符、去空、类型转换
df[target_col] = df[target_col].astype(str).str.replace(r'[^\w\s]', '', regex=True).str.strip()
df[value_col] = pd.to_numeric(df[value_col], errors='coerce')
df = df.dropna(subset=[target_col, value_col])

# 分类映射函数骨架
def map_category(val):
    if 'A类特征' in str(val): return 'Category_A'
    elif 'B类特征' in str(val): return 'Category_B'
    return 'Other'

df['Mapped_Category'] = df[target_col].apply(map_category)
```

Step2 进行多维度统计与交叉分析，计算分类占比并生成包含总计行的交叉表。
```python
group_col = '分组字段'

# value_counts 统计与占比计算
counts = df[group_col].value_counts()
proportions = (counts / counts.sum() * 100).round(2)

# 交叉分析 (crosstab)，包含总计行
cross_analysis = pd.crosstab(df[group_col], df['Mapped_Category'], margins=True, margins_name='总计')

# 多维度聚合统计
stats = df.groupby(group_col)[value_col].agg(['sum', 'mean', 'min', 'max']).round(2)
```

Step3 执行业务逻辑计算（如多维度评分与分级），将结果导出为 Excel 并生成沙盒下载链接。
```python
# 多维度评分/分级算法结构
df['Score'] = df[value_col] * 1.5  # 示例计算逻辑
df['Grade'] = pd.cut(df['Score'], bins=[0, 50, 80, 100], labels=['C', 'B', 'A'])

# 导出结构化结果
output_excel_path = 'analysis_result.xlsx'
df.to_excel(output_excel_path, index=False)

# 生成可点击的下载链接
print(f"分析结果已保存，下载链接：[下载结果数据](sandbox:{output_excel_path})")
```

Step4 配置中英文字体，生成包含饼图、柱状图、箱线图和直方图的综合可视化面板，并导出高分辨率双格式图片。
```python
output_img_path = 'comprehensive_chart.png'

# 中英文字体配置与图表美化
plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans', 'WenQuanYi Zen Hei']
plt.rcParams['axes.unicode_minus'] = False

fig, axes = plt.subplots(2, 2, figsize=(15, 12))
fig.suptitle('多维度数据分布综合分析', fontsize=16, fontweight='bold')

# 饼图：分布比例
colors = ['#ff9999', '#66b3ff', '#99ff99', '#ffcc99']
axes[0, 0].pie(counts.values, labels=counts.index, autopct='%1.1f%%', colors=colors, startangle=90)
axes[0, 0].set_title('分组选项分布比例')

# 柱状图：交叉分类分布
plot_data = cross_analysis.drop('总计', axis=0, errors='ignore').drop('总计', axis=1, errors='ignore')
plot_data.plot(kind='bar', ax=axes[0, 1], color=colors[:len(plot_data.columns)])
axes[0, 1].set_title('不同分组下分类分布')
axes[0, 1].tick_params(axis='x', rotation=45)

# 箱线图：数值分布
df.boxplot(column=value_col, by=group_col, ax=axes[1, 0])
axes[1, 0].set_title('不同分组下数值分布')

# 直方图：频数分布
for grp in df[group_col].dropna().unique():
    subset = df[df[group_col] == grp]
    axes[1, 1].hist(subset[value_col].dropna(), alpha=0.7, label=str(grp), bins=8)
axes[1, 1].legend()
axes[1, 1].set_title('数值分布直方图')

plt.tight_layout()
# 高分辨率图像导出
plt.savefig(output_img_path, format='png', dpi=300)
plt.savefig(output_img_path.replace('.png', '.svg'), format='svg')
plt.close()
```

Step5 整合统计数据与图表路径，生成包含关键发现与详细洞察的完整 Markdown 分析报告。
```python
report = [
    "# 数据综合分析报告\n",
    "## 1. 关键发现",
    f"- 数据集共包含 {len(df)} 条有效记录。",
]

for idx, val in proportions.items():
    report.append(f"- 分组 '{idx}' 的占比为 {val}%。")

report.extend([
    "\n## 2. 交叉分析汇总",
    cross_analysis.to_markdown(),
    "\n## 3. 聚合统计指标",
    stats.to_markdown(),
    f"\n## 4. 可视化分析\n![综合分析图表]({output_img_path})\n",
    "**结论**: 各类别在数据中呈现特定分布特征，详细明细与评分定级结果请参考上方下载链接获取完整附件。"
])

report_content = '\n'.join(report)
print(report_content)
```
