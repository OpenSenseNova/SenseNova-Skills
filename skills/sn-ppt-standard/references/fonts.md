# 字体系统：可核验开源字体与用户授权字体

本文件只在默认字体角色不足或场合对字体敏感时读取。字体选择先服从受众、场合和材料气质，再考虑题材。

## 1. 许可边界

- 默认字体必须同时满足：官方项目可追溯、明确标注 `OFL-1.1`、已登记在 `font_bundle.py` 白名单。
- 若工作区存在 `materials/font-config.json`，其中字体是用户主动上传且已确认具备演示与嵌入权利的项目字体；优先服从其角色映射。不得把字体文件当普通 Material，也不得自行推断其许可。
- 页面只使用 `--font-*` 角色 token，不写外部 `@import`、CDN 字体 URL 或未登记的本机字体名。
- 本机即使安装了字体，只要不在白名单且不是本项目授权上传字体，交付时也必须回退到已批准的 OFL 字体。只写一个字体名称、未提供字体文件，不算自定义字体。
- 字体子集随 deck 一起分发时，必须生成 `assets/fonts/LICENSES.txt`；内置字体附 `OFL-1.1.txt`，用户字体附 `USER-FONTS.txt` 与来源哈希。
- 字体子集属于修改产物，构建时必须把内部 family/PostScript 名称改成 `Deck-*`，避免沿用 OFL Reserved Font Name。
- 不修改字体保留名称，不单独售卖字体文件。此处是工程护栏，不代替具体项目的法律审核。

来源或再分发授权不够清晰的旧本机字体已经全部移出模板；不要把未登记字体重新加回 fallback。构建器会把用户字体裁剪、改名为 `Deck-*` 并保留 Noto 中文兜底，最终 HTML 不依赖观看者本机安装字体。

## 2. 角色 token 与开源替代

| token | 默认字体 | 角色与来源 |
| --- | --- | --- |
| `--font-sans` | Noto Sans SC | 正文、表格、图表标注；Google Fonts / OFL |
| `--font-serif` | Noto Serif SC，Spectral | 中文编辑标题与拉丁衬线补充；Google Fonts / OFL |
| `--font-hei-heavy` | Noto Sans SC 900 | 超粗 hero；需要窄斜展示效果时可显式选 Smiley Sans（官方项目 / OFL） |
| `--font-brush` | Ma Shan Zheng | 书法主标题、金句；Google Fonts / OFL |
| `--font-kai` | Xiaolai，LXGW WenKai | 清晰硬笔感章节、引言和人文标题；官方项目 / OFL |
| `--font-write` | Xiaolai | 工整批注、引语和短标题；官方项目 / OFL |
| `--font-write-cursive` | Liu Jian Mao Cao，Long Cang | 草书/行书大字；Google Fonts / OFL |
| `--font-playful` | ZCOOL KuaiLe | 活泼、漫画、儿童标题；Google Fonts / OFL |
| `--font-round` | ZCOOL QingKe HuangYou，ZCOOL KuaiLe | 圆润/趣味展示；Google Fonts / OFL |
| `--font-jotter` | Xiaolai，Zhi Mang Xing，Long Cang | 校园、手账、便签式中文手写；默认使用更清楚的小赖字体；官方项目 / OFL |
| `--font-display-serif` | Fraunces | 编辑、杂志拉丁展示衬线；Google Fonts / OFL |
| `--font-grotesque` | Archivo | 现代拉丁无衬线展示与数字；Google Fonts / OFL |
| `--font-geometric` | Sora，Montserrat | 几何科技、产品发布和现代品牌；Google Fonts / OFL |
| `--font-ui-clean` | DM Sans，Manrope | 克制商业、UI 与服务设计；Google Fonts / OFL |
| `--font-tech-display` | Space Grotesk | 科技编辑、创新与未来主题；Google Fonts / OFL |
| `--font-condensed` | Oswald，Barlow Condensed | 体育、海报、纵向节奏和窄栏标题；Google Fonts / OFL |
| `--font-condensed-xl` | League Gothic，Bebas Neue | 极窄英文/数字主声部，不承担中文正文；Google Fonts / OFL |
| `--font-poster` | Bebas Neue | 编辑海报与强节奏拉丁标题；Google Fonts / OFL |
| `--font-display-wide` | Unbounded，Syne | 前沿、潮流、实验性展示；Google Fonts / OFL |
| `--font-display-pop` | Bungee | 活泼消费与节庆标题；Google Fonts / OFL |
| `--font-editorial-serif` | Playfair Display | 时尚、杂志和奢华编辑拉丁展示；Google Fonts / OFL |
| `--font-classic-serif` | Cormorant Garamond | 文艺、历史与精致拉丁展示；Google Fonts / OFL |
| `--font-cn-display-serif` | ZCOOL XiaoWei | 中文文化、人文与复古展示；Google Fonts / OFL |
| `--font-hand-en` | Patrick Hand，Caveat | 英文手写批注；Google Fonts / OFL |
| `--font-hand-en-neat` | Architects Daughter | 工整英文手写；Google Fonts / OFL |
| `--font-hand-en-casual` | Indie Flower | 随性英文手写；Google Fonts / OFL |
| `--font-hand-en-script` | Dancing Script，Sacramento | 英文连笔、签名和短引语；Google Fonts / OFL |
| `--font-hand-en-marker` | Kalam，Shadows Into Light | 英文马克笔、板书和教学批注；Google Fonts / OFL |
| `--font-mono` | IBM Plex Mono | **纯拉丁**代码、坐标、ID、真实编号、纯拉丁技术眉签；无中文字形，**中文一律不用**；IBM/Google Fonts / OFL |
| `--font-number` | 由 Style Lock 映射 | Hero 数字、KPI、章节序号的数字主声部 |

