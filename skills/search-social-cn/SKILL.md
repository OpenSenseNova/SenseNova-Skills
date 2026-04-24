---
name: search-social-cn
description: 搜索中文社交平台：B站视频、知乎问答、抖音视频。部分平台需要 cookie 认证，稳定性因平台而异。
---

# search-social-cn - 中文社交平台搜索

搜索 B站、知乎、抖音三个中文社交平台。

## 稳定性说明

中文社交平台没有稳定的公开搜索 API，所有脚本依赖内部 API 或第三方库，**可能因平台更新而失效**。

| 脚本 | 平台 | 稳定性 | 认证方式 |
|------|------|--------|---------|
| `bilibili_search.py` | B站 | 较高 | 无需（可选 cookie 提高质量） |
| `zhihu_search.py` | 知乎 | 中等 | 需 `ZHIHU_COOKIE` |
| `douyin_search.py` | 抖音 | 较低 | 需 `DOUYIN_COOKIE` |

## Cookie 获取方式

1. 在浏览器中登录对应平台
2. 打开开发者工具（F12）→ Network 标签
3. 刷新页面，在请求头中找到 `Cookie` 字段
4. 将完整 cookie 字符串设置为对应环境变量

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
