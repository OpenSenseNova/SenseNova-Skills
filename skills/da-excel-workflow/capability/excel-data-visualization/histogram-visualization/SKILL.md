---
name: statistical-distribution-and-outlier-analysis
description: "执行数值型数据的分布分析与异常值检测，支持通过正则表达式从文本中提取误差项并生成高分辨率的箱线图与直方图报告。"
---

Step 1 加载数据并进行预处理，配置中文字体与环境参数
```python
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns
import re

# 设置中文字体，兼容不同环境
plt.rcParams['font.sans-serif'] = ['SimHei', 'WenQuanYi Zen Hei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

# 加载数据并处理合并单元格
file_path = 'input_data.xlsx'
df = pd.read_excel(file_path)
df.ffill(inplace=True) # 处理可能的合并单元格空值

# 统一重命名列名以便于程序化处理
original_columns = df.columns.tolist()
df.columns = [f'col_{i+1}' for i in range(df.shape[1])]

print(f"数据形状: {df.shape}")
print(f"原始列映射: {dict(zip(df.columns, original_columns))}")
```

Step 2 生成多子图箱线图，直观展示各维度数据的分布特征与统计量
```python
# 计算子图布局
num_cols = len(df.columns)
rows = (num_cols + 2) // 3
fig, axes = plt.subplots(rows, 3, figsize=(18, 5 * rows))
fig.suptitle('数据分布维度分析', fontsize=16, fontweight='bold')
axes_flat = axes.flatten()

for i, column in enumerate(df.columns):
    data_series = df[column].dropna()
    if pd.api.types.is_numeric_dtype(data_series):
        axes_flat[i].boxplot(data_series, patch_artist=True,
                            boxprops=dict(facecolor='lightblue', alpha=0.7),
                            medianprops=dict(color='red', linewidth=2))
        
        stats = data_series.describe()
        axes_flat[i].set_title(f'{column} (n={len(data_series)})', fontsize=12)
        axes_flat[i].text(0.05, 0.95, f'均值: {stats["mean"]:.2f}\n中位数: {stats["50%"]:.2f}',
                         transform=axes_flat[i].transAxes, verticalalignment='top',
                         bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
    axes_flat[i].grid(True, alpha=0.3)

plt.tight_layout(rect=[0, 0.03, 1, 0.95])
output_path = 'individual_boxplots.png'
plt.savefig(output_path, dpi=300, bbox_inches='tight')
plt.show()
```

Step 3 执行异常值检测算法，计算四分位距（IQR）并生成统计报告
```python
analysis_results = []

for col in df.columns:
    data = df[col].dropna()
    if not pd.api.types.is_numeric_dtype(data):
        continue
        
    Q1 = data.quantile(0.25)
    Q3 = data.quantile(0.75)
    IQR = Q3 - Q1
    lower_bound = Q1 - 1.5 * IQR
    upper_bound = Q3 + 1.5 * IQR
    
    outliers = data[(data < lower_bound) | (data > upper_bound)]
    
    analysis_results.append({
        '维度': col,
        '样本量': len(data),
        '异常值数量': len(outliers),
        '偏度': round(data.skew(), 3),
        '峰度': round(data.kurtosis(), 3),
        '范围': f"{data.min():.2f} ~ {data.max():.2f}"
    })

report_df = pd.DataFrame(analysis_results)
print("=== 数据质量与分布报告 ===")
print(report_df.to_string(index=False))
```

Step 4 使用正则表达式从文本列中提取误差值（±模式）并进行量化分析
```python
# 假设 target_col 包含类似 "10.5 ± 0.2" 的文本
target_col = df.columns[0] 
text_data = df[target_col].astype(str).str.cat(sep=' ')

# 正则表达式提取 ± 后面的数值
error_pattern = r'±(\d+\.?\d*)'
extracted_errors = [float(val) for val in re.findall(error_pattern, text_data)]

if extracted_errors:
    print(f"提取到误差样本量: {len(extracted_errors)}")
    print(f"误差均值: {np.mean(extracted_errors):.4f}")
else:
    print("未在指定列中检测到符合 ± 模式的误差数据")
```

Step 5 绘制误差分布直方图，并标注核心统计参考线
```python
if extracted_errors:
    plt.figure(figsize=(10, 6))
    # 自动计算 bins 数量
    n, bins, patches = plt.hist(extracted_errors, bins='auto', color='skyblue', 
                                edgecolor='black', alpha=0.7)
    
    # 在柱体上方标注频次
    for i in range(len(n)):
        if n[i] > 0:
            plt.text(bins[i] + (bins[i+1]-bins[i])/2, n[i] + 0.1, 
                    str(int(n[i])), ha='center', va='bottom', fontweight='bold')

    # 添加均值参考线
    mean_val = np.mean(extracted_errors)
    plt.axvline(mean_val, color='red', linestyle='--', linewidth=2, 
                label=f'误差均值: {mean_val:.3f}')
    
    plt.title('误差项分布特征直方图', fontsize=14)
    plt.xlabel('误差量级', fontsize=12)
    plt.ylabel('出现频次', fontsize=12)
    plt.legend()
    plt.grid(axis='y', alpha=0.3)
    
    plt.tight_layout()
    plt.savefig('error_distribution_histogram.png', dpi=300)
    plt.show()
```

Step 6 导出分析摘要并生成下载链接
```python
summary_file = 'analysis_summary.csv'
report_df.to_csv(summary_file, index=False, encoding='utf_8_sig')

from IPython.display import FileLink
print("分析完成，点击下方链接下载报告：")
display(FileLink(summary_file))
display(FileLink('individual_boxplots.png'))
```
