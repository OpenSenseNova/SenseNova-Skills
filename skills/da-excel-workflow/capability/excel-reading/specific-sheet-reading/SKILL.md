---
name: excel-multi-sheet-dynamic-analysis
description: "用于分析包含多个Sheet的Excel文件，动态判断数据量级以决定是否转换为Parquet进行大文件处理，并支持跨Sheet的特定字段统计、数据清洗、交叉分析与可视化，最终生成带下载链接的汇总报告。"
---

Step1 遍历所有sheet，灵活定位目标列并统计特定类型字段的数量。
```python
target_col_keyword = 'type' # 占位示例
target_val_keyword = 'varchar' # 占位示例

total_target_count = 0
target_details = []

for sheet_name in wb.sheetnames:
    ws = wb[sheet_name]
    raw_data = list(ws.iter_rows(values_only=True))

    # 实用技巧：灵活策略定位目标列，通过扫描前几行数据内容定位表头行
    header_row_idx = None
    for i, row in enumerate(raw_data):
        if any(cell and isinstance(cell, str) and target_col_keyword in str(cell).lower() for cell in row):
            header_row_idx = i
            break

    if header_row_idx is not None:
        header = raw_data[header_row_idx]
        type_col_idx = next((j for j, col in enumerate(header) if col and target_col_keyword in str(col).lower()), None)
        
        if type_col_idx is not None:
            target_count = 0
            target_fields = []
            for i in range(header_row_idx + 1, len(raw_data)):
                row = raw_data[i]
                if len(row) <= type_col_idx:
                    continue
                cell_val = row[type_col_idx]
                if cell_val and isinstance(cell_val, str) and target_val_keyword in cell_val.lower():
                    target_count += 1
                    field_name = row[0] if len(row) > 0 else None
                    if field_name and field_name not in target_fields:
                        target_fields.append(field_name)
                        
            total_target_count += target_count
            target_details.append({
                'sheet': sheet_name,
                'target_count': target_count,
                'target_fields': target_fields[:10]
            })
```

Step2 对特定Sheet进行数据清洗、分类映射、多维度评分及交叉聚合分析。
```python
import pandas as pd
import re

# 读取特定Sheet并处理列名
sheet1_df = pd.read_excel(file_path, sheet_name='Sheet1', engine='openpyxl', header=None, skiprows=1)
sheet1_df.columns = ['id_col', 'name_col', 'year_col', 'value_col', 'group_col'] # 占位示例

# 合并单元格处理（ffill + 遍历还原）
sheet1_df['group_col'] = sheet1_df['group_col'].ffill()

# 数据清洗正则表达式 (提取数值)
sheet1_df['value_col'] = sheet1_df['value_col'].astype(str).str.replace(r'[^\d.]', '', regex=True)
sheet1_df['value_col'] = pd.to_numeric(sheet1_df['value_col'], errors='coerce').fillna(0)

# 分类映射函数骨架（具体值替换为占位示例，保留函数结构）
def map_category(val):
    if pd.isna(val): return 'Unknown'
    if 'keyword' in str(val): return 'Category A' # 占位示例
    return 'Other'
sheet1_df['mapped_category'] = sheet1_df['name_col'].apply(map_category)

# 多维度评分/分级算法结构
def calculate_score(row):
    score = 0
    if row['value_col'] > 100: score += 50 # 占位示例
    if row['mapped_category'] == 'Category A': score += 50
    return score
sheet1_df['score'] = sheet1_df.apply(calculate_score, axis=1)

# 筛选特定条件的数据
target_val = 'target_value' # 占位示例
filtered_df = sheet1_df[sheet1_df['group_col'] == target_val]
count = len(filtered_df)
total_value = filtered_df['value_col'].sum()

# value_counts + 占比 + 总计行
stats_df = sheet1_df['group_col'].value_counts().rename('数量').to_frame()
stats_df['占比'] = sheet1_df['group_col'].value_counts(normalize=True).apply(lambda x: f"{x:.2%}")
stats_df.loc['总计'] = [stats_df['数量'].sum(), '100.00%']

# 交叉分析 crosstab/pivot
cross_table = pd.crosstab(sheet1_df['group_col'], sheet1_df['mapped_category'], margins=True, margins_name='总计')

result_df = pd.DataFrame({
    '统计项': [f'{target_val} 数量', f'{target_val} 总值'],
    '数值': [count, total_value]
})
```

Step3 对统计结果进行可视化图表绘制与美化。
```python
import matplotlib.pyplot as plt
import seaborn as sns
import os

# 中英文字体配置 (SimHei, DejaVu Sans)
plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

# 图表美化（dpi、颜色方案、标签位置）
plt.figure(figsize=(10, 6), dpi=120)
plot_data = stats_df.drop('总计') # 排除总计行进行绘图
ax = sns.barplot(x=plot_data.index, y=plot_data['数量'], palette='Blues_d')

# 标签位置优化
for p in ax.patches:
    ax.annotate(f'{int(p.get_height())}', 
                (p.get_x() + p.get_width() / 2., p.get_height()), 
                ha='center', va='bottom', fontsize=10)

plt.title('各分组数量统计')
plt.xlabel('分组')
plt.ylabel('数量')
plt.tight_layout()

plot_path = os.path.join(os.getcwd(), 'stats_chart.png')
plt.savefig(plot_path)
plt.close()
```

Step4 将所有分析结果保存为Excel文件，并生成可点击的下载链接。
```python
from datetime import datetime
from IPython.display import HTML, display
import os

summary_df = pd.DataFrame([{'total_target_count': total_target_count}])
details_df = pd.DataFrame(target_details)

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
output_filename = f"analysis_result_{timestamp}.xlsx"
output_path = os.path.join(os.getcwd(), output_filename)

with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
    summary_df.to_excel(writer, sheet_name='汇总表', index=False)
    details_df.to_excel(writer, sheet_name='详细列表', index=False)
    result_df.to_excel(writer, sheet_name='特定条件统计', index=False)
    stats_df.to_excel(writer, sheet_name='分组统计')
    cross_table.to_excel(writer, sheet_name='交叉分析')

print(f"\n文件已保存至: {output_path}")

# 下载链接生成
download_link = f'<a href="{output_path}" download="{output_path}">点击下载分析结果</a>'
display(HTML(download_link))
```
