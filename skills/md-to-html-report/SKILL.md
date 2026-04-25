---
name: md-to-html-report
description: 将 Markdown 文档转换为美观、结构清晰、可直接打开的单文件 HTML 报告，并使用深蓝标题区、浅灰页面、青色/琥珀强调色、深色表头、左侧粘性目录的统一视觉模板，包含语义化结构、响应式表格/图片、打印样式和本地图片引用校验。适用于把 .md 文件转成 HTML、统一 Markdown 报告版式、生成可分享网页报告，或检查 HTML 中图片是否能正确渲染。
---

# Markdown 转 HTML 报告

## 工作流程

1. 定位输入 Markdown 文件，并确定输出 HTML 路径。
   - 如果用户只给输入路径，就在同目录生成同名 `.html` 文件。
   - 以 Markdown 文件所在目录作为相对图片路径的基准。
2. 转换前先检查 Markdown。
   - 识别标题层级、表格、引用块、代码块和图片引用。
   - 运行 `scripts/check_image_refs.py <input.md>` 检查本地图片引用是否存在。
3. 生成一个完整 HTML5 文件。
   - 包含 `<!doctype html>`、`<html lang="zh-CN">`、`<head>`、`<body>`。
   - 所有 CSS 写入 `<style>` 标签。
   - 不依赖 CDN、在线字体、外部 CSS 或外部 JavaScript。
   - 只有在明显提升阅读体验时，才使用少量原生 JavaScript，例如目录高亮、阅读进度条或返回顶部。
4. 忠实保留原文内容。
   - 除非用户明确要求，不要删减、改写、总结、翻译或新增事实。
   - 将标题、段落、列表、表格、引用、代码块、分隔线、链接和图片转换为语义化 HTML。
   - 根据 Markdown 标题生成稳定的章节 ID 和可点击目录。
5. 校验输出结果。
   - 生成后运行 `scripts/check_image_refs.py <output.html>`。
   - 如果本地图片路径错误，修正为相对于 HTML 文件的正确路径。
   - 确认表格和图片在移动端不会撑破页面。
   - 快速检查 HTML/CSS 字符串，修正破损属性、非法标签、错误闭合、缺空格的 `calc()`、污染的 CSS 值和损坏的锚点链接。

## 统一视觉模板

不同主题的 Markdown 文档都优先使用以下统一样式，保证产出的 HTML 观感稳定。

- 整体风格：专业文档/报告，现代、克制、清晰、易读，不做成营销落地页。
- 视觉指纹：深蓝渐变标题区、浅灰页面背景、白色内容卡片感、左侧粘性目录、顶部青色到琥珀阅读进度条、青色/琥珀强调块、深色表头、圆形返回顶部按钮。
- 生成结果必须是干净有效的 HTML，标签、属性、链接、表格结构和 CSS 语法都要正确。
- 使用 CSS 变量，优先采用这组色值：

```css
:root{
  --text:#1a1e23;--text-s:#5a6470;--text-m:#8a949e;
  --p:#1e3a5f;--pl:#2d5a87;--a:#00b4c8;--aw:#e8a838;
  --bg:#f4f6f8;--card:#fff;--bd:#d8dde3;--tth:#253240;
  --tr:#f8f9fa;--grn:#0d9488;--red:#dc2626;--ambr:#d97706;
  --r:8px;
}
```

- 页面背景：`var(--bg)`；正文和卡片背景：`var(--card)`。
- 页面最大宽度：`1280px`，左右内边距 `20px`。
- 桌面端布局：`1100px` 以上使用 `.page{display:flex}`；左侧粘性目录宽 `250px`，右侧为正文。
- 移动端布局：`1099px` 以下改为单栏，目录默认隐藏，通过左上角 `☰ 目录` 按钮展开。
- 顶部增加 `#prog` 阅读进度条，颜色为 `linear-gradient(90deg,var(--a),var(--aw))`，高度 `3px`。
- 字体：`-apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif`。
- 正文字号：`15px`；正文行高：`1.8`。
- H1：放在 `.hero` 内，`24px`，`700`，行高 `1.35`。
- H2：`20px`，主色文字，底部 `2px solid var(--a)`，下内边距 `8px`。
- H3：`16px`，使用 `var(--pl)`。
- 表格字号：`14px`；图注字号：`12.5px`。
- 内容密度：主内容保持报告阅读密度，不使用超大标题、巨幅留白、营销式分屏 hero 或装饰性背景图。
- 元信息：`.hero-m` 用短文本 chip 式横排展示日期、数据范围、作者、版本、预测范围等；可以使用纯文本标签，不要为了装饰引入外部图标库。

