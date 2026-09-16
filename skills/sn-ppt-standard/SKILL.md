---
name: sn-ppt-standard
description: 仅在 `sn-ppt-entry` 与 `sn-ppt-story` 已准备绝对 `DECK_DIR` 和 `outline.md` 后使用；生成每页独立 HTML（1600×900）、渲染 PNG、逐页讲稿、`present.html`，并按 `static_postprocess` 选择生成由 Standard 自有 exporter 转换的 PPTX。**`present.html` 始终是必交付产物，缺失即技术故障，不得交付；`static_postprocess` 含 `pptx` 时 PPTX 同为必交付产物（缺一即技术故障），且只能由 Standard 自有 exporter 生成；仅当用户明确要求只要 HTML（`static_postprocess` 为 `[]`）时，PPTX 才可不交付。**
---

# sn-ppt-standard

把本文件当作**路线图**，不要当作需要一次背完的规范全集。只读取已准备任务的 Entry/Story 交接、该路径要求的 reference 和职责卡。

## Box-Agent 兼容入口

当当前 harness 暴露 `sub_agent`、`inspect_images`、`generate_image`、`bash` 等 Box-Agent 原生工具时，开始任何制作动作前必须完整读取 `references/box-agent-tool-contract.md`。该契约只覆盖工具名称、参数、脚本路径、委派方式和权限边界；本文件及各职责卡的事实、设计、质量和交付标准仍然有效。委派任何角色时，都要在 `task` 中显式要求其先读取同一契约与自己的 `subagents/<role>.md`。

## Hermes 环境等效工具

Hermes 不暴露 Box-Agent 工具名，但提供等价能力。在 Hermes 宿主中，正文下文中出现的
`bash` / `inspect_images` / `generate_image` / `sub_agent` 调用一律按下表翻译后执行，
且无须读取 `references/box-agent-tool-contract.md`（该契约仅用于 Box-Agent harness）：

| Box-Agent 写法（正文） | Hermes 等效工具 | 翻译要点 |
| --- | --- | --- |
| `bash(command, timeout)` | `terminal(command, timeout)` | 参数直接对应；Hermes 专属参数（workdir/pty）按需使用 |
| `inspect_images(image_paths=[...], instruction=..., strategy="native")` | `vision_analyze(image_url=<单张路径>, question=<instruction>)` | 每张图一次调用；`strategy` 参数 Hermes 无，忽略 |
| `generate_image(prompt, output_path, size, watermark=false)` | `image_generate(prompt, aspect_ratio=<按尺寸取>)` | 无 `output_path`，生成后回读返回路径验证落盘 |
| `sub_agent(title, task, required_tools, write_scope, budget)` | `delegate_task(goal=<task>, context=<背景>)` | 用 Hermes 参数形态；自包含 task、语言合同、绝对路径与产物双读验证的要求不变 |

委派仍要求子任务自包含、携带语言合同与职责卡绝对路径，并用 `read_file` / `search_files`
验证声明的产物；正文的阶段划分、质量标准与交付要求不因宿主变化而放宽。

## Entry / Story 输入契约（最高优先级）
本 Skill 不接收裸 query，不自行创建任务目录。只接受绝对 `DECK_DIR`，且必须存在 `task_pack.json`、`info_pack.json` 和 `outline.md`。
`choices.output` 必须为 `static_html`，且 `ppt_mode` 必须为 `standard`。开始和恢复时重新读取磁盘上的 `outline.md`；不得自行 Research、重复解析材料、改写 outline、增删页面、重排页序或新增事实。输入不满足时返回 Entry。

## 1. 所有模式共享的合同

### 1.1 Orchestrator 的职责与边界

Orchestrator 只负责：**读取 Entry/Story 交接、规划、委派、合并、验收和确定性收尾**。

- 可写：`plan/`、`base.css`、知识汇总和构建产物。
- 不直接写：`slides/slide_NN.html`；页面由 Slide 或 Review 修改。
- 不伪装工具能力，不把计划动作写成已完成动作。
- 每个 subagent 必须有显式 label；失败、超时或未自然收尾的结果不得当成完成品。
- `sub_agent(title, task, skills, required_tools, files, write_scope, budget)` 负责委派；其返回的结构化 contract、artifact paths 与 `handoff_path` 是父级交接真相，Orchestrator 不读取子 Agent 的 `messages.json`、`tool_log.json` 或 system/tool 快照来轮询进度。父级负责通过 `inspect_images` 完成视觉检查，以及通过 bash、render、build 和 export 完成确定性收尾。

### 1.2 角色

| 角色 | 数量与时机 | 唯一职责 |
| --- | --- | --- |
| Image | 按素材量并行 | 获取或生成位图素材，返回实际路径 |
| Slide | 新建或复杂编辑时按设计亲缘页组并行 | 只制作/重做自己的页组并完成组内像素闭环 |
| Review | 首次验收 1 个，修复后最多复验 2 次；简单编辑时也是执行者 | 先诊断、后集中修复、批量重渲和最终讲稿收口 |

所有角色开工前完整读取自己的 `subagents/<role>.md`。任何选中的文件或章节出现截断提示时，续读到结束；**未被路由命中的 reference 不读**。

### 1.3 语言与能力

开始前锁定：

- `response_language`：过程与最终回复语言；
- `deliverable_language`：屏显、规划和讲稿语言；
- attachments、web、真实图片获取、图片生成、渲染、vision、写文件等能力状态。

默认采用用户 query 的主要语言；用户明确指定交付语言时单独覆盖。只能规划实际可用的能力。
`inspect_images(image_paths=["/absolute/path/to/slide_NN.png"], instruction="复述第一眼焦点、阅读路径、主要视觉载体、溢出与裁切", strategy="native")` 由当前角色使用；视觉判断、问题账本和看图后的回复使用 `response_language`，不得因模型默认语言切换，屏显原文与专有名词可保留原语言。

