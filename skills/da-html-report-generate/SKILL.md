---
name: da-html-report-generate
description: "HTML 分析报告生成 skill，提供完整的设计系统（CSS 变量、布局、全套组件），输出美观、专业的单文件 HTML 报告，保存至 /mnt/data/ 并附下载链接。**遇到以下任一情况就主动使用本 skill，不要用纯文字或 Markdown 输出报告**：① 用户要求生成报告、可视化报告、数据分析报告；② 分析结果需要以美观文档形式呈现，而非纯文字；③ 用户提到"生成报告"、"生成 HTML"、"做一个报告页面"、"可视化报告"、"数据报告"、"出一份报告"；④ 数据分析完成后需要输出正式、可交付的报告文件。仅不用于：纯文本摘要、Markdown 文档输出、图表图片生成（使用 matplotlib 即可）。"
---

# HTML 报告生成 Skill

生成专业、美观的单文件 HTML 分析报告。每份报告包含：封面、目录、正文章节、数据可视化组件、页脚。

## 核心原则

1. **始终写完整文件** — 生成完整的 `<!DOCTYPE html>` 文件，不要输出片段
2. **单文件自包含** — 所有样式内联在 `<style>` 中，图表用 inline base64 或 `<img src="...">` 引用 `/mnt/data/` 中已生成的图片
3. **保存路径** — 输出到 `/mnt/data/report.html`（或更具描述性的名称），并打印下载链接
4. **中文字体** — 始终引入 Noto Sans SC，并保留系统字体回退
5. **数据忠实** — 报告中的所有数字、结论均来自实际分析结果，不虚构

---

## 设计系统 CSS — 完整复制此块

**每次生成报告，将以下完整 CSS 复制到 `<style>` 标签内，然后按需叠加各章节的具体样式。**