避免：

- 除标题区外的大面积装饰性渐变、霓虹色、高饱和撞色、营销页构图、超大 hero、嵌套卡片和过度装饰。
- 除非用户明确要求品牌化，否则不要临时改成另一套配色系统。

## HTML 骨架

优先使用这个页面结构：

```html
<body>
  <div id="prog"></div>
  <button class="toc-toggle" type="button" aria-controls="toc" aria-expanded="false">☰ 目录</button>
  <div class="page">
    <nav id="toc" aria-label="目录">
      <div class="toc-title">目录</div>
      <ul class="tox">...</ul>
    </nav>
    <main id="content">
      <div class="hero">
        <h1>文档标题</h1>
        <div class="hero-m">...</div>
      </div>
      <section id="...">...</section>
    </main>
  </div>
  <button id="back-top" type="button" aria-label="返回顶部">↑</button>
</body>
```

生成时必须使用合法标签和属性，避免无效链接、错误闭合标签、损坏的表格结构或非法 CSS。目录按钮使用 `<button>`，不要用无 `href` 的 `<a>`。

## 结构规则

- 将第一个 H1 作为文档标题区。
- 将紧随标题后的报告元信息放入 `.hero-m`，例如日期、数据范围、作者、版本、预测范围等；没有元信息就省略 `.hero-m`。
- 将 H2 作为主章节，将 H3 作为小节。
- 每个 H2 主章节尽量包裹为 `<section id="...">`。
- 当原文中明确存在摘要、执行摘要、核心发现、结论、风险、建议等内容时，可以用 `.highlight`、`.highlight.amber`、`.highlight.dark` 或 `.concl-text` 突出，但不得改变原文含义。
- 原文中的“核心判断/核心发现”编号列表可转换为 `.judgments` 列表，每项左侧使用圆形编号 `.n`。
- 原文中的“因果链/传导路径/机制链条”可转换为 `.causal`，每个节点用 `<span>`，箭头用 `<span class="arr">→</span>`。
- 保持稳定间距，避免正文过密。
- 表格必须包裹在可横向滚动容器中：

```html
<div class="table-wrap">
  <table>...</table>
</div>
```

- 表格样式：
  - `border-collapse: collapse`
  - 表格最小宽度 `560px`
  - 表头背景 `var(--tth)`
  - 表头文字白色
  - 行底部边框 `1px solid #eee`
  - 单元格内边距 `9px 14px`
  - 隔行背景 `#fafafa`
  - 明显的数字列居中或右对齐
  - 正向数字可加 `.pos`，负向数字可加 `.neg`，中性强调可加 `.ambr`

## 图片规则

- 本地图片引用必须保持为相对于输出 HTML 文件的路径。
- 除非用户明确要求，不要改成绝对路径。
- 不要把本地图片转成 base64。
- 将 Markdown 图片转换为 `figure`：

```html
<figure>
  <img src="relative/path.png" alt="图片说明">
  <figcaption>图片说明</figcaption>
</figure>
```

- 统一图片样式：
  - figure 上下边距：`18px 0`
  - figure 背景 `var(--card)`
  - figure 边框 `1px solid var(--bd)`
  - figure 圆角 `var(--r)`
  - figure 内边距 `12px`
  - 图片最大宽度：`100%`；高度自适应
  - 居中显示
  - 图片圆角 `4px`
  - 图注居中，颜色 `var(--text-s)`，字号 `12.5px`，可用斜体

## 交互规则

- 阅读进度条：监听页面滚动，根据文档滚动比例更新 `#prog` 宽度。
- 目录高亮：滚动时高亮当前 section 或当前 H3 对应的目录项。
- 移动端目录：点击 `.toc-toggle` 切换 `#toc.open`；点击目录链接后收起目录。
- 返回顶部按钮：滚动超过一屏后显示，点击平滑回到顶部。
- 所有交互必须使用原生 JavaScript，代码简洁，不依赖外部库。
- 交互脚本只操作已有元素；使用 `querySelector` 前检查元素存在，避免空引用报错。

## 生成质量自检

生成 HTML 后必须快速自检并修正：

