# search.py 统一学术搜索入口

`search.py` 聚合 `sn-search-academic/scripts` 目录下的搜索脚本，按逻辑搜索源调用不同 provider，并输出统一 JSON。

它只聚合搜索功能，不包含 `paper`、`pdf_paper`、`refTree` 等论文阅读或引用树脚本。

## 基本用法

```bash
python3 scripts/search.py "NSA"
```

指定搜索源：

```bash
python3 scripts/search.py "NSA" \
  --source arxiv,semantic,wikipedia \
  --limit 5
```

写入 JSON 文件：

```bash
python3 scripts/search.py "NSA" \
  --source arxiv,semantic \
  --limit 5 \
  --output results/search.json
```

## 参数

| 参数 | 说明 | 默认值 |
| --- | --- | --- |
| `query` | 搜索关键词，必填位置参数 | 无 |
| `--source`, `--sources`, `-s` | 搜索源；支持逗号分隔或重复传参 | `all` |
| `--limit`, `-n` | 每个 source 的返回数量 | `10` |
| `--category`, `-c` | ArXiv 分类过滤，只传给支持分类的 provider | 无 |
| `--lang`, `-l` | 语言提示，只传给支持 `lang` 的 provider | 无 |
| `--output`, `-o` | 将最终输出 JSON 写入文件，会自动创建父目录 | 无 |
| `--provider-timeout` | 每个 provider 调用的超时时间，单位秒；`0` 表示不限制 | `60` |

支持的 `--source`：

- `all`
- `arxiv`
- `semantic`
- `google_scholar`
- `pubmed`
- `wikipedia`

`--source all` 等价于：

```text
arxiv,semantic,google_scholar,pubmed,wikipedia
```

## Provider 回退链

### arxiv

按顺序尝试，直到某个 provider 成功返回非空结果：

1. `arxiv_search.py` -> `arxiv_official`
2. `deepxiv_search.py` -> `deepxiv`
3. `openalex_search.py` -> `openalex`
4. `arxiv_crawler_search.py` -> `arxiv_crawler`
5. `crossref_search.py` -> `crossref`
6. `arxiv_mirror_search.py` -> `arxiv_mirror`

### semantic

按顺序尝试，直到某个 provider 成功返回非空结果：

1. `semantic_scholar_search.py` -> `semantic_scholar_official`
2. `semantic_scholar_crawler_search.py` -> `semantic_scholar_crawler`

### 独立 source

- `google_scholar` -> `google_scholar_search.py`
- `pubmed` -> `pubmed_search.py`
- `wikipedia` -> `wikipedia_search.py`

## 参数分发规则

聚合入口只把内部脚本支持的参数传给对应 provider，避免因为多传参数导致脚本报错。

- `category`
  - `arxiv_search.py`: 传为 `category`
  - `deepxiv_search.py`: 传为 `categories=[category]`
  - `arxiv_mirror_search.py`: 传为 `category`
  - 其他 provider 不传
- `lang`
  - `google_scholar_search.py`: 传为 `lang`
  - `wikipedia_search.py`: 传为 `lang`
  - 其他 provider 不传

## 并发与超时

- 不同 source 并发执行，例如 `arxiv`、`semantic`、`wikipedia` 会同时启动。
- 同一 source 内的 provider 按回退链顺序执行。
- 每个 provider 默认超时 `60s`。
- provider 超时会记录为该 provider 的失败，并继续尝试同 source 的下一个 provider。

示例：

```bash
python3 scripts/search.py "transformer" \
  --source all \
  --provider-timeout 30
```

## 输出格式

CLI stdout 和 `--output` 文件使用同一份输出格式。

一级输出不包含 `items` 字段。每个 source 的结果保留在 `source_results[*].items` 中。

```json
{
  "success": true,
  "query": "NSA",
  "provider": "search.py",
  "sources": ["arxiv", "semantic"],
  "source_results": [
    {
      "source": "arxiv",
      "success": true,
      "provider": "arxiv_official",
      "items": [
        {
          "source": "arxiv",
          "provider": "arxiv_official",
          "provider_rating": null,
          "title": "Example title",
          "abstract": "Example abstract",
          "citation_count": null,
          "url": "https://arxiv.org/abs/..."
        }
      ],
      "attempts": [
        {
          "provider": "arxiv_official",
          "success": true,
          "count": 1,
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

如果使用 `--output`，输出中会额外包含：

```json
{
  "output_path": "/absolute/path/to/results/search.json"
}
```

## Item 字段

每条 item 至少尽量包含：

- `source`
- `provider`
- `provider_rating`，当前固定为 `null`
- `title`
- `abstract`
- `citation_count`

同时会保留原 provider 返回的有用字段，例如：

- ArXiv: `arxiv_id`, `pdf_url`, `categories`, `doi`
- Semantic Scholar: `paper_id`, `doi`, `arxiv_id`, `venue`, `year`
- Google Scholar: `scholar_id`, `cited_by_url`, `pdf_url`
- PubMed: `pmid`, `pmc_id`, `journal`, `pub_date`, `doi`
- Wikipedia: `page_id`, `word_count`, `timestamp`, `section_title`

## 去重规则

同一 source 内按稳定 ID 去重。不同 source 之间不互相去重。

优先使用的去重字段：

- `arxiv`: `arxiv_id`, `doi`, `paper_id`, `openalex_id`, `url`, `title`
- `semantic`: `paper_id`, `doi`, `arxiv_id`, `url`, `title`
- `google_scholar`: `scholar_id`, `doi`, `url`, `title`
- `pubmed`: `pmid`, `doi`, `pmc_id`, `url`, `title`
- `wikipedia`: `page_id`, `url`, `title`

## Python API

也可以直接导入调用：

```python
from search import search

result = search(
    "NSA",
    sources=["arxiv", "semantic"],
    limit=5,
    category="cs.CL",
    provider_timeout=60,
)
```

注意：Python API 返回的内部结果会保留一级 `items`，方便程序使用；CLI stdout 和 `--output` 文件会去掉一级 `items`，避免重复输出。