```css
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@300;400;500;600;700;800&display=swap');

/* ==================== 设计 Token ==================== */
:root {
    /* 主色 */
    --primary:        #1e3a5f;
    --primary-light:  #2563eb;
    --primary-dark:   #0c2d4a;
    --accent:         #0891b2;
    /* 语义色 */
    --success:        #0d9488;
    --success-light:  #ccfbf1;
    --warning:        #d97706;
    --warning-light:  #fef3c7;
    --danger:         #be123c;
    --danger-light:   #ffe4e6;
    --info:           #2563eb;
    --info-light:     #eff6ff;
    /* 中性色 */
    --muted:          #64748b;
    --bg-page:        #f1f5f9;
    --bg-card:        #ffffff;
    --text:           #0f172a;
    --text-secondary: #475569;
    --border:         #e2e8f0;
    /* 圆角 */
    --radius-sm:  8px;
    --radius-md:  12px;
    --radius-lg:  16px;
    --radius-xl:  24px;
    /* 阴影 */
    --shadow-sm:  0 1px 3px rgba(0,0,0,0.08), 0 1px 2px rgba(0,0,0,0.04);
    --shadow-md:  0 4px 12px rgba(0,0,0,0.08), 0 2px 6px rgba(0,0,0,0.04);
    --shadow-lg:  0 10px 40px rgba(0,0,0,0.10), 0 4px 16px rgba(0,0,0,0.06);
}

/* ==================== Reset ==================== */
*, *::before, *::after { margin: 0; padding: 0; box-sizing: border-box; }
html { scroll-behavior: smooth; }

body {
    font-family: 'Noto Sans SC', -apple-system, BlinkMacSystemFont,
                 'PingFang SC', 'Microsoft YaHei', sans-serif;
    background: var(--bg-page);
    color: var(--text);
    line-height: 1.75;
    min-height: 100vh;
}

/* ==================== 封面 ==================== */
.cover {
    min-height: 100vh;
    background:
        radial-gradient(circle at 20% 30%, rgba(30,58,95,0.12) 0%, transparent 500px),
        radial-gradient(circle at 80% 70%, rgba(37,99,235,0.18) 0%, transparent 600px),
        linear-gradient(135deg, var(--primary-dark) 0%, var(--primary) 45%, var(--primary-light) 100%);
    display: flex;
    align-items: center;
    justify-content: center;
    position: relative;
    overflow: hidden;
    padding: 2rem;
}

.cover-grid {
    position: absolute;
    inset: 0;
    background-image:
        linear-gradient(rgba(255,255,255,0.04) 1px, transparent 1px),
        linear-gradient(90deg, rgba(255,255,255,0.04) 1px, transparent 1px);
    background-size: 40px 40px;
    pointer-events: none;
}

.cover-content {
    text-align: center;
    color: white;
    z-index: 1;
    animation: fadeInUp 0.9s ease-out both;
    max-width: 780px;
    width: 100%;
}

.cover-badge {
    display: inline-block;
    background: rgba(255,255,255,0.12);
    border: 1px solid rgba(255,255,255,0.22);
    border-radius: 999px;
    padding: 0.4rem 1.4rem;
    font-size: 0.82rem;
    letter-spacing: 0.12em;
    margin-bottom: 2rem;
    backdrop-filter: blur(8px);
}

.cover-title {
    font-size: clamp(1.9rem, 5vw, 3.4rem);
    font-weight: 800;
    line-height: 1.25;
    margin-bottom: 1.5rem;
    text-shadow: 0 4px 20px rgba(0,0,0,0.25);
}

.cover-title .sub {
    display: block;
    font-size: 0.55em;
    font-weight: 300;
    color: rgba(255,255,255,0.72);
    margin-top: 0.4rem;
    letter-spacing: 0.02em;
}

.cover-divider {
    width: 72px;
    height: 3px;
    background: rgba(255,255,255,0.45);
    margin: 2rem auto;
    border-radius: 2px;
}

.cover-meta {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
    gap: 1.25rem;
    max-width: 640px;
    margin: 0 auto;
}

.cover-meta-item {
    background: rgba(255,255,255,0.09);
    border: 1px solid rgba(255,255,255,0.16);
    border-radius: var(--radius-md);
    padding: 1.25rem 1rem;
    backdrop-filter: blur(12px);
}

.cover-meta-label {
    font-size: 0.75rem;
    color: rgba(255,255,255,0.58);
    text-transform: uppercase;
    letter-spacing: 0.1em;
    margin-bottom: 0.35rem;
}

.cover-meta-value {
    font-size: 1.15rem;
    font-weight: 600;
}

/* ==================== 主文档容器 ==================== */
.document {
    max-width: 1020px;
    margin: 0 auto;
    padding: 4rem 2rem;
}

/* ==================== 目录 ==================== */
.toc {
    background: var(--bg-card);
    border-radius: var(--radius-lg);
    padding: 3rem;
    margin-bottom: 3rem;
    box-shadow: var(--shadow-md);
    border: 1px solid var(--border);
}

.toc-title {
    font-size: 1.6rem;
    font-weight: 700;
    color: var(--primary);
    margin-bottom: 2rem;
    padding-bottom: 1rem;
    border-bottom: 2px solid var(--border);
}

.toc-list { list-style: none; }

.toc-list li {
    padding: 0.7rem 0;
    border-bottom: 1px dashed var(--border);
}

.toc-list li:last-child { border-bottom: none; }

.toc-list a {
    color: var(--text);
    text-decoration: none;
    display: flex;
    align-items: center;
    gap: 0.75rem;
    transition: color 0.2s;
}

.toc-list a:hover { color: var(--primary-light); }

.toc-num {
    min-width: 2.2rem;
    font-weight: 600;
    color: var(--muted);
    font-size: 0.9rem;
}

.toc-sub { padding-left: 2rem !important; }
.toc-sub .toc-num { color: var(--accent); font-size: 0.82rem; }

/* ==================== 章节 ==================== */
.section {
    background: var(--bg-card);
    border-radius: var(--radius-lg);
    padding: 3rem;
    margin-bottom: 2.5rem;
    box-shadow: var(--shadow-sm);
    border: 1px solid var(--border);
}

.section-header {
    display: flex;
    align-items: flex-start;
    gap: 1rem;
    margin-bottom: 2.5rem;
    padding-bottom: 1.5rem;
    border-bottom: 2px solid var(--border);
}

.section-index {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 3rem;
    height: 3rem;
    background: linear-gradient(135deg, var(--primary), var(--primary-light));
    border-radius: var(--radius-sm);
    color: white;
    font-size: 1.1rem;
    font-weight: 700;
    flex-shrink: 0;
    box-shadow: var(--shadow-sm);
}

.section-heading { flex: 1; }

.section-heading h2 {
    font-size: 1.65rem;
    font-weight: 700;
    color: var(--text);
    line-height: 1.3;
    margin-bottom: 0.25rem;
}

.section-heading p {
    color: var(--text-secondary);
    font-size: 0.92rem;
    margin: 0;
}

.section h3 {
    font-size: 1.2rem;
    font-weight: 600;
    color: var(--primary-light);
    margin: 2rem 0 1rem;
    padding-left: 0.85rem;
    border-left: 4px solid var(--accent);
    line-height: 1.4;
}

.section p {
    color: var(--text-secondary);
    margin-bottom: 1.25rem;
    text-align: justify;
}

.section p:last-child { margin-bottom: 0; }

.section ul, .section ol {
    color: var(--text-secondary);
    padding-left: 1.5rem;
    margin: 1rem 0;
}

.section li { margin-bottom: 0.4rem; }

/* ==================== 统计卡片网格 ==================== */
.stats-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    gap: 1.25rem;
    margin: 2rem 0;
}

.stat-card {
    background: linear-gradient(145deg, #f8fafc, #f1f5f9);
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    padding: 1.5rem 1.25rem;
    text-align: center;
    position: relative;
    overflow: hidden;
    transition: box-shadow 0.2s, transform 0.2s;
}

.stat-card:hover {
    box-shadow: var(--shadow-md);
    transform: translateY(-2px);
}

.stat-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 3px;
    background: linear-gradient(90deg, var(--primary), var(--accent));
    border-radius: var(--radius-sm) var(--radius-sm) 0 0;
}

.stat-card.danger::before  { background: var(--danger); }
.stat-card.warning::before { background: var(--warning); }
.stat-card.success::before { background: var(--success); }

.stat-value {
    font-size: 2.2rem;
    font-weight: 800;
    color: var(--primary);
    line-height: 1;
    margin-bottom: 0.5rem;
}

.stat-label {
    font-size: 0.82rem;
    color: var(--muted);
    line-height: 1.4;
}

.stat-sub {
    font-size: 0.8rem;
    color: var(--muted);
    margin-top: 0.35rem;
}

/* ==================== 表格 ==================== */
.table-wrapper {
    overflow-x: auto;
    margin: 1.5rem 0;
    border-radius: var(--radius-md);
    border: 1px solid var(--border);
    box-shadow: var(--shadow-sm);
}

table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.9rem;
}

thead tr {
    background: linear-gradient(135deg, var(--primary), var(--primary-light));
}

th {
    color: white;
    font-weight: 600;
    padding: 0.9rem 1.1rem;
    text-align: left;
    white-space: nowrap;
}

td {
    padding: 0.85rem 1.1rem;
    border-bottom: 1px solid var(--border);
    color: var(--text-secondary);
}

tbody tr:last-child td { border-bottom: none; }
tbody tr:nth-child(even) { background: #f8fafc; }
tbody tr:hover { background: #eff6ff; transition: background 0.15s; }

.td-num { text-align: right; font-variant-numeric: tabular-nums; }
.td-bold { font-weight: 700; color: var(--text); }
.positive { color: var(--success); font-weight: 700; }
.negative { color: var(--danger);  font-weight: 700; }
.warn     { color: var(--warning); font-weight: 700; }

/* 高亮行 */
.row-danger  { background: var(--danger-light)  !important; }
.row-warning { background: var(--warning-light) !important; }
.row-success { background: var(--success-light) !important; }

/* ==================== 提示框 ==================== */
.callout {
    padding: 1.35rem 1.5rem;
    border-radius: var(--radius-sm);
    margin: 1.5rem 0;
    border-left: 4px solid;
    display: flex;
    gap: 0.75rem;
    align-items: flex-start;
}

.callout-icon { font-size: 1.25rem; flex-shrink: 0; margin-top: 0.1rem; }
.callout-body { flex: 1; }
.callout-title { font-weight: 700; margin-bottom: 0.35rem; font-size: 0.95rem; }
.callout p { margin: 0; font-size: 0.92rem; }

.callout-info    { background: var(--info-light);    border-color: var(--info);    }
.callout-warning { background: var(--warning-light); border-color: var(--warning); }
.callout-danger  { background: var(--danger-light);  border-color: var(--danger);  }
.callout-success { background: var(--success-light); border-color: var(--success); }

.callout-info    .callout-title { color: var(--info);    }
.callout-warning .callout-title { color: var(--warning); }
.callout-danger  .callout-title { color: var(--danger);  }
.callout-success .callout-title { color: var(--success); }

/* ==================== 图表容器 ==================== */
.figure {
    background: #f8fafc;
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    padding: 1.25rem;
    margin: 2rem 0;
    text-align: center;
}

.figure img {
    max-width: 100%;
    height: auto;
    border-radius: var(--radius-sm);
    box-shadow: var(--shadow-sm);
}

.figure-caption {
    margin-top: 0.85rem;
    color: var(--muted);
    font-size: 0.88rem;
    font-style: italic;
}

/* ==================== 进度条 ==================== */
.progress-list { margin: 1.5rem 0; display: flex; flex-direction: column; gap: 1rem; }

.progress-item {}

.progress-header {
    display: flex;
    justify-content: space-between;
    margin-bottom: 0.4rem;
    font-size: 0.88rem;
}

.progress-label { color: var(--text); font-weight: 500; }
.progress-value { color: var(--muted); }

.progress-bar-bg {
    background: var(--border);
    border-radius: 999px;
    height: 8px;
    overflow: hidden;
}

.progress-bar-fill {
    height: 100%;
    border-radius: 999px;
    background: linear-gradient(90deg, var(--primary), var(--primary-light));
    transition: width 0.8s ease;
}

.progress-bar-fill.danger  { background: linear-gradient(90deg, var(--danger),  #f43f5e); }
.progress-bar-fill.warning { background: linear-gradient(90deg, var(--warning), #fbbf24); }
.progress-bar-fill.success { background: linear-gradient(90deg, var(--success), #34d399); }

/* ==================== 标签 ==================== */
.tag {
    display: inline-block;
    padding: 0.2rem 0.65rem;
    border-radius: 999px;
    font-size: 0.78rem;
    font-weight: 600;
    letter-spacing: 0.03em;
}

.tag-primary { background: #dbeafe; color: var(--primary); }
.tag-success { background: var(--success-light); color: var(--success); }
.tag-warning { background: var(--warning-light); color: var(--warning); }
.tag-danger  { background: var(--danger-light);  color: var(--danger);  }
.tag-muted   { background: #f1f5f9; color: var(--muted); }

/* ==================== 洞察卡片 ==================== */
.insight-card {
    background: linear-gradient(135deg, #eff6ff, #f0f9ff);
    border: 1px solid #bfdbfe;
    border-radius: var(--radius-md);
    padding: 1.75rem;
    margin: 1.5rem 0;
}

.insight-card h4 {
    font-size: 1rem;
    font-weight: 700;
    color: var(--primary);
    margin-bottom: 0.75rem;
}

.insight-card p { margin: 0; font-size: 0.92rem; color: var(--text-secondary); }

/* ==================== 侧边导航 ==================== */
.side-nav {
    position: fixed;
    left: 18px;
    top: 50%;
    transform: translateY(-50%);
    background: white;
    padding: 0.85rem;
    border-radius: var(--radius-md);
    box-shadow: var(--shadow-lg);
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
    z-index: 100;
    border: 1px solid var(--border);
}

.nav-dot {
    width: 34px;
    height: 34px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    text-decoration: none;
    color: var(--muted);
    font-size: 0.8rem;
    font-weight: 600;
    transition: all 0.25s;
}

.nav-dot:hover { background: #eff6ff; color: var(--primary-light); }
.nav-dot.active { background: var(--primary); color: white; box-shadow: 0 2px 8px rgba(30,58,95,0.3); }

/* ==================== 页脚 ==================== */
.report-footer {
    text-align: center;
    padding: 4rem 2rem 5rem;
    color: var(--muted);
    font-size: 0.88rem;
    border-top: 2px solid var(--border);
    margin-top: 2rem;
}

.footer-end {
    font-weight: 700;
    color: var(--text);
    letter-spacing: 0.12em;
    margin-bottom: 1rem;
}

.footer-line {
    width: 36px; height: 2px;
    background: var(--border);
    margin: 1rem auto;
    border-radius: 2px;
}

/* ==================== 动画 ==================== */
@keyframes fadeInUp {
    from { opacity: 0; transform: translateY(28px); }
    to   { opacity: 1; transform: translateY(0); }
}

/* ==================== 响应式 ==================== */
@media (max-width: 768px) {
    .side-nav   { display: none; }
    .document   { padding: 2rem 1rem; }
    .section    { padding: 1.75rem 1.25rem; }
    .toc        { padding: 1.75rem 1.25rem; }
    .cover-title { font-size: 1.7rem; }
    .stats-grid { grid-template-columns: repeat(2, 1fr); }
}

/* ==================== 打印 ==================== */
@media print {
    .side-nav, .cover { display: none; }
    .section { box-shadow: none; border: 1px solid #ddd; }
    body { background: white; }
}
```