- CSS 变量块必须存在，且 `rgba()`、`calc()`、`linear-gradient()` 都是合法语法；`calc()` 运算符两侧必须有空格，例如 `calc(100vh - 48px)`。
- 所有目录链接必须是 `href="#id"`，不能出现 `href "&id"`、空 href、重复 id 或指向不存在 id 的链接。
- 表格必须有完整的 `<table><thead><tbody><tr><th/td>` 结构，不能出现 `<tr <th>`、`</strongel>`、`color="dark"` 这类破损 HTML。
- 只使用标准 HTML 标签；不要生成自定义标签如 `<causal>`，应使用 `<div class="causal">`。
- 所有打开的 `<section>`、`<div>`、`<ol>`、`<ul>`、`<table>`、`<figure>` 必须闭合。
- 不要在表格和列表中加入会改变原文含义的文字；视觉增强只通过 class 和包裹结构实现。

## 默认 CSS 模板

生成 HTML 时应包含与下面等价的 CSS。可以根据内容少量增删选择器，但不要改变整体效果。

```css
*,*::before,*::after{box-sizing:border-box}
:root{
  --text:#1a1e23;--text-s:#5a6470;--text-m:#8a949e;
  --p:#1e3a5f;--pl:#2d5a87;--a:#00b4c8;--aw:#e8a838;
  --bg:#f4f6f8;--card:#fff;--bd:#d8dde3;--tth:#253240;
  --tr:#f8f9fa;--grn:#0d9488;--red:#dc2626;--ambr:#d97706;
  --r:8px;
}
html{scroll-behavior:smooth}
body{margin:0;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;font-size:15px;line-height:1.8;color:var(--text);background:var(--bg)}
#prog{position:fixed;top:0;left:0;height:3px;background:linear-gradient(90deg,var(--a),var(--aw));z-index:9999;transition:width .3s}
.toc-toggle{display:none;position:fixed;left:12px;top:12px;z-index:100;background:var(--card);border:1px solid var(--bd);border-radius:6px;padding:6px 12px;cursor:pointer;font-size:13px;color:var(--text)}
@media(min-width:1100px){.page{display:flex;max-width:1280px;margin:0 auto;padding:0 20px}#toc{position:sticky;top:24px;max-height:calc(100vh - 48px);overflow:auto;width:250px;flex-shrink:0;padding-right:24px}main{flex:1;min-width:0}}
@media(max-width:1099px){.toc-toggle{display:block}.page{display:block}#toc{display:none;position:fixed;inset:0 0 auto 0;z-index:1000;background:var(--card);border-bottom:1px solid var(--bd);padding:48px 20px 12px;overflow-y:auto;max-height:44vh}#toc.open{display:block}}
.toc-title{font-size:12px;font-weight:700;letter-spacing:1px;color:var(--text-m);text-transform:uppercase;margin-bottom:12px}
.tox{list-style:none;padding-left:0;margin:0}.tox ul{list-style:none;padding-left:12px;margin:4px 0}.tox li{margin:6px 0}
.tox a{text-decoration:none;color:var(--text-s);font-size:13px;display:block;padding:4px 10px;border-radius:4px;transition:all .2s}
.tox a:hover{background:rgba(0,180,200,.08);color:var(--p)}.tox a.active{background:rgba(0,180,200,.12);color:var(--p);font-weight:600}
main{padding:24px 0 80px}.hero{background:linear-gradient(135deg,var(--p),#162838);color:#fff;padding:36px 32px;border-radius:12px;margin-bottom:28px}
.hero h1{margin:0 0 8px;font-size:24px;line-height:1.35;font-weight:700}.hero-m{display:flex;flex-wrap:wrap;gap:16px;font-size:13px;opacity:.82}
section{margin-bottom:32px}h1,h2,h3,h4{margin:28px 0 12px;line-height:1.4}h2{font-size:20px;color:var(--p);border-bottom:2px solid var(--a);padding-bottom:8px;margin-top:36px}h3{font-size:16px;color:var(--pl);margin-top:24px}
p{margin:12px 0}ul,ol{padding-left:22px;margin:10px 0}li{margin:6px 0;padding-left:4px}
.highlight{background:linear-gradient(135deg,rgba(0,180,200,.07),rgba(232,168,56,.05));border-left:4px solid var(--a);padding:16px 20px;border-radius:0 var(--r) var(--r) 0;margin:16px 0}
.highlight.amber{border-left-color:var(--aw);background:linear-gradient(135deg,rgba(232,168,56,.08),rgba(0,180,200,.04))}.highlight.dark{border-left-color:var(--tth);background:linear-gradient(135deg,rgba(37,50,64,.06),rgba(0,180,200,.03))}
.idx-lbl{font-size:11px;font-weight:700;letter-spacing:1px;text-transform:uppercase;color:var(--a);margin-bottom:6px}
.judgments{list-style:none;padding:0;margin:14px 0}.judgments li{display:flex;gap:14px;align-items:flex-start;padding:12px 16px;margin:8px 0;background:var(--card);border:1px solid var(--bd);border-radius:var(--r)}
.judgments .n{width:26px;height:26px;border-radius:50%;background:var(--p);color:#fff;display:flex;align-items:center;justify-content:center;font-size:13px;font-weight:700;flex-shrink:0;margin-top:2px}
.concl-text{font-size:15px;line-height:1.75;padding:14px 18px;background:var(--card);border:1px solid var(--bd);border-radius:var(--r)}
.causal{display:flex;flex-wrap:wrap;gap:6px;align-items:center;background:var(--card);border:1px solid var(--bd);border-radius:var(--r);padding:10px 14px;margin:10px 0}.causal span{padding:4px 8px;background:rgba(0,180,200,.06);border-radius:4px;font-size:13px;white-space:nowrap}.causal .arr{color:var(--text-m);background:transparent;padding:4px 0;user-select:none}
.table-wrap{overflow-x:auto;border-radius:var(--r);border:1px solid var(--bd);margin:14px 0;background:var(--card)}table{width:100%;border-collapse:collapse;font-size:14px;min-width:560px}
thead th{background:var(--tth);color:#fff;padding:10px 14px;text-align:left;font-weight:600;font-size:13.5px;white-space:nowrap}tbody tr{border-bottom:1px solid #eee}tbody tr:nth-child(even){background:var(--tr)}tbody td{padding:9px 14px;vertical-align:top;line-height:1.6}
.pos{color:var(--grn);font-weight:600}.neg{color:var(--red);font-weight:600}.ambr{color:var(--ambr);font-weight:600}
blockquote{margin:14px 0;padding:12px 18px 12px 20px;background:rgba(37,50,64,.04);border-left:4px solid var(--text-m);border-radius:0 var(--r) var(--r) 0}
pre{overflow-x:auto;background:#111827;color:#e5e7eb;padding:14px 16px;border-radius:var(--r);font-size:13px;line-height:1.65}code{font-family:"SFMono-Regular",Consolas,"Liberation Mono",monospace;font-size:.92em}
figure{margin:18px 0;text-align:center;background:var(--card);border:1px solid var(--bd);border-radius:var(--r);padding:12px;max-width:100%}figure img{max-width:100%;height:auto;display:block;margin:0 auto;border-radius:4px}figcaption{font-size:12.5px;color:var(--text-s);margin-top:8px;font-style:italic}
footer{text-align:center;padding:32px 20px;font-size:12.5px;color:var(--text-m);border-top:1px solid var(--bd);margin-top:40px}
#back-top{display:none;position:fixed;right:18px;bottom:18px;z-index:90;background:var(--p);color:#fff;border:none;border-radius:50%;width:42px;height:42px;cursor:pointer;font-size:18px;box-shadow:0 2px 8px rgba(0,0,0,.15)}#back-top.show{display:flex;align-items:center;justify-content:center}
@media print{#prog,.toc-toggle,#back-top,#toc{display:none!important}.page{display:block;max-width:100%;padding:0}main{padding:0}body{background:#fff;color:#000;font-size:11pt}.hero{background:#253240!important;color:#fff!important;-webkit-print-color-adjust:exact;print-color-adjust:exact}.table-wrap,figure,blockquote,.highlight,.judgments li,.concl-text{break-inside:avoid;page-break-inside:avoid}h1,h2,h3{break-after:avoid;page-break-after:avoid}}
@media(max-width:600px){.hero{padding:22px 18px}.hero h1{font-size:19px}main{padding:14px 0 60px}h2{font-size:18px}.judgments li{flex-direction:column;gap:6px;padding:10px 12px}.table-wrap{border-radius:0}table{font-size:13px;min-width:480px}thead th,tbody td{padding:7px 10px}}
```

## 打印规则

添加 `@media print` 样式：

- 隐藏目录、阅读进度条、返回顶部等辅助 UI。
- 页面背景改为白色。
- 去掉阴影。
- 尽量避免图片和表格被不自然截断。
- 保持链接、表格和标题在打印/PDF 中清晰可读。

## 最终回复

保持简洁，说明：

- HTML 文件路径。
- 图片引用检查结果。
- 缺失或已修正的图片路径，如有。
- 未能运行的校验，如有。

## 内置脚本

使用 `scripts/check_image_refs.py` 检查 Markdown 或 HTML 中的本地图片引用：

```bash
python3 /path/to/md-to-html-report/scripts/check_image_refs.py /path/to/report.md
python3 /path/to/md-to-html-report/scripts/check_image_refs.py /path/to/report.html
```