### 1.4 工作区真相源

```text
task_pack.json
info_pack.json
outline.md
plan/design-brief.md
plan/deck.md
plan/slide_NN.md
base.css
assets/
slides/slide_NN.html
renders/slide_NN.png
speech.md
present.html   ← 必交付产物：由 `deck.py build` 生成，缺失即技术故障
`<DECK_DIR>/<DECK_ID>.pptx`   ← 必交付产物（`static_postprocess` 含 `pptx` 时）：只能由 `scripts/export_pptx/html_to_pptx.mjs` 生成
```

`outline.md` 是页面事实、页数、页序、标题、结论和内容关系的真相源；`grounded-knowledge.md` 仅是 Entry/Story 生成的研究汇总，Standard 只读，不得覆盖 `outline.md`。
`design-brief.md` 是视觉真相源；
`slide_NN.md` 是页面内容合同；
`base.css` 是全局设计系统；
最终判断必须基于最新 PNG，而不是只看 HTML。

### 1.5 Reference 路由

| 场景 | 读取 |
| --- | --- |
| 场景定调 | `design-rules.md` §T1–T3、§1–3 + 命中的主题节；`design-styles.md` 目录 + 一个风格家族 |
| 全局与逐页规划 | `planning-contract.md`；每页只读 `layout-patterns.md` 对应页型 |
| 编辑现有 deck | `editing-contract.md` |
| Slide | 自己的逐页计划、`base.css`、`quality-checklist.md`“一、单页检查”与本页命中章节 |
| Review | 完整读取 `quality-checklist.md`：先用“一、单页检查”核对视觉语义，再做“二、整套检查”和“三、可机核 lint 项” |

字体只在默认角色不足或场合敏感时读 `fonts.md`。不要在开工前扫描所有 design、style、layout、font 文档。

无论是否读取 `fonts.md`，中文眉签、部门名、页脚、来源和元数据都不得使用等宽字体或拉丁 ALL CAPS 的疏字距：使用 `--font-sans` / `--font-serif`，字距保持 `0–0.03em`。`--font-mono`、`--tracking-caps`、`.is-latin-label` 只用于纯拉丁技术标识、代码、坐标和真实编号。

同一句中文标题、结论或标签必须使用同一字体家族；强调词只通过颜色、字重、字号或下划线建立层级，禁止把其中几个字换成卡通、手写或另一套展示字体。**全册字体家族总数 ≤ 3 且必须全册统一**：同一角色在每页都用同一家族，不因页面题材临时换字体；严谨型收敛到 1–2 族。字体选择服从场景与 Style Lock——中文正文/表格/页脚/眉签一律 `--font-sans`（严谨衬线可 `--font-serif`），**中文绝不放进 `--font-mono`**（IBM Plex Mono 无中文字形，会回退成卡通体）；`--font-mono` 只服务纯拉丁代码、坐标、ID。`playful`、圆趣、手写和书法字体只有在主题与受众真正支持时启用（至多占那 3 族里的 1 个点缀位），并在对应元素加 `.is-expressive-type` 或 `data-type-intent="expressive"`，让渲染检查确认这是有意选择。

### 1.6 视觉媒介优先级

按内容选择媒介：

1. 真实人物、地点、产品、事件：真实照片；
2. 氛围、隐喻、故事场景、视觉主画面：生成图或高质量位图；
3. 数据：ECharts；
4. 大型流程、架构、机制、关系示意：**Canvas 绘制几何 + HTML 文字层**，或“无文字图片 + HTML 标注”；
5. SVG：仅用于 icon、logo、箭头、标记和小型装饰。

普通内容页只要存在人物、地点、产品、作品、活动、体验、自然/城市环境、故事场景或情绪画面等可见主体，优先让一张有分量的真实/生成位图成为主视觉，而不是用彩色块、图标或抽象线框替代。配图数量服从叙事，不机械凑数；但能够增加识别、证据、临场感或情绪价值的位图机会不得静默放弃。

**默认禁止把手写 SVG 当作 hero、半屏/全屏主视觉或大型示意图。**SVG 只承担小型辅助图形；复杂的非位图主视觉若确需程序化表达，优先使用 Canvas 几何 + HTML 文字层。只有用户明确要求矢量交付，或必须复用用户提供的准确矢量资产时才例外。详细实现见 `design-rules.md` §5 和 `layout-patterns.md` 的 Canvas diagram 章节。

## 2. 新建 PPT

### 阶段 0：解析任务

1. 读取 `task_pack.json`、`info_pack.json` 和当前磁盘 `outline.md`；页数、页序、标题、结论、事实与内容关系全部以 `outline.md` 为准，场景、受众、材料与 Research 路径以 task/info pack 为准。
2. 锁定语言、能力、附件清单和交付范围，不向用户追问非阻塞偏好，并在规划中显式记录合理假设。
3. `static_html` 新建流程不启动 Research 或 Material，只读取 Entry/Story 已生成的产物；若 required Research 报告缺失则返回 Entry，事实不足时不编造数字、不改写 Story，`grounded-knowledge.md` 仅作为生产汇总。

### 阶段 1：按需接地

#### Grounding gate

Entry/Story 产物交接后，Orchestrator 先校验 `info_pack.json`、Entry/Story 的 Research 报告和当前磁盘 `outline.md`；缺少必需报告时返回 Entry，不能在 Standard 内重新 Research、解析材料或改写事实。校验通过后再写唯一 `plan/grounded-knowledge.md`，并用 `read_file` 验证文件完整；完成前不得进入 `design-brief.md`、Style Lock 或逐页规划。文件只整理已交接的用户事实、外部核验、编排器假设、示意、冲突和未确认项，不添加无来源的新事实。