---

## HTML 基础结构

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>【报告标题】</title>
    <link rel="preconnect" href="https://fonts.googleapis.com"/>
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin/>
    <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@300;400;500;600;700;800&display=swap" rel="stylesheet"/>
    <style>
        /* === 粘贴完整设计系统 CSS === */
    </style>
</head>
<body>

<!-- 封面 -->
<section class="cover">
    <div class="cover-grid"></div>
    <div class="cover-content">
        <div class="cover-badge">【机密级别 · 内部报告】</div>
        <h1 class="cover-title">
            【主标题】
            <span class="sub">【副标题 / 年度范围】</span>
        </h1>
        <div class="cover-divider"></div>
        <div class="cover-meta">
            <div class="cover-meta-item">
                <div class="cover-meta-label">报告期间</div>
                <div class="cover-meta-value">YYYY.MM — YYYY.MM</div>
            </div>
            <div class="cover-meta-item">
                <div class="cover-meta-label">数据来源</div>
                <div class="cover-meta-value">【来源描述】</div>
            </div>
            <div class="cover-meta-item">
                <div class="cover-meta-label">生成日期</div>
                <div class="cover-meta-value">【YYYY年M月D日】</div>
            </div>
        </div>
    </div>
</section>

<!-- 主文档 -->
<div class="document">

    <!-- 目录 -->
    <section class="toc">
        <h2 class="toc-title">目 录</h2>
        <ul class="toc-list">
            <li><a href="#s1"><span class="toc-num">01</span>章节一标题</a></li>
            <li class="toc-sub"><a href="#s1-1"><span class="toc-num">1.1</span>小节标题</a></li>
            <li><a href="#s2"><span class="toc-num">02</span>章节二标题</a></li>
        </ul>
    </section>

    <!-- 章节示例（复制此块生成各章节） -->
    <section id="s1" class="section">
        <div class="section-header">
            <div class="section-index">一</div>
            <div class="section-heading">
                <h2>章节标题</h2>
                <p>本章节一句话概述。</p>
            </div>
        </div>
        <!-- 内容区 -->
    </section>

    <!-- 页脚 -->
    <footer class="report-footer">
        <p class="footer-end">— 报告完 —</p>
        <div class="footer-line"></div>
        <p>【部门名称】 | 【报告标题简称】</p>
        <p>数据来源：【来源】 | 生成时间：【日期】</p>
    </footer>
