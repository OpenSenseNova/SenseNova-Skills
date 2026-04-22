---
name: excel-data-analysis-and-report-generation
description: "从Excel提取多类型数据，并生成包含可视化图表与下载链接的综合分析报告。"
---

## Skill Steps

> This sub-skill covers one capability of the Excel workflow. For reading/counting/Parquet optimization, see the parent workflow SKILL.md.

Step1 基于指定列提取有效代码或进行分类映射，生成包含占比与总计行的统计表，并支持交叉分析。
```python
# 分类映射函数骨架
def categorize_item(item_name):
    category_a_keywords = ['keyword1', 'keyword2'] # 占位示例
    if pd.isna(item_name):
        return '未知'
    if any(kw in str(item_name) for kw in category_a_keywords):
        return '类别A'
    return '其他'

target_col = '项目名称' # 替换为实际列名
group_col = '所属区域'  # 替换为实际分组列名

if target_col in combined_df.columns:
    combined_df['分类'] = combined_df[target_col].apply(categorize_item)
    
    # value_counts + 占比 + 总计行
    category_counts = combined_df['分类'].value_counts().reset_index()
    category_counts.columns = ['类别', '数量']
    total = category_counts['数量'].sum()
    category_counts['占比'] = (category_counts['数量'] / total).apply(lambda x: f'{x:.2%}')
    
    total_row = pd.DataFrame([{'类别': '总计', '数量': total, '占比': '100.00%'}])
    category_counts = pd.concat([category_counts, total_row], ignore_index=True)
    
    # 交叉分析 crosstab
    if group_col in combined_df.columns:
        cross_tb = pd.crosstab(combined_df[group_col], combined_df['分类'], margins=True, margins_name='总计')
        print("交叉分析结果:\n", cross_tb)
```

Step2 识别目标值超过限值的行，基于关键字定位并反向搜索限值以确保数据关联。
```python
import re

exceed_rows = []
df_target = combined_df.copy()

for i, row in df_target.iterrows():
    if '共计' in str(row.iloc[0]):
        try:
            target_val = float(row.iloc[8]) # 目标值所在列索引
        except (ValueError, TypeError):
            continue
        
        limit_val = None
        structure_name = "未知结构"
        
        # 反向搜索限值
        for j in range(i-1, max(0, i-15), -1):
            check_row = df_target.iloc[j, :]
            check_str = ' '.join([str(x) for x in check_row.values if pd.notna(x)])
            if '限值' in check_str:
                # 数据清洗正则表达式
                match = re.search(r'限值([\d.]+)', check_str)
                if match:
                    limit_val = float(match.group(1))
                    for k in range(j-1, max(0, j-5), -1):
                        name_row = df_target.iloc[k, 0]
                        if pd.notna(name_row) and '关键字' in str(name_row):
                            structure_name = str(name_row)
                            break
                    break
        
        # 多维度评分/分级算法结构
        if limit_val is not None and target_val > limit_val:
            severity = '高' if (target_val - limit_val) > 10 else '中'
            exceed_rows.append({
                'row_index': i,
                'structure_name': structure_name,
                'target_val': target_val,
                'limit': limit_val,
                'exceed_value': target_val - limit_val,
                'severity': severity
            })
```

Step3 生成高分辨率可视化图表展示分类占比，保存统计结果并生成沙箱下载链接。
```python
import matplotlib.pyplot as plt
import matplotlib

# 中英文字体配置
matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']
matplotlib.rcParams['axes.unicode_minus'] = False

# 准备图表数据 (排除总计行)
plot_data = category_counts[category_counts['类别'] != '总计']
categories = plot_data['类别'].tolist()
counts = plot_data['数量'].tolist()

# 图表美化（dpi、颜色方案、标签位置）
fig, ax = plt.subplots(figsize=(10, 8))
colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#F9A826']
explode = [0.05] * len(categories)

wedges, texts, autotexts = ax.pie(
    counts, 
    labels=categories, 
    autopct='%1.1f%%',
    startangle=90,
    colors=colors[:len(categories)],
    explode=explode,
    shadow=True,
    textprops={'fontsize': 12}
)

ax.set_title('各类别数量占比分析', fontsize=16, fontweight='bold', pad=20)
ax.legend(wedges, categories, title="类别", loc="center left", bbox_to_anchor=(1, 0, 0.5, 1))

# 保存图表
chart_path = os.path.join(output_dir, 'category_analysis.png')
plt.savefig(chart_path, dpi=150, bbox_inches='tight')

# 保存统计结果并生成下载链接
output_path = os.path.join(output_dir, 'analysis_result.xlsx')
category_counts.to_excel(output_path, index=False)

print(f"统计结果已保存至: {output_path}")
print(f"下载链接: [下载统计结果](sandbox:{output_path})")
print(f"图表下载链接: [下载图表](sandbox:{chart_path})")
```
