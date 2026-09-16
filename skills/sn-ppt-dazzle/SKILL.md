---
name: sn-ppt-dazzle
description: 需要把演示 / 幻灯片 / PPT / slides 做成单文件 HTML 动态 deck（动效、跨页过渡、键盘翻页、1280×720）时使用。本 skill 非入口：使用前必须先确认 sn-ppt-entry 与 sn-ppt-story 两个前置 skill 可用，依次执行 entry（建 DECK_DIR / task_pack.json）→ story（生成 outline.md）完成后才可开始；前置缺失或未完成时停止并回报，严禁绕过（如改用生图+手写 HTML 等方式）。
metadata:
  project: SenseNova-Skills
  tier: 1
  category: scene
  user_visible: false
triggers:
  - "sn-ppt-dazzle"
  - "动态 HTML"
  - "动态演示"
  - "炫彩 deck"
  - "dazzle"
---

# sn-ppt-dazzle：单 HTML 炫彩演示 deck

你要交付的不是一份"幻灯片"，而是一场在浏览器里上演的**动态视觉演出**：持续运行的动态背景、每页的入场编排、页间的过渡特效、键盘可交互——同时排版严谨、内容真实、零控制台报错。

## 0. Entry / Story 输入契约（最高优先级）

本 Skill 不是用户请求入口，不直接接收裸 query 或附件创建新任务。只接受
`sn-ppt-entry` 传入的绝对 `DECK_DIR`，并且必须已经存在：

- `<DECK_DIR>/task_pack.json`；
- `<DECK_DIR>/info_pack.json`；
- `<DECK_DIR>/outline.md`；
- `task_pack.choices.output == "dynamic_html"`，或旧任务的 `ppt_mode == "dazzle"`。

任一条件不满足时停止并返回 `sn-ppt-entry` 补齐，不自行新建 deck 目录、不从 query 绕过 `sn-ppt-story`。
开始和恢复时都 **重新读取`read_file`磁盘上的当前 `outline.md`**，不得使用`sn-ppt-story` 的 write_file 返回内容或对话上下文中的 outline；`outline.md`是 Dazzle 的唯一内容输入并固定：

- 最终页数、页序和标题；
- 每页核心结论、内容依据、上屏内容边界和前后关系；
- 用户明确保留、删除或修改的内容。

Dazzle 仍按本文后续六阶段决定风格 family、动态背景、版式、素材、动画和实现细节，但不得
合并、拆分、增删或重排 outline 页面，不得改变标题和核心结论的含义，不得恢复用户删除的
内容，也不得自行 Research 或补造事实。事实不足时停止相关页面并返回 Entry / Story。

`DECK_DIR` 只能取 `task_pack.deck_dir` 的绝对路径，所有任务产物都写入该目录。当前 Skill
目录只读并记为 `SKILL_ROOT`；references 和渲染脚本只从 `SKILL_ROOT` 读取。

## 1. 产物与边界

- 最终产物：`<DECK_DIR>/deck.html`（如用了生成图则外加 `<DECK_DIR>/assets/`，图片在 HTML 中仍用相对路径 `assets/img_NN.png` 引用；没有生成图时 `deck.html` 就是唯一演示交付物）。
- 画布 **1280×720（16:9）**，固定设计画布 + JS 等比缩放适配屏幕（见 §4 契约）。
- CSS / JS 全部内联在 `<style>` / `<script>`。允许 CDN：**Three.js r128**、GSAP、ECharts、D3、Google Fonts。**禁止外链图片 URL**（图片只能来自 assets/ 下的本地文件）。
- `DECK_DIR` 内文件：`plan.md`（你的规划）、`deck.html`、`assets/`（可选）、`shots/`（渲染截图输出）。

只在现有阶段边界同步 `task_pack.json`，不改变后续阶段的执行内容：

- 进入阶段 1：`current_stage="output.dynamic_html.plan"`、`status="generating"`；`plan.md`
  完成后把绝对路径写入 `state.artifacts.plan`。
- 进入阶段 3：`current_stage="output.dynamic_html.build"`；阶段 4 每完成并看图确认一页，把
  页号追加到 `state.artifacts.dynamic_pages_completed`。
- 阶段 6 完成：把 `deck.html`、`shots/`、`shots/render.json` 和可用的
  `shots/contact_sheet.png` 的绝对路径分别写入 `state.artifacts.deck_html`、`shots`、
  `render_manifest`、`contact_sheet`；把 `dynamic_html` 加入 `completed_stages`。全部页面通过时
  写 `current_stage="complete"`、`status="completed"`；仍有已如实报告的缺陷时写
  `status="partial"` 和 `last_error`，保留全部可用产物。

## 2. 工作流（六阶段）

**必须先渲后看：只读代码不算自检。** 渲染统一用 bash 执行 skill 自带脚本：

```bash
python "$SKILL_ROOT/scripts/render_deck.py" "$DECK_DIR/deck.html" "$DECK_DIR/shots/" --page N  # 渲染第 N 页
python "$SKILL_ROOT/scripts/render_deck.py" "$DECK_DIR/deck.html" "$DECK_DIR/shots/" --all     # 全部页 + contact_sheet.png
```

成功时 stdout 每行一个 PNG 路径（告警以 `[console]/[static]/[blank]/[nav]` 前缀打在路径之前）；渲染元数据写 `$DECK_DIR/shots/render.json`（console_errors / static_pages / blank_pages / 页数 / 导航方式）。截图后用 `vision_analyze` 查看。

