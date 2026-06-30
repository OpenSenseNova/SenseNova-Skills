# refTree.py 统一引用树入口

`refTree.py` 聚合 `sn-search-academic/scripts` 目录下的 refTree 功能脚本，用来查询一篇论文的参考文献和被引论文，并输出统一 JSON。

它只聚合引用树功能，不包含 `search` 或 `paper`。

## 基本用法

查询一篇论文的参考文献和被引论文：

```bash
python3 scripts/refTree.py \
  --paper_id "2309.16609" \
  --title "Qwen Technical Report"
```

只查询参考文献：

```bash
python3 scripts/refTree.py \
  --paper_id "2309.16609" \
  --title "Qwen Technical Report" \
  --direction references
```

只查询被引论文：

```bash
python3 scripts/refTree.py \
  --paper_id "2309.16609" \
  --title "Qwen Technical Report" \
  --direction citations
```

写入 JSON 文件：

```bash
python3 scripts/refTree.py \
  --paper_id "2309.16609" \
  --title "Qwen Technical Report" \
  --limit 20 \
  --output results/refTree.json
```

## 参数

| 参数 | 说明 | 默认值 |
| --- | --- | --- |
| `--paper_id` | 论文 ID，必填。支持 Semantic Scholar paper ID、DOI、ArXiv ID、PMID 等底层脚本可识别的格式 | 无 |
| `--title` | 论文标题，必填。官方 provider 失败后 crawler fallback 会用它做精确匹配 | 无 |
| `--direction` | 查询方向；支持 `references` 或 `citations`。不填则两个方向都查询 | 无 |
| `--source`, `--sources`, `-s` | 搜索源；目前支持 `all`、`semantic` | `all` |
| `--limit`, `-n` | 每个 source、每个 direction 返回数量 | `10` |
| `--output`, `-o` | 将最终 JSON 结果写入指定文件，会自动创建父目录 | 无 |
| `--api-key` | Semantic Scholar API Key，只传给官方 Semantic Scholar provider | 无 |
| `--provider-timeout` | 每个 provider 调用的超时时间，单位秒；`0` 表示不限制 | `60` |

注意：`paper_id` 统一只用 `--paper_id "<paper_id>"` 传入，不支持位置参数，也不支持 `--paper-id`。

## 支持的 Source

目前只有：

- `semantic`

`--source all` 等价于：

```text
semantic
```

## Provider 回退链

### semantic

1. `semantic_scholar_refTree.py` -> `semantic_official`
2. `semantic_scholar_crawler_refTree.py` -> `semantic_crawler`

`semantic_official` 优先使用 Semantic Scholar SDK；SDK 不可用或请求失败时，底层脚本会再回退到 Semantic Scholar Graph API HTTP 请求。

`semantic_crawler` 是页面爬取 fallback，需要 `semantic_scholar_crawler_refTree.py` 的运行环境可用，包括 Playwright、Node.js 和 `camoufox-js`。

## Direction 回退逻辑

### 指定 direction

如果传入：

```bash
--direction references
```

或：

```bash
--direction citations
```

则只查询这个方向：

1. 先调用 `semantic_official`
2. 如果失败，再调用 `semantic_crawler`

### 不指定 direction

不传 `--direction` 时默认查询两个方向：

- `references`
- `citations`

执行逻辑：

1. 并发调用 `semantic_official` 查询 `references` 和 `citations`
2. 如果只有一个方向失败，只用 `semantic_crawler` 补查失败的方向
3. 如果两个方向都失败，只调用一次 `semantic_crawler`，不传 direction，让 crawler 默认查询两个方向

## 参数分发规则

统一入口只把内部脚本支持的参数传给对应 provider，避免多传参数导致脚本报错。

### semantic_official

传入：

- `paper_id`
- `direction`
- `limit`
- `api_key`

内部固定过滤参数：

- `min_citations=0`
- `year_min=None`
- `year_max=None`

不传：

- `title`
- `output`
- `source`
- `provider_timeout`

### semantic_crawler

传入：

- `title`
- `direction`，只有需要限制方向时才传；两个方向都失败时不传
- `limit`

内部固定运行参数：

- `headless=True`
- `max_pages=None`
- 临时 `output` 文件路径

不传：

- `paper_id`
- `api_key`
- `source`
- `provider_timeout`

## 输出格式

CLI stdout 和 `--output` 文件使用同一份输出格式。

成功时示例：

