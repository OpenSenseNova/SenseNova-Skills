---
name: search-social-en
description: 搜索英文社交平台：Reddit 帖子、Twitter/X 推文、YouTube 视频。用于获取英文社区讨论和视频内容。
---

# search-social-en - 英文社交平台搜索

搜索 Reddit、Twitter/X、YouTube 三个英文社交平台。

## 可用脚本

| 脚本 | 平台 | 用途 | API key |
|------|------|------|---------|
| `reddit_search.py` | Reddit | 帖子和讨论搜索 | 无需 |
| `twitter_search.py` | Twitter/X | 推文搜索 | 需 `TIKHUB_TOKEN` |
| `youtube_search.py` | YouTube | 视频搜索 | 需 `YOUTUBE_API_KEY` |

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
| `--token` | TikHub Token（也可通过 `TIKHUB_TOKEN` 环境变量设置，必填） | — |

```bash
python3 scripts/twitter_search.py "AI agents" --limit 10
python3 scripts/twitter_search.py "LLM" --token your_tikhub_token --limit 5
```

### youtube_search.py

```bash
python3 scripts/youtube_search.py <query> [选项]
```

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `query` | 搜索关键词（必填） | — |
| `--limit`, `-n` | 返回结果数量 | 10 |
| `--api-key` | YouTube API Key（也可通过 `YOUTUBE_API_KEY` 环境变量设置，必填） | — |
| `--order` | 排序方式：`relevance`, `date`, `viewCount`, `rating` | relevance |

```bash
python3 scripts/youtube_search.py "transformer explained" --limit 5
python3 scripts/youtube_search.py "python tutorial" --order viewCount --limit 10
```

## 输出格式

标准 JSON：`{"success": true, "query": "...", "provider": "reddit|twitter|youtube", "items": [...], "error": null}`
