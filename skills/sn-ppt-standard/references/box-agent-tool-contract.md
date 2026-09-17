# Box-Agent 工具契约

本文件是 `sn-ppt-standard` 在 Box-Agent 上的薄适配层。只翻译 harness 接口，不降低根 `SKILL.md`、reference 或角色卡中的事实、设计、视觉验收与交付要求。

## 1. 路径与执行所有权

- 从已加载 Skill 提示中的 `Skill Root Directory` 取得绝对路径，记为 `<SKILL_ROOT>`。所有确定性命令使用 `python "<SKILL_ROOT>/scripts/<name>.py" ...`；不得依赖 `${SKILL_DIR:-skills/sn-ppt-standard}` 或当前目录中存在 `skills/`。
- 父 Orchestrator 不在 Standard 阶段执行材料解析；Standard 只读取 Entry/Story 已交接的 `raw_documents.json`、`info_pack.json` 和 `outline.md`。父级使用 `bash` 执行 `deck.py`、`render.py`、`font_bundle.py`、`image_cutout.py` 和本契约的 `serper_images.py`。Box-Agent 子代理不请求 `bash`；父级负责转换、渲染、联系表、来源登记和 build。
- 所有 bash/脚本命令的任务根参数必须传入已验证的绝对 `"$DECK_DIR"`；禁止以当前工作目录、`.`或未解析的 `output/` 代替任务根。只有 `write_scope` 以及 CLI 明确要求的资产键（例如`assets/<file>`）可以使用 artifact-root-relative 形式；脚本内部负责把它们解析到`$DECK_DIR`。产物直接写 `plan/`、`assets/`、`slides/`、`renders/`、`speech.md`、`present.html`，并可由 Standard exporter 生成 `<DECK_ID>.pptx`；不要添加 `output/` 层。

## 2. 工具映射

只调用 Box-Agent 展示的 canonical 工具名，不依赖执行期旧别名。

| 旧 harness 写法 | Box-Agent 写法 |
| --- | --- |
| `read_file(path, offset, limit)` | `read_file(path, offset, limit)` |
| `write_file(path, content)` | `write_file(path, content)`；大文件按该工具返回的 chunk 合同继续 |
| `patch(path, old_string, new_string)` | `edit_file(path, old_str, new_str)`；旧串必须唯一，先读后改 |
| `search_files(...)` | `search_files(...)` |
| `terminal(command, ...)` | 父级 `bash(command, timeout)`；不用旧 `workdir/background` 参数 |
| `vision_analyze(image_url, question)` | `inspect_images(image_paths=[...], instruction=..., strategy="native")` |
| `image_generate(prompt, aspect_ratio)` | `generate_image(prompt, output_path, size, watermark=false)` |
| `delegate_task(...)` | `sub_agent(title, task, required_tools, write_scope, budget)` |

视觉模型优先使用 `strategy="native"`，让当前角色直接看新鲜像素。只有工具明确返回 `IMAGE_NATIVE_UNSUPPORTED` 时才改用 `proxy`，并在交接中标明这是代理视觉结论。每次最多检查 6 张图；HTML/CSS 修改后必须先重渲再看。

## 3. Box-Agent 委派合同

- 一次 `sub_agent` 只委派一个完整工作单元；需要并行时，在同一模型回合发出多个互相独立的 `sub_agent` 调用，不使用旧 `tasks` 数组。
- `title` 对应旧 `label`；`task` 必须自包含，包含语言合同、角色卡绝对路径、此契约绝对路径、输入路径、输出路径、页码/素材所有权和结构化返回要求。
- `required_tools` 只给完成任务所需的 canonical 工具。凡包含 `write_file`、`append_file` 或 `edit_file`，必须给精确且互不重叠的 `write_scope`。
- 子代理不递归委派，不读运行轨迹。父级以子代理自然语言合同为交接，并用 `read_file` / `search_files` 验证声明的正式产物。
- Research 可用 `read_file/search_files/web_search/web_extract/write_file`；Material 只在父级 staging 后读取解析产物并写指定摘要；Image 优先用 `generate_image/inspect_images/read_file`；Slide/Review 用文件工具和 `inspect_images`，由父级在两次委派之间完成渲染。

## 4. 生图、搜图与来源账本

### 生图

调用 Box-Agent 原生 `generate_image`，必须给出位于 `assets/` 下的稳定 `output_path`。OpenAI 兼容服务使用 `1536x1024`、`1024x1536` 或 `1024x1024`；16:9 页面素材先选 `1536x1024`，再按计划的 crop contract 处理。PPT 素材调用显式传 `watermark=false`。

生成成功后，父级立即登记来源：

```bash
python "<SKILL_ROOT>/scripts/deck.py" asset-register "$DECK_DIR" \
  --path assets/<file> --origin generated \
  --generator-model gpt-image-2 --prompt '<原始提示词>'
```

### Serper 搜图和真实图落地

若会话已有 schema 明确支持 `search_type="images"` 的 `web_search`，可先用它检索；否则父级使用 skill 自带的确定性入口，密钥只从 `SERPER_API_KEY` 环境变量读取：

```bash
python "<SKILL_ROOT>/scripts/serper_images.py" search --query '<查询>' --limit 6
python "<SKILL_ROOT>/scripts/serper_images.py" fetch --url '<图片直链>' --root "$DECK_DIR"
```

`fetch` 校验响应确为可解析位图，写入 `assets/`，并通过现有 `deck.py asset-register` 自动记录 `origin=downloaded` 与原始 URL。不得把密钥写进计划、日志、HTML、讲稿或 `assets/catalog.json`。

## 5. 父级渲染闭环

Box-Agent 路线将 shell 与页面写入分离：

1. Slide 子代理只写自己 `write_scope` 内的 HTML，并返回待渲染页码。
2. 父级运行 `render.py --batch`，再用 `inspect_images(strategy="native")` 看新 PNG。
3. 有硬伤时，父级把新鲜像素证据和精确问题交给同页范围的修复子代理；最多遵守根 Skill 规定的修复预算。
4. 父级重渲并复看。最终 Review 同样由父级先提供新鲜 PNG、Review 子代理集中修复、父级统一重渲/build；父级统一执行重渲、build、inspect 和 Standard exporter，只有最终 PNG 与 `present.html` 验证通过后才导出，失败登记 `state.status=partial`。

工具名或权限失败先按本契约修正一次；相同失败再次出现就保存原始错误、调用参数和产物状态，返回 `blocked`，不得搜索或修改 Box-Agent 源码。
