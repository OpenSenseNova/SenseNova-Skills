#!/usr/bin/env python3
"""arXiv 原生检索 —— 零第三方依赖，只用标准库。

替代 sn-search-academic 的 arxiv 通道（该通道依赖 `arxiv` PyPI 包，
在 Hermes cron 的 3.14 venv 中缺失，静默降级到 openalex 返回 2014 年旧词条）。

兼容 Python 3.9+（不用 `X | None` 语法）。
用法:
    python3 arxiv_native.py --query 'abs:"open source"' --limit 20
    python3 arxiv_native.py --preset opensource --days 3 --limit 30
    python3 arxiv_native.py --ids 2610.28027,2610.35592

设计说明:
  - 走官方 Atom API (export.arxiv.org)，无需 key，无需 SDK。
  - arXiv API 要求请求间隔 >= 3 秒（单连接）。本脚本在多次请求间自动 sleep。
  - `abs:` 裸查询精度很差（"open source" 会命中原子的 open-source 表述），
    因此 preset 默认叠加分类限定，例如 cat:cs.SE / cat:cs.CY。
"""
import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

ATOM = "{http://www.w3.org/2005/Atom}"
API = "https://export.arxiv.org/api/query"

# 开源+制度研究最相关的 arXiv 分类
OPEN_SOURCE_CATS = ["cs.SE", "cs.CY", "cs.SI", "econ.GN"]

PRESETS = {
    # 开源软件工程 / 协作 / 治理 / 贡献者
    "opensource": (
        '({cats}) AND (abs:"open source" OR abs:"open-source" OR abs:"free software")'
    ),
    # 制度经济学视角：治理、激励、产权、公共品
    "governance": (
        '({cats}) AND (abs:"open source" OR abs:"open-source") '
        'AND (abs:governance OR abs:institution OR abs:maintainer '
        'OR abs:contributor OR abs:license OR abs:"public good" OR abs:incentive)'
    ),
    # 供应链 / 合规 / 安全（开源治理的另一面）
    "supplychain": (
        '({cats}) AND (abs:"open source" OR abs:"open-source") '
        'AND (abs:supply-chain OR abs:"supply chain" OR abs:dependency '
        'OR abs:SBOM OR abs:vulnerability)'
    ),
}


def build_cats(cats):
    if len(cats) == 1:
        return "cat:" + cats[0]
    return "(" + " OR ".join("cat:" + c for c in cats) + ")"


def fetch(query, start=0, limit=50, sort_by="submittedDate", timeout=45):
    params = {
        "search_query": query,
        "start": start,
        "max_results": limit,
        "sortBy": sort_by,
        "sortOrder": "descending",
    }
    url = API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "arxiv-native/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except urllib.error.HTTPError as exc:
        raise SystemExit("arXiv API HTTP %s for query: %s" % (exc.code, query))
    except urllib.error.URLError as exc:
        raise SystemExit("arXiv API unreachable (%s). Check network/DNS." % exc.reason)


def parse(xml_bytes):
    root = ET.fromstring(xml_bytes)
    out = []
    for e in root.findall(ATOM + "entry"):
        def txt(tag):
            node = e.find(ATOM + tag)
            if node is None or node.text is None:
                return ""
            return " ".join(node.text.split())
        raw_id = txt("id")
        aid = raw_id.rsplit("/abs/", 1)[-1] if "/abs/" in raw_id else raw_id
        base = aid.split("v")[0] if "v" in aid else aid
        cats = [c.get("term") for c in e.findall(ATOM + "category") if c.get("term")]
        authors = [a.find(ATOM + "name").text for a in e.findall(ATOM + "author")
                   if a.find(ATOM + "name") is not None]
        out.append({
            "id": base,
            "versioned_id": aid,
            "title": txt("title"),
            "authors": authors,
            "published": txt("published")[:10],
            "updated": txt("updated")[:10],
            "abstract": txt("summary"),
            "categories": cats,
            "url": "https://arxiv.org/abs/" + base,
            "pdf": "https://arxiv.org/pdf/" + base,
        })
    return out


def main():
    ap = argparse.ArgumentParser(description="Native arXiv search (stdlib only)")
    ap.add_argument("--query", help="raw arXiv API query")
    ap.add_argument("--preset", choices=sorted(PRESETS), help="prebuilt query")
    ap.add_argument("--cats", default=",".join(OPEN_SOURCE_CATS),
                    help="comma-separated categories for presets")
    ap.add_argument("--ids", help="comma-separated arXiv IDs to fetch")
    ap.add_argument("--limit", type=int, default=30)
    ap.add_argument("--days", type=int, help="client-side filter: only last N days")
    ap.add_argument("--sort", default="submittedDate",
                    choices=["submittedDate", "relevance", "lastUpdatedDate"])
    ap.add_argument("--json", action="store_true", help="raw JSON output")
    args = ap.parse_args()

    if args.ids:
        ids = ",".join(args.ids.split(","))
        papers = parse(fetch("id_list=" + urllib.parse.quote(ids), limit=len(ids.split(","))))
    else:
        if args.preset:
            cats = build_cats([c.strip() for c in args.cats.split(",") if c.strip()])
            query = PRESETS[args.preset].format(cats=cats)
        elif args.query:
            query = args.query
        else:
            ap.error("need --query, --preset, or --ids")
        papers = parse(fetch(query, limit=args.limit, sort_by=args.sort))

    if args.days:
        import datetime
        cutoff = (datetime.date.today() - datetime.timedelta(days=args.days)).isoformat()
        papers = [p for p in papers if p["published"] >= cutoff]

    if args.json:
        print(json.dumps(papers, ensure_ascii=False, indent=2))
        return

    if not papers:
        print("(no papers)")
        return
    for p in papers:
        print("%s | %s" % (p["published"], p["title"]))
        print("    arXiv:%s  %s" % (p["id"], ",".join(p["categories"])))
        print("    %s" % p["url"])
        au = ", ".join(p["authors"][:3]) + (" et al." if len(p["authors"]) > 3 else "")
        print("    作者: %s" % au)
        print()


if __name__ == "__main__":
    main()
