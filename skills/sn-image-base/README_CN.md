# sn-image-base

该技能属于 [SenseNova-Skills](https://github.com/OpenSenseNova/SenseNova-Skills) 项目，提供图像生成、图像识别（VLM）和文本优化（LLM）的底层 API 能力。

完整行为请见 [SKILL.md](SKILL.md)。

本文档主要介绍该技能的详细配置。

概览与技能安装、使用方法请参考项目根目录下的 [README.md](../../README.md)（中文可见 [README_CN.md](../../README_CN.md)）；详细配置以本文档为准。

## 概览

该技能提供以下子命令：

- `sn-image-generate`：图像生成
- `sn-image-recognize`：图像识别（VLM）
- `sn-text-optimize`：文本优化（LLM）

支持的模型服务如下：

- 图像生成：
  - [SenseNova](https://platform.sensenova.cn/)
  - Nano Banana API
  - OpenAI 图像生成 API（例如 GPT-Image-2）

- 文本与视觉 Chat：
  - [SenseNova](https://platform.sensenova.cn/)
  - 通过 Anthropic Messages API 接入的模型（例如 Claude Sonnet 4.6）
  - 通过 OpenAI Chat Completion API 接入的模型（例如 GPT、Gemini/Qwen 等 OpenAI 兼容格式模型）

## 配置

### 快速开始

推荐使用 [SenseNova Token Plan](https://platform.sensenova.cn/token-plan)。

前往 <https://platform.sensenova.cn/token-plan/> 注册免费账号，并获取可用于图像生成和 chat 调用的 API Key。

将以下环境变量写入 `~/.openclaw/.env`（OpenClaw）或 `~/.hermes/.env`（Hermes）：

```ini
# 图像生成
SN_IMAGE_GEN_API_KEY="<sensenova-token-plan-api-key>"
SN_IMAGE_GEN_MODEL="sensenova-u1-fast"   # 或 Token Plan 中可用的其他图像生成模型
# 文本与视觉 Chat Runtime
SN_CHAT_API_KEY="<sensenova-token-plan-api-key>"
SN_CHAT_MODEL="sensenova-6.7-flash-lite"
```

**注意：不要将 `.env` 文件或 API key 提交到 git。**

### 详细配置

完成 [快速开始](#快速开始) 后即可使用本技能。

若需更进一步配置（例如使用不同模型、修改 base URL 等），请参考以下内容。

支持多重配置来源，优先级（从高到低）如下：

- （推荐）`~/.openclaw/.env`（OpenClaw）或 `~/.hermes/.env`（Hermes）
- 当前工作目录 `.env`（不一定存在，取决于 agent 运行技能的方式）
- 进程环境变量

> 进阶开发者可查看 [configs.py](scripts/sn_image_base/configs.py) 获取完整变量与默认值。
>
> 便于快速追踪行为的关键符号：
>
> - `prepare_env()`：`.env` 加载顺序
> - `Field.resolve()`：环境变量回退顺序（“第一个已设置值优先”）
> - `Configs`：默认值与环境变量映射

#### 图像生成

图像生成完整配置如下：

| 配置键 | 说明 | 默认值 |
| ------ | ---- | ------ |
| `SN_IMAGE_GEN_API_KEY` | SenseNova Token Plan 的 API Key | （必填） |
| `SN_IMAGE_GEN_MODEL_TYPE` | 图像生成模型类型 | `"sensenova"` |
| `SN_IMAGE_GEN_MODEL` | 图像生成模型名 | `"sensenova-u1-fast"` |
| `SN_IMAGE_GEN_BASE_URL` | 图像生成 API 的基础 URL | `"https://token.sensenova.cn/v1"` |

默认值适用于 [SenseNova](https://platform.sensenova.cn/)。

通常只需设置 `SN_IMAGE_GEN_API_KEY`，并可按需将 `SN_IMAGE_GEN_MODEL` 设置为 token plan 提供的模型名。

如需使用非默认图像生成模型，请按以下步骤：

1. 设置 `SN_IMAGE_GEN_MODEL_TYPE` 为对应模型类型，可选值如下：

    ```ini
    # （默认）用于 [SenseNova](https://platform.sensenova.cn/)
    SN_IMAGE_GEN_MODEL_TYPE="sensenova"
    # 用于 Google Nano Banana 模型 API
    SN_IMAGE_GEN_MODEL_TYPE="nano-banana"
    # 用于 OpenAI 图像生成 API
    SN_IMAGE_GEN_MODEL_TYPE="openai-image"
    ```

2. 设置 `SN_IMAGE_GEN_BASE_URL` 为图像生成 API 的基础 URL，例如：

    ```ini
    # （默认）用于 [SenseNova](https://platform.sensenova.cn/)
    SN_IMAGE_GEN_BASE_URL="https://token.sensenova.cn/v1"
    # 用于 Google Nano Banana 模型 API
    SN_IMAGE_GEN_BASE_URL="https://generativelanguage.googleapis.com"
    # 用于 OpenAI 图像生成 API
    SN_IMAGE_GEN_BASE_URL="https://api.openai.com/v1"
    ```

3. 设置 `SN_IMAGE_GEN_MODEL` 为对应类型下的模型名，例如：

    ```ini
    # （默认）用于 [SenseNova](https://platform.sensenova.cn/)
    SN_IMAGE_GEN_MODEL="sensenova-u1-fast"
    # 用于 Google Nano Banana 模型 API
    SN_IMAGE_GEN_MODEL="gemini-3.1-flash-image-preview"
    # 用于 OpenAI 图像生成 API
    SN_IMAGE_GEN_MODEL="gpt-image-2"
    ```

4. （必填）设置 `SN_IMAGE_GEN_API_KEY` 为图像生成 API 的密钥：

    ```ini
    SN_IMAGE_GEN_API_KEY="sk-your-image-generation-api-key"
    ```

#### 文本与视觉 Chat

##### 配置共享 Chat Runtime

文本优化和图像识别现在共享一套 chat runtime。协议、endpoint、API key 与默认模型配置一次，仅在需要时分别覆盖文本或视觉模型：

| 配置键 | 说明 | 默认值 |
| ------ | ---- | ------ |
| `SN_CHAT_API_KEY` | text/vision chat 调用共用 API key | （必填） |
| `SN_CHAT_BASE_URL` | 共享 Chat API 基础 URL | `"https://token.sensenova.cn/v1"` |
| `SN_CHAT_TYPE` | 共享 Chat 协议类型 | `"openai-completions"` |
| `SN_CHAT_MODEL` | text/vision chat 调用共用默认模型 | `"sensenova-6.7-flash-lite"` |
| `SN_TEXT_API_KEY` | 可选文本 provider API key | `SN_CHAT_API_KEY` |
| `SN_TEXT_BASE_URL` | 可选文本 provider 基础 URL | `SN_CHAT_BASE_URL` |
| `SN_TEXT_TYPE` | 可选文本协议类型 | `SN_CHAT_TYPE` |
| `SN_TEXT_MODEL` | 可选的 `sn-text-optimize` 模型覆盖 | `SN_CHAT_MODEL` |
| `SN_VISION_API_KEY` | 可选视觉 provider API key | `SN_CHAT_API_KEY` |
| `SN_VISION_BASE_URL` | 可选视觉 provider 基础 URL | `SN_CHAT_BASE_URL` |
| `SN_VISION_TYPE` | 可选视觉协议类型 | `SN_CHAT_TYPE` |
| `SN_VISION_MODEL` | 可选的 `sn-image-recognize` 视觉模型覆盖 | `SN_CHAT_MODEL` |

默认值适用于 [SenseNova](https://platform.sensenova.cn/)。

仅当文本或视觉命令需要使用不同 provider 时，才需要配置 `SN_TEXT_*` 或 `SN_VISION_*`。

对于 chat 调用，runner 也兼容不带路径的 host-only base URL，例如
`https://token.sensenova.cn`：如果 URL 中没有 path，会先补上 API 版本路径再追加具体接口。
为保持和内置默认值一致，建议优先使用带版本路径的 base URL，例如
`https://token.sensenova.cn/v1`。

如需使用非默认 chat 设置，请按以下步骤：

1. 按 chat API 协议设置 `SN_CHAT_TYPE`。可选值如下：

    ```ini
    # （默认）OpenAI 兼容 `/chat/completions` 接口（最常见）
    SN_CHAT_TYPE="openai-completions"
    # Anthropic Messages `/messages` 接口
    SN_CHAT_TYPE="anthropic-messages"
    ```

2. 将 `SN_CHAT_BASE_URL` 设置为共享 chat endpoint 的基础 URL，例如：

    ```ini
    # （默认）用于 [SenseNova](https://platform.sensenova.cn/)
    SN_CHAT_BASE_URL="https://token.sensenova.cn/v1"
    # 用于 Anthropic Messages API
    SN_CHAT_BASE_URL="https://api.anthropic.com/v1"
    # 用于 OpenAI Chat Completion API
    SN_CHAT_BASE_URL="https://api.openai.com/v1"
    # 用于 Google Gemini API（OpenAI 兼容）
    SN_CHAT_BASE_URL="https://generativelanguage.googleapis.com/v1beta/openai/"
    ```

3. 设置 `SN_CHAT_MODEL`，仅在文本或视觉命令需要不同模型时再设置 `SN_TEXT_MODEL` / `SN_VISION_MODEL`：

    ```ini
    # （默认）SenseNova 6.7 Flash Lite
    SN_CHAT_MODEL="sensenova-6.7-flash-lite"
    # Anthropic Claude Sonnet 4.6
    SN_VISION_MODEL="claude-sonnet-4-6"
    # Google Gemini 3 Flash Preview
    SN_VISION_MODEL="gemini-3-flash-preview"
    # OpenAI GPT 5.5
    SN_TEXT_MODEL="gpt-5.5"
    ```

4. （必填）设置 `SN_CHAT_API_KEY` 为共享 chat endpoint 的 API key：

    ```ini
    SN_CHAT_API_KEY="sk-your-api-key"
    ```

## 故障排查

### 缺少 API key

- 现象：报错包含 "required but not set"、"missing api key" 或请求未授权。
- 处理：图像生成需设置 `SN_IMAGE_GEN_API_KEY`；chat 调用需设置 `SN_CHAT_API_KEY`。如果文本和视觉使用不同 provider，可设置 `SN_TEXT_API_KEY` 或 `SN_VISION_API_KEY`。

### base URL 配置错误

- 现象：请求立即失败，或出现 URL 校验 / endpoint 相关错误。
- 处理：检查 `SN_IMAGE_GEN_BASE_URL`、`SN_CHAT_BASE_URL`、`SN_TEXT_BASE_URL`、`SN_VISION_BASE_URL` 是否为完整基础 URL（包含 scheme + host），例如 `https://token.sensenova.cn/v1`。

### 模型名不支持

- 现象：provider 返回 HTTP 404 / model-not-found / bad request。
- 处理：确认 `*_MODEL_TYPE` / `*_TYPE` 与 `*_MODEL` 来自同一 provider，且模型在当前账号下可用。

### 鉴权 / 权限错误

- 现象：HTTP 401/403、"permission denied"、"forbidden"。
- 处理：确认密钥与所选 provider endpoint 匹配，检查账号配额/权限，并使用已知可用模型重试。

## 安全说明

- **不要**将 `.env` 文件或 API key 提交到 git。
- 若密钥泄露，请立即轮换并更新本地环境变量文件。
- 优先使用本地密钥管理（`~/.openclaw/.env` 或 `~/.hermes/.env`），避免在脚本或提示词中硬编码密钥。