### 阶段 0 —— 读取 outline.md 与定调

**第一步必须是完整读取`read_file`当前 `outline.md`，不得先生成 plan.md 或 deck.html。**
`task_pack.request.query` 只补充场景和用户明确风格偏好，不能覆盖
outline 的内容决定：

- 页数、页序、标题和每页核心结论：严格取自连续的 `## 第 N 页`，不得再按 8–12 页自行决定。
- 语言、受众和场景：优先取 outline；outline 未明确时读取 `task_pack.params` 和`task_pack.request.query`，不得改变 outline 内容。
- **先判使用场景的庄重度**（§3 场景适配），据此圈定风格候选域与动画密度档。
- **风格必须点名**：读取 `$SKILL_ROOT/references/style-families.md`，选定一个与主题、场景都契合的 family（outline 或 `task_pack.request.query` 带了风格倾向则在其方向内落到具体 family）。
- 读取 `$SKILL_ROOT/references/fancy-cookbook.md`，为本 deck 挑 2–3 个技法配方（全局背景选一种、入场编排选一种、过渡/彩蛋按需）。
- **定一个"招牌视觉"**：每个 deck 要有一处配得上题材的招牌手法。**选最贴本题材的技术——CSS/SVG/Canvas-2D/shader/代码 3D 平权，有创意、有题材绑定就是满分 fancy**（纯 CSS 几何、Canvas-2D 概念可视化也能很惊艳）。**fancy ≠ 3D**，评判看"有想法 vs 平庸套路"，不是用没用 3D。**分清 3D/shader 的两种用法**：① **灵动背景层**（shader 流场 / 节点球 / Fresnel 辉光球 / 粒子流 / 3D 氛围层）——背景默认就该"活"（持续微动），这类背景层**对任何题材都可用、科技抽象数据网络类尤其加分，不算"硬套 3D"**，鼓励上；② **沉浸漫游场景**（把整套 deck 架在可巡游的 3D 世界 + 翻页相机运镜）——这个才只给有空间主体的题材（建筑、天体、地形地貌等；分子晶体、实体产品三维也算）。**别为"避免 3D"把背景做成静态死平面。两种坍缩都要防**：别不分题材默认"canvas 粒子背景+编辑排版"，也别默认"沉浸漫游+翻页相机翻转"——都是套路。

### 阶段 1 —— 写 plan.md

**第二步必须是写plan.md，不得先生成 deck.html。**
一次 write_file 写出完整规划，包含：

1. **场景判断**：本 deck 用于什么场景、庄重度档位（庄重/自由/题材）、动画密度档位、为何选这个 family——把适配理由写明白。
2. **设计系统**：family 名；精确 palette（`--bg / --ink / --accent / --accent-2` 的 hex）；display + body 字体（含中文字体兜底）；全局背景层方案（**CSS/Canvas-2D 程序化纹理 / 粒子流场 / shader 噪声 / 代码搭 3D 场景 / 每页多场景，按招牌视觉选一**——别条件反射默认某一种）；通用过渡方案。

2b. **招牌视觉（必填一行）**：本 deck 的招牌手法 + 为何契合题材/场景；选了 3D/沉浸/shader 要写明用什么搭。**定了就必须真做出来**（见 §5 招牌兑现）。
3. **页序表**：**与 `outline.md` 的页面逐页一一对应**，每页一行 `NN | 页型 | 一句话内容 | 本页 fancy 手法 | 版面骨架`；NN、顺序、一句话结论必须服从 outline。页型从：封面 / 议程 / 观点 / 数据 / 对比 / 流程 / 案例 / 架构 / 时间线 / 总结 中选，相邻页不重复同一页型；fancy 手法不要超过 2 页雷同。**「版面骨架」一栏先想清楚这页怎么分区、主视觉摆哪、余量留给谁**（如"左叙事右大图 / 居中单 hero / 四等卡一行 / 满屏场景 / 上标题下两栏对比"）——分几区不限，但要让留白是有意的构图、不是排完剩下的边角料（见 §7 布局与留白）；并列项预想好怎么等高对齐。布局在 plan 里想透，初稿就少返工。
4. **素材清单**（如需）：逐页判断"摄影刚需"（§6），需要的写出生图 prompt 草稿与用途。**同组并列对象（N 枚卡片 / 一排同类）整组决策**：把 N 个成员列全，整组选"全真实图"或"全代码绘制"——选真图就 N 个各列一行，绝不能页序表写 4 枚卡片、清单只列 2 张（见 §6）。

规划自检：页数、页序、标题、核心结论和依据是否逐页对应当前 outline？palette 是不是精确 hex？有没有滑回暖米黄/奶油底？页型有变化吗？内容是否只使用 outline 已支持的真实主体与真实数据、没有占位词或新增事实？

### 阶段 2 —— 生成素材（仅当确需真实图片）

按 §6 的纪律生图：生成 → `vision_analyze` 核对（内容对不对 / 色调搭不搭 / 有无文字水印）→ 不合格改 prompt 重生，**绝不硬用**；确切路径记入 plan.md。没有摄影刚需的 deck 跳过本阶段（多数 deck 应该跳过）。

### 阶段 3 —— 写全局骨架 shell（只写骨架，不写页面内容）

一次 write_file 写出**完整可运行但页面为空**的 `$DECK_DIR/deck.html` 骨架（结构契约见 §4）：