## 3. 使用规则

- 正文、表格和图表标注固定用 `--font-sans`；代码与技术编号才用 `--font-mono`。
- `--font-number` 按语义选择：报告用 sans/grotesque，编辑叙事用 serif/display-serif，海报用 heavy/playful，工程读数才用 mono。
- 中文信息标题先服从 Style Lock 与场合：严谨报告使用 Noto Sans/Serif SC，表达型人文、课堂、手作或文旅页面可使用 Xiaolai / LXGW WenKai 承担章节、引言或短标题。不要因题材里出现“科技”“数据”就机械切成卡通黑体，也不要把硬笔体用于党政、法律、医疗等严肃信息正文。草书只用于 ≥48px 且足够短、且主题确实需要书写性的封面、hero 或金句。
- 中文眉签、页脚、部门名、元数据和短标签默认使用 `--font-sans` 或 `--font-serif`，字距为 `0–0.03em`，允许范围 `-0.01–0.06em`；不得使用 `--font-mono`、`--tracking-caps` 或超过 `0.08em` 的字距。只有纯拉丁 ALL CAPS、代码、API、坐标和真实编号可使用 mono 与疏字距。
- 同一句中文标题、结论、按钮或标签只用一个字体家族。局部强调只改颜色、字重、字号或装饰线，不把强调词换成另一套字体；“普通黑体 + 卡通强调字”属于硬伤。
- 卡通、圆趣、手写、书法字体是场景化角色，不是全局默认，也不是全局禁用。童趣、漫画、手作、课堂、私人手账、文旅与明确书写性主题可以主动选择；政务、法律、医疗、严谨学术与正式商务通常不选。使用时在元素上添加 `.is-expressive-type` 或 `data-type-intent="expressive"`；没有声明时渲染器会判为字体语义错误。
- 连笔签名字体只承担短语和名字；马克笔/板书体适合教学提示和海报批注，均不承担长正文。
- **全册字体家族总数 ≤ 3(硬约束)**：整册（跨全部页面）最多出现 **3 个**字体家族，且必须全册统一——同一角色在每一页都用同一家族，不因页面题材临时换字体。典型的三族分工：中文标题/正文一族（Noto Sans SC 或按场合的中文展示体）+ 拉丁/数字一族（如 Archivo / IBM Plex Sans）+ 至多一个合题点缀族（书法/手写/展示，仅在主题真正需要时）。严谨型 deck 收敛到 **1–2 族**即可。字体数量不是质量目标：宁可少而统一，也不要每页换花样。
- 中文正文、表格、图表标注、页脚、眉签、页码一律用 `--font-sans`（严谨衬线场景可用 `--font-serif`），**绝不用 `--font-mono` 承载中文**——IBM Plex Mono 无中文字形，中文落进去会回退成系统里的卡通/手写体。`--font-mono` 只服务纯拉丁代码、坐标、API、真实编号。
- 中文必须保留 Noto Sans/Serif SC 兜底，避免拉丁展示体缺中文字形时出现豆腐块。

