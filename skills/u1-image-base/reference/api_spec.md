# u1-image-base API 规格说明

## 目录

- [image-generate](#image-generate)
- [image-edit](#image-edit)
- [image-recognize](#image-recognize)
- [text-optimize](#text-optimize)
- [错误处理](#错误处理)

---

## image-generate

图片生成工具，调用 U1 text-to-image-no-enhance API。

### 命令格式

```bash
python openclaw_runner.py image-generate \
    --prompt <string> \
    [--api-key <string>] \
    [--base-url <string>] \
    [--negative-prompt <string>] \
    [--image-size 1k|2k] \
    [--aspect-ratio <string>] \
    [--seed <int>] \
    [--unet-name <string>] \
    [--poll-interval <float>] \
    [--timeout <float>] \
    [--insecure] \
    [--output-format text|json] \
    [--save-path <path>]
```

### 参数说明

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| `--prompt` | string | **是** | - | 文本提示词 |
| `--api-key` | string | 否 | 读取 `U1_API_KEY` 环境变量 | API Key（CLI 参数优先；两者都为空时抛出 `MissingApiKeyError`） |
| `--base-url` | string | 否 | 无硬编码默认值 | API 基础 URL（CLI > `U1_BASE_URL` 环境变量；均未设置时抛出错误） |
| `--negative-prompt` | string | 否 | `""` | 负向提示词 |
| `--image-size` | string | 否 | `"2k"` | 图片尺寸：1k 或 2k |
| `--aspect-ratio` | string | 否 | `"16:9"` | 宽高比 |
| `--seed` | int | 否 | `None` | 随机种子（可复现） |
| `--unet-name` | string | 否 | `None` | UNet 模型名称 |
| `--poll-interval` | float | 否 | `5.0` | 轮询间隔（秒） |
| `--timeout` | float | 否 | `300.0` | 超时时间（秒） |
| `--insecure` | flag | 否 | `False` | 禁用 TLS 验证 |
| `--output-format` | string | 否 | `"text"` | 输出格式：text 或 json |
| `--save-path` | path | 否 | 自动生成 | 输出图片路径 |

### 宽高比选项

`2:3`, `3:2`, `3:4`, `4:3`, `4:5`, `5:4`, `1:1`, `16:9`, `9:16`, `21:9`, `9:21`

### 输出路径

默认输出到 `/tmp/openclaw-u1-image/t2i_<timestamp>.png`

### 返回示例

**text 格式**:
```
Image generated successfully
/tmp/openclaw-u1-image/t2i_20260414_120000.png
```

**json 格式**:
```json
{
  "status": "ok",
  "output": "/tmp/openclaw-u1-image/t2i_20260414_120000.png",
  "task_id": "task_xxx",
  "message": "Image generated successfully",
  "elapsed_seconds": 1.23
}
```

### API Key 说明

`--api-key` 非必填，优先取 CLI 参数，未提供时自动读取环境变量 `U1_API_KEY`。若两者都为空，则抛出 `MissingApiKeyError`，错误信息如下：

**text 格式**:
```
Error: API key is required but was not provided. Set the U1_API_KEY environment variable or pass --api-key explicitly.
```

**json 格式**:
```json
{"status": "failed", "error": "API key is required but was not provided. Set the U1_API_KEY environment variable or pass --api-key explicitly.", "elapsed_seconds": 0.05}
```

---

## image-edit

图片编辑工具，调用 U1 image-edit API。

### 命令格式

```bash
python openclaw_runner.py image-edit \
    --image <string> \
    --prompt <string> \
    [--api-key <string>] \
    [--base-url <string>] \
    [--seed <int>] \
    [--poll-interval <float>] \
    [--timeout <float>] \
    [--insecure] \
    [--output-format text|json] \
    [--save-path <path>]
```

### 参数说明

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| `--image` | string | **是** | - | 输入图片路径、远程 URL 或缓存文件 key |
| `--prompt` | string | **是** | - | 编辑指令 |
| `--api-key` | string | 否 | 读取 `U1_API_KEY` 环境变量 | API Key（CLI 参数优先；两者都为空时抛出 `MissingApiKeyError`） |
| `--base-url` | string | 否 | 无硬编码默认值 | API 基础 URL（CLI > `U1_BASE_URL` 环境变量；均未设置时抛出错误） |
| `--seed` | int | 否 | `None` | 随机种子（可复现） |
| `--poll-interval` | float | 否 | `5.0` | 轮询间隔（秒） |
| `--timeout` | float | 否 | `300.0` | 超时时间（秒） |
| `--insecure` | flag | 否 | `False` | 禁用 TLS 验证 |
| `--output-format` | string | 否 | `"text"` | 输出格式：text 或 json |
| `--save-path` | path | 否 | 自动生成 | 输出图片路径 |

### 输出路径

默认输出到 `/tmp/openclaw-u1-image/edit_<timestamp>.png`

### 返回示例

**text 格式**:
```
Image edited successfully
/tmp/openclaw-u1-image/edit_20260414_120000.png
```

**json 格式**:
```json
{
  "status": "ok",
  "output": "/tmp/openclaw-u1-image/edit_20260414_120000.png",
  "task_id": "task_xxx",
  "message": "Image edited successfully",
  "elapsed_seconds": 1.47
}
```

### API Key 说明

与 `image-generate` 一致：`--api-key` 非必填，CLI 参数 > 环境变量 `U1_API_KEY`，两者都为空时抛出 `MissingApiKeyError`。

---

## image-recognize

图片识别工具，使用 VLM（Vision Language Model）分析图片内容。

### 命令格式

```bash
python openclaw_runner.py image-recognize \
    (--user-prompt <string> | --user-prompt-path <path>) \
    --images <string> [<string> ...] \
    --api-key <string> \
    --base-url <string> \
    --model <string> \
    [--system-prompt <string>] \
    [--system-prompt-path <path>] \
    [--vlm-type openai-completions|anthropic-messages] \
    [--output-format text|json]
```

### 参数说明

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| `--user-prompt` | string | 二选一 | - | 用户指令（与 `--user-prompt-path` 互斥） |
| `--user-prompt-path` | path | 二选一 | - | 本地文件路径，读取用户指令（与 `--user-prompt` 互斥） |
| `--images` | string[] | **是** | - | 图片路径列表（支持多个） |
| `--api-key` | string | 否 | 无硬编码默认值 | CLI > `VLM_API_KEY` > `U1_LM_API_KEY`；均未设置时抛出 `MissingApiKeyError` |
| `--base-url` | string | 否 | 无硬编码默认值 | CLI > `VLM_BASE_URL` 环境变量；均未设置时抛出错误 |
| `--model` | string | 否 | 无硬编码默认值 | CLI > `VLM_MODEL` 环境变量；均未设置时抛出错误 |
| `--system-prompt` | string | 否 | `""` | 系统指令（与 `--system-prompt-path` 互斥） |
| `--system-prompt-path` | path | 否 | - | 本地文件路径，读取系统指令（与 `--system-prompt` 互斥） |
| `--vlm-type` | string | 否 | `openai-completions` | CLI > `VLM_TYPE` 环境变量 > 内置默认 |
| `--output-format` | string | 否 | `"text"` | 输出格式：text 或 json |

`--vlm-type` 可选值：
- `openai-completions`: OpenAI 兼容 `/v1/chat/completions` 接口
- `anthropic-messages`: Anthropic Messages `/v1/messages` 接口

### 返回示例

**text 格式**:
```
这张图片展示了一只可爱的橘色猫咪在阳光下打盹。
```

**json 格式**:
```json
{
  "status": "ok",
  "result": "这张图片展示了一只可爱的橘色猫咪在阳光下打盹。",
  "model": "sensenova-122b-128k-step9k",
  "base_url": "http://10.210.9.11:615",
  "interface_type": "openai-completions",
  "elapsed_seconds": 2.15
}
```

### 参数优先级

`--api-key`、`--base-url`、`--model`、`--vlm-type` 均遵循两级优先级：**CLI 参数 > 环境变量**（无内置默认值，必须通过其中一种方式提供）

| 参数 | 内置默认值 | 环境变量 |
|------|-----------|---------|
| `--api-key` | 无（必须提供） | `VLM_API_KEY`（优先）→ `U1_LM_API_KEY`（兜底） |
| `--base-url` | 无（必须提供） | `VLM_BASE_URL` |
| `--model` | 无（必须提供） | `VLM_MODEL` |
| `--vlm-type` | `openai-completions` | `VLM_TYPE` |

---

## text-optimize

文本优化工具，使用 LLM（Language Language Model）优化文本内容。

### 命令格式

```bash
python openclaw_runner.py text-optimize \
    (--user-prompt <string> | --user-prompt-path <path>) \
    --api-key <string> \
    --base-url <string> \
    --model <string> \
    [--system-prompt <string>] \
    [--system-prompt-path <path>] \
    [--llm-type openai-completions|anthropic-messages] \
    [--output-format text|json]
```

### 参数说明

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| `--user-prompt` | string | 二选一 | - | 用户指令（与 `--user-prompt-path` 互斥） |
| `--user-prompt-path` | path | 二选一 | - | 本地文件路径，读取用户指令（与 `--user-prompt` 互斥） |
| `--api-key` | string | 否 | 无硬编码默认值 | CLI > `LLM_API_KEY` > `U1_LM_API_KEY`；均未设置时抛出 `MissingApiKeyError` |
| `--base-url` | string | 否 | 无硬编码默认值 | CLI > `LLM_BASE_URL` 环境变量；均未设置时抛出错误 |
| `--model` | string | 否 | 无硬编码默认值 | CLI > `LLM_MODEL` 环境变量；均未设置时抛出错误 |
| `--system-prompt` | string | 否 | `""` | 系统指令（与 `--system-prompt-path` 互斥） |
| `--system-prompt-path` | path | 否 | - | 本地文件路径，读取系统指令（与 `--system-prompt` 互斥） |
| `--llm-type` | string | 否 | `openai-completions` | CLI > `LLM_TYPE` 环境变量 > 内置默认 |
| `--output-format` | string | 否 | `"text"` | 输出格式：text 或 json |

`--llm-type` 可选值：
- `openai-completions`: OpenAI 兼容 `/v1/chat/completions` 接口
- `anthropic-messages`: Anthropic Messages `/v1/messages` 接口

### 返回示例

**text 格式**:
```
优化后的文本内容...
```

**json 格式**:
```json
{
  "status": "ok",
  "result": "优化后的文本内容...",
  "model": "sensenova-122b-128k-step9k",
  "base_url": "http://10.210.9.11:615",
  "interface_type": "openai-completions",
  "elapsed_seconds": 0.83
}
```

### 参数优先级

`--api-key`、`--base-url`、`--model`、`--llm-type` 均遵循两级优先级：**CLI 参数 > 环境变量**（`--llm-type` 有内置默认值 `openai-completions`，其他参数无内置默认值，必须通过其中一种方式提供）

| 参数 | 内置默认值 | 环境变量 |
|------|-----------|---------|
| `--api-key` | 无（必须提供） | `LLM_API_KEY`（优先）→ `U1_LM_API_KEY`（兜底） |
| `--base-url` | 无（必须提供） | `LLM_BASE_URL` |
| `--model` | 无（必须提供） | `LLM_MODEL` |
| `--llm-type` | `openai-completions` | `LLM_TYPE` |

---

## 错误处理

### 错误类型

| 类型 | 来源 | 触发条件 | 输出格式 |
|------|------|----------|----------|
| `MissingApiKeyError` | 业务层自定义异常 | `image-generate`/`image-edit` 的 API Key 未提供 | text: `Error: ...` / json: `{"status": "failed", "error": "..."}` |
| `ValueError` (prompt) | `_resolve_prompt` | `--user-prompt` 与 `--user-prompt-path` 同时提供、两者都未提供、或文件读取失败 | text: `Error: ...` / json: `{"status": "failed", "error": "..."}` |
| argparse 缺失参数 | argparse 标准报错 | `image-recognize`/`text-optimize` 缺少必填参数 | `usage: ...` + exit 2 |
| HTTP 错误 | httpx 请求层 | API 返回非 2xx 状态码 | `{"status": "failed", "error": "HTTP NNN", "message": "..."}` |
| 请求异常 | httpx 请求层 | 网络错误、超时等 | `{"status": "failed", "error": "<ExceptionType>", "message": "..."}` |

### text 格式

错误信息输出到 stderr，不影响 stdout 内容。

### json 格式

```json
{
  "status": "failed",
  "error": "错误类型",
  "message": "详细错误信息",
  "elapsed_seconds": 0.05
}
```

---

## API Key 环境变量

| 工具 | 环境变量（优先级高→低） | 说明 |
|------|----------------------|------|
| `image-generate` | `U1_API_KEY` | CLI 参数优先；未提供时读取此变量；均为空时抛出 `MissingApiKeyError` |
| `image-edit` | `U1_API_KEY` | CLI 参数优先；未提供时读取此变量；均为空时抛出 `MissingApiKeyError` |
| `image-recognize` | `VLM_API_KEY` → `U1_LM_API_KEY` | CLI > `VLM_API_KEY` > `U1_LM_API_KEY`；均为空时抛出 `MissingApiKeyError` |
| `text-optimize` | `LLM_API_KEY` → `U1_LM_API_KEY` | CLI > `LLM_API_KEY` > `U1_LM_API_KEY`；均为空时抛出 `MissingApiKeyError` |

`U1_LM_API_KEY` 是 VLM 和 LLM 的共同兜底变量，适合在 `.env` 中统一配置 Sensenova 内网 key。`VLM_API_KEY` / `LLM_API_KEY` 可在需要时独立覆盖各自的 key。