附件提供的是**事实与可复用素材边界，不是默认设计上限**。合并时同时整理材料里的可复用页图、内嵌图片、图表结构和品牌线索；随后在 `design-brief.md` 明确 `material_visual_mode`：`facts-only`、`visual-reuse`、`style-reference` 或用户明确要求的 `faithful-restyle`。对每张图片附件另写 `attachment_visual_map`，决定 must-show / reuse / reference-only / omit、上屏页与处理方式；论文整页视觉与页内命名 Figure 必须区分为 `page-facsimile` 和 `figure-crop`。这项判断独立于外部搜图/生图的 `image_opportunity`。除 `faithful-restyle` 外，不继承附件的小字号、密集表格、普通文档排版或低质量视觉；仍按听众、场合和叙事重新定调。

### 阶段 2：场景定调与 Style Lock

1. 按 Reference 路由读取视觉规则，不扫描全库。
2. 先锁定 `scene_register`（庄重汇报 / 编辑叙事 / 产品发布 / 教学解释 / 文化体验等）和一个明确的主风格；风格必须能解释“为什么适合这个受众、场合与内容”，不能只写抽象形容词，也不要把多个风格编号拼成折中套餐。允许借一种辅助 craft，但整册要能用一句视觉主张说清。
3. 写 `plan/design-brief.md#Style Lock`：
   - scene；
   - primary_style；
   - supporting_craft（最多一种）；
   - visual_thesis / signature_visual；
   - palette / typography / numeric_voice；
   - image_language / image_opportunity_map / composition_grammar；
   - background_system：先根据场景说明背景应偏“克制秩序”还是“氛围表达”，再定义一个贯穿内容页的 `base_canvas_family` 与允许变化的视觉状态（明度、色场、环境光、肌理、图片占比、密度和章节状态）；每种状态写清叙事用途、适用页面及进入/退出承接。学术、组会、合规、严肃评审等场景可以更安静，但仍需有排版和证据视觉；其他场景不要把整册同一纯色底当作安全默认。统一不等于全册同底色；变化也不能脱离同一画布家族；
   - motif_role：说明主题母题在哪些页作为主视觉、在哪些页只作次要线索、哪些页主动缺席。同一装饰母题不得承担封面、章节页和大多数内容页的主要视觉；一致性主要来自字体、颜色语义、图片处理和构图语法。技术注、坐标、场记、档案编号等只有在传递真实且有用的信息时才可成为母题，不能编造伪元数据营造“高级感”；
   - special_pages；
   - avoid；
   - spatial_rhythm：内容页如何铺开、呼吸页如何聚焦、峰值页在哪里；
   - special_page_system：封面、章节页、结尾页共享什么设计 DNA，各自用什么构图动作。
   - material_visual_mode（有附件时）：哪些只作为事实，哪些图片/图表可直接复用，哪些风格线索值得保留。
   - attachment_visual_map（有图片附件时）：原路径、must-show / reuse / reference-only / omit、`material_asset_type`、正式 asset 路径、上屏页、裁切/整图/抠图/调色与理由。论文 `Figure N` 必须记录 figure-crop 的来源页与边界，不能直接复用整页 PDF PNG。
4. 用户未指定风格时，按主题 × 受众 × 场合主动判断。没有 Style Lock 不进入规划；没有可见的 `signature_visual` 兑现页，也不把通用配色和字体清单当作完成定调。

`image_language` 先说明哪些颜色本身承担识别、证据或教学信息，再决定统一处理。人物、动物、植物、作品、产品、场地、实验输出等真实主体默认保留有意义的原始色彩；统一感优先来自选图、裁切、色温、局部色罩、边框与背景。只有用户明确要求黑白/双色调，或本册视觉主张确实依赖该处理且不会损害辨认与证据价值时，才使用整图灰阶或 duotone；“学术感”“高级感”“为了统一”本身不构成把整册真实图片去色的理由。对承担识别、证据或主视觉职责的图片，同时定义轻量 `crop_contract`：焦点、必须保留的主体部位/图内信息、允许裁掉的背景与推荐 fit；不能只写宽高比后让 Slide 猜裁切。

Style Lock 锁定的是**视觉语言与判断边界**，不是一套固定 HTML 模板，也不锁死每页几何。必须明确区分：

- 稳定语言：字体角色、颜色语义、间距节奏、背景语法、图片裁切/调色、图形语法与特殊页亲缘关系；
- 受控变化：每页主焦点、构图方向、媒介比例、信息密度、留白位置和章节状态；
- 禁止项：临时引入新字体、新配色、无主题装饰或复制上一页几何只换文案。

它应当像可执行的 Art Direction：足够具体，使不同 Slide 能做出同一世界里的页面；又保留足够空间，让每页按内容选择最佳构图。无需另建模板文件或共享装饰素材。

`image_opportunity_map` 必须先做一次与实现方式无关的“可见主体扫描”：这页有没有值得被看见的人物、场地、产品、作品、活动、体验场景、虚构角色或情绪主画面；先说明图片能增加的证据、识别、临场感或情绪价值，再选择真图、生成图或代码视觉。不得先偏爱 CSS/Canvas，再倒推“没有图片机会”。

当页面的核心内容是一组**具名真实人物、主创、嘉宾或团队成员**时，默认把“人物可识别”视为真实图片机会，并交给 Image 批量检索人物肖像、官方简介照、活动照或团队合影。“不应生成假真人”只意味着不能用生成肖像冒充本人，不能据此把该页改判为 `image_opportunity: none`。若只能可靠取得部分人物照片，优先采用一张可信团队/机构场景图配少量关键人物肖像，或降低人物数量并重组叙事；不得用身份不明的相似面孔补齐。只有经过真实检索仍无可辨认、可下载且适合上屏的素材，且图片不会增加识别价值时，才使用纯排印，并在计划中记录缺口与降级理由。

