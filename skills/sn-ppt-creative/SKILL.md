---
name: sn-ppt-creative
description: Use when a prepared PPT task with a current outline.md should be generated as an image-first presentation with one 16:9 image per slide and optional PPTX packaging.
metadata:
  project: SenseNova-Skills
  tier: 1
  category: scene
  user_visible: false
triggers:
  - "sn-ppt-creative"
---

# sn-ppt-creative

把公共 Story 转译成一套 16:9 整页视觉：每页生成一张完整 PNG，并可组装为 PPTX。
Creative 负责视觉转译，不负责 Research，不生成自己的内容大纲。

## 前置与目录边界

必须存在：

- `<DECK_DIR>/task_pack.json`
- `<DECK_DIR>/info_pack.json`
- `<DECK_DIR>/outline.md`
- `task_pack.choices.output == "creative"`，或旧任务的 `ppt_mode == "creative"`

`DECK_DIR` 只能取 `task_pack.deck_dir` 的绝对路径。所有生成产物只写到该目录；不得写入
用户 home 根目录、宿主 workspace 根目录、Skill 目录、repo、`/tmp` 或另一个 workspace。
已有任务必须复用原 `DECK_DIR`，不得另建目录。

把当前 Skill 所在目录记为只读的 `SKILL_ROOT`，把同级 `sn-ppt-tools/` 解析为绝对
`PPT_TOOLS_DIR`。开始生图前读取
`$PPT_TOOLS_DIR/references/capability-policy.md`。文本推理、风格判断和视觉理解使用宿主
Agent 原生能力；图片生成优先使用宿主原生工具，原生能力不存在或一次实际调用失败时，
才使用 PPT 整包自带的 `image_generate.py`。

不得调用 `model_client.py`、`sn_agent_runner.py`，不得要求用户在 Agent 外再配置文本或
视觉模型 API。

## 公共 Story 契约

开始和恢复时重新读取磁盘上的 `outline.md`。它固定：

- 页数、页序和标题；
- 每页核心结论、内容依据、上屏内容边界和前后关系；
- 用户明确保留、删除或修改的内容。

Creative 可以决定视觉隐喻、艺术媒介、构图、页面动势和信息图形语言，但不能：

- 合并、拆分、增删或重排页面；
- 改变标题和核心结论的含义；
- 恢复用户从 outline 删除的内容；
- 自行搜索事实、补案例或另写 `outline.json`；
- 因整页生图偏好而牺牲事实、逻辑或文字可读性。

发现现有材料不足时，保留对应页位并明确缺口，返回 Entry/Story；不得在 Creative 内补做
Research。

## 设计丰富度

读取 `task_pack.choices.design_richness`：

- `restrained`：收敛构图、材质、文字装饰和视觉隐喻，优先稳定与清晰。
- `rich`：默认，在清晰信息层级上提供充分画面、页型变化和跨页一致性。
- `high_creative`：允许更大胆的构图、艺术媒介、英雄页面和视觉动势，但不牺牲文字
  可读性、事实和 Story。

丰富度只控制视觉投入，不改变页数、结论和 Research 边界。本发布版不再提供额外的
Artistic/Classical 分线选择。

## 产物

```text
style_spec.md
pages/
  page_001.prompt.txt
  page_001.png
  page_002.prompt.txt
  page_002.png
...
<deck_id>.pptx
```

`style_spec.md` 是出口内部的视觉说明，不是第二份 Story；它只能补充跨页视觉语言、构图
规则、配色、材质、字体气质和负面约束，不得重写 outline。

## 恢复

先运行：

```bash
python3 "$SKILL_ROOT/scripts/resume_scan.py" --deck-dir "$DECK_DIR"
```

按磁盘真实产物继续：

- `style_spec.md` 不存在：重新形成 deck 级视觉说明；
- `page_NNN.prompt.txt` 存在而 PNG 缺失：只重新生图；
- PNG 已存在：跳过该页；
- 用户修改了 outline：重新生成受影响页面的 prompt 和 PNG，不让旧 prompt 覆盖新内容；
- PPTX 缺失或页面发生变化：重新打包；
- 已有 style、prompt、PNG 和 PPTX 不无故删除。

## 工作流

### 1. 读取输入并形成视觉说明

读取 task/info pack、当前 outline、用户材料索引、已有 Research 主报告以及
`reference_image_captions`。把 `task_pack.state.current_stage` 写为
`output.creative.plan`，状态写为 `generating`。

