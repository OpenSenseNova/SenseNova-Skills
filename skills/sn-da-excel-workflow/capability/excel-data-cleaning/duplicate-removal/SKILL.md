---
name: excel-multi-sheet-threshold-analysis
description: "统计多Sheet Excel总行数并根据规模选择处理策略，提取特定维度信息进行去重统计，并生成摘要与明细报表。"
---

# Excel_Multi_Sheet_Deduplication

> This sub-skill covers one capability of the Excel workflow. For reading/counting/Parquet optimization, see the parent workflow SKILL.md.

Step1 加载目标数据表，并进行初步的数据预览与结构检查。
```python
import pandas as pd

file_path = 'input_file.xlsx'
target_sheet = 'Sheet1' # 根据实际情况指定 sheet 名称

# 读取数据，header=None 用于处理无表头或非标准表头文件
df = pd.read_excel(file_path, sheet_name=target_sheet, header=None)
print(f"数据形状: {df.shape}")
print("前 5 行预览：")
print(df.head())
```

Step2 遍历数据行，基于关键词提取目标信息，并执行数据清洗（去除空格、空值过滤）。
```python
import pandas as pd

# 设定目标列索引及过滤关键词
target_col_idx = 1 
keywords = ["关键词A", "关键词B"] # 示例：如"综合楼"、"控制中心"
extracted_data = []

for idx, row in df.iterrows():
    cell_val = str(row[target_col_idx]) if pd.notna(row[target_col_idx]) else ""
    # 数据清洗：去除首尾空格并匹配关键词
    clean_val = cell_val.strip()
    if any(k in clean_val for k in keywords):
        if clean_val and clean_val.lower() not in ["nan", "null", ""]:
            extracted_data.append(clean_val)

print(f"提取到相关记录共 {len(extracted_data)} 条")
```

Step3 对提取的信息进行分类去重，统计各维度的唯一项数量。
```python
# 使用 set 进行高效去重
category_a_items = set()
category_b_items = set()

for item in extracted_data:
    if "关键词A" in item:
        category_a_items.add(item)
    elif "关键词B" in item:
        category_b_items.add(item)

# 转换为排序后的列表
list_a = sorted(list(category_a_items))
list_b = sorted(list(category_b_items))

print(f"类别A 唯一项数量: {len(list_a)}")
print(f"类别B 唯一项数量: {len(list_b)}")
```

Step4 将统计摘要与详细清单整理为 DataFrame，并导出为 Excel 文件提供下载。
```python
import pandas as pd

# 1. 生成统计摘要
summary_df = pd.DataFrame({
    '分类名称': ['类别A', '类别B'],
    '唯一项总数': [len(list_a), len(list_b)]
})

# 2. 生成详细清单
detail_list = []
for val in list_a:
    detail_list.append({'分类': '类别A', '详细名称': val})
for val in list_b:
    detail_list.append({'分类': '类别B', '详细名称': val})
detail_df = pd.DataFrame(detail_list)

# 导出结果
output_summary_path = 'summary_report.xlsx'
output_detail_path = 'detail_list.xlsx'

summary_df.to_excel(output_summary_path, index=False)
detail_df.to_excel(output_detail_path, index=False)

print(f"统计摘要已保存: {output_summary_path}")
print(f"详细清单已保存: {output_detail_path}")
```