同样审视具名作品、软件/产品、制作流程与案例：可检索的官方画面、界面、幕后制作图、过程拆解、实物或现场照片通常比小图标和空卡片更能建立识别与可信度。每张普通内容页都应有一个与内容相称的主要视觉载体——真实/生成图片、图表、解释性 Canvas，或真正能独立成立的排印主视觉。边框、空面板、微型图标和装饰线不算主要视觉载体；纯排印只有在文字本身被有意放大、组织并形成明确焦点时才成立。增加配图不等于增加散点：优先一张有分量的主图或一组视觉口径一致的素材，让其他元素安静地服务它。

有附件时同样执行完整扫描：优先复用其中真正有信息价值且清晰的图片；附件没有实景、人物或品牌图，只说明“没有附件真图”，不等于“生成图会虚构所以禁止配图”。用于气氛、愿景、概念体验或非特定场景的生成图可以作为表达层使用，准确事实、数字和关系仍留在 HTML / 图表层。把事实保真与视觉想象分开，不把材料摘要机械搬成卡片墙。

图片附件不能只被“读懂后重画”而默认消失。用户明确要求根据某张图制作，或该图本身是唯一产品、人物、场地、作品、证据、前后对比或流程总图时，将其标为 `must-show`，至少在一页以可辨认的整图或忠实裁切出现；复杂流程图可以先用原图建立全貌，再用 Canvas/HTML 分步重绘。只有重复、无关、不可读或用户明确不希望展示时才 omit。`image_opportunity: none` 只表示不新增外部/生成位图，不能覆盖 `attachment_visual_map`。

真实对象的识别与证据、场景的临场感、人物与产品的可信度、故事与情绪的锚点，都属于有效配图机会。虚构人物、概念场景、未建成空间和风格化主视觉正是生成图的适用对象，不应因其不是真实对象而改用彩色方块、抽象符号或纯 CSS 占位。“CSS 更可控”“没有用户实拍”“担心 AI 生成错误”“为了风格统一”都不能单独成为 `none` 的理由；这些问题应通过真图/生成图分流、提示词约束、统一裁切与调色解决。只有当位图确实不增加听众价值，或会比图表、Canvas 或排印更含糊时，才选择 `none`。如果一册存在多个明显可见主体，却被整体判成无位图或仅封面一张图，在冻结计划前必须重做这次扫描。这里不设图片数量配额，也不为装饰而配图。

当搜图或生图能力可用时，**整册全部 `none` 或只有封面一张图属于需要证明的异常，不是默认安全路线**。数据、商业、技术、学术或代码题材也不能因此整册退回卡片墙：事实页可以用图表/Canvas，但封面、章节转场、案例、场景、愿景或结论中至少应选择两个真正能从图像获益的节点，给出可执行的搜索/生成 brief；短册则至少保证一个内容节点，而不只是封面。只有用户明确要求纯排印/纯图表，或逐页证明位图都会降低准确性与可读性时，才允许整册无位图，并在 `plan/deck.md` 写明逐页例外理由。这是防止误判的最低覆盖线，不是为了凑数；事实型真图与非证据性的氛围生成图必须明确分流。卡片、极简、学术、商务等风格描述不等于禁止位图，也不能作为免配图理由。只有用户原文明确要求“纯文字”“不要图片”或语义完全等价的限制时，才能把 `explicit_user_request` 作为图片豁免依据；不得根据风格标签自行推断用户拒绝图片。

可见主体扫描必须同步落盘为 `plan/image-strategy.json`，供生成流程在 Slide 委派前确定性验收。存在配图机会时写入 `status: images_required`、`visible_subject_scan_complete: true` 和完整的 `image_opportunity_pages`；整册无位图时必须写入 `status: bitmap_exception`、`visible_subject_scan_complete: true`、覆盖全部计划页的 `reviewed_pages`、不少于 20 字的 `exception_reason`，以及 `explicit_user_request | pure_typography | pure_chart | wireframe | accuracy_critical` 之一的 `exception_basis`。不能用自然语言总结替代该文件。

背景不等于一块纯色，也不等于每页随机换皮。学术、组会、合规、严肃评审等场景可用安静画布承托事实；产品、品牌、招商、文旅、文化、故事、课程导入、活动与大众传播等表达型场景，应主动考虑一层与主题相容的环境设计，而不是整册退回纯色：可以是有方向的柔和光场、局部光晕、低对比颗粒/网点/纸纹/地形等主题肌理、图片背景，或由 Image 统一生成的背景。光晕只有在能解释光源、主题和视觉焦点，且形状、位置与构图相关时才成立；标题后反射式复制的圆形模糊光斑仍属于无主题 glow。先确定贯穿普通内容页的基础画布家族，再选择少量相容手法形成背景语法。章节差异优先通过局部大色场、图片调色、条带或母题状态表达；只有章节页、hero、结尾或叙事确需整体换场时才更换整页画布，并在前一张或后一张保留颜色、肌理、图片处理或构图方向的承接。图片或生成背景必须进入 `image_opportunity_map` 与素材 brief，不能由 Slide 临时发明路径。避免出现数页突然像另一套 Deck、随后又无过渡切回，也避免把深藏青、霓虹蓝紫渐变或通用科技 glow 当作默认“高级感”。

后续主链只有一条：`Style Lock → 全册计划 + prepare → Image 分片并行 → 素材路径一次回填 → Slide 页组并行 → Review 诊断/有限返修 → 讲稿同步 + build → Review 查看 build 后最终像素并返回合同`。前一节点的真相源未冻结，不启动依赖它的下游；互不依赖的同层任务一次并行派出。`build` 可能裁剪字体、更新 `base.css` 并重渲全册，因此 build 前的 Vision 只能用于诊断，不能作为最终像素证据。

### 阶段 3：全局规划与字体前置

