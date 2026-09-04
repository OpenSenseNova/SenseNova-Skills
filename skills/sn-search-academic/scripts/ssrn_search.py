#!/usr/bin/env python3
"""SSRN (Social Science Research Network) search via CrossRef API.

SSRN is behind Cloudflare, so direct API access is blocked.
But SSRN assigns DOIs to all papers (prefix 10.2139/ssrn.*), which are
indexed by CrossRef. This script searches CrossRef and filters for SSRN
papers.

IMPORTANT: SSRN working papers have NO published-date in CrossRef — they use
'created' or 'deposited' date. The --days filter uses 'from-deposit-date'.

Usage:
    python3 ssrn_search.py "open source governance" --limit 20
    python3 ssrn_search.py "institutional economics" --limit 10 --days 30
"""

import argparse, json, sys, urllib.request, urllib.parse

CROSSREF_BASE = "https://api.crossref.org/works"


def search(query: str, limit: int = 20, days: int | None = None) -> list[dict]:
    """Search SSRN papers via CrossRef, filtering for DOI prefix 10.2139/ssrn.*."""
    params = {
        "query": query,
        "rows": min(limit * 3, 100),  # SSRN results are sparse; fetch more
        "sort": "relevance",
        "order": "desc",
    }
    if days:
        from datetime import datetime, timedelta
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        params["filter"] = f"from-deposit-date:{cutoff}"  # SSRN uses deposit-date

    url = f"{CROSSREF_BASE}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "OpenSourceWay/1.0 (mailto:opensourceway@example.com)",
            "Accept": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}, indent=2))
        sys.exit(1)

    items = data.get("message", {}).get("items", [])
    ssrn_items = []

    for item in items:
        doi = (item.get("DOI") or "").strip()
        is_ssrn = doi.startswith("10.2139/ssrn")

        if not is_ssrn:
            urls = [l.get("URL", "") for l in item.get("link", [])]
            publisher = (item.get("publisher") or "").lower()
            is_ssrn = any("ssrn.com" in u.lower() for u in urls) or "ssrn" in publisher

        if not is_ssrn:
            continue

        # SSRN working papers use 'created' or 'deposited' (no published-* fields)
        date_parts = []
        for key in ("created", "deposited", "published-online", "published-print"):
            dp = item.get(key, {}).get("date-parts", [[]])
            if dp and dp[0] and dp[0][0]:
                date_parts = dp[0]
                break

        ssrn_items.append({
            "title": (item.get("title", [""]))[0],
            "doi": doi,
            "url": f"https://doi.org/{doi}" if doi else "",
            "authors": [f"{a.get('given','')} {a.get('family','')}".strip()
                        for a in item.get("author", [])
                        if a.get("given") or a.get("family")],
            "year": date_parts[0] if date_parts else None,
            "publication_date": "-".join(str(p) for p in date_parts) if date_parts else "",
            "publisher": item.get("publisher", ""),
            "container": (item.get("container-title", [""]))[0] if item.get("container-title") else "",
            "abstract": (item.get("abstract") or "")[:500],
        })

    ssrn_items.sort(key=lambda x: x["year"] or 0, reverse=True)
    return ssrn_items[:limit]


def main():
    parser = argparse.ArgumentParser(description="Search SSRN papers via CrossRef")
    parser.add_argument("query", help="Search query")
    parser.add_argument("--limit", type=int, default=20, help="Max results")
    parser.add_argument("--days", type=int, help="Only papers deposited in last N days")
    args = parser.parse_args()

    results = search(args.query, args.limit, args.days)
    print(json.dumps({
        "success": True,
        "query": args.query,
        "provider": "ssrn (via CrossRef)",
        "count": len(results),
        "items": results,
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
