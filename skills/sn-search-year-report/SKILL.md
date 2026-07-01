---
name: sn-search-year-report
description: 用于搜索免费官方年报、年度报告、定期报告、上市公司披露文件、债券发行人报告和海外公司年度账目。
---

# Search Year Report

## 凭证配置

API key、token 与 cookie 统一建议写在仓库根目录 `.env`（参考 `.env.example`），并由 runtime 或用户在执行前加载为同名环境变量。脚本仍只从环境变量或显式 CLI 参数读取凭证；不要把真实密钥写入 skill payload、报告、日志或提交。

只使用免费、官方、可正常访问的年报/年度账目/定期报告来源。遇到商业库、订阅、试用额度、付费下载、登录墙、验证码、防护页、不可访问页面，立即丢弃，不要绕过限制。

输出时保留公司/证券代码、报告期、文件标题、披露日期、PDF 或详情页 URL、来源名称。

## 工作流

1. 先判断主体类型：A 股/港股/美股/英企/日本上市公司/发债主体/加拿大/新加坡/澳洲。
2. `scripts/year_report_api.py` 和 browser-use 可混合使用：脚本适合结构化查询，网页适合站内筛选、页面确认、下载公开 PDF。
3. 没有脚本覆盖或需要交互筛选的来源，用 browser-use 打开下表网页，通过站内搜索、筛选公告类别、定位 PDF 或详情页。
4. 只接受官方披露源；公司官网 IR 可作补充，但不能替代官方源。
5. 中国普通非上市企业通常没有公开完整财务年报；工商年报不是审计财报，且本技能已丢弃不可稳定访问的工商公示系统。

## API 脚本

脚本位置：`scripts/year_report_api.py`。只依赖 Python 标准库。

```bash
python scripts/year_report_api.py cninfo "平安银行" --year 2023 --page-size 5
python scripts/year_report_api.py sec-company apple --limit 5
python scripts/year_report_api.py sec-filings --ticker AAPL --limit 5
python scripts/year_report_api.py download "https://static.cninfo.com.cn/finalpage/2024-03-15/1219306493.PDF" --output report.pdf
```

| 命令 | 免费性 | 用途 |
| --- | --- | --- |
| `cninfo` | 免费、免 key | 巨潮资讯 A 股公告，默认查年度报告 PDF |
| `sec-company` / `sec-filings` | 免费、免 key | SEC EDGAR 公司 CIK、10-K/20-F/40-F 年报文件 |
| `download` | 免费公开 URL | 下载脚本返回的公开 PDF |

`cninfo --year` 表示报告期年份；脚本会自动查下一年的披露窗口。若要按披露日期精确过滤，改用 `--date-range`。

脚本只保留免 key 接口；任何需要 API key、token、注册登录或订阅的接口都不要加入脚本。

## Browser-use 资源

以下来源作为免费官方网页入口；按任务需要与 API 脚本混合使用。

| 范围 | 资源 | URL | 使用要点 |
| --- | --- | --- | --- |
| A 股全市场 | 巨潮资讯 | https://www.cninfo.com.cn/new/index?lang=zh | 搜索公司名/证券代码，筛“年度报告” |
| 沪市上市公司 | 上交所定期报告 | https://www.sse.com.cn/disclosure/listedinfo/regular/ | 按证券代码、年份、定期报告筛选 |
| 深市上市公司 | 深交所上市公司公告 | https://www.szse.cn/www/disclosure/notice/company/ | 按公司、公告类型、时间筛选 |
| 北交所上市公司 | 北交所信息披露 | https://www.bse.cn/disclosure/announcement.html | 搜索年度报告/定期报告 |
| 港股 | HKEXnews Predefined Documents | https://www1.hkexnews.hk/search/predefineddoc.xhtml | 选 Annual Report / Environmental, Social and Governance Information |
| 中国债券发行人 | 中国货币网债券信息披露 | https://www.chinamoney.org.cn/chinese/zqfx/ | 搜索发行人年报、审计报告、跟踪评级 |
| 中国债券发行人 | 上海清算所 | https://www.shclearing.com.cn/ | 搜索发行人年度报告/审计报告 |
| 中国债券发行人 | 上交所债券信息披露 | https://bond.sse.com.cn/disclosure/ | 搜索债券发行人年度报告 |
| 英国公司账目 | Companies House 网页 | https://find-and-update.company-information.service.gov.uk/ | 无 API key 时查 filing history / accounts |
| 加拿大上市公司 | SEDAR+ Documents Search | https://www.sedarplus.ca/csa-party/service/create.html?_locale=en&service=searchDocuments&targetAppCode=csa-party | 选择 Documents，按 issuer/profile 和 annual filings 搜索 |
| 新加坡上市公司 | SGX Company Announcements | https://www.sgx.com/securities/company-announcements | 搜索 Annual Report 或公司代码 |
| 澳洲上市公司 | ASX Announcements | https://www.asx.com.au/markets/trade-our-cash-market/announcements | 按 ASX code 和 announcement type 搜索 |

## 已丢弃

| 资源 | 原因 |
| --- | --- |
| 国家企业信用信息公示系统 `https://www.gsxt.gov.cn/` | 与工商年报相关，但访问被阻断，不作为稳定免费源 |
| 市场监管总局说明页 | 只是政策说明，不是年报搜索入口 |
| Companies House API、EDINET API | 需要 API key，不写入脚本 |
| 任何商业数据库或付费 API | 不符合免费官方源要求 |

## 输出规范

能定位到 PDF 时给 PDF；没有 PDF 时给官方详情页。说明报告类型差异：工商年报、上市公司年度报告、SEC 10-K/20-F/40-F、Companies House accounts、债券发行人年度报告不是同一披露口径。
