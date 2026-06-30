# paper.py 统一论文阅读入口

`paper.py` 聚合 `sn-search-academic/scripts` 目录下的 paper 功能脚本，按论文来源选择 provider，并输出统一 JSON。

它只聚合论文全文/章节阅读功能，不包含 `search` 或 `refTree`。

## 基本用法

读取 arXiv 论文全文，默认 source 为 `arxiv`：

```bash
python3 scripts/paper.py 2603.00729
```

读取 arXiv 指定章节：

```bash
python3 scripts/paper.py 2603.00729 \
  --section introduction
```

列出 arXiv 论文可用章节：

```bash
python3 scripts/paper.py 2603.00729 \
  --list_section
```

读取 PMC 论文全文：

```bash
python3 scripts/paper.py PMC11119143 \
  --source pmc
```

读取 PMC 指定章节：

```bash
python3 scripts/paper.py PMC11119143 \
  --source pmc \
  --section methods
```

写入 JSON 文件：

```bash
python3 scripts/paper.py 2603.00729 \
  --output results/paper.json
```

## 参数

| 参数 | 说明 | 默认值 |
| --- | --- | --- |
| `id` | 论文 ID，必填位置参数。arXiv 支持原始 ID、`arXiv:` 前缀、abs/pdf URL；PMC 支持 `PMC11119143`、`11119143`、PMC URL | 无 |
| `--source` | 论文来源；支持 `arxiv`、`pmc` | `arxiv` |
| `--section`, `-s` | 要读取的章节名；不填则返回全文。只有支持章节读取的 provider 才会收到该参数 | 无 |
| `--list_section` | 列出论文可用章节，不返回正文；也支持别名 `--list-section`。不能和 `--section` 同时使用 | false |
| `--output`, `-o` | 将最终 JSON 结果写入指定文件，会自动创建父目录 | 无 |

## Provider 回退链

同一 source 内按顺序尝试。读取全文/章节时，直到某个 provider 成功返回非空 `content`；列章节时，直到某个 provider 成功返回非空 `sections`。

### arxiv

1. `arxiv_paper.py` -> `arxiv_html`
2. `deepxiv_paper.py` -> `deepxiv`
3. `arxiv_pdf_paper.py` -> `arxiv_pdf`

注意：`arxiv_pdf_paper.py` 不支持 `section` 和 `list_section`。如果调用 `paper.py` 时传入 `--section` 或 `--list_section`，arXiv 回退链会跳过 `arxiv_pdf`。

### pmc

1. `pmc_paper.py` -> `pmc`

## 参数分发规则

统一入口只把内部脚本支持的参数传给对应 provider，避免多传参数导致脚本报错。

- `id`
  - arXiv source 会规范化为 arXiv ID 后传给 arXiv provider
  - PMC source 会规范化为不带 `PMC` 前缀的数字 ID 后传给 `pmc_paper.py`
- `section`
  - `arxiv_paper.py`: 传给 `cmd_read_section(arxiv_id, section)`
  - `deepxiv_paper.py`: 传给 `cmd_read_section(arxiv_id, section)`
  - `pmc_paper.py`: 传给 `cmd_read_section(pmc_num, section)`
  - `arxiv_pdf_paper.py`: 不传；带 `section` 时直接跳过
- `list_section`
  - `arxiv_paper.py`: 调用 `cmd_list_sections(arxiv_id)`
  - `deepxiv_paper.py`: 调用 `cmd_list_sections(arxiv_id)`
  - `pmc_paper.py`: 调用 `cmd_list_sections(pmc_num)`
  - `arxiv_pdf_paper.py`: 不调用；带 `list_section` 时直接跳过

## 输出格式

CLI stdout 使用统一 JSON。成功时至少包含：

```json
{
  "success": true,
  "arxiv_id": "2603.00729",
  "source": "arxiv",
  "provider": "arxiv_html",
  "provider_rating": null,
  "content": "<全文/章节内容>",
  "attempts": [
    {
      "provider": "arxiv_html",
      "success": true,
      "error": null
    }
  ],
  "error": null
}
```

PMC source 会返回 `pmc_id`：

```json
{
  "success": true,
  "pmc_id": "PMC11119143",
  "source": "pmc",
  "provider": "pmc",
  "provider_rating": null,
  "content": "<全文/章节内容>",
  "error": null
}
```

如果传入 `--section`，输出会包含 `section` 字段；未传入时不会包含该字段。

如果传入 `--list_section`，输出会包含 `sections` 和 `section_count`，不包含 `content`：

```json
{
  "success": true,
  "arxiv_id": "2603.00729",
  "source": "arxiv",
  "provider": "arxiv_html",
  "provider_rating": null,
  "section_count": 2,
  "sections": [
    {
      "name": "Abstract",
      "level": 0
    },
    {
      "name": "1 Introduction",
      "level": 1
    }
  ],
  "error": null
}
```

如果传入 `--output`，stdout 和文件使用同一份 JSON，输出中会额外包含 `output_path`：

```json
{
  "success": true,
  "arxiv_id": "2603.00729",
  "source": "arxiv",
  "provider": "arxiv_html",
  "provider_rating": null,
  "content": "<全文/章节内容>",
  "output_path": "/absolute/path/to/results/paper.json",
  "error": null
}
```

失败时返回统一错误对象，并保留每个 provider 的尝试结果：

```json
{
  "success": false,
  "arxiv_id": "2603.00729",
  "source": "arxiv",
  "provider": null,
  "provider_rating": null,
  "content": null,
  "attempts": [
    {
      "provider": "arxiv_html",
      "success": false,
      "error": "HTML unavailable"
    },
    {
      "provider": "deepxiv",
      "success": false,
      "error": "provider returned no content"
    }
  ],
  "error": "arxiv_html: HTML unavailable; deepxiv: provider returned no content"
}
```

## 保留字段

`paper.py` 会在统一字段之外保留 provider 返回的有用字段，方便大模型阅读和后续处理。

常见字段包括：

- arXiv: `title`, `abs_url`, `html_url`, `pdf_url`, `char_count`, `section_count`, `sections`, `level`, `page_count`
- DeepXiv: `abs_url`, `char_count`
- PMC: `title`, `pmid`, `pmc_url`, `char_count`, `section_count`, `sections`, `level`

## Python API

也可以直接导入调用：

```python
from paper import read_paper

result = read_paper("2603.00729", source="arxiv")
section = read_paper("2603.00729", source="arxiv", section="introduction")
sections = read_paper("2603.00729", source="arxiv", list_section=True)
pmc = read_paper("PMC11119143", source="pmc")
```

返回值与 CLI stdout 的 JSON 结构一致。

## 适用场景

- 先用 `search.py` 搜索论文，拿到 `arxiv_id` 或 `pmc_id`
- 用 `--list_section` 先查看可用章节
- 用 `paper.py` 默认读取全文，交给大模型做整体理解
- 用 `--section` 精读 `introduction`、`method`、`experiment`、`conclusion` 等关键章节
- arXiv HTML 不可用时，自动回退到 DeepXiv，再回退到 PDF 全文解析