```json
{
  "success": true,
  "id": "2309.16609",
  "title": "Qwen Technical Report",
  "provider": "refTree.py",
  "sources": ["semantic"],
  "direction": "all",
  "source_results": [
    {
      "source": "semantic",
      "success": true,
      "provider": "semantic_official",
      "provider_rating": null,
      "citations": [
        {
          "source": "semantic",
          "id": "example-citing-paper-id",
          "title": "Example citing paper",
          "provider": "semantic_official",
          "provider_rating": null,
          "citation_count": 42,
          "abstract": "Example abstract",
          "paper_id": "example-citing-paper-id",
          "doi": "10.1234/example"
        }
      ],
      "references": [
        {
          "source": "semantic",
          "id": "example-reference-paper-id",
          "title": "Example referenced paper",
          "provider": "semantic_official",
          "provider_rating": null,
          "citation_count": 128,
          "abstract": "Example abstract",
          "paper_id": "example-reference-paper-id",
          "arxiv_id": "2301.00001"
        }
      ],
      "attempts": [
        {
          "provider": "semantic_official",
          "direction": "references",
          "success": true,
          "count": 10,
          "error": null
        },
        {
          "provider": "semantic_official",
          "direction": "citations",
          "success": true,
          "count": 10,
          "error": null
        }
      ],
      "error": null
    }
  ],
  "errors": [],
  "error": null
}
```

`source_results` 是每个 source 的结果和内部执行明细。每个元素包含该 source 的 `citations`、`references`、实际使用的 provider、每次 provider 尝试是否成功、返回数量和错误信息。论文列表不放在一级字段里，模型消费论文结果时读取 `source_results[*].citations` 和 `source_results[*].references`。

如果使用 `--output`，输出中会额外包含：

```json
{
  "output_path": "/absolute/path/to/results/refTree.json"
}
```

失败时示例：

```json
{
  "success": false,
  "id": "2309.16609",
  "title": "Qwen Technical Report",
  "provider": "refTree.py",
  "sources": ["semantic"],
  "direction": "references",
  "source_results": [
    {
      "source": "semantic",
      "success": false,
      "provider": null,
      "provider_rating": null,
      "citations": [],
      "references": [],
      "attempts": [
        {
          "provider": "semantic_official",
          "direction": "references",
          "success": false,
          "count": 0,
          "error": "provider error"
        },
        {
          "provider": "semantic_crawler",
          "direction": "references",
          "success": false,
          "count": 0,
          "error": "provider error"
        }
      ],
      "error": "semantic_official[references]: provider error; semantic_crawler[references]: provider error"
    }
  ],
  "errors": [
    {
      "source": "semantic",
      "error": "semantic_official[references]: provider error; semantic_crawler[references]: provider error",
      "attempts": [
        {
          "provider": "semantic_official",
          "direction": "references",
          "success": false,
          "count": 0,
          "error": "provider error"
        },
        {
          "provider": "semantic_crawler",
          "direction": "references",
          "success": false,
          "count": 0,
          "error": "provider error"
        }
      ]
    }
  ],
  "error": "All selected sources failed"
}
```

## Article 字段

`source_results[*].citations` 和 `source_results[*].references` 中的每条 article 至少尽量包含：

- `source`
- `id`
- `title`
- `provider`
- `provider_rating`，当前固定为 `null`
- `citation_count`

同时会保留底层 provider 返回的有用字段，例如：

- `abstract`
- `url`
- `snippet`
- `authors`
- `year`
- `venue`
- `publication_date`
- `doi`
- `arxiv_id`
- `paper_id`
- `influential_citation_count`
- `is_open_access`
- `open_access_pdf`
- `fields_of_study`
- `citation_contexts`
- `citation_intents`

## 去重规则

同一 source 内按稳定 ID 去重。不同 source 之间不互相去重。

`semantic` source 优先使用的去重字段：

1. `paper_id`
2. `doi`
3. `arxiv_id`
4. `url`
5. `title`

如果 crawler 只返回 Semantic Scholar URL，`refTree.py` 会尽量从 URL 中提取论文 ID，填入统一字段 `id` 和 `paper_id`。

## Python API

也可以直接导入调用：

```python
from refTree import ref_tree

result = ref_tree(
    paper_id="2309.16609",
    title="Qwen Technical Report",
    sources=["semantic"],
    direction=None,
    limit=10,
    provider_timeout=60,
    api_key=None,
)
```

返回值与 CLI stdout 的 JSON 结构一致。

## 适用场景

- 先用 `search.py` 搜索论文，拿到 `paper_id`、`arxiv_id` 或 DOI
- 用 `refTree.py` 查询该论文的 `references`，找奠基工作
- 用 `refTree.py` 查询该论文的 `citations`，找后续进展
- 对返回的高引用论文继续用 `paper.py` 阅读全文或章节