- head（Google Fonts / CDN）→ `:root` design tokens → 全部基础 CSS（.deck/.slide/.active/导航 UI/通用 keyframes 库/通用过渡）→ `#bg-layer` 全局动态背景（**完整实现并运行**，不是占位）→ N 个空 `<section class="slide">`（仅含 `<!-- SLIDE NN: 页型 + 一句话 -->` 注释，**不写任何真实内容**；封面页可先放最小标题文字保证 smoke 有内容可看，其余页一律保持空）→ 导航控制器 JS → 页码 + 进度条。

**硬性纪律：骨架这一次 write_file 里，除封面外的 section 必须是空的（只有注释）。不要在骨架阶段就把多页内容一次性写满**——那会让一整批未经单页验证的页面同时落地，错误跨页累积、后面更难收拾，也丢掉了逐页"渲染即验证"的全部价值。

然后 smoke 验证：`render --page 1` + 看图——封面可见、页码/进度条在、背景层在动（看 stdout 的 [static] 与 [console]）、零报错。骨架不过关先修骨架，再进入逐页填充。

### 阶段 4 —— 逐页填充（一页一个循环，不要跳步）

按页序**一页一页**来，每页走完一个完整的"填充→渲染→看图"小循环再进入下一页：

1. `edit` 把**该一页**的空 section 替换为完整内容（页内样式可放 section 内 `<style>` 或按 `#sNN` 前缀写进全局 style；页内 JS 一律注册到 `window.slideInits[N]`，见 §4）。**一次 edit 只填一页**，不要一次 edit 灌进多页内容。
2. `render --page N` → `vision_analyze` 该页截图，按 §5 清单自检。**先渲后看是硬要求**——不渲染就接着填下一页是不允许的。
3. 有硬伤 → 最小修改 → 重渲重看，**每页最多 3 轮**。通过的页不再回看，进入下一页。

为什么坚持逐页：每页在落地的当下就被单独看过、确认无溢出/遮挡/报错，问题在最便宜的时候被发现和修掉；这也是这条技能要教给模型的核心节奏——增量构建 + 即时验证，而非一次写完赌它对。

### 阶段 5 —— 全局复审

`render --all` → 先看 **contact_sheet.png** 一图扫全局：风格有无漂移、相邻页有无雷同、页码连续性、背景全套统一；再核对 render.json：**console_errors 必须为空**；static_pages 逐页核对是否"静得有理由"（§5）。发现问题：单页问题 edit 该 section、只看该页大图；**跨页/系统性问题才改 `:root` token 或共享骨架——但 token / 共享 CSS 会波及所有页（含逐页阶段早已通过、不再回看的前面页），改完必须 `render --all` 复扫全部页确认没把别的页带歪，绝不能只看原问题页。** 全局性的版面 token 调整最适合在这一步做（这里本就 render --all）。行有余力，此时可给关键页加页面级专属过渡/彩蛋增强。

### 阶段 6 —— 收尾

收尾前必须已做过阶段⑤全局复审（`render --all` + 看 contact_sheet），且**最后一次 edit 之后必须再渲染验证过**——没验证就收尾不允许。然后一段简短文字总结：页数、风格 family、最得意的 1–2 个 fancy 点、**如实报告遗留问题**（还有哪页有什么没修掉）。**谎报"全部通过"而实际有硬伤 = 整条产出作废。** 禁止"谢谢聆听/感谢观看"式收尾页套话。

## 3. 场景适配：fancy 的边界

**fancy 是执行质量与视觉冲击的拉满，不是风格的出格。** 给毕业答辩配赛博朋克霓虹，和给发布会配灰白模板，是同一种失败。阶段 0 先把场景庄重度判清楚：


| 档位      | 典型场景                 | 风格候选域                                 | 动画密度                                                                               |
| ------- | -------------------- | ------------------------------------- | ---------------------------------------------------------------------------------- |
| **庄重档** | 学术答辩、政企汇报、医疗/金融/法务报告 | 深色商务、编辑杂志、数据仪表盘等沉稳系（**禁瑞士极简/国际主义排版**） | **演示级**：克制深邃的背景微动效 + 精致入场编排 + 数据动画（count-up / draw-in），页面落定后静帧为常态；禁霓虹故障、粒子轰炸、强干扰特效 |
| **自由档** | 产品发布会、创意提案、科技分享、个人作品 | dazzle 簇放开：赛博、沉浸 3D、极繁、孟菲斯……          | **秀场级**：跨页过渡特效、粒子 / 3D / shader、戏剧化编排放手做                                           |
| **题材档** | 文旅、儿童教育、文化艺术、美食      | 跟着题材气质走（文化→东方美学、儿童→明快插画……）            | 介于两档之间，动效形式贴合题材隐喻                                                                  |


- 庄重档发力点：排印张力、数据可视化做满（真实数据 + 动画入场）、深邃背景层次（缓慢渐变流动、低调几何微动、克制 shader 噪声）、过渡干净利落。**克制 ≠ 低野心**——同样要有招牌记忆点，用精致而非喧闹实现；绝不上霓虹/故障/赛博/3D 奇观。
- **题材档按题材选技术**：**有空间主体的题材**（建筑、天体、地形地貌等）可把空间用代码搭成 **3D 漫游场景**"演出来"（如紫禁城漫游级）；**其余题材**别硬套 3D 漫游场景——但**灵动的 3D/shader 背景层（shader 流场 / 节点球 / 粒子流等）该用就用**，前景按题材选最贴的 CSS/SVG/Canvas-2D 表达；背景别做成静态死平面。
- plan.md 必须写明档位与理由；优先使用 outline 中的场景，未明确时再用 `task_pack.request.query` 里的场景词（"答辩""路演""组会"）判断。