## 4. 常用搭配

优先从下表选一个预设，再按用户品牌材料微调；不要让模型从全部字体中自由拼盘：

| 预设 | 中文标题 | 正文 | 英文 / 数字 | 可选点缀 |
| --- | --- | --- | --- | --- |
| `formal-business` 政务、管理、销售 | Noto Sans SC 800/900 | Noto Sans SC | Archivo | 无；中文眉签仍用 Noto Sans SC |
| `academic-editorial` 学术、人文 | Noto Serif SC 700/900 | Noto Sans SC | Spectral / Archivo | LXGW WenKai 短引言 |
| `tech-product` 科技、产品、工程 | Noto Sans SC 800/900 | Noto Sans SC | Sora / Space Grotesk / Archivo | IBM Plex Mono 仅代码与接口 |
| `brand-editorial` 品牌、杂志、奢华 | Noto Serif SC / ZCOOL XiaoWei | Noto Sans SC | Playfair Display / Fraunces | 无或一次短引语 |
| `culture-travel` 文旅、文化 | Noto Serif SC / ZCOOL XiaoWei | Noto Sans SC | Archivo | LXGW WenKai；Ma Shan Zheng 仅一次短大字 |
| `children-comic` 儿童、漫画、手作 | ZCOOL KuaiLe | Noto Sans SC | Patrick Hand | Xiaolai 短批注 |
| `sport-poster` 体育、海报 | Noto Sans SC 900 | Noto Sans SC | Oswald / Bebas Neue | 无 |

- 政务/管理/销售：Noto Sans SC 800/900 标题 + Noto Sans SC 正文 + Archivo 数字；部门名和眉签仍用 Noto Sans SC，不使用 mono。
- 学术/报告：Noto Serif SC 标题 + Noto Sans SC 正文；教学、人文或演讲型内容可加入 Xiaolai 短批注，正式论文答辩则不加。
- 技术/数据：Noto Sans SC 900 大字 + Noto Sans SC 正文 + Archivo 数字；IBM Plex Mono 只做技术标识。
- 电影/漫画/儿童：ZCOOL KuaiLe 标题 + Noto Sans SC 正文 + Patrick Hand 批注。
- 文旅/传统：Ma Shan Zheng 只做短大标题 + Xiaolai / LXGW WenKai 章节与引言 + Noto Sans SC 正文；信息型长标题根据场合在 Xiaolai、LXGW WenKai、Noto Serif SC 或 ZCOOL XiaoWei 中选一套，草书只点一次。
- 编辑/杂志：Fraunces 拉丁展示 + Noto Serif SC 中文标题 + Noto Sans SC 正文 + Archivo accent。
- 科技/产品：Space Grotesk 或 Sora 展示 + Noto Sans SC 中文 + DM Sans 数据与英文标签。
- 体育/海报：Oswald 或 Barlow Condensed 主标题 + Noto Sans SC 中文正文；Bebas Neue / League Gothic 只做英文和数字。
- 时尚/奢华：Playfair Display 拉丁展示 + ZCOOL XiaoWei 或 Noto Serif SC 中文 + Manrope 正文。
- 潮流/实验：Unbounded 或 Syne 作为单一强展示声部 + Noto Sans SC 正文，避免多个怪体互抢。

构建前运行 `deck.py prepare`。它从白名单或 `materials/font-config.json` 选择实际字体并前置字符子集；最终 `deck.py build` 会重新校验字体文件、授权/许可证元数据和渲染新鲜度。