</div>

<!-- 侧边导航（按章节数量增减 .nav-dot） -->
<nav class="side-nav">
    <a href="#s1" class="nav-dot" title="章节一">1</a>
    <a href="#s2" class="nav-dot" title="章节二">2</a>
</nav>

<script>
    // 侧边导航高亮
    const sections = document.querySelectorAll('.section[id]');
    const dots = document.querySelectorAll('.nav-dot');
    window.addEventListener('scroll', () => {
        let current = '';
        sections.forEach(s => {
            if (s.getBoundingClientRect().top <= 200) current = s.id;
        });
        dots.forEach(d => d.classList.toggle('active', d.getAttribute('href') === '#' + current));
    });
</script>
</body>
</html>
```

---

## 组件速查

### 统计卡片网格

```html
<div class="stats-grid">
    <div class="stat-card">
        <div class="stat-value">1,234</div>
        <div class="stat-label">总数量</div>
    </div>
    <div class="stat-card success">
        <div class="stat-value">87.5%</div>
        <div class="stat-label">合格率</div>
        <div class="stat-sub">↑ 较上期 +3.2%</div>
    </div>
    <div class="stat-card danger">
        <div class="stat-value">42</div>
        <div class="stat-label">异常项</div>
    </div>
    <div class="stat-card warning">
        <div class="stat-value">12.3</div>
        <div class="stat-label">平均分</div>
    </div>
