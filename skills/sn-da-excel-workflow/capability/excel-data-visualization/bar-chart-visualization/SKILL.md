---
name: excel-bar-chart-visualization
description: "读取多工作表Excel文件，自动处理合并单元格与数据清洗，进行交叉分组统计并生成带总计行的结果表，最后绘制支持中英文字体的美化柱状图，适用于多维度数据汇总与可视化分析。"
---

## Skill Steps

> This sub-skill covers one capability of the Excel workflow. For reading/counting/Parquet optimization, see the parent workflow SKILL.md.

### Step1: 数据合并与清洗
```python
combined_df = pd.concat(data_frames, ignore_index=True)

# 数据清洗：使用正则表达式统一命名
if '题型' in combined_df.columns:
    combined_df['题型'] = combined_df['题型'].astype(str).str.replace('判', '判断题', regex=False)

# 处理合并单元格技巧1：前向填充
if '流程描述' in combined_df.columns:
    combined_df['流程描述'] = combined_df['流程描述'].fillna(method='ffill')

# 处理合并单元格技巧2：通过逻辑判断与手动映射还原完整名称
group_col = '项目阶段'
target_col = '控制要点'
if group_col in combined_df.columns and target_col in combined_df.columns:
    project_stages, control_points = [], []
    current_stage = None
    for _, row in combined_df.iterrows():
        stage = row[group_col]
        point = row[target_col]
        if pd.notna(point) and point != target_col:
            if pd.notna(stage):
                current_stage = stage
            project_stages.append(current_stage)
            control_points.append(point)
    combined_df = pd.DataFrame({
        group_col: project_stages,
        target_col: control_points
    })
```

### Step2: 交叉分析与分类映射
```python
# 分类映射函数骨架
if group_col in combined_df.columns:
    stage_mapping = {
        '碎片值1': '标准分类A',
        '碎片值2': '标准分类A',
        '碎片值3': '标准分类B',
        '异常值': '其他'
    }
    combined_df[f'{group_col}_合并'] = combined_df[group_col].map(stage_mapping).fillna('其他')
    grouped_stats = combined_df.groupby(f'{group_col}_合并')[target_col].count().sort_values(ascending=False)
elif '题目分类' in combined_df.columns and '题型' in combined_df.columns:
    # 交叉分析 crosstab/pivot
    grouped_stats = combined_df.groupby(['题目分类', '题型']).size().unstack(fill_value=0)
else:
    grouped_stats = combined_df.groupby(combined_df.columns[0]).size()
```

### Step3: 统计结果输出与下载
```python
import tempfile
import os

output_path = os.path.join(tempfile.gettempdir(), "统计结果.xlsx")

# 计算占比并生成包含总计行的Excel文件
if isinstance(grouped_stats, pd.Series):
    result_df = pd.DataFrame({
        '分类': grouped_stats.index,
        '数量': grouped_stats.values,
        '占比(%)': (grouped_stats.values / grouped_stats.sum() * 100).round(2)
    })
    total_row = pd.DataFrame({
        '分类': ['总计'],
        '数量': [grouped_stats.sum()],
        '占比(%)': [100.00]
    })
    result_df = pd.concat([result_df, total_row], ignore_index=True)
else:
    result_df = grouped_stats.reset_index()

result_df.to_excel(output_path, index=False)

# 生成临时可访问的下载链接
download_url = invoke_skill("file_service.get_download_url", {"file_path": output_path})
print(f"下载链接: {download_url}")
```

### Step4: 图表绘制与美化
```python
import matplotlib.pyplot as plt
import matplotlib

# 技巧：配置中英文字体以确保在不同系统中正常显示
matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']
matplotlib.rcParams['axes.unicode_minus'] = False

stage_mapping_en = {
    '标准分类A': 'Standard Category A',
    '标准分类B': 'Standard Category B',
    '其他': 'Others'
}

if isinstance(grouped_stats, pd.Series):
    stage_counts_sorted = grouped_stats.sort_values(ascending=True)
    stage_counts_en = stage_counts_sorted.rename(index=stage_mapping_en)
    
    # 图表美化（dpi、颜色方案、标签位置）
    fig, ax = plt.subplots(figsize=(12, 8), dpi=120)
    colors = plt.cm.Set3(range(len(stage_counts_en)))
    bars = ax.barh(stage_counts_en.index, stage_counts_en.values, color=colors, edgecolor='black', linewidth=0.5)
    
    for bar, value in zip(bars, stage_counts_en.values):
        ax.text(bar.get_width() + (stage_counts_en.max() * 0.01), 
                bar.get_y() + bar.get_height()/2, 
                str(value), va='center', ha='left', fontsize=11, fontweight='bold')
                
    ax.set_xlabel('Count', fontsize=12, fontweight='bold')
    ax.set_ylabel('Category', fontsize=12, fontweight='bold')
    plt.tight_layout()
```