## 4. deck 架构契约（骨架必须满足）

```
<body>
  <div id="bg-layer"></div>            ← 全局动态背景层（canvas/Three.js/CSS 动画）
  <div class="stage">                  ← 居中容器，position:fixed; inset:0; flex 居中
    <div class="deck" id="deck">       ← 固定 1280×720 设计画布，overflow:hidden
      <section class="slide active" data-slide="1">…</section>
      <section class="slide" data-slide="2">…</section>
      …
      <div class="hud">页码 + 进度条</div>
    </div>
  </div>
</body>
```

1. **design tokens**：所有颜色 / 字体 / 间距 / 字号阶梯在 `:root` 定义，全文只用 `var()` 引用，不写散落的裸 hex / 裸数值。
  - 颜色字体：`--bg/--ink/--accent/--accent-2/--font-display/--font-body`。
  - **版面 token（骨架期就定、全页共享 → 改一处全页生效，这是"改根因、不逐页打地鼠"的地基）**：安全边距 `--safe-x/--safe-y`（如 64/56px，内容不越此边距，HUD/页码可贴边）；成体系的间距档 `--gap-s/-m/-l`（如 12/24/48，元素间留白只从这组取，别随手写散值，留白才有节奏）；最小可读字号 `--fs-min`（约 20–22px，正文/标注永不缩到它以下来塞内容——宁可拆页/删内容）。巨字用 `clamp(min, Nvw, max)` 兼顾戏剧性与上界、防出界。**这些版面 token 在骨架期就要定准并保持稳定**，逐页填充都在其约束内工作；中途若必须改 token，它会牵连所有页（含前面已过的页），须按 §5 修复纪律全局重验。
2. **固定画布 + 等比缩放**（根治溢出/裁切/比例失真）：`.deck{position:relative;width:1280px;height:720px;overflow:hidden}`，内容一律按 1280×720 用 px 布局与定字号；JS `fitDeck()` 按 `Math.min(innerWidth/1280, innerHeight/720)` 缩放 deck，监听 resize。**绝不混用单位**（最忌 deck 按 vh 定尺寸、字号按 vw 定——letterbox 屏下字体撑爆画布）。
3. **一次只显示一页**：`.slide{position:absolute;inset:0;opacity:0;visibility:hidden;pointer-events:none}`，`.slide.active` 三项全开。**非当前页必须彻底不可见**（只切 opacity 不切 visibility 会互相透叠）；任一时刻有且仅有一页 active；给单页加自定义样式时**绝不要改 position**（脱离堆叠会把该页压成 0 高、canvas 黑屏）。
4. **导航控制器**（骨架期写完整）：
  - 键盘 ArrowRight/Left、Space、PageDown/Up 翻页；`window.addEventListener('load', () => window.focus())` 抢焦点（iframe 内键盘可用的前提）。
  - 翻页时把 `.active` 切到目标页（渲染脚本靠 `.active` 类识别当前页，这是硬契约）、更新页码与进度条、对目标页调用 `window.slideInits[N]`（见第 6 条）、派发 `slidechange` 事件。
  - **必须支持 URL 参数直跳**：`new URLSearchParams(location.search).get('slide')` → 初始化时直接跳到第 N 页（1-based）。渲染脚本靠它做单页 O(1) 渲染，缺失会显著拖慢自检并在 stderr 告警。
5. **全局背景层**：`#bg-layer{position:fixed;inset:0;z-index:0;pointer-events:none}`，deck 容器 `z-index:1`。背景动画**骨架期完整实现**；复审期只准调参（颜色/密度/速度），不要重写。事件监听挂 `window`（背景层不可交互），尺寸用 `window.innerWidth/Height` + resize 监听。

5b. **背景-前景易读性（全屏 3D / 重动态背景必守）**：**别靠全局压暗背景救正文**——会同时杀死封面/章节页的 3D。改用：

- **按页型分级**：封面/章节页放开背景；内容/数据页让背景局部退让——降该页粒子/高光（微尘 `opacity→~.25`、减弱 glow），相机别把 3D 主体摆在前景图解同象限。
- **前景图解自带底板**（页内有 SVG 图解 / canvas / 密集小字 / 数据表）：首选**软边径向 scrim**——`radial-gradient(70% 70% at 50% 50%, rgba(<bg>,.85), rgba(<bg>,.55) 60%, transparent)`（用 `--bg` 同色），中心托住、边缘渐隐、3D 仍从四周透出、不切硬框；密集页用**卡片 + `backdrop-filter:blur(6px)`**。**绝不裸 `<svg><g stroke>` 直接挂 `.slide`**（背景会从笔画缝隙透上来吞掉正文；详见 fancy-cookbook「背景-前景分离 scrim」）。
- 描线 `stroke-opacity ≥ .5`、线宽 ≥ 1.2px；淡色文字/细线只在已有 scrim 处用。

