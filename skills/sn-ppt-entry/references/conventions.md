# PPT 系 skill 共用约定

## 模型调用 = `sn-ppt-standard/lib/model_client.py`

所有 LLM / VLM / T2I 调用都走 `sn-ppt-standard/lib/model_client.py`（自包含、直接 httpx 打 endpoint、自动 `load_dotenv`）。**不再依赖 `sn-image-base`**。

三个函数：

```python
from model_client import llm, vlm, t2i
text = llm(system_prompt, user_prompt)                       # OpenAI-compat /v1/chat/completions
text = vlm(system_prompt, user_prompt, images=[path1, ...])  # same endpoint, with base64 image blocks
t2i(prompt, aspect_ratio="16:9", image_size="2k", save_path="...")  # U1 text-to-image
```

sn-ppt-standard 的 `scripts/run_stage.py` 对每个阶段都封装成 `python run_stage.py <stage> ...` 的 CLI；其它 skill（sn-ppt-entry, sn-ppt-creative）要调模型时直接 `sys.path.insert(sn-ppt-standard/lib)` + `from model_client import llm`。

## 占位符

| 占位符 | 含义 | 示例 |
|---|---|---|
| `$SKILL_DIR` | 当前 skill 的安装目录（OpenClaw 自动注入） | `/abs/.../skills/sn-ppt-standard` |
| `$PPT_STANDARD_DIR` | `sn-ppt-standard` skill 的安装目录（OpenClaw 自动注入，跨 skill 用） | `/abs/.../skills/sn-ppt-standard` |
| `<deck_dir>` | `task_pack.json` 的 `deck_dir` 字段（主 agent 按任务上下文替换） | `/abs/.../ppt_decks/AI_...` |
| `<deck_id>` | `task_pack.json` 的 `deck_id` | `AI_20260422_212501` |
| `<NNN>` | 页号三位补零 | `001` / `012` |

`$NAME` 是 shell 变量（OpenClaw 注入），shell 原生解析；`<name>` 是主 agent 按字面替换。

## `.env` 定位

`model_client.py` 启动时按顺序尝试加载：
1. `<repo>/.env`
2. `<repo>/skills/.env`
3. `cwd/.env`

用户把 `.env` 放哪都行（建议仓库根）。

必填变量：
- `SN_CHAT_API_KEY`（LLM/VLM 默认共享 key；可用 `SN_TEXT_API_KEY` / `SN_VISION_API_KEY` 分别覆盖）
- `SN_IMAGE_GEN_API_KEY` + `SN_IMAGE_GEN_BASE_URL` + `SN_IMAGE_GEN_MODEL`

可选覆盖：`SN_CHAT_BASE_URL` / `SN_CHAT_TYPE` / `SN_CHAT_MODEL`、`SN_TEXT_*`、`SN_VISION_*`、`SN_CHAT_TIMEOUT` 等。

## 绝对路径原则

所有落盘到 `<deck_dir>` 的工件里涉及 path 的字段**一律用绝对路径**，但 **asset_plan.json 的 `local_path` 例外**——它是相对 `<deck_dir>` 的 `images/page_XXX_<slot>.png`，这样下游 HTML 能用 `../images/...` 相对引用。

## 内联注入 `<<<INLINE: path>>>`

Prompt 文件里出现这种字面量：

```
<<<INLINE: references/html_constraints.md>>>
```

`run_stage.py` 的 `_load_prompt()` 读 prompt 时自动用同 skill 目录下对应文件的全文替换。主 agent 不用管。
