---
name: condition-filtering-and-large-file-optimization
description: "根据数据规模动态选择处理策略。"
---

# condition_filtering

> **Note**: This sub-skill covers one step of the Excel analysis workflow. For the full pipeline (file reading, row counting, large-file optimization, export), see the parent workflow SKILL.md.

Step1 执行多维度数据清洗与条件筛选，包含列名自动识别、RGB 颜色过滤、前缀匹配及正则提取。
```python
# 1. 自动识别同义列名并筛选非空值
target_cols = ['域名', '缩写', 'code', 'domain']
for col in target_cols:
    if col in df.columns:
        df = df[df[col].notna()]
        break

# 2. 基于数值通道的精确筛选（如 RGB 颜色过滤）
# 技巧：多条件组合筛选时使用 & 符号
if all(c in df.columns for c in ['Red', 'Green', 'Blue']):
    df = df[(df['Red'] == 0) & (df['Green'] == 0) & (df['Blue'] == 0)]

# 3. 基于字符串前缀筛选并进行数值转换计算
if '编号' in df.columns:
    # 筛选特定前缀的项目
    df = df[df['编号'].astype(str).str.startswith('TXL3')]
    # 技巧：使用 errors='coerce' 处理无法转换的脏数据
    df['val_a'] = pd.to_numeric(df['技工'], errors='coerce')
    df['val_b'] = pd.to_numeric(df['普工'], errors='coerce')
    df['total_val'] = df['val_a'] + df['val_b']
    avg_val = df['total_val'].mean()

# 4. 基于特定分类值的筛选与统计
if '钢筋级别' in df.columns:
    sub_df = df[df['钢筋级别'] == 'Ⅱ'].copy()
    sub_df['target_val'] = pd.to_numeric(sub_df['屈服荷载'], errors='coerce')
    avg_target = sub_df['target_val'].mean()

# 5. 正则表达式匹配提取特定字段
if '命令' in df.columns:
    pattern = r'--pct-'
    matched_df = df[df['命令'].astype(str).str.contains(pattern, na=False)]
    # 提取关键列保留追溯性
    extracted_data = matched_df[['NO', '命令', '说明']].copy()
```

Step2 将处理结果保存至 Excel，并对输出文件进行样式美化（如全行标红），最后生成下载链接。
```python
from openpyxl.styles import PatternFill

output_path = "filtered_result.xlsx"

with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
    if 'total_val' in df.columns:
        df.to_excel(writer, sheet_name='统计结果', index=False)
    if 'extracted_data' in locals():
        extracted_data.to_excel(writer, sheet_name='正则提取', index=False)

# 技巧：使用 openpyxl 进行后期样式加工，突出显示关键结果
wb = openpyxl.load_workbook(output_path)
red_fill = PatternFill(start_color='FFFF0000', end_color='FFFF0000', fill_type='solid')

for sheet_name in wb.sheetnames:
    ws = wb[sheet_name]
    for row in ws.iter_rows(min_row=2):  # 跳过表头
        for cell in row:
            cell.fill = red_fill

wb.save(output_path)

# 输出标准下载链接格式
print(f"[下载结果文件](sandbox:{output_path})")
```
