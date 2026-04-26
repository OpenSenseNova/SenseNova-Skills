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

- LLM/VLM：
  - [SenseNova](https://platform.sensenova.cn/)
  - 通过 Anthropic Messages API 接入的模型（例如 Claude Sonnet 4.6）
  - 通过 OpenAI Chat Completion API 接入的模型（例如 GPT、Gemini/Qwen 等 OpenAI 兼容格式模型）

## 配置

### 快速开始

推荐使用 [SenseNova Token Plan](https://platform.sensenova.cn/token-plan)。

前往 <https://platform.sensenova.cn/token-plan/> 注册免费账号，并获取可用于图像生成和 LLM/VLM 的 API Key。

将以下环境变量写入 `~/.openclaw/.env`（OpenClaw）或 `~/.hermes/.env`（Hermes）：

```ini
# 图像生成
SN_API_KEY="<sensenova-token-plan-api-key>"
SN_IMAGE_GEN_MODEL="sensenova-u1-fast"   # 或 Token Plan 中可用的其他图像生成模型
# LLM/VLM
SN_LM_API_KEY="<sensenova-token-plan-api-key>"
SN_LM_MODEL="sensenova-6.7-flash-lite"   # 或 Token Plan 中可用的其他 LLM/VLM 模型
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
| `SN_API_KEY` | SenseNova Token Plan 的 API Key | （必填） |
| `SN_IMAGE_GEN_MODEL_TYPE` | 图像生成模型类型 | `"sensenova"` |
| `SN_IMAGE_GEN_MODEL` | 图像生成模型名 | `"sensenova-u1-fast"` |
| `SN_IMAGE_GEN_BASE_URL` | 图像生成 API 的基础 URL | `"https://token.sensenova.cn/v1"` |

默认值适用于 [SenseNova](https://platform.sensenova.cn/)。

通常只需设置 `SN_API_KEY`，并可按需将 `SN_IMAGE_GEN_MODEL` 设置为 token plan 提供的模型名。

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

4. （必填）设置 `SN_API_KEY` 为图像生成 API 的密钥：

    ```ini
    SN_API_KEY="sk-your-image-generation-api-key"
    ```

#### VLM 与 LLM

若你不打算为 VLM 和 LLM 分别使用不同模型，可直接使用同一组 `SN_LM_*` 环境变量统一配置，并跳过后续拆分配置部分。

##### 使用相同的 VLM 和 LLM 模型

使用共享 `SN_LM_*` 环境变量时，VLM/LLM 的完整配置如下：

| 配置键 | 说明 | 默认值 |
| ------ | ---- | ------ |
| `VLM_API_KEY` 与 `LLM_API_KEY`（通过 `SN_LM_API_KEY` env var） | VLM 与 LLM API Key | （必填） |
| `VLM_BASE_URL` 与 `LLM_BASE_URL`（通过 `SN_LM_BASE_URL` env var） | VLM 与 LLM API 的基础 URL | `"https://token.sensenova.cn/v1"` |
| `VLM_MODEL` 与 `LLM_MODEL`（通过 `SN_LM_MODEL` env var） | VLM 与 LLM 模型名 | `"sensenova-6.7-flash-lite"` |
| `VLM_TYPE` 与 `LLM_TYPE`（通过 `SN_LM_TYPE` env var） | VLM 与 LLM API 类型 | `"openai-completions"` |

默认值适用于 [SenseNova](https://platform.sensenova.cn/)。

通常只需设置 `SN_LM_API_KEY`，并可按需将 `SN_LM_MODEL` 设置为 token plan 提供的模型名。

如需使用非默认的 VLM/LLM 设置，请按以下步骤：

1. 按 VLM/LLM 的 API 类型设置 `VLM_TYPE` 与 `LLM_TYPE`（配置 `SN_LM_TYPE` 环境变量）。可选值如下：

    ```ini
    # （默认）OpenAI 兼容 `/chat/completions` 接口（最常见）
    SN_LM_TYPE="openai-completions"
    # Anthropic Messages `/messages` 接口
    SN_LM_TYPE="anthropic-messages"
    ```

2. 将 `VLM_BASE_URL` 与 `LLM_BASE_URL`（配置 `SN_LM_BASE_URL` 环境变量）设置为 VLM/LLM API 的基础 URL，例如：

    ```ini
    # （默认）用于 [SenseNova](https://platform.sensenova.cn/)
    SN_LM_BASE_URL="https://token.sensenova.cn/v1"
    # 用于 Anthropic Messages API
    SN_LM_BASE_URL="https://api.anthropic.com/v1"
    # 用于 OpenAI Chat Completion API
    SN_LM_BASE_URL="https://api.openai.com/v1"
    # 用于 Google Gemini API（OpenAI 兼容）
    SN_LM_BASE_URL="https://generativelanguage.googleapis.com/v1beta/openai/"
    ```

3. 将 `VLM_MODEL` 与 `LLM_MODEL`（配置 `SN_LM_MODEL` 环境变量）设置为 VLM/LLM 模型名，例如：

    ```ini
    # （默认）SenseNova 6.7 Flash Lite
    SN_LM_MODEL="sensenova-6.7-flash-lite"
    # Anthropic Claude Sonnet 4.6
    SN_LM_MODEL="claude-sonnet-4-6"
    # Google Gemini 3 Flash Preview
    SN_LM_MODEL="gemini-3-flash-preview"
    # OpenAI GPT 5.5
    SN_LM_MODEL="gpt-5.5"
    ```

4. （必填）设置 `VLM_API_KEY` 与 `LLM_API_KEY`（配置 `SN_LM_API_KEY` 环境变量）为 VLM/LLM API 的密钥：

    ```ini
    SN_LM_API_KEY="sk-your-api-key"
    ```

##### 使用不同的 VLM 和 LLM 模型

如果你希望 VLM 和 LLM 使用不同模型，可以使用不同环境变量分别配置 VLM（图像识别）API 与 LLM（文本优化）API。

> **变量优先级（明确规则）**
>
> 当同一配置项可由多个变量配置时，`configs.py` 中定义顺序靠前且已设置的 env var 优先。
>
> - 对于 VLM 模型：若同时设置 `VLM_MODEL` 与 `SN_LM_MODEL`，则 `VLM_MODEL` 生效。
> - 对于 LLM 模型：若同时设置 `LLM_MODEL` 与 `SN_LM_MODEL`，则 `LLM_MODEL` 生效。
>
> 例如：
>
> ```ini
> SN_LM_MODEL="sensenova-6.7-flash-lite"
> VLM_MODEL="claude-sonnet-4-6"
> ```
>
> 在此情况下，VLM 使用 `claude-sonnet-4-6`，而 LLM 仍使用 `sensenova-6.7-flash-lite`（除非也设置了 `LLM_MODEL`）。

VLM 的独立环境变量如下：

| 配置键 | 说明 | 默认值 |
| ------ | ---- | ------ |
| `VLM_API_KEY` | VLM API Key | （必填） |
| `VLM_BASE_URL` | VLM API 基础 URL | `"https://token.sensenova.cn/v1"` |
| `VLM_MODEL` | VLM 模型名 | `"sensenova-6.7-flash-lite"` |
| `VLM_TYPE` | VLM API 类型 | `"openai-completions"` |

LLM 独立环境变量如下：

| 配置键 | 说明 | 默认值 |
| ------ | ---- | ------ |
| `LLM_API_KEY` | LLM API Key | （必填） |
| `LLM_BASE_URL` | LLM API 基础 URL | `"https://token.sensenova.cn/v1"` |
| `LLM_MODEL` | LLM 模型名 | `"sensenova-6.7-flash-lite"` |
| `LLM_TYPE` | LLM API 类型 | `"openai-completions"` |

以上独立变量可用于覆盖 `SN_LM_*` 对 VLM/LLM 的共享配置。

## 故障排查

### 缺少 API key

- 现象：报错包含 "required but not set"、"missing api key" 或请求未授权。
- 处理：图像生成需设置 `SN_API_KEY`；VLM/LLM 需设置 `SN_LM_API_KEY`，或分别设置 `VLM_API_KEY` / `LLM_API_KEY`。

### base URL 配置错误

- 现象：请求立即失败，或出现 URL 校验 / endpoint 相关错误。
- 处理：检查 `SN_IMAGE_GEN_BASE_URL`、`SN_LM_BASE_URL`、`VLM_BASE_URL`、`LLM_BASE_URL` 是否为完整基础 URL（包含 scheme + host），例如 `https://token.sensenova.cn/v1`。

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
