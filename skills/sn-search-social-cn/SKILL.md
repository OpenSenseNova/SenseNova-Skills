---
name: sn-search-social-cn
description: 用于搜索中文社交平台。脚本入口覆盖 B站视频、知乎问答和抖音视频；小红书、微博当前没有脚本入口，只能通过 browser-use / 公开网页兜底。
---

# sn-search-social-cn - 中文社交平台搜索

## 凭证配置

API key、token 与 cookie 统一建议写在仓库根目录 `.env`（参考 `.env.example`），并由 runtime 或用户在执行前加载为同名环境变量。脚本仍只从环境变量或显式 CLI 参数读取凭证；不要把真实密钥写入 skill payload、报告、日志或提交。

脚本搜索 B站、知乎、抖音三个中文社交平台。小红书、微博当前没有可用脚本入口，如研究必须覆盖这两类来源，使用 browser-use 打开公开网页结果或平台搜索页，并在结果中说明该来源来自网页兜底。

## 稳定性说明

中文社交平台没有稳定的公开搜索 API，所有脚本依赖内部 API 或第三方库，**可能因平台更新而失效**。

| 脚本 | 平台 | 稳定性 | 认证方式 |
|------|------|--------|---------|
| `bilibili_search.py` | B站 | 较高 | 无需（可选 cookie 提高质量） |
| `zhihu_search.py` | 知乎 | 中等 | 需 `ZHIHU_COOKIE` |
| `douyin_search.py` | 抖音 | 较低 | 需 `DOUYIN_COOKIE` |
| 无脚本 | 小红书 | 低 | browser-use / 公开网页兜底 |
| 无脚本 | 微博 | 低 | browser-use / 公开网页兜底 |

## 依赖

首次运行或脚本提示缺库时，使用本技能的依赖清单安装到当前 Python 环境：

```bash
python3 -m pip install -r requirements.txt
```

不要在脚本内部自动安装依赖。若安装失败、网络不可用或包不可用，停止使用对应脚本并改用 browser-use 搜索免费可见网页，说明缺少依赖。

## Cookie 获取方式

1. 在浏览器中登录对应脚本平台
2. 打开开发者工具（F12）→ Network 标签
3. 刷新页面，在请求头中找到 `Cookie` 字段
4. 将完整 cookie 字符串设置为对应环境变量。小红书、微博当前没有脚本入口，不读取 `XHS_COOKIE` / `WEIBO_COOKIE`。

## 参数说明

### bilibili_search.py

```bash
python3 scripts/bilibili_search.py <query> [选项]
```

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `query` | 搜索关键词（必填） | — |
| `--limit`, `-n` | 返回结果数量 | 10 |
| `--cookie` | B站 Cookie（也可通过 `BILIBILI_COOKIE` 环境变量设置，可选，提高结果质量） | — |
| `--order` | 排序：空=综合, `totalrank`=最佳匹配, `click`=播放, `pubdate`=最新, `dm`=弹幕, `stow`=收藏 | 综合 |

```bash
python3 scripts/bilibili_search.py "机器学习教程" --limit 5
python3 scripts/bilibili_search.py "Python" --order click --limit 10
```

### zhihu_search.py

```bash
python3 scripts/zhihu_search.py <query> [选项]
```

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `query` | 搜索关键词（必填） | — |
| `--limit`, `-n` | 返回结果数量 | 10 |
| `--cookie` | 知乎 Cookie（也可通过 `ZHIHU_COOKIE` 环境变量设置，必填） | — |
| `--type` | 搜索类型：`general`, `topic`, `people`, `zvideo` | general |

```bash
ZHIHU_COOKIE="..." python3 scripts/zhihu_search.py "Python 异步编程" --limit 5
python3 scripts/zhihu_search.py "大模型" --cookie "..." --type topic --limit 5
```

### douyin_search.py

```bash
python3 scripts/douyin_search.py <query> [选项]
```

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `query` | 搜索关键词（必填） | — |
| `--limit`, `-n` | 返回结果数量 | 10 |
| `--cookie` | 抖音 Cookie（也可通过 `DOUYIN_COOKIE` 环境变量设置，必填） | — |

```bash
DOUYIN_COOKIE="..." python3 scripts/douyin_search.py "编程教程" --limit 5
```

## 输出格式

标准 JSON：`{"success": true, "query": "...", "provider": "bilibili|zhihu|douyin", "items": [...], "error": null}`

小红书、微博通过 browser-use / 公开网页兜底时，不承诺以上脚本 JSON 结构；记录打开的页面 URL、检索词、可见结果和限制即可。
