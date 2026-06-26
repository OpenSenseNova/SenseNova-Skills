---
name: sn-search-code
description: 用于查找代码示例、开源项目、GitHub Issue、技术问答、开发者讨论、HuggingFace 模型/数据集/Space。
---

# sn-search-code - 开发者搜索

搜索 GitHub、Stack Overflow、Hacker News、HuggingFace 四个开发者核心平台。所有脚本无需 API 密钥 即可使用，但 GitHub `--type code` 搜索是例外（见下方说明）。

## 可用脚本

| 脚本 | 平台 | 用途 | API 密钥 |
|------|------|------|---------|
| `github_search.py` | GitHub | 仓库、代码、Issue 搜索 | `code` 类型**必须**；其他类型可选（提高限额） |
| `stackoverflow_search.py` | Stack Overflow | 技术问答搜索 | 无需 |
| `hackernews_search.py` | Hacker News | 技术新闻和讨论 | 无需 |
| `huggingface_search.py` | HuggingFace | 模型、数据集、Space 搜索 | 可选 `HF_TOKEN`（提高限额） |

## 依赖

首次运行或脚本提示缺库时，使用本技能的依赖清单安装到当前 Python 环境：

```bash
python3 -m pip install -r requirements.txt
```

不要在脚本内部自动安装依赖。若安装失败、网络不可用或包不可用，停止使用对应脚本并改用网页搜索，说明缺少依赖。

## 参数说明

### github_search.py

```bash
python3 scripts/github_search.py <query> [选项]
```

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `query` | 搜索关键词（必填） | — |
| `--limit`, `-n` | 返回结果数量 | 10 |
| `--type`, `-t` | 搜索类型：`repositories`, `code`, `issues`, `repo`, `issue` | repositories |
| `--token` | GitHub Token（也可通过 `GITHUB_TOKEN` 环境变量设置） | — |

> **注意：`--type code` 必须提供 token。**  
> GitHub API 对代码搜索接口强制要求认证，未提供 token 会返回 401。  
> `repositories` 和 `issues` 类型无需 token，但有 token 可提高速率限制（未认证 10 次/分钟 → 认证 30 次/分钟）。

```bash
python3 scripts/github_search.py "machine learning framework" --type repositories --limit 5
python3 scripts/github_search.py "import asyncio" --type code --token ghp_xxx --limit 5
# 或通过环境变量：
GITHUB_TOKEN=ghp_xxx python3 scripts/github_search.py "import asyncio" --type code --limit 5
```

### stackoverflow_search.py

```bash
python3 scripts/stackoverflow_search.py <query> [选项]
```

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `query` | 搜索关键词（必填） | — |
| `--limit`, `-n` | 返回结果数量 | 10 |
| `--sort` | 排序方式：`relevance`, `votes`, `creation`, `activity` | relevance |
| `--tagged` | 按标签过滤，多个用分号分隔（如 `python;asyncio`） | — |
| `--api-key` | Stack Exchange API 密钥（也可通过 `SO_API_KEY` 环境变量设置，可选，提高限额） | — |

```bash
python3 scripts/stackoverflow_search.py "python async await" --limit 5
python3 scripts/stackoverflow_search.py "rust lifetime" --sort votes --tagged rust --limit 10
```

### huggingface_search.py

```bash
python3 scripts/huggingface_search.py <query> [选项]
```

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `query` | 搜索关键词（必填） | — |
| `--limit`, `-n` | 返回结果数量 | 10 |
| `--type`, `-t` | 搜索类型：`models`, `datasets`, `spaces`（及别名 `model`, `dataset`, `space`） | models |
| `--token` | HuggingFace Token（也可通过 `HF_TOKEN` 环境变量设置，可选，提高限额） | — |

```bash
python3 scripts/huggingface_search.py "bert" --type models --limit 5
python3 scripts/huggingface_search.py "text classification" --type datasets --limit 5
python3 scripts/huggingface_search.py "stable diffusion" --type spaces --limit 5
```

### hackernews_search.py

```bash
python3 scripts/hackernews_search.py <query> [选项]
```

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `query` | 搜索关键词（必填） | — |
| `--limit`, `-n` | 返回结果数量 | 10 |
| `--sort` | 排序方式：`relevance`, `date` | relevance |
| `--tags` | HN 标签过滤：`story`, `comment`, `ask_hn`, `show_hn` | — |

```bash
python3 scripts/hackernews_search.py "LLM agents" --limit 10
python3 scripts/hackernews_search.py "GPT-5" --sort date --tags story --limit 5
```

## 输出格式

所有脚本输出标准 JSON：
```json
{
  "success": true,
  "query": "...",
  "provider": "github|stackoverflow|hackernews",
  "items": [
    {"title": "...", "url": "...", "snippet": "...", ...}
  ],
  "error": null
}
```
