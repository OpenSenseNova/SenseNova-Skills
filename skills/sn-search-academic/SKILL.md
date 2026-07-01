---
name: sn-search-academic
description: 用于学术调研、论文精读、相关工作梳理、百科知识查询和引用链追溯。
---

# sn-search-academic - 学术搜索

## 凭证配置

API key、token 与 cookie 统一建议写在仓库根目录 `.env`（参考 `.env.example`），并由 runtime 或用户在执行前加载为同名环境变量。脚本仍只从环境变量或显式 CLI 参数读取凭证；不要把真实密钥写入 skill payload、报告、日志或提交。

使用三个统一入口完成学术调研：

- `search.py`：搜索论文和百科条目
- `paper.py`：列出论文章节，读取论文全文或指定章节
- `refTree.py`：查询论文的 references 和 citations

不要直接调用历史 provider 脚本；它们只是统一入口的内部实现细节。
需要 provider 回退链、参数分发或完整输出字段时，按需读取 `references/search.md`、`references/paper.md`、`references/refTree.md`。

## 可用脚本

| 脚本 | 用途 | 主要输入 | 主要输出 |
|------|------|----------|----------|
| `scripts/search.py` | 搜索论文/百科 | `query`，可选 `--source`、`--limit`、`--category`、`--lang` | 按 source 分组的论文/百科条目，位于 `source_results[*].items` |
| `scripts/paper.py` | 列出章节，读取论文全文或章节 | 论文 ID，可选 `--source`、`--list_section`、`--section` | 章节列表位于 `sections`；全文或章节正文位于 `content` |
| `scripts/refTree.py` | 查询引用树 | `--paper_id`、`--title`，可选 `--direction` | 参考文献与被引论文，位于 `source_results[*].references` / `source_results[*].citations` |

## 执行约定

本技能的 `scripts/...`、`requirements.txt`、`references/...` 路径均相对本 skill 目录；若当前工作目录不同，先解析为绝对路径，不要依赖 `${SKILL_DIR}` 运行时变量。

调用约定：

- 不要并行启动多个本技能脚本；`search.py` 和 `refTree.py` 内部已经处理并发、超时和 provider 回退链。
- 长结果优先加 `--output <path>` 写入文件，再读取必要字段，避免终端输出过长。
- `--provider-timeout` 表示单个 provider 超时；默认使用脚本内置超时。

## 依赖

首次运行或脚本提示缺库时，使用本技能的依赖清单安装到当前 Python 环境：

```bash
python3 -m pip install -r requirements.txt
```

不要在脚本内部自动安装依赖。若安装失败、网络不可用或包不可用，停止使用对应脚本并改用 WebSearch/browser-use，说明缺少依赖。

Crawler 回退还需要额外运行时环境：

```bash
python3 -m playwright install firefox
```

`arxiv_crawler_search.py` 和 `semantic_scholar_crawler_refTree.py` 还需要 Node.js，以及某个当前目录或祖先目录中已安装 `camoufox-js` 的 `node_modules`。缺少这些环境时，不要尝试绕过；改用非 crawler provider 或网页搜索。

## 参数说明

### search.py

统一搜索入口。默认搜索所有支持的 source，并按 source 分组返回结果。

```bash
python3 scripts/search.py <query> [选项]
```

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `query` | 搜索关键词，必填位置参数 | - |
| `--source`, `--sources`, `-s` | 搜索源；支持重复传参或逗号分隔 | `all` |
| `--limit`, `-n` | 每个 source 返回数量 | `10` |
| `--category`, `-c` | ArXiv 分类过滤，只传给支持分类的 source | - |
| `--lang`, `-l` | 语言提示，只传给支持语言参数的 source | - |
| `--output`, `-o` | 将最终 JSON 写入文件 | - |
| `--provider-timeout` | 每个 provider 的超时时间，单位秒；`0` 表示不限制 | `60` |

支持的 `--source`：

- `all`
- `arxiv`
- `semantic`
- `google_scholar`
- `pubmed`
- `wikipedia`

示例：

```bash
python3 scripts/search.py "retrieval augmented generation" --limit 5
python3 scripts/search.py "diffusion model" --source arxiv,semantic --category cs.CV --limit 5
python3 scripts/search.py "阿尔茨海默病 多模态诊断" --source pubmed,wikipedia --lang zh --limit 5
python3 scripts/search.py "agentic memory" --source all --limit 8 --output results/search.json
```

### paper.py

统一论文阅读入口。默认按 arXiv 论文读取；读取 PMC 论文时显式传 `--source pmc`。不确定章节名时先用 `--list_section` 列出可用章节，再用 `--section` 精读。