1. **per-slide JS 惰性注册**：页内脚本一律写成 `window.slideInits = window.slideInits || {}; slideInits[N] = () => {…}`，由导航控制器在该页激活时调用（已初始化的做幂等保护）。**禁止顶层立即执行的代码去摸其他页（或尚未填充的空 section）的 DOM**——这是空骨架阶段渲染不报错、逐页填充互不踩踏的关键。
  - **骨架的 `<head>` 顶部（任何页内 `<script>` 之前）必须预置一行 `window.slideInits = window.slideInits || {};`**——保证任何页内脚本执行时它必已存在，根治"页内 script 早于主控制器执行 → `Cannot set properties of undefined`"的时序坑；且 `goto()`/`?slide=N` 直跳要在所有 `slideInits[N]` 注册之后才调用。
2. **入场动画契约**（动画与截图自检不再矛盾的官方解法）：每页入场编排总时长 **≤2s**，全部入场动画必须 `animation-fill-mode: forwards`（或 both），**最终态 = 完整内容**（渲染脚本在 ~2.6s 截图，截到的就是最终态）。持续型动画（背景粒子、呼吸光效、HUD 滚动）不受 2s 限制。禁止停在 boot/loading/打字机未完成态。
3. **通用过渡**归导航控制器、骨架期写好：class 驱动（`.slide.leaving` / `.slide.active` + transition/keyframes），默认给一套有戏剧性的编排（位移 + 透明度 + 模糊/裁切的组合，配 cubic-bezier 缓动）。页面级专属过渡（粒子重构、shader wipe 等）是复审期的可选增强。
4. **性能预算**：动画只动 transform / opacity / filter（不动 layout 属性）；canvas 粒子总数与 Three.js draw call 克制（见 §8 粒子参数表）；持续动画用 requestAnimationFrame 且页面不可见时无须暂停（渲染检查依赖动态可见）。

## 5. 渲染自检清单

每页 `render --page N` + `vision_analyze` 后对照：

**必修——每页都要做到位，口径是"配得上 fancy 第一目标"，不是"过线就收手"。下面 1–12 是"读不了 / 看不懂"类硬问题，最先清零：**

1. 溢出 / 裁切——内容越过 1280×720 画布或容器边；巨字被裁半截；固定小盒文字撑破。`overflow:hidden` 会**静默裁切不露白边**——别以为没出血就没事，主动核对页脚/页码/正文首末行/图表轴标签有没有被切掉。
2. 遮挡压盖——装饰元素 / 大数字 / 浮层压住正文；**SVG/Canvas 内部装饰线、光晕、连线画在文字之上**（绘制顺序问题：文字要最后画、或给文字加描边/底板托住，见 §7 第 6 条）；负字距导致字形粘连（中文大标题尤其）。
3. 占位残留 / 空壳——空图表容器、KPI 全 0、只有表头没有数据行、坐标轴没曲线。
4. 破图破表——img / canvas / Three.js / ECharts 没真正渲出来（黑块、空白区）。
5. 中文豆腐块——字体没加载（中文必须 Google Fonts 引入并放进所有显示中文的 font-family 链）。
6. 对比不足——文字在其背景**或所压的插画 / 线条 / 渐变**上看不清；深色风格同样要保证可读。
7. 配色出界——palette 之外的颜色乱入（ECharts 默认色、生成图跑色未调和）。
8. **console error ≠ 0**——看 stdout 的 `[console]` 行与 render.json；JS 报错常意味着后续动画/翻页全挂。
9. 入场动画未到最终态——截图里文字半透明 / 位移中途（说明动画 >2s 或缺 fill-mode: forwards）。
10. **网格底纹背景**——出现方格纸 / 蓝图网格 / 透视网格地面（地平线网格）/ 规则点阵 / Three.js GridHelper 作为背景，**一律算硬伤要删掉**（见 §7 第 10 条）。
11. **前景裸压动态背景**——含 SVG 图解 / 密集标注小字 / 数据表的内容页，前景没有 scrim 软底板或 `backdrop-filter` 卡片、直接浮在 3D / 粒子背景上导致正文或图解看不清，**算硬伤**。修法见 §4 第 5b 条：给前景加软边径向 scrim 或卡片底板 + 降该页背景密度，**不要全局压暗背景**。
12. **同组图源混用**——一组并列同类对象（一组美食 / 物产 / 展品 / 人物…）里部分用真实生成图、部分用 SVG 代码绘制，图文风格断裂，**算硬伤**（见 §6：整组统一，缺图补生或整组改代码）。

**招牌兑现（硬纪律）**：plan.md 第 2b 条定的招牌视觉必须在 deck 里**真正实现**。**严禁把它降级充数**——定了"代码 3D 场景 / immersive_3d / 沉浸"，deck 就必须真有 Three.js 3D 场景（几何体 + 光照 + 相机运动），用 2D canvas 粒子假装"沉浸感"是不合格的；要么把它补成真 3D，要么诚实地把 plan 改成你真做出来的模式（不要谎报）。**用 3D 当招牌时，自检必须看"3D 主体本身能不能认出是什么"**（不是只看 2D 覆盖层）——暗底 + fog 容易把 3D 主体糊成黑块、内容全靠 2D 层硬扛，那是招牌名存实亡；糊了就加轮廓光/提亮/减 fog/换机位。

**[static] 是信号不是硬伤**：stdout 出现 `[static] page N` 表示该页在采样窗口内无可见动态。自问：这是**有意识的设计**（庄重档的数据密集页、节奏上的安静页），还是偷懒？静得有理由 → 忽略并继续；说不出理由 → 按本页的密度档位补恰当的动态（背景微动 / 数据动画），**不是无脑堆粒子**。

**版面卫生（同样必修，别当"软伤"跳过）**：留白、对齐、层级、字距和上面的出界/遮挡一样要修到位——