</div>
```

stat-card 颜色变体：默认（蓝色顶线）、`success`、`danger`、`warning`

---

### 提示框（4 种类型）

```html
<!-- 信息 -->
<div class="callout callout-info">
    <div class="callout-icon">💡</div>
    <div class="callout-body">
        <div class="callout-title">分析说明</div>
        <p>补充说明文字。</p>
    </div>
</div>

<!-- 警告 -->
<div class="callout callout-warning">
    <div class="callout-icon">⚠️</div>
    <div class="callout-body">
        <div class="callout-title">注意事项</div>
        <p>警告内容。</p>
    </div>
</div>

<!-- 危险 -->
<div class="callout callout-danger">
    <div class="callout-icon">🚨</div>
    <div class="callout-body">
        <div class="callout-title">风险提示</div>
        <p>危险内容。</p>
    </div>
</div>

<!-- 成功 / 亮点 -->
<div class="callout callout-success">
    <div class="callout-icon">✅</div>
    <div class="callout-body">
        <div class="callout-title">关键发现</div>
        <p>积极结论。</p>
    </div>
</div>
```

---

### 表格（含高亮行）

```html
<div class="table-wrapper">
    <table>
        <thead>
            <tr>
                <th>名称</th>
                <th>数量</th>
                <th class="td-num">占比</th>
                <th>状态</th>
            </tr>
        </thead>
        <tbody>
            <!-- 普通行 -->
            <tr>
                <td class="td-bold">项目 A</td>
                <td>128</td>
                <td class="td-num positive">+12.3%</td>
                <td><span class="tag tag-success">正常</span></td>
            </tr>
            <!-- 危险高亮行 -->
            <tr class="row-danger">
                <td class="td-bold">项目 B</td>
                <td>3</td>
                <td class="td-num negative">-45.0%</td>
                <td><span class="tag tag-danger">异常</span></td>
            </tr>
            <!-- 警告高亮行 -->
            <tr class="row-warning">
                <td class="td-bold">项目 C</td>
                <td>21</td>
                <td class="td-num warn">+1.2%</td>
                <td><span class="tag tag-warning">关注</span></td>
            </tr>
        </tbody>
    </table>
