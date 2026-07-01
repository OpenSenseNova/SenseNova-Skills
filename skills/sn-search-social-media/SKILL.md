---
name: sn-search-social-media
description: 搜索社区、社媒、新闻热点、百科趋势、开发者生态和技术讨论时使用。
---

# sn-search-social-media - 社区/社媒/新闻热点搜索

## 凭证配置

API key、token 与 cookie 统一建议写在仓库根目录 `.env`（参考 `.env.example`），并由 runtime 或用户在执行前加载为同名环境变量。脚本仍只从环境变量或显式 CLI 参数读取凭证；不要把真实密钥写入 skill payload、报告、日志或提交。

本技能给 agent 用于抓取公开热点信号。只使用免费、免注册、免 API key、非加密货币的数据源；不要要求用户提供 token、cookie、API key，也不要使用商业收费接口。

## 硬性规则

- 禁止处理加密货币、虚拟货币、区块链、Web3、NFT、DeFi、交易所，以及加密货币语境下的挖矿/钱包等查询。
- 如果用户请求加密货币相关热点，直接说明本技能不覆盖该主题，不要运行脚本。
- 不使用 GitHub code search、GitHub GraphQL、Stack Exchange key、BigQuery、YouTube API、Twitter/X API、TikHub、Reddit OAuth 或任何需要注册 key/token/cookie 的方式。
- 不使用无法访问、要求登录、要求付费或只有商业计划的资源；遇到新增资源，先确认能访问且符合以上限制。
- API 脚本和 browser-use 没有优先级，可在同一任务中混合使用。
- 百度指数、微博热搜/微指数只用公开网页可见内容；不要进入或引导使用付费商业功能。
- 脚本返回标准 JSON；引用 `items[].url` 或 browser-use 打开的页面链接作为证据。

## 依赖

首次运行或脚本提示缺库时，使用本技能的依赖清单安装到当前 Python 环境：

```bash
python3 -m pip install -r requirements.txt
```

不要在脚本内部自动安装依赖。若安装失败、网络不可用或包不可用，停止使用对应脚本并改用 browser-use/公开网页搜索，说明缺少依赖。

## 资源选择

| 场景 | API 脚本 | browser-use 入口 | 说明 |
| --- | --- | --- | --- |
| 百科页面关注度、公众注意力辅助指标 | `scripts/wikimedia_pageviews.py` | `https://doc.wikimedia.org/generated-data-platform/aqs/analytics-api/` | Wikimedia Pageviews 需要 User-Agent |
| 开源项目热度、工程活动、开发者生态 | `scripts/github_public_search.py` | `https://github.com/search` | 只搜公共仓库和 Issue；不搜 code |
| 技术问题热度、开发者需求 | `scripts/stackexchange_search.py` | `https://stackexchange.com/search` | 默认 Stack Overflow，可指定 `--site` |
| 创业、科技社区讨论热榜 | `scripts/hackernews_hotspots.py` | `https://news.ycombinator.com/` | 官方 API 不支持服务端搜索，脚本本地过滤 |
| 指数趋势、搜索热度、地域、人群画像、需求变化 | 无 | `https://index.baidu.com/` | 百度指数；网页可用，只用免费可见内容 |
| 社媒舆情、热点、品牌声量、事件监测 | 无 | `https://s.weibo.com/top/summary` | 微博热搜/微指数；网页可用，只用免费可见内容 |

## 常用命令

以下 `scripts/...` 路径相对本 skill 目录；若当前工作目录不同，先解析为绝对路径：

```bash
python3 scripts/gdelt_news_search.py "artificial intelligence" --timespan 1week --limit 10
python3 scripts/wikimedia_pageviews.py article "Artificial intelligence" --start 2026-05-01 --end 2026-05-17
python3 scripts/wikimedia_pageviews.py top --date 2026-05-17 --project en.wikipedia.org --limit 20
python3 scripts/github_public_search.py "llm agents" --type repositories --sort stars --limit 10
python3 scripts/github_public_search.py "agent framework bug" --type issues --sort comments --limit 10
python3 scripts/stackexchange_search.py "python asyncio" --site stackoverflow --sort votes --limit 10
python3 scripts/hackernews_hotspots.py --kind top --limit 10
python3 scripts/hackernews_hotspots.py --kind best --query "AI agents" --scan 150 --limit 10
```

`wikimedia_pageviews.py` 默认使用带项目 URL 的 User-Agent；如运行环境需要自定义，可设置 `WIKIMEDIA_USER_AGENT`，这不是 API key。

## 使用策略

- 新闻热点：用 GDELT 和 browser-use 打开新闻结果页交叉查看；必要时用 Wikimedia 页面浏览量验证公众关注度。
- 技术/开发者热点：组合 GitHub 公共仓库、GitHub Issue、Stack Exchange、Hacker News，并可用 browser-use 打开结果页查看上下文；不要调用需要 token 的代码搜索。
- 公众关注趋势：对已知实体或事件标题跑 Wikimedia `article`；找当天广泛关注对象跑 `top`，也可用 browser-use 打开百科页面核对实体含义。
- 中文指数趋势：用 browser-use 打开百度指数，查看搜索热度、地域、人群画像、需求变化；只记录免费网页可见信息。
- 中文社媒舆情：用 browser-use 打开微博热搜/微指数，查看热点、品牌声量、事件监测线索；只记录免费网页可见信息。
- HN 关键词搜索只是“热榜后本地过滤”，如果结果少，提高 `--scan`，不要改用非官方或收费搜索 API。
- 多源结果冲突时，优先报告“各源信号不同”，不要把单一平台热度说成全网趋势。

## 输出约定

脚本输出：

```json
{
  "success": true,
  "query": "...",
  "provider": "gdelt|wikimedia-pageviews|github-public|stackexchange|hackernews",
  "items": [
    {"title": "...", "url": "...", "snippet": "..."}
  ],
  "error": null
}
```

当 `success=false` 且错误提示为加密货币限制时，停止处理该请求。