```bash
python3 scripts/paper.py <id> [选项]
```

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `id` | 论文 ID。arXiv 支持原始 ID、`arXiv:` 前缀、abs/pdf URL；PMC 支持 `PMC11119143`、`11119143`、PMC URL | - |
| `--source` | 论文来源：`arxiv` 或 `pmc` | `arxiv` |
| `--section`, `-s` | 读取指定章节；不填则读取全文 | - |
| `--list_section`, `--list-section` | 列出论文可用章节，不返回正文；不能和 `--section` 同时使用 | false |
| `--output`, `-o` | 将最终 JSON 写入文件 | - |

示例：

```bash
python3 scripts/paper.py 2603.00729
python3 scripts/paper.py 2603.00729 --list_section
python3 scripts/paper.py arXiv:2603.00729 --section introduction
python3 scripts/paper.py 2603.00729 --section method --output results/paper-method.json
python3 scripts/paper.py PMC11119143 --source pmc
python3 scripts/paper.py PMC11119143 --source pmc --list-section
python3 scripts/paper.py PMC11119143 --source pmc --section results
```

### refTree.py

统一引用树入口。`--paper_id` 和 `--title` 都必填；标题用于回退时精确匹配。

```bash
python3 scripts/refTree.py --paper_id <paper_id> --title <title> [选项]
```

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--paper_id` | 论文 ID：Semantic Scholar ID、DOI、ArXiv ID、PMID 等 | - |
| `--title` | 论文标题，必填 | - |
| `--direction` | 查询方向：`references` 或 `citations`；不填则两者都查 | - |
| `--source`, `--sources`, `-s` | 引用树 source；当前支持 `all`、`semantic` | `all` |
| `--limit`, `-n` | 每个 source、每个 direction 返回数量 | `10` |
| `--api-key` | Semantic Scholar API 密钥，可选 | - |
| `--provider-timeout` | 每个 provider 的超时时间，单位秒；`0` 表示不限制 | `60` |
| `--output`, `-o` | 将最终 JSON 写入文件 | - |

注意：参数名是 `--paper_id`，不是 `--paper-id`；`paper_id` 不支持位置参数。

示例：

```bash
python3 scripts/refTree.py --paper_id "2309.16609" --title "Qwen Technical Report"
python3 scripts/refTree.py --paper_id "2309.16609" --title "Qwen Technical Report" --direction references --limit 20
python3 scripts/refTree.py --paper_id "10.1038/s41586-024-07487-w" --title "AlphaFold 3" --direction citations
python3 scripts/refTree.py --paper_id "2309.16609" --title "Qwen Technical Report" --output results/refTree.json
```

## 输出格式

所有脚本都输出 JSON。先看顶层 `success`；失败时读取 `error`、`errors` 和 `attempts` 判断是无结果、超时还是 provider 失败。

### search.py 输出

CLI 输出的顶层不包含 `items`，论文条目在 `source_results[*].items` 中：

```json
{
  "success": true,
  "query": "retrieval augmented generation",
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
          "title": "Example title",
          "abstract": "Example abstract",
          "citation_count": null,
          "arxiv_id": "2301.00001",
          "url": "https://arxiv.org/abs/2301.00001"
        }
      ],
      "attempts": [],
      "error": null
    }
  ],
  "errors": [],
  "error": null
}
```

常用 item 字段：

- 通用：`title`、`abstract`、`snippet`、`url`、`citation_count`、`doi`
- arXiv：`arxiv_id`、`pdf_url`、`categories`
- Semantic Scholar：`paper_id`、`venue`、`year`
- PubMed：`pmid`、`pmc_id`、`journal`、`pub_date`
- Wikipedia：`page_id`、`word_count`、`section_title`

### paper.py 输出

默认读取全文；指定 `--section` 时读取章节。正文在顶层 `content`：

```json
{
  "success": true,
  "source": "arxiv",
  "provider": "arxiv_html",
  "arxiv_id": "2603.00729",
  "section": "introduction",
  "content": "<全文或章节正文>",
  "char_count": 12345,
  "attempts": [],
  "error": null
}
```

指定 `--list_section` 时只返回章节结构，不返回 `content`：

```json
{
  "success": true,
  "source": "arxiv",
  "provider": "arxiv_html",
  "arxiv_id": "2603.00729",
  "section_count": 2,
  "sections": [
    {"name": "Abstract", "level": 0},
    {"name": "1 Introduction", "level": 1}
  ],
  "attempts": [],
  "error": null
}
```

常用字段：

- arXiv：`arxiv_id`、`title`、`abs_url`、`html_url`、`pdf_url`、`section_count`、`sections`
- PMC：`pmc_id`、`pmid`、`title`、`pmc_url`、`section_count`、`sections`
- 指定 `--list_section` 时返回 `sections` 和 `section_count`，不包含 `content`
- 指定 `--section` 时会包含 `section`；不指定 `--list_section` / `--section` 时读取全文

### refTree.py 输出

引用树结果在 `source_results[*].references` 和 `source_results[*].citations`：

```json
{
  "success": true,
  "id": "2309.16609",
  "title": "Qwen Technical Report",
  "provider": "refTree.py",
  "direction": "all",
  "source_results": [
    {
      "source": "semantic",
      "success": true,
      "provider": "semantic_official",
      "references": [
        {
          "title": "Example reference",
          "abstract": "Example abstract",
          "citation_count": 128,
          "paper_id": "example-reference-id",
          "arxiv_id": "2301.00001"
        }
      ],
      "citations": [
        {
          "title": "Example citing paper",
          "abstract": "Example abstract",
          "citation_count": 42,
          "paper_id": "example-citing-id",
          "doi": "10.1234/example"
        }
      ],
      "attempts": [],
      "error": null
    }
  ],
  "errors": [],
  "error": null
}
```

如果使用 `--output`，三个脚本都会在 JSON 中额外加入 `output_path`。

## 并发与限流约定
这些脚本会访问外部学术服务，必须控制请求频率。
执行本技能脚本时：
- 不要并发运行多个搜索脚本。
- 不要使用并行工具同时调用多个 `python3 scripts/...` 命令。
- 一次只运行一个脚本命令，等待结果返回后再运行下一个。
- 批量查询时，优先使用脚本自带的 `--limit`、`--id-list` 等参数，而不是启动多个进程。
- 如果需要连续调用，按顺序执行，并在必要时等待数秒。

## 全文阅读工作流

搜索结果只有摘要时，用 `paper.py` 先列章节，再补充全文或关键章节。

1. 先用 `search.py` 搜索，优先从 `source_results[*].items` 里记录 `title`、`arxiv_id`、`pmc_id`、`paper_id`、`doi`、`citation_count`。
2. 如果条目有 `arxiv_id`，先用 `python3 scripts/paper.py <arxiv_id> --source arxiv --list_section` 查看章节；再用 `--section <section>` 精读。
3. 如果条目有 `pmc_id`，先用 `python3 scripts/paper.py <pmc_id> --source pmc --list_section` 查看章节；再按需读 `--section <section>` 。
4. 如果需要整体理解，再不带 `--section` / `--list_section` 读取全文。
5. 全文很长时使用 `--output results/paper.json`，再读取 `content`、`sections`、`char_count` 等字段。

## 引用追溯工作流

通过论文的引用关系发现关键词搜索覆盖不到的相关工作。

通过 references 找奠基工作，通过 citations 找后续进展。`refTree.py` 需要同时传论文 ID 和标题。

**后向追溯（找奠基工作）**：


1. 关键词搜索找到高相关论文 → 取其 `paper_id` 或 `arxiv_id` 和 `title`
2. `refTree.py --paper_id "<id>" --title "<title>" --direction references --limit 20`  → 找到高引参考文献
3. 筛选与研究问题相关的条目 → 用 `paper.py`深入阅读

**前向追踪（找后续进展）**：

1. 找到领域奠基论文或关键论文 → 取其 ID
2. `refTree.py --paper_id "<id>" --title "<title>" --direction citations --limit 20` → 找到近期高引跟进工作
3. 筛选与研究问题相关的条目 → 用 `paper.py`深入阅读

**引用链：构建演化路径**

1. 从种子论文 A 出发 → backward 找到 A 的关键参考文献 B
2. 从 B 出发 → forward 找到引用 B 的后续工作（可能发现 A 没引用的相关论文 C）
3. 形成 B → A → ... 和 B → C → ... 的知识脉络

## 主工作流
严格遵循本工作流去执行学术搜索的全流程

1. 在提供的学术平台选择所有可能的平台搜索学术文献
2. 如果摘要不足或论文高度相关时，列出章节，尝试读取论文章节或全文，判断论文和搜索需求的相关性
3. 选择相关性高的论文，搜索它的参考文献和被引（使用引用追溯工作流）。
4. 选择引用树中 高引用的文献，执行步骤 2、步骤 3。
5. 重复以上步骤，进行多轮搜索，尽可能多的进行搜索。
6. 当文献数量、引用链和全文证据足够支撑回答时停止搜索，并在结论中说明主要依据。

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