完整读取 `references/planning-contract.md`，然后按顺序：

若存在 `materials/font-config.json`，先读取一次并把其中 title/body/number/annotation 角色作为 Style Lock 的字体输入；用户上传字体优先于自动选型，未覆盖字符由交付字体包自动回退，禁止凭字体名改用未上传的本机字体。

1. 补全 `design-brief.md`；
2. 写 `plan/deck.md`；
3. 复制 `base-template.css` 为 `base.css` 并填写 token；
4. 一次写完全部 `plan/slide_NN.md`，每页附自己的 Reference route；
5. 在 `plan/deck.md` 定义 Production groups：全部过渡页为 `dividers`，封面与结尾为 `bookends`；内容页首先按**制作方式与构图亲缘性**分组，再考虑叙事连续，最后才考虑章节归属。一个组应共享同一种制作问题，而不是把 cards、复杂 Canvas、数据图表、真实照片等不同媒介仅因属于同一章就塞给一个 Agent；章名相同不构成分组理由。每组同时写 `boundary_handoff`，说明进入本组前与离开本组后的画布、明度、色场和母题状态；分组完成后按逐页表复核一次，确保每页恰好归属一个组，章节页与互动页等页型没有错号。
6. 参考文献与结尾页分开承担职责：需要上屏的来源使用独立 references 页或前置内容页；closing 只负责收束命题、行动或提问，不与长参考文献、详细回顾或多栏总结合并。
7. 在启动 Image 或 Slide 前写一段简短的 `## Repetition & rhythm preflight`：逐页比较画布状态、标题锚点、构图方向、媒介、图片占比、信息密度与母题角色；同时纵向比较各章的页面脚本，不能把同一套“痛点—案例前—案例后—步骤—工具”机械复制到不同章节。共享节奏可以形成亲缘性，但每章仍应有自己的问题视角、证据任务与阅读动作；某页没有独立职责时合并或重构。发现重复或节奏扁平时先改页面地图、Style Lock 或 Production groups，再冻结计划。
8. 做一次**内容充分性与屏显语义去重**：每个普通内容页先写清不可替代的听众所得，再用最适合该页的证据、机制、对比、案例、行动或边界继续解释；不设固定条数，但只有主题句、同义副题和状态角标的页面不算内容成立。若没有新的支撑层，合并页面、改变叙事职责或改成真正有单一焦点的过渡/呼吸页，不用大片无职责空白或重复标签把薄内容拉成一页。逐页确认主要视觉载体与 `spatial_budget` 相符；不能靠大边框、等高卡或空面板在几何上“占满”，却把短文字钉在边缘、留下大块未参与阅读的内部空白。逐页比较标题、kicker / subtitle、图片角标、badge、callout、图例和页脚；同一短语通常只选择一个最强载体，其他区域补充对象、原因、变化或结果。只有导航或同屏比较确有必要时才重复，且每次出现必须承担不同作用。`dense` 不是一句标签：若主内容只压在半张画布或一条窄带里、其余空间没有焦点或方向，必须重做空间计划。
9. 做一次 `screen-copy firewall`：逐页区分“观众必须看到”与“只供生产使用”。Speaker/Audience/Occasion/Objective、页面职责、production group、视觉验收、素材路线、证据编号、假设、文件名和 Research/Material 来源都留在计划或讲稿中，不得自动进入 `## 最终屏显文案`。只有当页面主题本身确实讨论目标受众、项目目标或研究方法时，才把相关内容重新写成观众可理解的叙事，而不是显示 `受众：…`、`主体：…`、`页面角色：…` 等内部标签。屏显文案和 HTML 不使用 emoji / Unicode 图标（如 `👀 ✋ 💡 ✨ ★ ✦`）；需要图标时使用与 Style Lock 一致的本地小 SVG、CSS 形状或直接用文字表达。星芒、爱心、礼花等通用装饰不能作为“全册点缀”散布到多数页面，只在确有构图职责的页面出现。
10. 用一个确定性命令同步讲稿并从计划前置字体包：

```bash
python "$SKILL_ROOT/scripts/deck.py" prepare "$DECK_DIR" --expected <总页数>
```

规划冻结条件：事实、页序、屏显文案、视觉媒介、逐页配图机会、素材 brief、背景处理、来源、讲稿、页型和字体全部确定，`plan/image-strategy.json` 已写入，并已通过内容充分性、屏显语义去重与 screen-copy firewall。冻结前专门反证所有 `image_opportunity: none`：若页面已经有可视化的主体或场景，不能只用“代码更可控”将它排除。屏显文案或字体 token 变化时，先同步计划再重跑 `deck.py prepare`。

逐页计划还必须完成一次空间预演与视觉验收预演：写清主视觉与文字各占哪块、主信息如何使用安全区、剩余空间为什么存在，以及观众从最终像素应读出哪些对象、方向、领域证据和结论。`deck.md` 与逐页计划的媒介不能互相矛盾。普通内容页若预演结果是“主体缩在中间、外围大片无归属空白”“只能靠小字塞下”或“只能用通用几何代替领域证据”，先改计划，不把问题留给 Slide。章节过渡页则预演“主信息团 + 视觉对重 + 留白职责”：内容保持简洁，但不能只在局部放一小团文字、让其余画布成为未设计的纯空白。

### 阶段 4：素材与页面制作

