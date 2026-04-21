---
name: search-academic
description: 搜索学术论文和百科知识：ArXiv 预印本、Semantic Scholar（含引用数）、PubMed 生医文献、Wikipedia 百科。支持按章节读取 ArXiv HTML 全文和 PMC 开放获取全文，适合学术调研和深度阅读。
---

# search-academic - 学术搜索

搜索 ArXiv、Semantic Scholar、PubMed、Wikipedia 四个学术平台，并提供 ArXiv 和 PMC 的**全文章节阅读**能力。全部免费，部分脚本有可选 API key 可提升限额。

## 可用脚本

| 脚本 | 平台 | 用途 | API key |
|------|------|------|---------|
| `arxiv_search.py` | ArXiv | 预印本搜索，支持作者/标题/ID查询 | 无需 |
| `arxiv_paper.py` | ArXiv HTML | 按章节读取 ArXiv 论文全文 | 无需 |
| `semantic_scholar_search.py` | Semantic Scholar | 全学科搜索，含引用数和 TLDR | 无需（有 key 限额更高） |
| `semantic_scholar_refs.py` | Semantic Scholar | 引用追溯：查论文的参考文献（backward）或被引论文（forward） | 无需（有 key 限额更高） |
| `pubmed_search.py` | PubMed | 生医文献搜索，含结构化摘要和 PMC ID | 无需（有 key 限额更高） |
| `pmc_paper.py` | PMC | 按章节读取 PMC 开放获取论文全文 | 无需（有 key 限额更高） |
| `wikipedia_search.py` | Wikipedia | 百科文章搜索，支持多语言 | 无需 |

## 参数说明

### arxiv_search.py

```bash
python3 scripts/arxiv_search.py <query> [选项]
```

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `query` | 搜索关键词（使用 `--id-list` 时可省略） | — |
| `--limit`, `-n` | 返回结果数量 | 10 |
| `--category`, `-c` | ArXiv 分类过滤（见下方"ArXiv 分类速查"） | — |
| `--sort` | 排序方式：`relevance`, `date`, `submitted` | relevance |
| `--author`, `-a` | 按作者过滤，多个用逗号分隔 | — |
| `--title-only` | 仅在标题中搜索 | — |
| `--id-list` | 直接按 arXiv ID 获取元数据，逗号分隔 | — |

```bash
python3 scripts/arxiv_search.py "transformer attention mechanism" --limit 5
python3 scripts/arxiv_search.py "diffusion model" --author "ho jonathan" --category cs.CV
python3 scripts/arxiv_search.py --id-list "2409.05591,2301.07041"
```

**输出字段**：`title`, `url`, `snippet`（摘要）, `arxiv_id`, `authors`, `published`, `updated`, `pdf_url`, `html_url`, `categories`, `primary_category`, `comment`, `journal_ref`, `doi`

### arxiv_paper.py

按章节读取 ArXiv 论文正文（需论文有 HTML 版本，2020 年后多数论文支持）。

```bash
python3 scripts/arxiv_paper.py <arxiv_id> [--section SECTION_NAME]
```

| 参数 | 说明 |
|------|------|
| `arxiv_id` | arXiv ID（如 `2409.05591` 或 `2409.05591v2`） |
| `--section`, `-s` | 章节名（大小写不敏感，支持部分匹配）。不指定则列出所有章节。 |

```bash
python3 scripts/arxiv_paper.py 2409.05591                      # 列出章节
python3 scripts/arxiv_paper.py 2409.05591 --section introduction
python3 scripts/arxiv_paper.py 2409.05591 --section method
```

**列出章节输出字段**：`arxiv_id`, `abs_url`, `html_url`, `pdf_url`, `section_count`, `sections[]`（name, level）

**读取章节输出字段**：`arxiv_id`, `section`, `level`, `content`, `char_count`

### semantic_scholar_search.py

```bash
python3 scripts/semantic_scholar_search.py <query> [选项]
```

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `query` | 搜索关键词（必填） | — |
| `--limit`, `-n` | 返回结果数量 | 10 |
| `--api-key` | Semantic Scholar API Key（也可通过 `S2_API_KEY` 环境变量） | — |

```bash
python3 scripts/semantic_scholar_search.py "transformer architecture" --limit 5
python3 scripts/semantic_scholar_search.py "RLHF language model" --limit 10
```

