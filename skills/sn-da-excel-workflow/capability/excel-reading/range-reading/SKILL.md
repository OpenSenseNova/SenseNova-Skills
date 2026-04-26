---
name: range-reading-and-large-file-analysis
description: "读取多 Sheet Excel 文件，根据数据量动态选择处理策略，支持特定区域数据提取、大文件 Parquet 转换、统计分析及可视化图表生成。"
---

> **Note**: This sub-skill covers one step of the Excel analysis workflow. For the full pipeline (file reading, row counting, large-file optimization, export), see the parent workflow SKILL.md.

Step1 针对特定 Sheet 进行数据清洗与空值统计。支持处理带空格的列名，并计算关键指标的缺失率。
```python
target_sheet = "Sheet2"
target_col = "是否通过"  # 示例列名，实际根据需求替换

# 读取指定 Sheet
df_target = pd.read_excel(file_path, sheet_name=target_sheet)

# 清洗列名：去除首尾空格
df_target.columns = [str(col).strip() for col in df_target.columns]

if target_col in df_target.columns:
    null_count = df_target[target_col].isna().sum()
    print(f"'{target_col}' 列为空的数量: {null_count}")
    
    # 统计占比
    stats = df_target[target_col].value_counts(dropna=False)
    print("分类统计结果：\n", stats)
else:
    print(f"未找到目标列: {target_col}")
```

Step2 大文件优化处理：将 Excel 转换为 Parquet 格式以提升后续读取速度，并提取特定行/列范围的数据进行结构化转换。
```python
import numpy as np

output_dir = "output_results"
os.makedirs(output_dir, exist_ok=True)

if is_large_file:
    # 转换为 Parquet 格式
    parquet_path = os.path.join(output_dir, "temp_data.parquet")
    # 注意：大文件读取建议分块或指定关键列
    df_full = pd.read_excel(file_path)
    df_full.to_parquet(parquet_path, engine='pyarrow', index=False)
    df = pd.read_parquet(parquet_path)
else:
    df = pd.read_excel(file_path)

# 提取特定区域数据（例如：行 40-50，特定两列）
# 模拟从非规范表格中提取数值对
data_rows = []
x_col_idx, y_col_idx = 0, 1 # 假设目标数据在第0列和第1列

for i in range(40, min(50, len(df))):
    row = df.iloc[i]
    try:
        # 清洗字符串并转换为浮点数
        val_x = float(str(row.iloc[x_col_idx]).replace(' ', ''))
        val_y = float(str(row.iloc[y_col_idx]).replace(' ', ''))
        if pd.notna(val_x) and pd.notna(val_y):
            data_rows.append((val_x, val_y))
    except (ValueError, TypeError):
        continue

analysis_df = pd.DataFrame(data_rows, columns=['target_x', 'target_y'])
```

Step3 执行高级统计分析与可视化。包含线性回归拟合、中英文字体配置、高分辨率图表保存及下载链接生成。
```python
import matplotlib.pyplot as plt

# 配置中文字体（兼容不同环境）
plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

if not analysis_df.empty:
    x = analysis_df['target_x'].values
    y = analysis_df['target_y'].values
    
    # 1. 线性拟合
    coeffs = np.polyfit(x, y, 1)
    poly_func = np.poly1d(coeffs)
    trend_line = poly_func(x)
    
    # 2. 绘图美化
    plt.figure(figsize=(10, 6), dpi=300)
    plt.scatter(x, y, color='#1f77b4', s=60, label='原始数据点', alpha=0.7)
    plt.plot(x, trend_line, color='#d62728', lw=2, label=f'趋势线: y={coeffs[0]:.4f}x+{coeffs[1]:.4f}')
    
    plt.title("数据分布与线性回归分析", fontsize=14, pad=20)
    plt.xlabel("维度 X", fontsize=12)
    plt.ylabel("维度 Y", fontsize=12)
    plt.grid(True, linestyle='--', alpha=0.5)
    plt.legend()
    
    chart_path = os.path.join(output_dir, "analysis_chart.png")
    plt.savefig(chart_path, bbox_inches='tight')
    plt.close()
    
    # 3. 结果导出
    result_path = os.path.join(output_dir, "analysis_results.csv")
    analysis_df['trend_prediction'] = trend_line
    analysis_df.to_csv(result_path, index=False, encoding='utf-8-sig')
    
    # 4. 输出下载链接
    print(f"分析图表已保存: sandbox:{chart_path}")
    print(f"结构化数据已保存: sandbox:{result_path}")
    print(f"拟合方程: y = {coeffs[0]:.4f}x + {coeffs[1]:.4f}")
else:
    print("未提取到有效数值数据，跳过可视化步骤")
```