由宿主 Agent 直接形成 `<DECK_DIR>/style_spec.md`。至少明确：

- 主题、受众、场景与视觉目标；
- 一句跨页视觉概念；
- 背景明暗、主辅色、文字层级和画面媒介；
- 封面、正文、数据页、过渡页和结尾页的统一关系；
- 为保证可读性和避免把设计说明画进页面而设置的负面约束。

有参考图片时使用宿主原生视觉能力理解它们，并优先复用 `info_pack` 中已有说明；同一张图
不重复理解。不得在本阶段搜索事实或改写 outline。

### 2. 逐页形成最终生图 prompt

每一页从当前 outline 的同序号页面生成一个
`<DECK_DIR>/pages/page_NNN.prompt.txt`。prompt 必须包含：

- 本页标题、核心结论和最终上屏文字；
- 本页与前后页的叙事关系；
- 构图、视觉层级、主体、背景、留白和阅读路径；
- `style_spec.md` 中需要跨页一致的视觉语言；
- 16:9 整页演示画面，以及所有文字清晰、完整、语言一致的要求；
- 禁止出现设计规格、色值、尺寸标注、代码、占位符和额外文案。

不能把 `style_spec.md`、JSON、CSS 或内部字段名直接拼进 prompt。写完每页后执行：

```bash
python3 "$SKILL_ROOT/scripts/sanitize_prompt.py" \
  --path "$DECK_DIR/pages/page_NNN.prompt.txt"
```

一页一个独立 Agent 动作，不用单个脚本循环生成全套 prompt。每页完成后输出简短进度。

### 3. 逐页生成整图

对每个缺少 PNG 的页面：

1. 当前 Agent 有原生图片生成工具时，先用它读取对应 prompt，生成 16:9 整页图片，并把
   最终文件保存到 `$DECK_DIR/pages/page_NNN.png`。
2. 原生工具不存在或一次实际调用失败时，执行内置回退：

   ```bash
   python3 "$PPT_TOOLS_DIR/scripts/image_generate.py" \
     --prompt-file "$DECK_DIR/pages/page_NNN.prompt.txt" \
     --deck-dir "$DECK_DIR" \
     --output "pages/page_NNN.png" \
     --size "2752x1536"
   ```

3. 两层都不可用或失败时，记录该页失败并继续其他页。不得创建空白图、透明图、占位图或
   伪造成功。

每页生图是一个独立工具调用，成功或失败后都输出 heartbeat。不得在第一次失败后循环
重试；用户后续明确要求重试时再恢复该页。

如果开始生产前已经确认原生和内置生图都不可用，保留 style、prompt 和前置公共产物，
把状态写为 `partial` 并停止 Creative 出口；不得静默切换到 Standard、Dynamic 或 Native
PPTX。

### 4. 打包 PPTX

所有页面处理后执行：

```bash
python3 "$SKILL_ROOT/scripts/build_pptx.py" --deck-dir "$DECK_DIR"
```

脚本按页号把已有 PNG 满版放入 16:9 PPTX；缺失页保留为空白页并在结果中报告。脚本或
本地依赖不可用时，不安装新依赖，不改用其他构建器；逐页 PNG 仍是有效交付。

把 `pages/` 和可用 PPTX 的绝对路径写入 `task_pack.state.artifacts`，把 `creative` 加入
`completed_stages`。全部页面成功时状态写 `completed`；存在缺页或打包失败时写
`partial` 和 `last_error`。

## 进度与收尾

必须提供用户可见的简短进度：

```text
已进入 sn-ppt-creative，共 N 页
[style] style_spec.md 完成
[prompt 2/N] 完成
[图 2/N] page_002.png 完成
[pptx] <deck_id>.pptx 完成
```

失败时在对应行说明原因，然后继续。收尾只总结输出目录、成功页、失败页和 PPTX 状态，
并指出 `outline.md` 是用户可编辑的叙事源。

## 硬规则

1. 不调用 `model_client.py`、`sn_agent_runner.py` 或额外文本模型 API。
2. 不生成第二份内容大纲，不让视觉计划反向覆盖 `outline.md`。
3. 不在 Creative 出口 Research 或新增事实。
4. 不伪造图片，不把远程 URL 当作最终页面。
5. 一页一个 prompt 和一次生图动作，不把整套页面藏进不可见循环。
6. 所有用户可见文字使用用户请求的语言。
7. 所有写入都位于 task pack 指定的绝对 `DECK_DIR`。
8. 原有可用产物、断点恢复和 PNG -> PPTX 能力不得无故删除。
