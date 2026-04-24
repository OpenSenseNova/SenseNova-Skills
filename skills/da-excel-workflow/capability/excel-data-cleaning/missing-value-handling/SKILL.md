---
name: excel-smart-analysis-and-cleaning
description: "对多 Sheet Excel 进行智能清洗、跨表核对与可视化分析。。"
---

Step1 对数据进行深度清洗，包括合并单元格填充（ffill）、正则化文本处理、RGB 颜色分量转换以及异常值识别。
```python
import re

def clean_data(df, target_col):
    # 1. 处理合并单元格：向下填充
    df[target_col] = df[target_col].ffill()
    
    # 2. 正则清洗：去除数字前缀、特殊字符及首尾空格
    def regex_clean(text):
        if not isinstance(text, str): return text
        text = re.sub(r'^\d+[\.\s\-]+', '', text) # 去除如 "1. " 的前缀
        text = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9]', '', text) # 仅保留中英数
        return text.strip()
    
    df[target_col] = df[target_col].apply(regex_clean)
    
    # 3. 数值转换与 RGB 逻辑筛选（示例：筛选黑色/无色值）
    # 假设列名为 'Red', 'Green', 'Blue'
    rgb_cols = ['Red', 'Green', 'Blue']
    for col in rgb_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    
    if all(c in df.columns for c in rgb_cols):
        black_mask = (df['Red'] == 0) & (df['Green'] == 0) & (df['Blue'] == 0)
        df = df[black_mask]
        
    return df

# 遍历所有 sheet 进行清洗
cleaned_dfs = {name: clean_data(df, 'group_col') for name, df in df_dict.items()}
```

Step2 执行跨表核对与多维度统计分析（如交叉分析、占比统计），并识别关键指标（如问题发现率）。
```python
# 跨表核对示例：核对 Sheet1 与 Sheet2 的数值合计
if 'Sheet1' in cleaned_dfs and 'Sheet2' in cleaned_dfs:
    val1 = cleaned_dfs['Sheet1']['amount'].sum()
    val2 = cleaned_dfs['Sheet2']['amount'].sum()
    print(f"核对结果: Sheet1({val1}) vs Sheet2({val2}), 差异: {val1 - val2}")

# 交叉分析与占比统计
target_df = pd.concat(cleaned_dfs.values(), ignore_index=True)
pivot_table = pd.crosstab(target_df['category_col'], target_df['status_col'])
pivot_table['占比'] = pivot_table.sum(axis=1) / pivot_table.sum().sum()

# 统计特定条件下的最大值（如配合比中的最大用量）
# df.groupby('id_col')['value_col'].max()
```

Step3 生成可视化图表，配置中英文字体支持，并输出带样式的 Excel 结果及下载链接。
```python
import matplotlib.pyplot as plt
from openpyxl.styles import Font

# 1. 可视化配置
plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans'] # 支持中文
plt.rcParams['axes.unicode_minus'] = False

plt.figure(figsize=(10, 6), dpi=100)
target_df['category_col'].value_counts().plot(kind='bar', color='skyblue')
plt.title("数据分布统计")
plt.tight_layout()
plt.savefig("analysis_chart.png")

# 2. 样式化输出
output_path = "analysis_result.xlsx"
with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
    target_df.to_excel(writer, index=False, sheet_name='Result')
    
    # 针对特定单元格标红加粗（如数值异常项）
    workbook = writer.book
    worksheet = writer.sheets['Result']
    red_bold_font = Font(color="FF0000", bold=True)
    
    for row in range(2, worksheet.max_row + 1):
        # 假设第 3 列是需要检查的数值列
        if worksheet.cell(row=row, column=3).value > 100:
            worksheet.cell(row=row, column=1).font = red_bold_font

print(f"分析完成，结果已保存至: {output_path}")
# 生成下载链接（环境相关）
# print(f"Download link: [点击下载]({output_path})")
```
