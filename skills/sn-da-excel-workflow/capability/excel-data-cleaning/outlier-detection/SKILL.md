---
name: outlier-detection-and-quality-assessment
description: "执行全面的异常值检测与数据质量评估，利用 IQR 方法识别异常值并结合偏度、峰度分析数据分布特征，适用于非正态分布数据的预处理阶段。"
---

### Step 1 加载数据并配置环境
```python
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns

# 设置中英文字体以支持可视化显示 (SimHei 或 WenQuanYi)
plt.rcParams['font.sans-serif'] = ['SimHei', 'WenQuanYi Zen Hei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

# 加载数据
file_path = 'data.xlsx'  # 替换为实际文件路径
df = pd.read_excel(file_path)

# 基础信息检查
print(f"数据形状: {df.shape}")
print(f"数据类型:\n{df.dtypes}")
print(df.head())
```

### Step 2 基于 IQR 方法识别异常值
```python
# 自动筛选数值型列进行分析
target_cols = df.select_dtypes(include=[np.number]).columns.tolist()
outlier_summary = []

for col in target_cols:
    data = df[col].dropna()
    if data.empty:
        continue
        
    # 四分位距计算 (IQR)
    Q1 = data.quantile(0.25)
    Q3 = data.quantile(0.75)
    IQR = Q3 - Q1
    lower_bound = Q1 - 1.5 * IQR
    upper_bound = Q3 + 1.5 * IQR
    
    # 识别异常值
    outliers = data[(data < lower_bound) | (data > upper_bound)]
    
    outlier_summary.append({
        'target_col': col,
        'outlier_count': len(outliers),
        'outlier_ratio': f"{(len(outliers)/len(data)*100):.2f}%",
        'lower_limit': lower_bound,
        'upper_limit': upper_bound,
        'sample_values': outliers.values.tolist()[:5]  # 保留前5个示例
    })

outlier_df = pd.DataFrame(outlier_summary)
print("\n=== 异常值统计汇总 ===")
print(outlier_df.to_string(index=False))
```

### Step 3 生成多维度可视化箱线图
```python
# 配置多子图布局
num_cols = len(target_cols)
cols_per_row = 3
rows = (num_cols + cols_per_row - 1) // cols_per_row

fig, axes = plt.subplots(rows, cols_per_row, figsize=(18, 5 * rows))
fig.suptitle('数据分布与异常值检测箱线图', fontsize=16, fontweight='bold')
axes_flat = axes.flatten()

# 遍历绘制每个维度的分布
for i, col in enumerate(target_cols):
    ax = axes_flat[i]
    # 绘制箱线图并美化
    sns.boxplot(y=df[col].dropna(), ax=ax, color='skyblue', width=0.4,
                flierprops=dict(marker='o', markerfacecolor='red', markersize=5, alpha=0.5))
    
    ax.set_title(f'列: {col}', fontsize=12)
    ax.grid(True, linestyle='--', alpha=0.6)
    
    # 嵌入实时统计标注
    stats = df[col].describe()
    stats_text = f'均值: {stats["mean"]:.2f}\n中位数: {stats["50%"]:.2f}\n标准差: {stats["std"]:.2f}'
    ax.text(0.05, 0.95, stats_text, transform=ax.transAxes, fontsize=9,
            verticalalignment='top', bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))

# 隐藏多余的子图
for j in range(i + 1, len(axes_flat)):
    axes_flat[j].axis('off')

plt.tight_layout(rect=[0, 0.03, 1, 0.95])
output_path = 'outlier_analysis_report.png'
plt.savefig(output_path, dpi=300, bbox_inches='tight')
plt.show()
```

### Step 4 偏度与峰度分析及质量评估
```python
# 分析分布形态以辅助清洗决策
print("=== 数据分布形态分析报告 ===")
quality_analysis = []

for col in target_cols:
    data = df[col].dropna()
    skewness = data.skew()
    kurtosis = data.kurtosis()
    
    # 判定分布特征
    skew_type = "右偏 (Positive)" if skewness > 0.5 else "左偏 (Negative)" if skewness < -0.5 else "对称"
    kurt_type = "尖峰 (Leptokurtic)" if kurtosis > 1 else "平峰 (Platykurtic)" if kurtosis < -1 else "正态趋向"
    
    quality_analysis.append({
        '字段': col,
        '偏度': round(skewness, 3),
        '峰度': round(kurtosis, 3),
        '分布形态': skew_type,
        '峰度特征': kurt_type
    })

analysis_df = pd.DataFrame(quality_analysis)
print(analysis_df.to_string(index=False))

# 导出分析结果
# analysis_df.to_csv('data_quality_report.csv', index=False)
```

### Step 5 异常值处理建议（骨架）
```python
def handle_outliers(df, col, method='cap'):
    """
    异常值处理骨架函数
    method: 'cap' (盖帽法), 'drop' (删除), 'none' (保留)
    """
    data = df[col].copy()
    Q1 = data.quantile(0.25)
    Q3 = data.quantile(0.75)
    IQR = Q3 - Q1
    lower = Q1 - 1.5 * IQR
    upper = Q3 + 1.5 * IQR
    
    if method == 'cap':
        df[col] = df[col].clip(lower=lower, upper=upper)
    elif method == 'drop':
        df = df[(df[col] >= lower) & (df[col] <= upper)]
    
    return df

# 示例：对特定列应用盖帽法处理
# df = handle_outliers(df, 'target_col', method='cap')
```