1. 汇总所有被判定为真实图或生成图的图片 brief，再启动 Image subagent；每个 goal 显式带上稳定 `group_id`、`response_language` 与 `deliverable_language`。**第一次 Image 委派前**，每个 `plan/slide_NN.md` 的唯一 `## 视觉实现` 都必须已有一条完整单行机器字段 `- image_opportunity: <枚举>`；有位图页另用同级独立行写 `- presentation: <四枚举之一>`，不得写成空的 `image_opportunity:` 父块，不得把 `full-bleed` / `framed-scene` 填进 `image_opportunity`，也不得把 `split-media` 等 layout 值填进 `presentation`。缺字段时直接修计划并重试，不搜索或修改运行时代码。只要计划中存在有效配图机会，就不能静默跳过 Image 阶段；若计划需要图片但当前没有 Image Worker，必须重新规划为真正成立的非位图表达，或补派 Image Agent，不能直接进入完成状态。同一视觉配方且能在一张联系表中共同审清的素材归入同一分片，多张生成图在同一工具回合并行提交。Image 与 Slide 不得在同一次 `sub_agent` 中派出：先完成并验收素材，再启动页面制作。
2. 先把 `attachment_visual_map` 中 must-show / reuse 的图片复制并登记来源，再交给对应 Image 分组；论文命名 Figure 先由 Image 使用 `deck.py material-figure` 从页图生成独立、可追溯的 Figure 裁图，整页 PNG 只作为定位上下文。每个 Image 分组将候选路径绑定到稳定 `asset_id`，由 `deck.py asset-contact` 生成一张带 ID 的素材联系表，默认只做一次整组 Vision；只有被标红、要求抠图、比例可疑或主体完整性无法从缩略图判断的素材才打开单图复核。Image 用 `asset-review` 写回最终状态后，Orchestrator 只按 `ready` 的 `asset_id → actual path + origin + crop_contract` 回填逐页计划；候选、被替换与废弃图片不算正式素材。`assets/catalog.json` 是唯一素材真相源，必须保留下载 URL、生成模型、用户附件路径和派生关系；Image 的自然语言总结不能代替 catalog。逐页图片先锁定 `presentation: subject-only | framed-scene | full-bleed | evidence-crop`（这是位图的展示/背景处理合同，**只允许这四个枚举**；`split-media`/`right-half`/`cards`/分屏等是版式不是 presentation，放到 `layout`；**无位图页完全省略 presentation**，不写 `无`/`none` 占位）：任何要悬浮、跨色场叠放或作为独立角色/物件的图都属于 `subject-only`，必须由 Image 完成透明检查、主体抠图、最终 Alpha 检查与必要的单图 Vision，再回填可用的 `*-cutout.png`；普通 RGB 图不得作为透明资产返回 `ready`。带背景图片只能作为有意的画框场景、满幅裁切或证据裁图，不能把其白底/奶油底矩形偶然贴到另一种画布上。Slide 不临时去背，也不用 CSS mask/multiply 冒充。映射确有问题时交回同一个 Image 复核。失败素材先换可行的真实图或生成图路线，确实不可得时才改为 Canvas 或排版降级，并写清原因，不留占位。Slide 启动前，Image 必须有 `status: ready` 的完成合同，catalog 中所有计划 `asset_id` 都必须为 `ready`、实际文件存在，且路径与裁切合同已经回填逐页计划。
3. 一个 Production group 委派一个 Slide，可并行执行；goal 的首行必须精确写成 `Slide Group <group_id> [NN,NN]:`，例如 `Slide Group bookends [01,20]:`。页码所有权以已冻结的 `production_group` 为准；不用“负责封面和结尾”、“第一组页面”等叙述取代组 ID 与标准页码头。显式带上 `response_language`、`deliverable_language` 与该组 `boundary_handoff`。不得为了提高并发把已经冻结的多页 group 再拆成“一页一个 Slide”；只有计划本身确实定义为单页组时才单页委派。同组必须同时满足叙事亲缘、设计亲缘和制作负荷相容；复杂 Canvas、独立数据图或重图像合成页在没有真正共享构图系统时应单独成组。Grouping 提供的是共享设计记忆，不是批量降精度：同一个 Slide 按组内页序串行完成每页闭环。
4. Slide 先读取 Style Lock 与组合同，然后对每一页依次执行“完整首稿 → 父级单页渲染 → 父级 `inspect_images(strategy=\"native\")` → 最多一次合并修复 → 父级重渲复看”；当前页达到 ready 后才进入下一页。全部页面完成后，再批量渲染本组并查看组内全部最终 PNG，确认亲缘性与明显回归，但不为审美偏好开启新循环。封面、每张章节页、结尾页都必须完成自己的单页闭环。首次看图后的“合并修改 → 重渲 → 复看”记为一轮 refine，每页最多 1 轮；仍有真实硬伤时改用更稳定的结构或返回 blocked。最后一次修改后没有重新渲染和看图，不得返回 ready。
5. 等待全部页面完成后再启动首次 Review。新建或复杂编辑过程中不得额外委派 `simple_edit` 或 `review-fix` 角色；Orchestrator 不得追逐 `cjkTypography`、`crowded`、bbox/contrast 候选、轻微换行/标点等 advisory，也不得在 Review 前开启审美清门循环。Review 发现有新鲜像素/DOM 证据的真实硬伤时，只交回原所属 Slide Group；每组最多返修 2 次，每次失败由运行时恢复该组最后一次已看过的版本。返修后才可启动下一次 Review，Review 总计最多 3 次。

### 阶段 5：全册 Review 与交付

每次 Review 的 goal 必须以以下语言合同开头，再写具体诊断范围：

```text
Review:
Response language: <response_language>
Deliverable language: <deliverable_language>
mode=final_review
```

不得只在父任务或 system 中隐含语言，也不得省略后让 Review 自行猜测。随后严格两段执行：