- **留白失衡**：余量渗漏成单边 / 单角的意外死白（说不出理由的空白就是 bug）；内容钉在顶上、底部塌空；并列栏 / 卡片不等高造出锯齿白。按 §7「布局与留白」修：余量要么摊匀、要么有意聚拢，并列项对齐到共同基线 / 等高。
- **对齐错位**：同页元素没对齐到共同网格 / 基线；混用居中与左对齐。
- **层级混乱**：视觉重量没主次，该跳出来的没跳出来。
- **字距**：中文大标题负字距粘连，或全大写小标签该放宽没放宽。

**只有纯主观的边际优化（某处呼吸再大一点更舒服、某个缓动再顺一点）才是"有余量再打磨"。** 把版面卫生当软伤一跳，正是 deck 显得"AI 糙"的主因——它和读不读得清同等重要。

**deck 级自评（全局复审时）**：

- **招牌视觉野心**：招牌是否配得上题材、是否平庸套路？**两种套路都算不合格**：无脑"粒子背景+编辑排版"，或不分题材硬套"沉浸漫游+相机翻转"。2D/CSS 有创意=满分；关键是技术选得贴题。**再查背景是不是"活"的**——退化成纯静态渐变就是丢分（除非前景自带持续动态，如极繁拼贴）；灵动的 3D/shader 背景层适用于任何题材、别因"非空间"就不敢上。
- 整套至少有 **2–3 个高光记忆页**（戏剧性的封面、惊艳的数据页、出人意料的过渡……）；允许安静页存在制造节奏——**页页高潮 = 没有高潮**；风格 / 配色 / 字体全套一致不漂移。

**修复纪律**：每页最多 3 轮 edit→render→看图，每轮只做能消除问题的最小修改；**禁止用"删掉动画 / 背景 / 特效"换取过检**——修复是修 bug 不是降级，确需移除某特效必须在收尾总结里说明理由；3 轮后仍有残留就保留最好一版并如实记录。**同一毛病多页复发（留白 / 对齐 / 字距 / 间距系统性偏），改 `:root` token 或共享骨架这个根因，别逐页 edit 打地鼠**——既改得准、又省返工与上下文。**但务必记住共享 token / CSS 的爆炸半径是全局的，会改动所有页（含前面早已通过、不再回看的页）**：阶段4 逐页填充时优先用 `#sNN` 页内覆盖做**局部**修复，不要因为某一页就动共享 token；确属系统性、非动 token 不可时，**改完必须 `render --all` 复验之前通过的页有没有被带歪**（别只看当前页就放行）——这类全局改最好攒到阶段5全局复审一并做（那里本就 render --all）。最稳的做法是阶段3 骨架期把版面 token 定准，让逐页填充都在固定约束内工作、根本不需要中途改它。

## 6. 配图与生图（image_generate 可用时）

**默认代码绘制。** 图表 / 数据可视化 / 抽象概念 / 几何装饰 / 图标 / UI 元素**严禁生图**——这些用 SVG / Canvas / CSS 画，这是本 skill 的看家本领。生图用于**需要真实图片的场景**：真实实物、自然风光、食物等等。**名家艺术画作、真实人物肖像尤其必须生图，严禁用 SVG/CSS 代码模仿**——代码硬画写实人脸 / 名画必然失真崩坏。要不要用、用几张，由内容的写实刚需自行判断（不刻意凑数，也不为省事回避）；确需的图在阶段 2 一次性生成。

- **prompt 模板**（每张都要带上 palette 与质感词，锁住色系）：
`"<主体描述>, <构图/视角>, <palette 色名词> palette, low saturation, editorial photography, <光线/情绪词>, no text, no watermark"`
其中 palette 色名词来自 plan.md 配色（如 "deep navy and muted gold"）；同一 deck 的所有图复用同一组色彩短语。宽高比按用途选（全页背景 16:9，半幅配图 4:3 / 3:4）。
- **生成后必核对**：`vision_analyze` 看内容是否对、色调是否贴 palette、有无文字/水印/多余人物；跑色就改 prompt 重生，救不回再用 CSS 压色罩（duotone / 半透明主色叠层）。
- **嵌入时二次调和**：`filter: saturate(.85) contrast(1.05)` 微调 + 用 `--bg` 的 rgba 做渐变蒙版（文字侧深、画面侧浅）+ 暗角，把图收进 deck 色域；文字区必须保证可读。
- **鼓励 fancy 化用法**：生成图不只是 `<img>` 平铺——clip-path 异形裁切、mask-image 做 reveal 入场（遵守 ≤2s + forwards）、mix-blend-mode 与背景层融合、作为 Three.js 纹理。让真实图片也成为视觉特效的一部分。
- **同组并列对象图源必须整组一致（硬规则）**：同页里网格 / 卡片墙 / 一排同类的对等同类项（一组美食 / 物产 / 展品 / 人物 / logo / 产品…），**要么全真实图、要么全代码绘制，禁止同组混用**。决定生图就为该组每个成员都生；做不到全员就整组退回代码——不许"有图用 `<img>`、缺图用 `<svg>` 顶"（组内图文割裂比整组代码更伤）。渲染该组前先确认成员图片都已就位，缺谁补生谁或整组改代码。**自检**：每组 N 个成员，要么 N 张真图全到、要么 0 张全代码；页序表"N 枚卡片"= 素材清单该组图片行数。

（若工具列表里没有 image_generate，跳过本节，一切视觉均代码绘制。）

