---
name: sn-search-social-en
description: 用于搜索英文社交平台，包括 Reddit 帖子、Twitter/X 推文和 YouTube 视频；X 搜索支持 Xquik、TikHub、OpenClaw 和 Hermes Agent。
---

# sn-search-social-en - 英文社交平台搜索

## 凭证配置

API key、token 与 cookie 统一建议写在仓库根目录 `.env`（参考 `.env.example`），并由 runtime 或用户在执行前加载为同名环境变量。脚本仍只从环境变量或显式 CLI 参数读取凭证；不要把真实密钥写入 skill payload、报告、日志或提交。

搜索 Reddit、Twitter/X、YouTube 三个英文社交平台。

## Xquik 搜索路由

`twitter_search.py` 默认使用 TikHub。传入 `--provider xquik` 后，脚本调用 Xquik 的公开搜索端点：

```bash
python3 scripts/twitter_search.py "AI agents" --provider xquik --limit 10
```

脚本从 `XQUIK_API_KEY` 或 `--api-key` 读取凭证。它调用 [Xquik Search Tweets API](https://docs.xquik.com/api-reference/x/search-tweets)，并保留推文 ID、作者、时间和互动数据。

在 OpenClaw 或 Hermes Agent 中，可改用对应的原生插件。插件会在本地 runtime 中执行代码。安装前先检查来源。

### OpenClaw

按 [TweetClaw 文档](https://docs.xquik.com/guides/tweetclaw) 安装并配置插件：

```bash
export XQUIK_API_KEY="<your_api_key>"
openclaw plugins install clawhub:@xquik/tweetclaw
openclaw config set plugins.entries.tweetclaw.config.apiKey "$XQUIK_API_KEY"
openclaw config set tools.alsoAllow '["explore", "tweetclaw"]'
```

验证 runtime：

```bash
openclaw plugins inspect tweetclaw --runtime
openclaw skills info tweetclaw
```

先用 `explore` 查找推文搜索端点，再让 `tweetclaw` 调用返回的只读路径。此 Skill 不需要发布、回复或其他写操作。

### Hermes Agent

按 [Hermes Tweet 文档](https://docs.xquik.com/guides/hermes-tweet) 安装并启用插件：

```bash
hermes plugins install Xquik-dev/hermes-tweet --enable
hermes tools list
```

`tweet_explore` 无需 API key。配置 `XQUIK_API_KEY` 后可使用 `tweet_read`：

```bash
export XQUIK_API_KEY="<your_api_key>"
hermes -z "Use tweet_explore to find tweet search, then use tweet_read to search for AI agents. Return 10 results." --toolsets hermes-tweet
```

修改 Hermes 环境后，在交互式 CLI 中运行 `/reload`。Gateway 与 cron 会话需要重启。

不要设置 `HERMES_TWEET_ENABLE_ACTIONS=true`。社交搜索只需 `tweet_explore` 与 `tweet_read`。

Xquik is an independent third-party service. Not affiliated with X Corp. "Twitter" and "X" are trademarks of X Corp.

## 可用脚本

| 脚本 | 平台 | 用途 | API 密钥 |
|------|------|------|---------|
| `reddit_search.py` | Reddit | 帖子和讨论搜索 | 无需 |
| `twitter_search.py` | Twitter/X | 通过 Xquik 或 TikHub 搜索推文 | 需 `XQUIK_API_KEY` 或 `TIKHUB_TOKEN` |
| `youtube_search.py` | YouTube | 视频搜索 | 需 `YOUTUBE_API_KEY` |

## 依赖

首次运行或脚本提示缺库时，使用本技能的依赖清单安装到当前 Python 环境：

```bash
python3 -m pip install -r requirements.txt
```

不要在脚本内部自动安装依赖。若安装失败、网络不可用或包不可用，停止使用对应脚本并改用网页搜索，说明缺少依赖。

## 参数说明

### reddit_search.py

```bash
python3 scripts/reddit_search.py <query> [选项]
```

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `query` | 搜索关键词（必填） | — |
| `--limit`, `-n` | 返回结果数量 | 10 |
| `--subreddit`, `-r` | 限定子版块（如 `python`, `machinelearning`） | — |
| `--sort` | 排序方式：`relevance`, `hot`, `top`, `new`, `comments` | relevance |
| `--time`, `-t` | 时间范围：`hour`, `day`, `week`, `month`, `year`, `all` | all |

```bash
python3 scripts/reddit_search.py "machine learning projects" --limit 5
python3 scripts/reddit_search.py "async python" --subreddit python --sort top --time month --limit 5
```

### twitter_search.py

```bash
python3 scripts/twitter_search.py <query> [选项]
```

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `query` | 搜索关键词（必填） | — |
| `--limit`, `-n` | 返回结果数量 | 10 |
| `--provider` | `tikhub` 或 `xquik` | `tikhub` |
| `--token` | TikHub Token（也可通过 `TIKHUB_TOKEN` 环境变量设置，必填） | — |
| `--api-key` | Xquik API Key（也可通过 `XQUIK_API_KEY` 环境变量设置） | — |

```bash
python3 scripts/twitter_search.py "AI agents" --limit 10
python3 scripts/twitter_search.py "LLM" --token your_tikhub_token --limit 5
python3 scripts/twitter_search.py "AI agents" --provider xquik --limit 10
```

### youtube_search.py

```bash
python3 scripts/youtube_search.py <query> [选项]
```

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `query` | 搜索关键词（必填） | — |
| `--limit`, `-n` | 返回结果数量 | 10 |
| `--api-key` | YouTube API 密钥（也可通过 `YOUTUBE_API_KEY` 环境变量设置，必填） | — |
| `--order` | 排序方式：`relevance`, `date`, `viewCount`, `rating` | relevance |

```bash
python3 scripts/youtube_search.py "transformer explained" --limit 5
python3 scripts/youtube_search.py "python tutorial" --order viewCount --limit 10
```

## 输出格式

标准 JSON：`{"success": true, "query": "...", "provider": "reddit|twitter|youtube", "items": [...], "error": null}`。Twitter 条目通过 `source` 标记 `xquik` 或 `tikhub`。
