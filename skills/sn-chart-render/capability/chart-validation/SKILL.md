---
name: chart-validation
description: 用 Playwright 打开含 Chart.js 的 HTML 文件，验证 canvas 渲染、JS 错误、中文字体。不负责生成图或嵌入。
tier: 2
category: ability
parent: sn-chart-render
---

# chart-validation — 图表渲染验证能力

## 行为边界

做：

- 用 Playwright 无头浏览器打开指定 HTML 文件
- 对每个 `canvas` 元素：检查是否被 Chart.js 实例化
- 遍历 `document.querySelectorAll('canvas')` 并检查：
  - canvas 存在
  - `canvas.height > 0`（实际渲染像素）
  - `Chart.getChart(canvas.id)` 返回非 null（已初始化）
- 收集所有 `console.error` 和 `window.onerror` 消息
- 检查中文字体渲染：对含中文的 canvas 采样像素，确认无全框/缺字
- 输出 JSON 验证报告

不做：

- 不截图对比（不是视觉回归）
- 不修复渲染失败
- 不修改 HTML 内容
- 不生成图表或注入

## 输入

```
--input     /path/to/report.html       # 要验证的 HTML 文件（必须）
--output    /path/to/validation.json   # 验证结果输出（默认 stdout）
--timeout   30000                       # Playwright 等待 ms
--viewport  "1280x800"                  # 浏览器视口尺寸
```

## 输出

```json
{
  "status": "passed | partial | failed",
  "file": "/path/to/report.html",
  "viewport": "1280x800",
  "canvas_count": 4,
  "charts": [
    {
      "id": "c1",
      "type": "bar",
      "initialized": true,
      "height_px": 200,
      "has_data": true,
      "errors": []
    },
    {
      "id": "c2",
      "type": "line",
      "initialized": true,
      "height_px": 200,
      "has_data": true,
      "errors": []
    }
  ],
  "console_errors": [],
  "font_issues": [],
  "elapsed_ms": 1245
}
```

status 含义：

| status | 条件 |
|--------|------|
| passed | 所有 canvas 已初始化，无 console 错误，无字体问题 |
| partial | 部分 canvas 未初始化或有警告级错误（不影响可读性） |
| failed | 所有 canvas 都失败或严重 JS 错误导致白页 |

## 环境检查

首次执行时自动运行：

```python
import subprocess
try:
    subprocess.run(["playwright", "--version"], capture_output=True)
except FileNotFoundError:
    print("❌ Playwright not installed. Run: pip install playwright && playwright install chromium")
```

## 中文字体检测

通过 `document.fonts.ready` + canvas 测量含中文文本的 bounding box：

```javascript
const canvas = document.getElementById('c1');
const ctx = canvas.getContext('2d');
ctx.font = '14px sans-serif';
const m = ctx.measureText('中文测试');
// 如果 width ≈ 每个字的宽度（~14px per char），说明字体正常
// 如果 width 明显偏小（缺字用方块替代），标记 font_issue
```

## 常见失败

- Chart.js CDN 加载超时（网络问题）→ 提示使用离线包
- canvas 在 hidden 元素中 → `canvas.offsetParent === null` 时 chart 初始化可能失败
- 多个 `Chart.constructor` 冲突 → 检查 `Chart.register()` 是否被重复调用
- 字体方块（□□□）→ 确认 target HTML 加载了中文字体
- Playwright 在 macOS 上首次运行需要权限 → `playwright install chromium` 已装的情况下检查路径
