---
name: single-sheet-reading-and-analysis
description: "读取并解析单个Excel工作表数据，支持合并单元格处理、数据清洗、交叉分析及多维度可视化，适用于需要从单表中提取关键指标并进行趋势模拟与图表生成的场景。"
---

## Skill Steps

Step1 导入依赖并配置中英文字体，防止图表乱码
```python
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import re
import base64
from IPython.display import HTML

# 设置中英文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans', 'WenQuanYi Zen Hei']
plt.rcParams['axes.unicode_minus'] = False
```

Step2 加载数据与基础清洗，包含合并单元格处理与正则提取
```python
def load_and_clean_data(file_path, sheet_name=0):
    # 读取数据
    df = pd.read_excel(file_path, sheet_name=sheet_name)
    
    # 处理合并单元格：向前填充并还原
    # df['group_col'] = df['group_col'].ffill()
    
    # 标准化列名：去除首尾空格及换行符
    df.columns = [str(col).strip().replace('\n', '') for col in df.columns]
    
    # 数据清洗正则表达式示例：提取数值
    if 'target_col' in df.columns:
        df['target_col'] = df['target_col'].astype(str).apply(lambda x: re.sub(r'[^\d.]', '', x))
        df['target_col'] = pd.to_numeric(df['target_col'], errors='coerce')
    
    # 处理全空行缺失值
    df = df.dropna(how='all')
    return df
```

Step3 数据分类映射与多维度评分/分级算法
```python
def categorize_and_score(df, target_col):
    # 分类映射函数骨架
    def map_category(val):
        if pd.isna(val):
            return '未知'
        elif val > 100:  # 占位示例：高阈值
            return 'A类'
        elif val > 50:   # 占位示例：中阈值
            return 'B类'
        else:
            return 'C类'
    
    if target_col in df.columns:
        df['category'] = df[target_col].apply(map_category)
    
    # 多维度评分/分级算法结构
    # df['score'] = df['metric1'] * 0.4 + df['metric2'] * 0.6
    return df
```

Step4 交叉分析与统计汇总（频数、占比、总计行）
```python
def analyze_data(df, group_col):
    # value_counts + 占比 + 总计行
    counts = df[group_col].value_counts().reset_index()
    counts.columns = [group_col, '数量']
    counts['占比'] = (counts['数量'] / counts['数量'].sum()).map('{:.2%}'.format)
    
    # 添加总计行
    total_row = pd.DataFrame({
        group_col: ['总计'], 
        '数量': [counts['数量'].sum()], 
        '占比': ['100.00%']
    })
    counts = pd.concat([counts, total_row], ignore_index=True)
    
    # 交叉分析 crosstab/pivot
    if 'category' in df.columns:
        cross_tb = pd.crosstab(df[group_col], df['category'], margins=True, margins_name='总计')
    else:
        cross_tb = None
        
    return counts, cross_tb
```

Step5 图表美化与高分辨率输出
```python
def visualize_results(df, group_col, target_col, output_path):
    # 设置高分辨率 dpi=300
    fig, ax = plt.subplots(figsize=(10, 6), dpi=300)
    
    # 颜色方案与图表绘制
    valid_data = df.dropna(subset=[group_col, target_col])
    colors = sns.color_palette("husl", len(valid_data[group_col].unique()))
    sns.barplot(data=valid_data, x=group_col, y=target_col, palette=colors, ax=ax)
    
    # 标签位置与美化
    ax.set_title('多维度数据分析', fontsize=16, pad=15)
    ax.set_xlabel('分组维度', fontsize=12)
    ax.set_ylabel('目标指标', fontsize=12)
    plt.xticks(rotation=45, ha='right')
    
    # 添加数据标签
    for p in ax.patches:
        ax.annotate(f'{p.get_height():.1f}', 
                    (p.get_x() + p.get_width() / 2., p.get_height()), 
                    ha='center', va='bottom', fontsize=10)
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
```

Step6 大文件 Parquet 转换与下载链接生成
```python
def export_and_generate_link(df, output_path):
    # 大文件 Parquet 转换
    parquet_path = output_path.replace('.png', '.parquet').replace('.csv', '.parquet')
    df.to_parquet(parquet_path, index=False)
    
    # 下载链接生成
    csv_data = df.to_csv(index=False).encode('utf-8')
    b64 = base64.b64encode(csv_data).decode()
    href = f'<a href="data:file/csv;base64,{b64}" download="analysis_result.csv">点击下载分析结果 (CSV)</a>'
    display(HTML(href))
```