</div>
```

---

### 进度条列表

```html
<div class="progress-list">
    <div class="progress-item">
        <div class="progress-header">
            <span class="progress-label">指标 A</span>
            <span class="progress-value">82%</span>
        </div>
        <div class="progress-bar-bg">
            <div class="progress-bar-fill" style="width: 82%"></div>
        </div>
    </div>
    <div class="progress-item">
        <div class="progress-header">
            <span class="progress-label">指标 B（警告）</span>
            <span class="progress-value">35%</span>
        </div>
        <div class="progress-bar-bg">
            <div class="progress-bar-fill warning" style="width: 35%"></div>
        </div>
    </div>
    <div class="progress-item">
        <div class="progress-header">
            <span class="progress-label">指标 C（高风险）</span>
            <span class="progress-value">90%</span>
        </div>
        <div class="progress-bar-bg">
            <div class="progress-bar-fill danger" style="width: 90%"></div>
        </div>
    </div>
</div>
```

---

### 图表图片（引用 /mnt/data/ 图片）

```html
<div class="figure">
    <img src="/mnt/data/chart_01.png" loading="lazy" alt="月度趋势图">
    <div class="figure-caption"><strong>图一：</strong>2024年12月—2025年8月月度趋势图</div>
</div>
```

---

### 洞察卡片

```html
<div class="insight-card">
    <h4>💡 核心结论</h4>
    <p>基于以上数据，【关键洞察内容，2-3 句话，直接指向决策建议】。</p>
