---
name: multi-file-excel-parquet-analysis
description: "读取多 Sheet Excel 文件并统计规模，支持大文件向 Parquet 格式转换、分类数据统计及可视化报告生成。"
---


> **Note**: This sub-skill covers one step of the Excel analysis workflow. For the full pipeline (file reading, row counting, large-file optimization, export), see the parent workflow SKILL.md.


Step1 读取 Excel 文件，遍历所有 Sheet 统计行数，评估数据规模。
```python
import pandas as pd
import os

file_path = "input_data.xlsx"  # 替换为实际文件路径

if not os.path.exists(file_path):
    print(f"Error: 文件 {file_path} 不存在")
else:
    # 获取所有 sheet 名称
    xl = pd.ExcelFile(file_path)
    sheet_names = xl.sheet_names
    print("Sheet 列表:", sheet_names)
    
    total_rows = 0
    for sheet in sheet_names:
        # 仅读取第一列以快速统计行数，避免大文件内存溢出
        df_tmp = pd.read_excel(file_path, sheet_name=sheet, usecols=[0])
        row_count = len(df_tmp)
        total_rows += row_count
        print(f"Sheet: {sheet}, 行数: {row_count}")
    
    print(f"总行数汇总: {total_rows}")
```

Step2 读取转换后的数据，执行分类统计分析，计算频数与占比。
```python
import pandas as pd

# 读取 Parquet 文件
df_analyzed = pd.read_parquet(output_parquet)

# 定义目标统计列（如 '剪裁结果'、'状态' 等）
target_col = '剪裁结果' 

if target_col in df_analyzed.columns:
    # 统计各分类数量及占比
    counts = df_analyzed[target_col].value_counts()
    percent = df_analyzed[target_col].value_counts(normalize=True) * 100
    
    # 构建统计表格并添加总计行
    summary_df = pd.DataFrame({
        '分类': counts.index,
        '数量': counts.values,
        '占比(%)': percent.values.round(2)
    })
    
    # 添加总计行
    total_row = pd.DataFrame([['总计', summary_df['数量'].sum(), 100.0]], columns=summary_df.columns)
    summary_df = pd.concat([summary_df, total_row], ignore_index=True)
    
    print("统计摘要:\n", summary_df)
else:
    print(f"未找到目标列: {target_col}")
```

Step3 生成可视化饼图并保存分析报告，提供结果下载链接。
```python
import matplotlib.pyplot as plt

# 配置中文字体（实战技巧：防止图表乱码）
plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

if target_col in df_analyzed.columns:
    # 绘制饼图
    plt.figure(figsize=(10, 7), dpi=100)
    plot_data = df_analyzed[target_col].value_counts()
    plt.pie(plot_data, labels=plot_data.index, autopct='%1.1f%%', startangle=90, colors=plt.cm.Paired.colors)
    plt.title(f'{target_col} 分布占比')
    
    # 保存图表
    chart_output = "analysis_pie_chart.png"
    plt.savefig(chart_output, bbox_inches='tight')
    
    # 保存统计结果为 Excel
    report_output = "analysis_report.xlsx"
    summary_df.to_excel(report_output, index=False)
    
    print(f"分析图表已保存: {chart_output}")
    print(f"统计表格已保存: {report_output}")
    
    # 生成下载链接（用于报告展示）
    print(f"下载链接: {os.path.abspath(report_output)}")
```