## 7. 美学底线（反 AI slop）与绚哲学

每一份 deck 都必须有性格、有立场，绝不能是套路化的 AI 设计：

1. **字体**：禁止默认 Inter / Roboto / Arial / Open Sans / Lato / Space Grotesk / 系统字体；display + body 搭配、与主题契合；不要言必复古衬线、不要反复用 Fraunces / Cormorant / Playfair。font-family 末尾必须带通用兜底（sans-serif / serif / monospace）；数字 / 数据读数用确含数字字形的等宽字体（JetBrains Mono / IBM Plex Mono 等）。**中文大标题必须用含完整中文字形的字体（Noto Sans SC 800/900 等），要冲击力就叠多层 text-shadow / `-webkit-text-stroke` 描边**——英文 display 字体（Bowlby / Bangers）和多数 ZCOOL 装饰体中文字符集不全，套上去大标题会缺字/破碎。

1b. **渲染安全（字符/图标）**：① 数学公式禁用花体 `𝒩` 与组合 Unicode（`ε̂`/`ε̃`），无头渲染成豆腐块——改 `<sub>/<sup>` 或纯 ASCII；② 核心图标 / 品类符号用 SVG，**不用 emoji**（emoji 字体常缺失 → 整片空白）。
2. **配色**：明确主色 + 尖锐重音、hex 精确、非平均分布；禁紫粉渐变白底 / 通用蓝绿渐变 / 无聊灰阶。
3. **反米黄**：除非 outline 或 `task_pack.request.query` 明确要求，禁止暖米黄 / 奶油 / 宣纸 / 象牙（#FBF7F0 #F5F1EA #ECE3D0 这类 R>G>B 暖白）做主背景，禁止做旧纸张 / 茶渍噪点 / 复古手稿基调。干净的纯深色 / 冷白 / 饱和品牌色都完全 OK。
4. **中文字体覆盖**：含中文必须 Google Fonts 引入中文字体（Noto Sans SC / Noto Serif SC / ZCOOL XiaoWei / Smiley Sans / LXGW WenKai 等按风格选）并放进所有显示中文的元素的 font-family 链；禁止只依赖 PingFang SC / Microsoft YaHei。整页语言自然统一，不做中英并行两套文本。
5. **形态贴合**：deck 是幻灯片不是网页应用——禁止浏览器式顶栏 / 侧边导航 / 贯穿全场的常驻控制台外壳（LIVE FEED / SESSION / VERSION / 脉冲指示灯这类 app 状态件）；元数据只放页脚或封面。
6. **内容真正画出来**：图表用 outline“内容与依据”中已有的真实数值直接画出图元；首屏即呈现真实内容；hero / 封面严禁"巨幅纯色块只配一两个字"——要有清晰主标题 + 说明文案 + 视觉焦点。内容要有 outline 已支持的真实主体与真实数据，严禁为填满页面编造数字；证据不足时返回 Entry / Story，不使用占位词冒充完成。

- **装饰永不压盖正文**：HTML 层用 z-index 阶梯（背景 0 / 内容 1–10 / 浮层 20 / HUD 50），装饰绝对元素 `pointer-events:none` 且 z-index 低于同区文字。**SVG / Canvas 内部没有 z-index，只认绘制顺序——文字必须最后画（在装饰线、光晕、连线、节点之上）**；若文字不可避免压在图形 / 插画上，给它加 `paint-order:stroke` + 与底色同色的浅描边，或垫一块半透明圆角底板 / 径向 halo 托住，确保任何角度都读得清（这正是"插画里小字被线条吃掉"的根治法）。

1. **布局与留白（留白是构图的一部分，不是排完剩下的边角料）**——不绑固定模板，按这几条判据排，任意区数 / 任意版式都适用：
  - **先划安全区，区内自由构图**：内容不越 `--safe-x/-y`（§4），这是唯一硬边框；框内分几区随题材定（1 区 hero / 2 栏 / 3–4 卡 / 拼贴 / 满屏场景都行），别套死"几区"模板。
  - **每块余量都要有归属**：空白要么成体系地分布在元素之间（间距只从 `--gap-*` 档取，节奏统一），要么有意聚成一处做呼吸 / 强调；**禁止余量渗漏成单边或单角的意外死白**。自检视角：把空白当成一个看不见的块——它该有位置感和理由，说不出理由就是 bug。
  - **并列项对齐到共同基线 / 等高**：一排卡片 / 两栏内容用 `align-items:stretch` 或等高配方，消除"一栏比另一栏矮"造出的锯齿死白；别用 `flex-start` 放任不齐。
  - **内容量驱动密度**：撑不满 → 放大主体 / 加呼吸 / 合并页，**不是钉在顶上塌出底白**（禁单个 `margin-top:auto` 钉底；满屏 flex 列用 `justify-content` 摊匀纵向余量）；撑破 → 拆页或降到 `--fs-min`，不是硬塞到溢出。
  - **不溢出的硬底**：固定容器 `overflow:hidden + 子 min-width:0`，或 `fit-content` / 允许换行，预留 ≥15% 余量；超大 display 标题设 max-width 允许换行、禁 `white-space:nowrap` 硬撑；`line-height<1` 的巨字按墨迹盒实算高度、与邻块留 ≥24px。
