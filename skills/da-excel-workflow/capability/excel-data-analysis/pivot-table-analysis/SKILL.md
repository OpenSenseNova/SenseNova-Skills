---
name: pivot-table-cross-analysis
description: "利用交叉表与热力图对分类数据进行多维度占比分析，适用于奖项分布、绩效评估或市场占有率等结构化数据的清洗与可视化。"
---

Step1 对原始数据进行清洗与重构，处理 Excel 合并单元格导致的缺失值，并筛选核心分析列。
```python
import pandas as pd

def preprocess_pivot_data(file_path, target_cols=['奖项', '项目名称', '成员', '单位']):
    """
    清理并重构数据列，处理合并单元格填充。
    """
    df = pd.read_excel(file_path)
    # 映射通用列名
    df.columns = target_cols
    
    # 关键技巧：处理合并单元格。ffill 前需确保数据按原始分类顺序排列
    # 假设第一列为分类标签（如奖项名称）
    df[target_cols[0]] = df[target_cols[0]].fillna(method='ffill')
    
    # 删除关键信息（如成员或单位）缺失的无效行
    df = df.dropna(subset=[target_cols[2], target_cols[3]])
    
    # 清洗字符串空格
    for col in df.select_dtypes(['object']).columns:
        df[col] = df[col].str.strip()
        
    return df
```

Step2 构建交叉分析表（Crosstab），计算不同维度下的频数分布及百分比占比。
```python
def create_cross_analysis(df, index_col='单位', columns_col='奖项'):
    """
    构建交叉表并计算各分类维度的获奖/分布比例。
    """
    # 生成频数统计交叉表
    cross_table = pd.crosstab(df[index_col], df[columns_col])
    
    # 计算占比：各列（奖项）下各行（单位）的分布比例
    # div(axis=1) 表示按列求和后进行除法
    award_proportions = cross_table.div(cross_table.sum(axis=0), axis=1) * 100
    
    # 技巧：生成带有总计行和占比的汇总表
    summary = cross_table.copy()
    summary['总计'] = summary.sum(axis=1)
    summary.loc['合计'] = summary.sum()
    
    return cross_table, award_proportions, summary
```

Step3 配置中文字体并生成热力图可视化，直观展示各维度间的分布差异。
```python
import matplotlib.pyplot as plt
import seaborn as sns

def generate_analysis_heatmap(proportions, output_path='analysis_heatmap.png'):
    """
    生成高分辨率热力图，支持中文字体显示。
    """
    # 关键技巧：中文字体配置，兼容不同系统环境
    plt.rcParams['font.sans-serif'] = ['SimHei', 'WenQuanYi Zen Hei', 'DejaVu Sans']
    plt.rcParams['axes.unicode_minus'] = False
    
    plt.figure(figsize=(14, 10))
    
    # 使用 Seaborn 绘制热力图，fmt='.2f' 保留两位小数
    sns.heatmap(
        proportions, 
        annot=True, 
        fmt='.2f', 
        cmap='YlGnBu', 
        linewidths=.5,
        cbar_kws={'label': '占比 (%)'}
    )
    
    plt.title('多维度分类占比分布热力图', fontsize=15, pad=20)
    plt.xlabel('分类维度 (Columns)', fontsize=12)
    plt.ylabel('分析对象 (Index)', fontsize=12)
    
    # 自动调整布局防止标签裁剪
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
```

Step4 执行综合分析算法，提取各维度的 Top-N 表现对象并计算整体排名。
```python
def extract_performance_insights(proportions, top_n=3):
    """
    分析各奖项/分类下的领先者，并计算整体加权表现。
    """
    insights = {}
    
    # 1. 提取每个分类维度的前 N 名
    top_performers = {}
    for category in proportions.columns:
        top_list = proportions[category].sort_values(ascending=False).head(top_n)
        top_performers[category] = top_list.to_dict()
    
    # 2. 计算整体表现排名（基于所有维度的平均占比）
    overall_performance = proportions.mean(axis=1).sort_values(ascending=False)
    
    insights['top_by_category'] = top_performers
    insights['overall_ranking'] = overall_performance.head(10).to_dict()
    
    return insights
```

Step5 导出分析结果为 Excel 多工作表格式，并提供下载链接。
```python
from IPython.display import FileLink

def export_results(cross_table, proportions, insights_df, file_name='analysis_report.xlsx'):
    """
    将分析结果保存至 Excel 并在环境中生成下载链接。
    """
    with pd.ExcelWriter(file_name) as writer:
        cross_table.to_excel(writer, sheet_name='频数统计')
        proportions.to_excel(writer, sheet_name='占比分析')
        insights_df.to_excel(writer, sheet_name='综合排名')
    
    return FileLink(file_name)
```