**输出字段**：`title`, `url`, `snippet`（摘要，缺失时降级为 tldr）, `tldr`, `authors`, `year`, `venue`, `publication_date`, `citation_count`, `influential_citation_count`, `reference_count`, `is_open_access`, `open_access_pdf`, `fields_of_study`, `publication_types`, `doi`, `arxiv_id`, `paper_id`

### semantic_scholar_refs.py

引用追溯：给定一篇论文，查询它的参考文献（backward）或被引论文（forward）。

```bash
python3 scripts/semantic_scholar_refs.py <paper_id> <direction> [选项]
```

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `paper_id` | 论文标识符：S2 ID、DOI（`10.xxxx/...`）、ArXiv ID（`2301.07041`）、PMID（`PMID:12345678`） | — |
| `direction` | `references`=参考文献（backward），`citations`=被引论文（forward） | — |
| `--limit`, `-n` | 返回结果数量 | 20 |
| `--min-citations` | 最低引用数过滤 | 0 |
| `--year-min` | 最早年份过滤 | — |
| `--year-max` | 最晚年份过滤 | — |
| `--api-key` | Semantic Scholar API Key（可选） | — |

```bash
# 查看某篇论文引用了哪些论文（backward：找奠基工作）
python3 scripts/semantic_scholar_refs.py 2301.07041 references --limit 10

# 查看某篇论文被谁引用（forward：找后续进展）
python3 scripts/semantic_scholar_refs.py 2301.07041 citations --limit 10 --min-citations 50

# 用 DOI 查引用，限定 2023 年以后
python3 scripts/semantic_scholar_refs.py "10.1038/s41586-024-07487-w" citations --year-min 2023

# 找高引参考文献
python3 scripts/semantic_scholar_refs.py ARXIV:2005.14165 references --min-citations 100 --limit 5
```

**输出字段**：`title`, `url`, `snippet`（摘要/tldr）, `authors`, `year`, `venue`, `citation_count`, `influential_citation_count`, `is_open_access`, `open_access_pdf`, `doi`, `arxiv_id`, `paper_id`, `citation_contexts`（引用上下文句子，最多 3 条）, `citation_intents`（引用意图）

**输出额外字段**：`source_paper`（被查询论文的标题/年份/引用数）, `total_available`（该方向总论文数）, `returned`（过滤后返回数）

### pubmed_search.py

支持 PubMed 查询语法，如字段限定（`cancer[Title]`）、日期范围（`2024[pdat]`）。

```bash
python3 scripts/pubmed_search.py <query> [选项]
```

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `query` | 搜索关键词，支持 PubMed 查询语法 | — |
| `--limit`, `-n` | 返回结果数量 | 10 |
| `--api-key` | NCBI API Key（可选，限额从 3 req/s 升至 10 req/s） | — |

```bash
python3 scripts/pubmed_search.py "CRISPR gene editing" --limit 5
python3 scripts/pubmed_search.py "Alzheimer[Title] AND treatment[Title]" --limit 5
```

**输出字段**：`title`, `url`, `snippet`（结构化摘要）, `authors`, `pmid`, `pmc_id`（有值则可传入 `pmc_paper.py`）, `pmc_url`, `journal`, `pub_date`, `volume`, `issue`, `pages`, `keywords`, `pub_types`, `doi`

### pmc_paper.py

读取 PubMed Central 开放获取全文（约 700 万篇生医论文，占 PubMed 约 35%）。`pubmed_search.py` 结果中 `pmc_id` 为 `null` 的论文无法使用本工具。

```bash
python3 scripts/pmc_paper.py <pmc_id> [--section SECTION_NAME]
python3 scripts/pmc_paper.py --pmid <pmid> [--section SECTION_NAME]
```

| 参数 | 说明 |
|------|------|
| `pmc_id` | PMC ID（如 `PMC11119143` 或 `11119143`） |
| `--pmid` | PubMed ID，自动转换为 PMC ID（与 `pmc_id` 二选一） |
| `--section`, `-s` | 章节名（大小写不敏感，支持部分匹配）。不指定则列出所有章节。 |
| `--api-key` | NCBI API Key（可选） |

```bash
python3 scripts/pmc_paper.py PMC11119143                       # 列出章节
python3 scripts/pmc_paper.py PMC11119143 --section introduction
python3 scripts/pmc_paper.py --pmid 38786024 --section conclusion
```

**列出章节输出字段**：`pmc_id`, `pmid`, `title`, `pmc_url`, `section_count`, `sections[]`（name, level，含子章节层级）

