---
name: invalid-data-cleaning
description: "用于大规模Excel数据的预处理，通过统计总行数判断是否转换为Parquet格式以提升读写效率，并使用正则表达式清洗指定文本列（如仅保留中文字符），最后导出清洗后的文件并提供下载链接。"
---

# Invalid_Data_Cleaning

> This sub-skill covers one capability of the Excel workflow. For reading/counting/Parquet optimization, see the parent workflow SKILL.md.

## Skill Steps

Step1 根据总行数判断是否数据量过大，若满足条件，则将 Excel 文件转换为 Parquet 格式提升读写效率，再读取数据进行后续分析。
```python
import pandas as pd

file_path = "input_data.xlsx"
parquet_path = "temp_data.parquet"

# 读取 Excel 文件并转换为 Parquet 格式
xls = pd.ExcelFile(file_path)
dfs = []
for sheet in xls.sheet_names:
    df_sheet = pd.read_excel(xls, sheet_name=sheet)
    dfs.append(df_sheet)

# 合并所有 sheet 数据并写入 Parquet 文件
if dfs:
    df_all = pd.concat(dfs, ignore_index=True)
    df_all.to_parquet(parquet_path, engine='pyarrow', index=False)

# 读取 Parquet 文件用于后续处理
df = pd.read_parquet(parquet_path)
```

Step2 对目标文本字段中的特殊字符（如 #、-、数字）进行清洗，使用正则表达式仅保留中文字符。
```python
import pandas as pd
import re

target_col = 'target_column' # 替换为实际需要清洗的列名

# 定义清洗函数
def clean_chinese_text(text):
    if pd.isna(text):
        return text
    s = str(text)
    # 提取所有中文字符（Unicode 范围：[一-鿿]）
    chinese_chars = re.findall(r'[一-鿿]', s)
    cleaned = ''.join(chinese_chars)
    return cleaned if cleaned else ''

# 应用清洗函数
if target_col in df.columns:
    df[target_col] = df[target_col].apply(clean_chinese_text)
```

Step3 将清洗后的数据保存为表格文件（.xlsx），并在报告中提供本地下载链接。
```python
import pandas as pd

# 保存清洗后的数据为 .xlsx 文件
output_path = "cleaned_data.xlsx"
df.to_excel(output_path, index=False)

print("清洗后的数据已保存至:", output_path)
# 生成本地文件下载链接
print("下载链接:", f"file://{output_path}")
```