</div>
```

---

### 标签 Tag

```html
<span class="tag tag-primary">主要</span>
<span class="tag tag-success">合格</span>
<span class="tag tag-warning">关注</span>
<span class="tag tag-danger">异常</span>
<span class="tag tag-muted">参考</span>
```

---

## 生成规则

### 文件输出

```python
output_path = "/mnt/data/report.html"
html_content = """..."""  # 完整 HTML 字符串

with open(output_path, "w", encoding="utf-8") as f:
    f.write(html_content)

print(f"[📄 下载报告](sandbox:{output_path})")
```

### 章节组织规则

| 章节数 | section-index 建议写法 |
|--------|----------------------|
| 1–9 章 | 一、二、三 … 九 |
| 10+ 章 | 1、2、3 … |

- 每章必须有 `id="sN"` 供目录锚点跳转
- 侧边导航的 `.nav-dot` 数量 = 章节数量
- 小节用 `<article id="sN-M">` 包裹，`<h3>` 开头

### 数据呈现规则

- **核心 KPI** → 用 `stats-grid` + `stat-card`，控制在 3–6 个
- **排名/明细表** → `table-wrapper` + `table`，超过 20 行考虑只展示 Top N
- **趋势/分布图** → `figure` 引用 matplotlib 生成的图片（先用 da-excel-workflow 等 skill 生成图片）
- **重要比率** → `progress-list`
- **结论/建议** → `callout-success` 或 `insight-card`
- **风险/异常** → `callout-danger` 或 `row-danger`

### 颜色使用约定

| 语义 | 用法 |
|------|------|
| `primary` 蓝 | 章节标题、表头、默认强调 |
| `success` 绿 | 正向指标、合格状态、增长 |
| `warning` 橙 | 需关注、中等风险、轻微异常 |
| `danger` 红 | 高风险、不合格、大幅下降 |

### 禁止事项

- 不要内联 `style="..."` 覆盖设计系统（只在必要的个别调整时使用）
- 不要引用外部 CDN 图表库（ECharts/Chart.js），图表统一用 matplotlib 生成图片
- 不要省略 `<!DOCTYPE html>` 或 `<html lang="zh-CN">`
- 不要在报告中放置未经计算的占位数据
