---
name: excel-large-file-processing-and-cleaning
description: "读取多 sheet Excel 文件，动态识别目标列进行统计，并使用正则清洗文本字段提取中文字符，最终输出标准化 Excel 文件。"
---

# Skill Steps

> This sub-skill covers one capability of the Excel workflow. For reading/counting/Parquet optimization, see the parent workflow SKILL.md.

Step1 文本字段清洗，使用正则表达式提取纯中文字符（过滤数字、特殊符号等）。
```python
import re

def extract_chinese(text):
    if pd.isna(text):
        return text
    # 仅保留 Unicode 中文字符范围
    chinese_chars = re.findall(r'[一-龥]', str(text))
    cleaned = ''.join(chinese_chars)
    return cleaned if cleaned else ''

clean_col = '目标清洗列' # 占位示例，如'收货人'
if clean_col in df.columns:
    df[clean_col] = df[clean_col].apply(extract_chinese)
```

Step2 动态模糊匹配列名，并统计该列中特定值的数量。
```python
# 动态查找包含特定关键字的列
keyword = 'type'
target_val = 'varchar'
target_col = next((col for col in df.columns if keyword in str(col).lower()), None)

total_target_count = 0
details = []

if target_col is not None:
    # 忽略大小写和首尾空格进行匹配
    mask = df[target_col].astype(str).str.lower().str.strip() == target_val
    count = mask.sum()
    total_target_count += count
    
    if count > 0:
        details.append({
            'sheet': target_sheet,
            'target_count': count,
            'total_rows': len(df)
        })

print(f"{'='*50}")
print(f"匹配列 '{target_col}' 中值为 '{target_val}' 的总数: {total_target_count}")
print(f"{'='*50}")
for detail in details:
    print(f"  {detail['sheet']}: {detail['target_count']} 个匹配项 (共 {detail['total_rows']} 行)")
```

Step3 将清洗和处理后的数据保存为 Excel，并输出文件大小与下载链接。
```python
output_path = "/mnt/data/cleaned_data_output.xlsx"
df.to_excel(output_path, index=False)

file_size = os.path.getsize(output_path)
print(f"清洗后的数据已保存至: {output_path}")
print(f"文件大小: {file_size} 字节")
# 生成标准下载链接格式
print(f"下载链接: sandbox:{output_path}")
```
