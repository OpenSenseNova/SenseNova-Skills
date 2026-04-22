---
name: category-statistics
description: "提取指定类别列并统计各类别数量与占比，生成高分辨率的柱状图、饼图等组合可视化报告，适用于分类数据的分布情况分析。"
---

## Skill Steps

Step1 提取目标类别数据，清洗无效标签，并统计各类别数量与占比。
```python
import pandas as pd

def calculate_distribution(data, target_col='类别'):
    # 检查目标列是否存在
    if target_col not in data.columns:
        raise ValueError(f'未找到指定的类别字段: {target_col}')
    
    # 提取数据，清洗无效标签（如'--'、'代码'等占位符）
    category_data = data[target_col].dropna().replace(['--', '代码'], pd.NA).dropna()
    
    # 统计各类别数量并计算占比
    counts = category_data.value_counts()
    proportions = (counts / counts.sum()) * 100
    
    # 实用技巧：生成包含总计行的统计表
    # summary = counts.copy()
    # summary.loc['总计'] = counts.sum()
    
    return counts, proportions
```

Step2 生成基础可视化（双轴图：柱状图+占比曲线），并保存为高分辨率图片。
```python
import matplotlib.pyplot as plt

def generate_and_save_basic_chart(counts, proportions, title='各类别数量分布', output_path='category_distribution.png'):
    # 设置中文字体避免乱码
    plt.rcParams['font.sans-serif'] = ['SimHei', 'WenQuanYi Zen Hei', 'Noto Sans CJK JP', 'DejaVu Sans']
    plt.rcParams['axes.unicode_minus'] = False
    
    fig, ax1 = plt.subplots(figsize=(10, 6))
    
    # 绘制柱状图
    bars = ax1.bar(counts.index, counts.values, color='skyblue', edgecolor='black')
    for bar in bars:
        height = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width()/2., height + 0.05, f'{height}', ha='center', va='bottom', fontsize=10)
    
    ax1.set_ylabel('数量', fontsize=12)
    ax1.set_title(title, fontsize=16, fontweight='bold', pad=20)
    
    # 创建第二个y轴显示占比曲线
    ax2 = ax1.twinx()
    ax2.plot(counts.index, proportions.values, color='red', marker='o', linestyle='-', linewidth=2)
    ax2.set_ylabel('占比 (%)', color='red', fontsize=12)
    ax2.tick_params(axis='y', labelcolor='red')
    
    plt.xticks(rotation=45)
    plt.tight_layout()
    
    # 保存高分辨率图表并使用 plt.close() 防止内存泄漏
    fig.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close(fig)
    
    return output_path
```

Step3 生成多图组合报告（饼图+柱状图，以及带分类映射的水平柱状图），用于多维度展示。
```python
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

def generate_comprehensive_report(counts, proportions, output_dir='./'):
    plt.rcParams['font.sans-serif'] = ['SimHei', 'WenQuanYi Zen Hei', 'Noto Sans CJK JP', 'DejaVu Sans']
    plt.rcParams['axes.unicode_minus'] = False
    
    # --- 1. 饼图与柱状图组合 ---
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))
    
    # 饼图
    colors = ['#ff9999', '#66b3ff', '#99ff99', '#ffcc99']
    explode = [0.05] * len(counts) if len(counts) > 0 else None
    wedges, texts, autotexts = ax1.pie(counts.values, labels=counts.index, autopct='%1.1f%%',
                                       colors=colors[:len(counts)], explode=explode, shadow=True, startangle=90)
    ax1.set_title('各类别比例分布', fontsize=14, fontweight='bold')
    for autotext in autotexts:
        autotext.set_color('white')
        autotext.set_fontweight('bold')
    
    # 柱状图
    bars = ax2.bar(range(len(counts)), counts.values, color=colors[:len(counts)], alpha=0.8, edgecolor='black')
    ax2.set_title('各类别数量', fontsize=14, fontweight='bold')
    ax2.set_xticks(range(len(counts)))
    ax2.set_xticklabels(counts.index, rotation=45, ha='right')
    
    for i, bar in enumerate(bars):
        height = bar.get_height()
        ax2.text(bar.get_x() + bar.get_width()/2., height + 0.5, f'{int(height)}\n({proportions.iloc[i]:.1f}%)',
                 ha='center', va='bottom', fontweight='bold')
    
    plt.tight_layout()
    pie_bar_path = f'{output_dir}category_pie_bar.png'
    plt.savefig(pie_bar_path, dpi=300, bbox_inches='tight')
    plt.close(fig)
    
    # --- 2. 水平柱状图 (带分类映射函数骨架与颜色区分) ---
    fig_h, ax_h = plt.subplots(figsize=(12, 8))
    positions = [f'类别{i+1}' for i in range(len(counts))]
    
    # 分类映射示例：根据类别名称包含的关键字动态分配颜色
    bar_colors = ['#66b3ff' if '关键字A' in str(p) else '#ff9999' for p in counts.index]
    bars_h = ax_h.barh(positions, counts.values, color=bar_colors, alpha=0.8, edgecolor='black')
    
    ax_h.set_title('各类别分布详情', fontsize=16, fontweight='bold', pad=20)
    
    for i, (bar, label) in enumerate(zip(bars_h, counts.index)):
        width = bar.get_width()
        # 动态标签示例：提取特定属性
        tag = '类型A' if '关键字A' in str(label) else '其他'
        ax_h.text(width + 0.3, bar.get_y() + bar.get_height()/2, f'{int(width)} ({tag})',
                  ha='left', va='center', fontsize=10)
    
    # 自定义图例
    legend_elements = [Patch(facecolor='#66b3ff', label='类型A组'), Patch(facecolor='#ff9999', label='其他组')]
    ax_h.legend(handles=legend_elements, loc='lower right')
    ax_h.grid(axis='x', alpha=0.3)
    
    plt.tight_layout()
    hbar_path = f'{output_dir}category_hbar.png'
    plt.savefig(hbar_path, dpi=300, bbox_inches='tight')
    plt.close(fig_h)
    
    return [pie_bar_path, hbar_path]
```