2. **覆盖层与光标**：canvas 拖尾淡出用 `clearRect` 或 `destination-out`，严禁低 alpha `fillRect` 整屏铺（累积成不透明遮罩盖住正文）；自定义光标 z-index 不高于正文且 `pointer-events:none`。
3. **不可遗忘点**：整套 deck 至少 2–3 处让人记住的细节——戏剧性开场、独特的数据动画、出人意料的过渡或彩蛋。
4. **禁网格底纹背景**：方格纸 / 蓝图网格 / 透视网格地面（地平线网格）/ 规则点阵，以及 Three.js `GridHelper`——**一律不用做背景**，这是被严重滥用的 AI 套路，哪怕低透明度单层也不行。需要纵深/质感请用：渐变光晕、shader 噪声、粒子流场、径向暗角。（**只禁"当背景平铺的视觉网格"**；CSS Grid 布局即 `display:grid` 的版面排布不受影响。）
5. **不走套路充数**：别不分题材默认"canvas 粒子背景+编辑排版"，也别不分题材默认"沉浸漫游+相机翻转"——两种都是套路。按题材选最贴的技术（见 §0 招牌视觉），2D/CSS 有创意同样满分；但灵动背景层（3D/shader/粒子流）广泛适用，别把背景做成静态死平面。

**绚哲学——尽可能绚，但绚得其所**：在场景档位允许的密度内做满视觉表现力——持续微动的背景、视差 / 磁吸 / 扰动的鼠标响应、形变 / 光晕的 hover、backdrop-filter / mix-blend-mode / mask-image / clip-path、preserve-3d 空间深度、粒子与程序化纹理、staggered reveal、大字号排印张力（字距不得让字形粘连）。**该上重型就上、别因难调试回避**：**3D/shader 灵动背景层（广泛适用，尤其科技/抽象/数据/网络）**、代码搭 3D 漫游场景（空间主体题材）、多场景沉浸、极繁拼贴都是加分项；但重型手法要**服务题材**，不是为炫而炫——2D/CSS 把题材表达透了同样是顶级 fancy。背景默认就该持续微动，纯静态渐变是丢分。绚 ≠ 杂乱：再密集也要层级清晰、配色有立场、贴合场景档位。

## 8. 工程避坑（常见 bug，写代码前过一遍）

1. **JS 函数引用顺序**：顶层立即执行的主控函数不要直接调用尚未注册的全局函数；对可能未定义的加 `if (typeof fn === 'function')` 防御——首行 ReferenceError 会杀掉后续全部脚本（翻页/动画全挂）。
2. **Three.js 锁 r128**：`https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js`（UMD 全局最稳）；OrbitControls 用 `three@0.128.0/examples/js/`，不要 r150+ 的路径（已废弃）。`ShaderMaterial({vertexColors:true})` 会自动注入 `attribute vec3 color`，vertexShader 里不要再声明一遍（redefinition → 粒子全黑）。
3. **Canvas / Three.js 尺寸与 DPI**：`renderer.setPixelRatio(devicePixelRatio)`；`setSize(w, h)` 不传第三参数；取尺寸用父元素 `getBoundingClientRect()`（canvas 自身初始可能为 0）并用 ResizeObserver 监听。
4. **粒子参数速查**（球面 starfield、相机 z≈400、AdditiveBlending）：偏暗 3000 粒 / sz 0.5–2.5 / 投影系数 300 / alpha 1.0 / 遮罩 0.85；适中 7000 / 1.2–4 / 550 / 1.3 / 0.78；偏亮 12000+ / 2–6 / 700 / 1.8 / 0.4。原则：封面要震撼（透明背景 + 多彩 + 高 alpha），内容页要背景化（半透明遮罩 + 冷色单调）。
5. **ECharts 配色**：所有系列色从 `:root` token 取，禁用 ECharts 默认色板；图表初始化放进 `slideInits[N]`，容器要有确定尺寸。
6. **键盘事件**：监听挂 `window`；`load` 时 `window.focus()` 抢焦点（deck 常被嵌 iframe 预览）。
7. **增量填充的幂等**：`slideInits[N]` 内做"已初始化"保护（重复激活不重复建 canvas / 不重复绑监听）。
8. **代码搭 3D 场景**（选了沉浸 3D 招牌时）：用参数化几何体（Box/Plane/Cone/Torus/Sphere 组合）拼出真实场景 + Ambient/Directional/Point 三类光，全 deck 共用一个常驻场景、每页一个相机机位、翻页时相机沿弧线 lerp 巡游（注视点必须同步插值）。完整范例见 `fancy-cookbook.md`「代码搭建 3D 场景」+「单一 3D 世界相机航点运镜」。骨架期就把场景与相机搭起来跑通，逐页只调机位与该页 HTML。
9. **避开封面调试黑洞**：你看不到 DOM/console、只能靠截图猜，所以**封面/hero 的视觉主体优先用大 SVG**；Three.js 用在背景（粒子/星场/上面的场景模板），别在封面现搓未验证的自定义几何（极易陷进猜谜式长链返工）。**大图 hero 用 `<img>` + `object-fit` 而非 `background-image`**——无头渲染里大图 `background-image` 常在截图时还没解码出来、整页近黑。

## 9. references

- `references/style-families.md` —— 风格家族库：气质 / 适用与禁用场景 / palette 示例 / 字体方向 / 该风格下 fancy 怎么发力。阶段 0 必读。
- `references/fancy-cookbook.md` —— 技法配方：入场动画 / 跨页过渡 / 全局背景 / 交互彩蛋，含核心代码模式与参数安全范围。阶段 0 选型时读。
