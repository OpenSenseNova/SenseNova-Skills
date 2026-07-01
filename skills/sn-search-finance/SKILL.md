---
name: sn-search-finance
description: 用于搜索金融市场、证券、上市公司基本面、价格、K 线、披露文件、财经新闻、A 股数据、港股或全球 ticker，可使用 yfinance、mootdx、API 脚本或 browser-use。
---

# 金融财经搜索

## 凭证配置

API key、token 与 cookie 统一建议写在仓库根目录 `.env`（参考 `.env.example`），并由 runtime 或用户在执行前加载为同名环境变量。脚本仍只从环境变量或显式 CLI 参数读取凭证；不要把真实密钥写入 skill payload、报告、日志或提交。

用于证券、指数、基金、财务报表、行情、K 线、公告线索、财经新闻和公司基本面的检索。API 脚本和 browser-use 可以混合使用；按任务需要选择，不设固定优先级。

## 工作流

1. 先确认市场和标的：A 股/港股/美股/全球 ticker、公司名、证券代码、时间区间、需要的数据口径。
2. 结构化数据用 `scripts/finance_search.py`：yfinance 查全球 ticker、行情、财务、新闻、SEC filings；mootdx 查通达信/A 股行情、K 线、财务包。
3. 需要页面证据、新闻正文、交互筛选、图表核对、脚本失败或字段缺失时，用 browser-use 打开 Yahoo Finance、交易所、上市公司 IR、公告页或搜索结果页交叉核对。
4. 输出结论时保留 ticker/证券代码、市场、数据区间、指标口径和来源 URL；不要把脚本结果当作投资建议。
5. 遇到登录墙、验证码、付费墙、商业授权、异常限流或禁止用途提示时停止该来源，改用可公开访问的页面或说明无法取得。

## API 脚本

脚本：`scripts/finance_search.py`。输出 JSON。依赖按命令懒加载。

首次运行或脚本提示缺库时，使用本技能的依赖清单安装到当前 Python 环境：

```bash
python3 -m pip install -r requirements.txt
```

不要在脚本内部自动安装依赖。若安装失败、网络不可用或包不可用，停止使用对应命令并改用公开网页来源，说明缺少依赖。

### yfinance

Yahoo Finance 代码后缀：美股直接用 `AAPL`；港股可用 `0700.HK`；A 股可用 `600036.SH`、`600036.SS`、`000001.SZ`，脚本会把 `.SH` 自动转成 `.SS`。不想自动转换时加 `--no-normalize`。

```bash
python scripts/finance_search.py yf-search "Tesla" --limit 5 --news-count 5
python scripts/finance_search.py yf-lookup "Tencent" --type stock --limit 10
python scripts/finance_search.py yf-profile AAPL --fields longName,sector,industry,marketCap,currentPrice,trailingPE
python scripts/finance_search.py yf-history AAPL --period 6mo --interval 1d --limit 120
python scripts/finance_search.py yf-download AAPL MSFT NVDA --period 1mo --interval 1d --group-by ticker
python scripts/finance_search.py yf-financials MSFT --statement income --freq yearly
python scripts/finance_search.py yf-financials MSFT --statement balance --freq quarterly
python scripts/finance_search.py yf-news TSLA --limit 8
python scripts/finance_search.py yf-sec-filings AAPL
```

常用命令：

| 命令 | 用途 |
| --- | --- |
| `yf-search` | 搜公司、ticker、新闻和研究入口 |
| `yf-lookup` | 按金融工具类型查找股票、ETF、指数、基金、期货、外汇、加密资产 |
| `yf-profile` | 基本面画像和 fast_info |
| `yf-history` / `yf-download` | 单标的或多标的历史行情 |
| `yf-financials` | 利润表、资产负债表、现金流、盈利数据 |
| `yf-news` | ticker 相关新闻线索 |
| `yf-sec-filings` | SEC filings 线索 |

## mootdx

mootdx 使用通达信代码格式，通常是纯数字。脚本会把 `600036.SH`、`600036.SS`、`000001.SZ` 转成 `600036`、`000001`。

```bash
python scripts/finance_search.py tdx-quotes 600036 000001
python scripts/finance_search.py tdx-bars 600036 --frequency day --offset 120 --adjust qfq
python scripts/finance_search.py tdx-index 000001 --market sh --frequency day --offset 60
python scripts/finance_search.py tdx-stocks --market sh --limit 50
python scripts/finance_search.py tdx-finance 600036
python scripts/finance_search.py tdx-xdxr 600036
python scripts/finance_search.py tdx-affair-files --limit 10
python scripts/finance_search.py tdx-affair-fetch gpcw20231231.zip --downdir tmp
python scripts/finance_search.py tdx-affair-parse gpcw20231231.zip --downdir tmp --limit 100
```

K 线 `--frequency` 可用：`1m`、`5m`、`15m`、`30m`、`1h`、`day`、`week`、`mon`、`3mon`、`year`，也可直接传 mootdx 数字频率。

## browser-use 场景

| 场景 | 用法 |
| --- | --- |
| 脚本返回新闻线索 | 打开新闻 URL 或 Yahoo Finance 新闻页核对标题、发布时间、正文要点 |
| 财务字段不全 | 打开 Yahoo Finance Financials、SEC、交易所公告、公司 IR 页面补证 |
| A 股公告/定期报告 | 配合 `sn-search-year-report` 或 `search-market` 技能查官方披露源 |
| 图表、复权、行情异常 | 打开行情页或交易所页面核对口径 |
| 公司名无法映射 ticker | 用 `yf-search`、`yf-lookup` 和网页搜索互相验证 |
