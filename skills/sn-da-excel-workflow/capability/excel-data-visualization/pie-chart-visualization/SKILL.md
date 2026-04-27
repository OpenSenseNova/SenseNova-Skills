---
name: pie-chart-data-analysis
description: "对多Sheet Excel或CSV数据进行分类汇总统计，自动识别关键字段并生成包含占比、数值及美化饼图的可下载分析报告。"
---

Step1 读取文件并统计所有 Sheet 的行数，确认数据规模以决定处理策略。
```python
import pandas as pd

file_path = input_file
total_rows = 0
sheet_names = []

try:
    if file_path.endswith('.xlsx'):
        excel_file = pd.ExcelFile(file_path)
        sheet_names = excel_file.sheet_names
        # 统计所有工作表总行数
        for sheet in sheet_names:
            df_tmp = pd.read_excel(file_path, sheet_name=sheet)
            total_rows += len(df_tmp)
    elif file_path.endswith('.csv'):
        df = pd.read_csv(file_path)
        total_rows = len(df)
    else:
        raise ValueError("不支持的文件格式，仅支持 .xlsx 或 .csv")
except Exception as e:
    raise RuntimeError(f"文件读取失败: {e}")

is_large_file = total_rows >= 10000
```

Step2 自动识别分类列与数值列，执行数据清洗与格式转换。
```python
import re

# 加载首个有效数据集
if file_path.endswith('.xlsx'):
    df = pd.read_excel(file_path, sheet_name=sheet_names[0])
else:
    df = pd.read_csv(file_path)

# 1. 识别数值目标列（如：金额、支出、得分、数量）
target_keywords = ['金额', '支出', '造价', '经费', '数量', '得分']
target_cols = [col for col in df.columns if any(k in col for k in target_keywords)]
target_col = target_cols[0] if target_cols else df.select_dtypes(include=['number']).columns[0]

# 2. 识别分类列（支持正则匹配中文序号或特定分类标识）
category_pattern = re.compile(r'[一二三四五六七八九十百]+|地区|类别|类型|状态')
category_cols = [col for col in df.columns if category_pattern.search(col)]
category_col = category_cols[0] if category_cols else df.select_dtypes(include=['object']).columns[0]

# 3. 数据清洗：处理合并单元格填充、缺失值及类型转换
df[category_col] = df[category_col].ffill() # 处理 Excel 合并单元格
df[target_col] = pd.to_numeric(df[target_col], errors='coerce')
clean_df = df[[category_col, target_col]].dropna()
clean_df.columns = ['category', 'value']
```

Step3 执行多维度聚合分析，计算占比及汇总统计。
```python
# 分类汇总
summary_df = clean_df.groupby('category', as_index=False)['value'].sum()
total_val = summary_df['value'].sum()

# 计算占比并格式化
summary_df['percentage'] = (summary_df['value'] / total_val * 100).round(2)
summary_df = summary_df.sort_values(by='value', ascending=False)

# 构造总计行（可选）
total_row = pd.DataFrame([['总计', total_val, 100.0]], columns=summary_df.columns)
display_df = pd.concat([summary_df, total_row], ignore_index=True)
```

Step4 生成美化饼图并导出包含图表的 Excel 报告。
```python
import matplotlib.pyplot as plt
from io import BytesIO
import base64
from openpyxl.drawing.image import Image

# 配置中英文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

fig, ax = plt.subplots(figsize=(10, 7), dpi=120)
colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7', '#DDA0DD']

# 突出显示最大占比项
explode = [0.05 if i == 0 else 0 for i in range(len(summary_df))]

wedges, texts, autotexts = ax.pie(
    summary_df['value'],
    labels=summary_df['category'],
    autopct='%1.1f%%',
    startangle=140,
    colors=colors,
    explode=explode,
    shadow=True,
    pctdistance=0.85
)

# 添加中心白圈（环形图效果）
centre_circle = plt.Circle((0,0), 0.70, fc='white')
fig.gca().add_artist(centre_circle)

plt.title(f'{target_col} 分布分析', fontsize=15, pad=20)
ax.legend(wedges, summary_df['category'], title="分类明细", loc="center left", bbox_to_anchor=(1, 0, 0.5, 1))

# 保存图表到内存
img_buffer = BytesIO()
plt.savefig(img_buffer, format='png', bbox_inches='tight')
plt.close()

# 写入 Excel 并嵌入图表
output_path = 'analysis_report.xlsx'
with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
    display_df.to_excel(writer, sheet_name='统计汇总', index=False)
    ws = writer.book['统计汇总']
    img_buffer.seek(0)
    img = Image(img_buffer)
    ws.add_image(img, 'E2')

# 生成 Base64 下载链接
with open(output_path, "rb") as f:
    b64 = base64.b64encode(f.read()).decode()
download_url = f"data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{b64}"

print(f"分析完成。总行数: {total_rows}，下载链接已生成。")
```
