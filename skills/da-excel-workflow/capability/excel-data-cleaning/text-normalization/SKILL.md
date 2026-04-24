---
name: text-normalization-and-large-file-processing
description: "对Excel文件进行文本标准化清洗（如去除异常前缀、提取纯中文字符等），并，最终输出清洗后的Excel文件并提供下载链接。"
---

## Skill Steps

> This sub-skill covers one capability of the Excel workflow. For reading/counting/Parquet optimization, see the parent workflow SKILL.md.

Step1 识别并清洗包含前缀符号的异常数值字段，统一转换为整数类型；同时使用正则表达式清洗文本字段，仅保留 Unicode 范围内的中文字符。
```python
import re
import numpy as np

target_numeric_col = '需要转数字的文本列' # 示例：'获赞'
target_text_col = '需要提取中文的列' # 示例：'收货人'

# 1. 清洗包含前缀符号的数值字段
prefix_patterns = ['.', 'I ', '■ ', '一 ', '_', '. ']
def clean_numeric_with_prefix(value):
    val_str = str(value).strip()
    if val_str in ['None', 'nan', '', 'nan']:
        return np.nan
    for prefix in prefix_patterns:
        if val_str.startswith(prefix):
            val_str = val_str[len(prefix):].strip()
            break
    if val_str == '':
        return np.nan
    try:
        return int(val_str)
    except ValueError:
        return np.nan

# 2. 清洗文本字段，仅保留 Unicode 范围内的中文字符（\u4e00-\u9fff）
def clean_chinese_name(name):
    if pd.isna(name):
        return name
    s = str(name)
    chinese_chars = re.findall(r'[\u4e00-\u9fff]', s)
    cleaned = ''.join(chinese_chars)
    return cleaned if cleaned else ''

if target_numeric_col in df.columns:
    df[f'{target_numeric_col}_清洗后'] = df[target_numeric_col].apply(clean_numeric_with_prefix)
    
if target_text_col in df.columns:
    df[f'{target_text_col}_清洗后'] = df[target_text_col].apply(clean_chinese_name)
```

Step2 将清洗后的结果保存为 Excel 文件，在报告中提供下载链接，并执行内存清理以应对大文件处理时的内存压力。
```python
output_path = '/mnt/data/标准化清洗结果.xlsx'

# 保存清洗结果
df.to_excel(output_path, index=False, engine='openpyxl')
print(f'清洗结果已保存到: {output_path}')

# 生成可下载链接
print(f'[下载清洗结果表](sandbox:{output_path})')

# 内存清理
if 'df' in locals():
    del df
    gc.collect()
```