1. **完整诊断：**先看 overview，再按 `review-contact.json` 分批看完全部联系表和必要单页；每批将覆盖页码与发现记入同一 `_trace/review-issues.md`。全册覆盖并冻结账本前禁止修改或渲染；不因 Deck 页数较长而跳过后续批次。
2. **内容保真核验：**任务含附件或使用了 Research 时，在像素修改前把每页屏显事实与 `grounded-knowledge.md` 对照；有附件时再对照 Material 摘要及 coverage ledger，并写 `_trace/content-fidelity.md`。数字、名称、日期、单位、产品身份、原话或关系无法追溯、自相矛盾时修正或 blocked。生成图只能承担概念/氛围表达；若用于具名真实产品、人物或案例识别，页面必须明确标“概念示意”，不能作为事实证据。仅当既无附件、又无 Research 和高风险外部事实时，`content_fidelity` 才可为 `not-applicable`。
   Review 停滞收口时允许补齐或更新的正式产物只有 `_trace/review-issues.md` 与 `_trace/content-fidelity.md`；运行时不得禁止写入最终验收合同明确要求的这两份文件，也不得在收口阶段允许继续修改页面。
3. **集中修复：**Review 既诊断也直接修复本次边界内可安全解决的问题；当前文件与已有素材能解决的问题不得只上报给 Orchestrator。按共同根因先全局、后局部，全部修改结束后才统一批量渲染。这一整批“修改 → 批量渲染 → focus 复验”记为 Review 的 1 轮 refine。任何 HTML/`base.css` 修改都会使旧 PNG 失效，重渲前禁止再次调用 Vision；Canvas/SVG/HTML 叠加页必须同步修正 CSS 尺寸、Canvas 属性、SVG `viewBox`、JS 坐标与节点锚点，不能只放大外容器。机检中的 `boxoverflow`、bbox 相交和装饰相交仅为定位候选；若新鲜像素没有真实遮挡、裁切或不可读，不得为清除告警缩字、压缩主体或删除有构图作用的元素。
4. 改过 base.css/字体时全册 batch；只改局部时 page batch。该批渲染用于确认修复没有退化，不是最终交付证据。
5. 生成一次 focus 联系表确认变化页。单个 Review 只做 1 轮 refine；仍有可见硬伤时返回 `blocked`，由 Orchestrator 将有证据的硬伤交回原页组。原页组保留最后验证版、做一次合并修复并重渲复看；新版退化或仍未解决时恢复验证版。修复后启动新的 Review 复验，最多形成 3 次 Review，不新增审美目标。
6. 修复确认后先同步讲稿，再执行一次 `deck.py build`。随后重新生成 `renders/review-contact.json` 与最终联系表，并用 Vision 覆盖 build 后的全部最终像素；若 build 改变 `base.css`、字体或任一页面渲染，build 前看过的 PNG 全部视为过期。最终看图后只允许更新 `_trace/review-issues.md` / `_trace/content-fidelity.md` 与返回合同，不得再改页面、渲染或 build。
7. **产物核验（硬门）**：Review 返回 `ready` 后，父级必须逐项确认 `outline.md`、全部 HTML/PNG、讲稿、`present.html` 与播放器均存在，并确认 `DECK_DIR/present.html` 可打开。`present.html` 由第 6 步 `deck.py build` 生成，**不得以其他文件或仅 PPTX 替代；缺失即技术故障，不得交付**。
8. **PPTX 导出（必做步骤，不是可选项）**：当 `static_postprocess` 含 `pptx` 时，**必须**执行以下唯一导出命令，不得跳过、不得改用任何其他工具：

    ```bash
    node "$SKILL_ROOT/scripts/export_pptx/html_to_pptx.mjs" --deck-dir "$DECK_DIR" --pages-dir "$DECK_DIR/slides" --output "$DECK_DIR/<DECK_ID>.pptx" --force
    ```

    - **这是 PPTX 的唯一合法产出路径**：禁止用 python-pptx、自写 python 脚本、宿主 Agent 原生演示工具或手工重建 PPTX 替代；导出失败时也不得用这些方式"补产出"，只能按下方失败分支处理。
    - Linux 下若该命令报 chromium 启动失败 / `Target page, context or browser has been closed` / 缺动态库（如 libnspr4.so），先执行 `export LD_LIBRARY_PATH="$HOME/.box-agent/runtime/linux-libs${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"` 再重跑同一条命令，最多重试一次；仍失败进入失败分支。
    - 成功且 `DECK_DIR/<DECK_ID>.pptx` 确实存在后，登记 `state.artifacts.pptx`；失败则写入 `state.last_error`（保留原始错误原文）、将 `state.status` 设为 `partial`、保留全部 HTML 产物并如实向用户报告，**不得伪造 PPTX 路径**。

Review 超时、返回 `blocked`、缺少最终像素复验或没有自然返回合同时，先进入有限恢复流程，而不是立即把整项任务判失败。达到 3 次 Review 或每个受影响页组 2 次返修预算后停止继续改页，保留 `_trace/review-issues.md`，恢复每组最后验证版并执行确定性 build。只要全部 slide、非空最终渲染、`speech.md` 与可打开的 `present.html` 存在，任务以“完成（有待改进）”交付并携带 warnings；只有缺页、渲染缺失/空白、播放器无法构建/打开或**缺少 `present.html`** 等不可用技术故障才判失败。`static_postprocess` 含 `pptx` 时，导出失败按第 8 步登记 `partial` 并如实交付 HTML 版，**不得以 python-pptx 等替代工具另产 PPTX 冒充完成**。

Review 不只查“有没有溢出”，还要比较全册设计兑现：封面是否具有统治性焦点和必要层级，章节页是否既有亲缘性又体现章节推进，结尾是否回应开场；普通页是否在投影字阶下充分使用画布并形成明确阅读路径；每个章节边界是否仍属于同一基础画布家族，整页换场是否有明确的进入与退出承接；屏显是否泄漏内部规划字段、来源、文件名或无听众价值的伪元数据。由父级实际调用 `inspect_images(strategy=\"native\")` 查看最终像素；未调用时必须 blocked。

```bash
python "$SKILL_ROOT/scripts/deck.py" build "$DECK_DIR" --expected <总页数>
```