**读取章节输出字段**：`pmc_id`, `section`, `level`, `content`（含子章节文本）, `char_count`

### wikipedia_search.py

```bash
python3 scripts/wikipedia_search.py <query> [选项]
```

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `query` | 搜索关键词（必填） | — |
| `--limit`, `-n` | 返回结果数量 | 10 |
| `--lang`, `-l` | 语言版本（`en`, `zh`, `ja`, `de`, `fr` 等） | en |

```bash
python3 scripts/wikipedia_search.py "machine learning" --limit 5
python3 scripts/wikipedia_search.py "深度学习" --lang zh --limit 5
```

## 全文阅读工作流

搜索脚本返回摘要，阅读脚本返回正文。两者配合可按需精读，节省 token。

**ArXiv 论文**：
1. `arxiv_search.py` 搜索 → 获取 `arxiv_id`
2. `arxiv_paper.py <id>` 列章节 → `arxiv_paper.py <id> --section introduction` 快速判断是否深入
3. 按需读取 `method` / `experiment` / `conclusion`

**PMC 生医论文**：
1. `pubmed_search.py` 搜索 → 结果中取 `pmc_id`（非 null 才有全文）
2. `pmc_paper.py <pmc_id>` 列章节 → 按需读取关键章节

## 引用追溯工作流

通过论文的引用关系发现关键词搜索覆盖不到的相关工作。

**Backward（找奠基工作）**：
1. 关键词搜索找到高相关论文 → 取其 `paper_id` 或 `arxiv_id`
2. `semantic_scholar_refs.py <id> references --min-citations 50` → 找到高引参考文献
3. 筛选与研究问题相关的条目 → 用 `arxiv_paper.py` 或 `pmc_paper.py` 深入阅读

**Forward（找后续进展）**：
1. 找到领域奠基论文或关键论文 → 取其 ID
2. `semantic_scholar_refs.py <id> citations --year-min 2024 --min-citations 10` → 找到近期高引跟进工作
3. 筛选与研究问题相关的条目 → 深入阅读

**Citation Chain（追溯演化路径）**：
1. 从种子论文 A 出发 → backward 找到 A 的关键参考文献 B
2. 从 B 出发 → forward 找到引用 B 的后续工作（可能发现 A 没引用的相关论文 C）
3. 形成 B → A → ... 和 B → C → ... 的知识脉络

## ArXiv 分类速查

顶层领域可直接用（如 `--category cs`），子分类更精确（如 `--category cs.AI`）。

| 领域 | 分类代码 | 说明 |
|------|---------|------|
| **计算机科学** | `cs.AI` | 人工智能 |
| | `cs.LG` | 机器学习 |
| | `cs.CL` | 计算语言学 / NLP |
| | `cs.CV` | 计算机视觉 |
| | `cs.IR` | 信息检索 |
| | `cs.RO` | 机器人 |
| | `cs.SE` | 软件工程 |
| | `cs.DC` | 分布式/并行计算 |
| | `cs.NI` | 网络与互联网 |
| | `cs.CR` | 密码学与安全 |
| | `cs.DB` | 数据库 |
| | `cs.HC` | 人机交互 |
| **统计** | `stat.ML` | 统计机器学习 |
| | `stat.AP` | 应用统计 |
| | `stat.ME` | 统计方法论 |
| **数学** | `math.OC` | 优化与控制 |
| | `math.ST` | 统计理论 |
| | `math.CO` | 组合数学 |
| **物理** | `physics` | 物理（全类） |
| | `cond-mat` | 凝聚态物理 |
| | `quant-ph` | 量子物理 |
| | `hep-th` | 高能理论物理 |
| **经济/金融** | `econ.GN` | 经济学综合 |
| | `q-fin.CP` | 计算金融 |
| | `q-fin.ST` | 统计金融 |
| **生物/医学** | `q-bio.NC` | 神经科学 |
| | `q-bio.GN` | 基因组学 |
| | `q-bio.QM` | 定量方法 |

## 输出格式

所有脚本输出标准 JSON：

```json
{
  "success": true,
  "query": "...",
  "provider": "arxiv|semantic_scholar|pubmed|wikipedia",
  "items": [{"title": "...", "url": "...", "snippet": "...", ...}],
  "error": null
}
```

`arxiv_paper.py` 和 `pmc_paper.py` 不走 `items` 格式，直接返回结构化对象（见各自"输出字段"说明）。
