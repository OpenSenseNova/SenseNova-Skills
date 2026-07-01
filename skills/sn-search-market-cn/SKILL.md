---
name: sn-search-market-cn
description: Use when researching China market, industry, macro, trade, procurement, listed-company disclosure, regulation, IP, healthcare, logistics, energy, environment, or industrial-operation information using free official sources with no registration, no API key, and no cryptocurrency data.
---

# 中国市场商业搜索

## 凭证配置

API key、token 与 cookie 统一建议写在仓库根目录 `.env`（参考 `.env.example`），并由 runtime 或用户在执行前加载为同名环境变量。脚本仍只从环境变量或显式 CLI 参数读取凭证；不要把真实密钥写入 skill payload、报告、日志或提交。

只使用本技能列出的中国官方免费资源。不要补充表外资源；遇到注册、登录、验证码、授权码、API key、OAuth、数字签名对接、商业试用、付费墙、访问防护或加密货币数据，立即放弃该资源。

## 工作流

1. 明确研究对象：行业、公司、地区、时间段、指标口径和需要的证据类型。
2. A 股公告、年报、季报、问询函先用 API 脚本；脚本拿不到再用 browser-use 打开巨潮页面。
3. 其它资源统一用 browser-use 正常访问网页，通过站内搜索、栏目导航、筛选器和公开下载文件取数。
4. 宏观、监管、招投标、采购、行业运行数据优先引用官方页面或官方文件链接；结论中保留来源 URL、指标口径和时间范围。
5. 不绕过验证码、防护页、登录墙、签名接口或授权申请；不要采集个人敏感信息。

## API 脚本

脚本：`scripts/free_market_api.py`。只依赖 Python 标准库。

可用接口：

| 命令 | 来源 | 适合用途 |
| --- | --- | --- |
| `cninfo-announcements` | 巨潮资讯公告查询接口 | A 股公告、年报、季报、问询函、招股书线索 |

示例：

```bash
python scripts/free_market_api.py cninfo-announcements --keyword 年报 --start-date 2026-01-01 --end-date 2026-05-18 --page-size 5
python scripts/free_market_api.py cninfo-announcements --keyword 业绩说明会 --page-size 10
python scripts/free_market_api.py cninfo-announcements --keyword 问询函 --start-date 2026-04-01 --end-date 2026-05-18
```

输出 JSON 中的 `data.announcements[].pdfUrl` 是公告 PDF 地址，可直接作为引用或交给 browser-use 打开核对原文。

## Browser-use 资源

以下资源没有可直接使用的免 key API，或接口需要签名/授权；统一用 browser-use 访问网页。

| 场景 | 资源 | URL | 用法 |
| --- | --- | --- | --- |
| 宏观经济 | 国家统计局国家数据 | https://data.stats.gov.cn/ | GDP、CPI、PPI、PMI、工业、社零、固定资产投资、房地产、人口、就业 |
| 宏观经济 | 国家统计局官网 | https://www.stats.gov.cn/ | 统计公报、月度/年度统计、专题数据、新闻发布稿 |
| 金融货币 | 中国人民银行调查统计 | https://www.pbc.gov.cn/diaochatongjisi/116219/index.html | M2、社融、贷款、利率、金融统计报告 |
| 外汇 | 国家外汇管理局统计数据 | https://www.safe.gov.cn/safe/tjsj1/index.html | 外储、汇率、国际收支、结售汇、跨境收支 |
| 商贸 | 商务部商务数据中心 | https://data.mofcom.gov.cn/index.shtml | 国内贸易、外资、ODI、服务贸易、商品市场 |
| 政府采购 | 中国政府采购网 | https://www.ccgp.gov.cn/xxgg/ | 采购公告、中标公告、预算金额、供应商、采购人 |
| 招投标 | 全国公共资源交易平台 | https://www.ggzy.gov.cn/ | 工程建设、政府采购、土地矿权、产权交易 |
| 信用风控 | 信用中国 | https://www.creditchina.gov.cn/ | 行政处罚、失信、信用承诺、信用信息公示 |
| 司法风险 | 中国执行信息公开网 | http://zxgk.court.gov.cn/ | 被执行人、失信被执行人、限制消费线索 |
| 破产风险 | 全国企业破产重整案件信息网 | https://pccz.court.gov.cn/ | 破产、重整、清算案件和招募投资人信息 |
| 上市公司 | 巨潮资讯 | https://www.cninfo.com.cn/new/index | A 股公告、年报、季报、招股书、问询函；优先用脚本 |
| 证券交易所 | 上海证券交易所 | https://www.sse.com.cn/ | 沪市公告、监管信息、上市公司、债券、基金、市场数据 |
| 证券交易所 | 深圳证券交易所 | https://www.szse.cn/ | 深市公告、监管信息、上市公司、市场数据 |
| 证券交易所 | 北京证券交易所 | https://www.bse.cn/ | 北交所公告、上市公司、市场统计 |
| 证券监管 | 中国证监会 | https://www.csrc.gov.cn/ | 监管政策、处罚、IPO、基金、证券期货统计 |
| 知识产权 | 国家知识产权局 | https://www.cnipa.gov.cn/ | 专利、商标、地理标志、知识产权政策 |
| 知识产权 | 专利检索及分析系统介绍 | https://www.cnipa.gov.cn/art/2023/2/13/art_3166_182074.html | 专利检索入口说明、技术路线和竞品研发趋势线索 |
| 医疗器械 | NMPA 医疗器械 UDI 数据共享 | https://udi.nmpa.gov.cn/toDetail.html?CatalogId=3&infoId=40 | 只用页面查询/数据下载；不要申请或使用接口授权码 |
| 医保 | 国家医保局 | https://www.nhsa.gov.cn/ | 医保目录、集采、支付标准、医保政策 |
| 农业 | 农业农村部数据平台 | https://data.moa.gov.cn/ | 农产品价格、农业生产、畜牧、水产、市场监测 |
| 交通物流 | 交通运输部数据 | https://www.mot.gov.cn/shuju/ | 货运、客运、港口吞吐量、公路水路运输 |
| 快递物流 | 国家邮政局 | https://www.spb.gov.cn/ | 快递业务量、业务收入、区域结构 |
| 民航 | 中国民航局 | https://www.caac.gov.cn/ | 旅客吞吐量、货邮吞吐量、航班、机场统计 |
| 能源 | 国家能源局 | https://www.nea.gov.cn/ | 电力、煤炭、油气、新能源、能源政策 |
| 环境 | 生态环境部环境质量 | https://www.mee.gov.cn/hjzl/ | 空气质量、水质、生态环境公报、环保监管 |
| 电力 | 中国电力企业联合会 | https://www.cec.org.cn/ | 发电量、用电量、电力行业运行、行业指数 |
| 工业运行 | 工业和信息化部 | https://www.miit.gov.cn/ | 工业经济、通信业、软件业、中小企业、政策 |

## 使用边界

- 国家统计局国家数据只通过页面、下载和公开文件使用，不调用未说明的非公开接口。
- 中国政府采购网数据接口规范需要数字签名，对普通搜索任务不要当作免 key API。
- NMPA UDI 接口对接需要授权码，只能使用页面查询和公开下载。
- 若 browser-use 打开后是空白页、防护页、被拦截或要求验证，直接换用其它官方来源，不要重试绕过。