`deck.py build` 生成并校验 `present.html`（缺失即报错，deck.py:1294-1295）。`present.html` 是必交付产物：不得省略 build、不得拿其他文件代替它交付。
Review ready 时交付为 `ready`。Review 最终仍有硬伤但全部页面、渲染、讲稿与 `present.html` 可用时，以 `needs_improvement` 交付并展示问题账本；不得因为 advisory、子 Agent 文本收尾或 Review 合同不完美丢弃可用成稿。

## 3. 编辑 PPT

先完整读取 `references/editing-contract.md`，只读检查现有 plan、HTML、素材、讲稿和渲染图，建立受影响文件/页面清单，再选择编辑路径。

### 3.1 简单与复杂的判定

**简单编辑**同时满足：

- 不改变核心论点、页序、页面职责或跨页叙事；
- 不需要新 Research、Material 或 Image；
- 不改变全局 Style Lock、字体系统或多个 arch；
- 可在少量页面内安全完成，且影响边界明确。

任一条件不满足即按复杂编辑处理。页数只是信号，不是唯一判据。

### 3.2 Review 快修

简单编辑只委派一个 Review，goal 标明 `mode=simple_edit`、用户原始修改要求、目标页和不可改变项。

Review：

1. 看现有 overview 与目标页最终 PNG；
2. 一次列完本次修改项；
3. 读取目标页计划与 HTML，集中修改；
4. 更新受影响的计划/讲稿；
5. 用 `render.py --batch --pages` 一次重渲并看 focus，确认修改不退化；
6. 同步讲稿并执行 `deck.py build`，再重新生成 focus、查看 build 后最终像素并返回 ready/blocked；最终看图后不再修改或 build。

不派 Slide、Image、Research 或第二个 Review。

### 3.3 Orchestrator 改造

复杂编辑由 Orchestrator：

1. 写影响图：事实、叙事、页序、Style Lock、base.css、素材、页面、讲稿分别受什么影响；
2. 只复用仍有效的既有成果，不从头覆盖无关页面；
3. 只在已存在的 `outline.md`、`info_pack.json`、`raw_documents.json` 和既有研究边界内，委派受影响的 Image/Slide 页组；Standard 阶段不得委派 Research 或 Material，也不得自行修改`outline.md`。若发现新事实、新附件、论文 Figure 页图缺失，立即返回 Entry/Story，待Entry 更新材料/研究、Story 覆盖同一 `outline.md` 后再重新进入 Standard；互不依赖的 Image/Slide任务仍可并行；
4. 更新受影响计划并运行 `deck.py prepare`；
5. 只重做受影响页面；全局 token 变化时 batch 重渲全册；
6. 最后委派唯一 Review，以 `mode=final_review` 做全册一致性与讲稿收口。

复杂编辑不允许让 Review 独自重写叙事或凭空补素材，也不允许 Orchestrator 直接改页面 HTML。当编辑改变事实、页序、页面职责或核心结论时，必须先回到 Entry → Story；Standard 只负责表达、渲染、Review、build 和 Standard exporter 收尾。

### 3.4 编辑交付门

- 用户要求逐项可追踪到修改结果；
- 未受影响页面和素材保持不变；
- 新旧页面风格、页码、讲稿和播放器一致；
- 所有变更页面已看最终像素；
- 字体包、render freshness、`speech.md`、`present.html` 重新通过。

## 4. 硬红线

- 图表必须用 ECharts，不用生成图伪造数据图表。
- AI 生成图不承载需要准确呈现的文字；文字放 HTML 层。
- SVG 只做小元素，不做大型结构图或主视觉。
- `slides/` 只保留正式 `slide_NN.html`，不放备份或临时页。
- 页面固定骨架、页脚安全区、最小字号、对比度与无溢出是硬门。听众阅读的正文不得低于 20px，注释、来源和辅助说明不得低于 18px；若字体 token 规定了更大值，以更大值为准。内容放不下时减少卡片数量、删减重复屏显文字、调整信息层级或拆页，不得继续缩字。
- 内部规划标签、来源、文件路径、制作状态和无听众价值的伪元数据不得出现在屏显内容中。
- 最终判断看 PNG；修改后未重渲、未看新像素，不得声称完成。
- Review 最多 3 个受控实例；只有页面实际修改并重渲后才允许复验。达到预算后停止返工并带 warnings 交付可用成稿。

## 5. 确定性脚本

| 脚本 | 用途 |
| --- | --- |
| `stage_materials.py` | 不参与 Entry → Story → Standard 新链路；材料解析由 Entry 完成，Standard 只读取 Entry/Story 已交接的产物 |
| `font_bundle.py` | 保留：OFL 白名单、官方来源、许可证随包、字符裁剪、交付校验和 render freshness 属于独立高风险能力 |
| `render.py` | 保留：单页诊断；`--batch` 复用同一 Chromium 渲染整册或指定页 |
| `image_cutout.py` | 保留：检查 Alpha、清除烘焙棋盘格/纯色背景，并在需要时用 GrabCut 生成独立主体 PNG；不覆盖来源原图 |
| `deck.py` | 保留：`prepare` 一次完成计划讲稿与字体前置；`asset-register` 登记来源；`asset-assign / asset-contact / asset-review` 管理语义素材、分组联系表与最终状态；`contact` 生成页面联系表；`build` 校验来源并生成播放器；`sync` 仅供只改讲稿时使用 |
| `install.sh` | 保留：跨环境依赖、字体和 Chromium 安装无法由运行脚本可靠替代；依赖清单已内联 |

首次部署依赖解析 venv、PyMuPDF、可分发字体、FontTools/Brotli 和 Playwright Chromium；用 `scripts/install.sh` 安装。运行脚本时若 skill 挂载路径不同，使用实际 skill root。
