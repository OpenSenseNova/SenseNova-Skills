# SenseNova-Skills 环境变量配置规范

> 适用范围：本文档为 `sn-image-*` / `sn-infographic` 等以 `SN_*` 变量配置的技能规范；
> `sn-ppt-*` PPT 套件使用独立的 `SN_PPT_*` 配置体系（Bundled 回退层），
> 见 [`../sn-ppt-generate_cn.md`](../sn-ppt-generate_cn.md) 的 API Key 章节。

> **TL;DR**：默认场景下，用户只需关注 4 个变量——`SN_BASE_URL`、`SN_API_KEY`、`SN_CHAT_MODEL`、`SN_IMAGE_GEN_MODEL`（除 `SN_API_KEY` 外，其余三项带有内置默认值）；如需对某一类能力做更细粒度的覆盖，再额外设置 `SN_TEXT_*`、`SN_VISION_*`、`SN_CHAT_*` 等专属/分组变量。API Key 仍需具备所选模型的调用权限，其他运行依赖和 Agent 登录按各技能指南配置。

## 一、设计目标

让用户在最常见的场景下"几乎不需要配置"，同时保留按能力维度精细覆盖的能力。整套体系围绕三条原则：

1. **必需变量最少化**：在默认网关、模型与权限适用时，`SN_*` 模型配置最少只需设置 `SN_API_KEY`；各技能的运行依赖和 Agent 认证仍需单独准备。
2. **默认值放在语义上最高的层级**：能在外层兜底的就不在内层重复，避免同一份默认值散落在多个变量上。
3. **覆盖关系清晰可预测**：从专属变量逐级回退到共享变量，最终回退到内置默认值，沿途使用第一个非空值。

## 二、变量分层

整套配置分为三类、三层：

- **三类能力**：文本对话（text）、视觉理解（vision）、图片生成（image-gen）。
- **三层作用域**：
  - 全局层 `SN_*`——与能力无关的通用配置（如网关地址、根密钥）。
  - 能力分组层 `SN_CHAT_*` / `SN_IMAGE_GEN_*`——`SN_CHAT_*` 同时覆盖 text 和 vision 两类能力（它们共享对话运行时），`SN_IMAGE_GEN_*` 单独管图生。
  - 专属层 `SN_TEXT_*` / `SN_VISION_*`——只覆盖单一能力，优先级最高。

回退方向：

```text
SN_TEXT_*    ┐
             ├─►  SN_CHAT_*       ─┐
SN_VISION_*  ┘                     ├─►  SN_*（全局）  ─►  内置默认值
                  SN_IMAGE_GEN_*  ─┘
```

> 注意：`SN_IMAGE_GEN_*` 不经过 `SN_CHAT_*`，因为图生与对话是不同的运行时；它直接回退到全局 `SN_*`。

## 三、默认值落点原则

默认值挂在"语义上能覆盖的最高层级"。具体落点如下：

| 维度 | 默认值挂载点 | 默认值 |
| --- | --- | --- |
| Base URL | `SN_BASE_URL` | `https://token.sensenova.cn/v1` |
| Chat 模型 | `SN_CHAT_MODEL` | `sensenova-6.8-flash-lite` |
| 图生模型 | `SN_IMAGE_GEN_MODEL` | `sensenova-u1.5-lite` |
| Chat 协议 | `SN_CHAT_TYPE` | `openai-completions` |
| 图生协议 | `SN_IMAGE_GEN_MODEL_TYPE` | `sensenova` |
| Timeout | `SN_CHAT_TIMEOUT` | `120`（秒） |
| API Key | 无默认值 | — |

## 四、完整回退链

解析规则：从左至右逐项尝试，使用第一个非空值；全部为空时使用末尾的内置默认值。

### 4.1 文本（text）

