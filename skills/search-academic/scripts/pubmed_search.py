#!/usr/bin/env python3
"""PubMed 生物医学文献搜索。通过 NCBI E-utilities API。"""
from __future__ import annotations

import sys
import xml.etree.ElementTree as ET

from search_utils import build_parser, get_client, make_item, make_result, print_json

ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"


def search(query: str, limit: int, api_key: str | None = None) -> list[dict]:
    """执行 PubMed 搜索（两步：esearch 获取 PMID，efetch 获取完整记录含摘要）。"""
    base_params: dict = {"api_key": api_key} if api_key else {}

    # Step 1: esearch 获取 PMID 列表
    with get_client(timeout=30) as client:
        resp = client.get(ESEARCH_URL, params={
            **base_params,
            "db": "pubmed",
            "term": query,
            "retmax": min(limit, 100),
            "retmode": "json",
            "sort": "relevance",
        })
        resp.raise_for_status()
        pmids = resp.json().get("esearchresult", {}).get("idlist", [])

    if not pmids:
        return []

    # Step 2: efetch 获取完整 XML 记录（含摘要）
    with get_client(timeout=30) as client:
        resp = client.get(EFETCH_URL, params={
            **base_params,
            "db": "pubmed",
            "id": ",".join(pmids[:limit]),
            "rettype": "xml",
            "retmode": "xml",
        })
        resp.raise_for_status()

    root = ET.fromstring(resp.text)
    items = []

    for article in root.findall(".//PubmedArticle"):
        medline = article.find("MedlineCitation")
        if medline is None:
            continue

        pmid_elem = medline.find("PMID")
        pmid = pmid_elem.text if pmid_elem is not None else ""

        article_data = medline.find("Article")
        if article_data is None:
            continue

        # 标题
        title_elem = article_data.find("ArticleTitle")
        title = "".join(title_elem.itertext()) if title_elem is not None else ""

        # 摘要（支持结构化摘要，如 BACKGROUND/METHODS/RESULTS/CONCLUSIONS）
        abstract_parts = []
        abstract_elem = article_data.find("Abstract")
        if abstract_elem is not None:
            for ab in abstract_elem.findall("AbstractText"):
                label = ab.get("Label")
                text = "".join(ab.itertext()).strip()
                if label:
                    abstract_parts.append(f"{label}: {text}")
                else:
                    abstract_parts.append(text)
        abstract = " ".join(abstract_parts)

        # 作者
        authors = []
        author_list = article_data.find("AuthorList")
        if author_list is not None:
            for author in author_list.findall("Author"):
                last = author.findtext("LastName", "")
                fore = author.findtext("ForeName", "")
                name = f"{fore} {last}".strip() if fore else last
                if name:
                    authors.append(name)

        # 期刊信息
        journal = article_data.find("Journal")
        journal_name = ""
        pub_date = ""
        volume = ""
        issue = ""
        if journal is not None:
            journal_name = journal.findtext("Title", "") or journal.findtext("ISOAbbreviation", "")
            ji = journal.find("JournalIssue")
            if ji is not None:
                volume = ji.findtext("Volume", "")
                issue = ji.findtext("Issue", "")
                pd = ji.find("PubDate")
                if pd is not None:
                    year = pd.findtext("Year", "")
                    month = pd.findtext("Month", "")
                    day = pd.findtext("Day", "")
                    pub_date = " ".join(filter(None, [year, month, day]))

        # 页码
        pages = article_data.findtext(".//MedlinePgn", "")

        # DOI 和 PMC ID（从 ArticleIdList 提取）
        doi = None
        pmc_id = None
        for id_elem in article.findall(".//ArticleId"):
            id_type = id_elem.get("IdType", "")
            if id_type == "doi":
                doi = id_elem.text
            elif id_type == "pmc" and id_elem.text:
                # 规范化：去掉 "PMC" 前缀，只保留数字
                pmc_id = id_elem.text.lstrip("PMCpmc").strip() or id_elem.text

        # MeSH 关键词
        keywords = [kw.text for kw in medline.findall(".//Keyword") if kw.text]

        # 文献类型
        pub_types = [pt.text for pt in article_data.findall(".//PublicationType") if pt.text]

        url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
        pmc_url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{pmc_id}/" if pmc_id else None

        items.append(make_item(
            title=title,
            url=url,
            snippet=abstract,
            authors=authors,
            pmid=pmid,
            pmc_id=f"PMC{pmc_id}" if pmc_id else None,
            pmc_url=pmc_url,
            journal=journal_name if journal_name else None,
            pub_date=pub_date if pub_date else None,
            volume=volume if volume else None,
            issue=issue if issue else None,
            pages=pages if pages else None,
            keywords=keywords if keywords else None,
            pub_types=pub_types if pub_types else None,
            doi=doi,
        ))

    return items


def main():
    parser = build_parser("搜索 PubMed 生物医学文献")
    parser.add_argument("--api-key", help="NCBI API Key（可选，限额从 3 req/s 提升至 10 req/s）")
    args = parser.parse_args()

    try:
        items = search(args.query, args.limit, getattr(args, "api_key", None))
        print_json(make_result(True, args.query, "pubmed", items))
    except Exception as e:
        print_json(make_result(False, args.query, "pubmed", [], str(e)))
        sys.exit(1)


if __name__ == "__main__":
    main()