| 维度 | 回退链 |
| --- | --- |
| API Key | `SN_TEXT_API_KEY` → `SN_CHAT_API_KEY` → `SN_API_KEY` |
| Base URL | `SN_TEXT_BASE_URL` → `SN_CHAT_BASE_URL` → `SN_BASE_URL` → `https://token.sensenova.cn/v1` |
| Model | `SN_TEXT_MODEL` → `SN_CHAT_MODEL` → `sensenova-6.8-flash-lite` |
| 协议类型 | `SN_TEXT_TYPE` → `SN_CHAT_TYPE` → `openai-completions` |
| 超时（秒） | `SN_TEXT_TIMEOUT` → `SN_CHAT_TIMEOUT` → `120` |

### 4.2 视觉（vision）

| 维度 | 回退链 |
| --- | --- |
| API Key | `SN_VISION_API_KEY` → `SN_CHAT_API_KEY` → `SN_API_KEY` |
| Base URL | `SN_VISION_BASE_URL` → `SN_CHAT_BASE_URL` → `SN_BASE_URL` → `https://token.sensenova.cn/v1` |
| Model | `SN_VISION_MODEL` → `SN_CHAT_MODEL` → `sensenova-6.8-flash-lite` |
| 协议类型 | `SN_VISION_TYPE` → `SN_CHAT_TYPE` → `openai-completions` |
| 超时（秒） | `SN_VISION_TIMEOUT` → `SN_CHAT_TIMEOUT` → `120` |

### 4.3 图生（image-gen）

| 维度 | 回退链 |
| --- | --- |
| API Key | `SN_IMAGE_GEN_API_KEY` → `SN_API_KEY` |
| Base URL | `SN_IMAGE_GEN_BASE_URL` → `SN_BASE_URL` → `https://token.sensenova.cn/v1` |
| Model | `SN_IMAGE_GEN_MODEL` → `sensenova-u1.5-lite` |
| 协议类型 | `SN_IMAGE_GEN_MODEL_TYPE` → `sensenova` |

### 4.4 Image Studio 的配置边界

`sn-image-studio` 使用独立的 `scripts/images.py`，不经过 `sn-image-base` runner，但沿用上面的图生回退链。
默认模型是 `sensenova-u1.5-lite`，协议为 `sensenova`；客户端仅接受 U1.5 系列模型，实际可用性取决于账号权限。

- 默认读取启动命令当前目录的 `.env`；使用其他配置文件时，为 `doctor`、`serve` 和直接生图命令传入一致的 `--env-file` 绝对路径。
- 先以所选 `.env` 中的同名值覆盖进程环境，再按图生回退链取第一个非空值；图生专属变量优先于共享变量。
- 网页配置表单保存 `SN_IMAGE_GEN_*` 覆盖值并保留其他配置，不会自动读取宿主 Agent 的登录凭据作为生图 Key。
- ACP Agent 使用所选 Codex、Claude Code 或 Hermes 自身的认证和模型配置，不由 `SN_CHAT_*` 配置其登录或模型。直接生图不需要 ACP Agent；按需求改写需额外准备对应 ACP 服务及认证。

完整步骤与两地区 Base URL 见 [Image Studio 使用指南](../sn-image-studio_cn.md)。

## 五、用户视角的两套配置面

- **默认配置面（推荐起点）**：用户只关心 4 个变量——`SN_BASE_URL`、`SN_API_KEY`、`SN_CHAT_MODEL`、`SN_IMAGE_GEN_MODEL`。其中 `SN_BASE_URL` / `SN_CHAT_MODEL` / `SN_IMAGE_GEN_MODEL` 都带有内置默认值，因此最小必需仅 `SN_API_KEY` 一项；私有部署再加一个 `SN_BASE_URL` 即可。
- **细粒度配置面（按需启用）**：当某一类能力需要走不同的网关、模型或协议时，再设置 `SN_CHAT_*`（同时影响 text 和 vision）、或 `SN_TEXT_*` / `SN_VISION_*`（只覆盖单一能力）；图生类则用 `SN_IMAGE_GEN_*`。这些专属变量优先级高于默认配置面，按第四节的回退链生效。
