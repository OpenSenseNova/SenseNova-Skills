"""Shared filters for the sn-search-social-media skill."""

from __future__ import annotations

import re
from typing import Iterable


CRYPTO_TERMS = (
    "bitcoin",
    "btc",
    "ethereum",
    "eth",
    "crypto",
    "cryptocurrency",
    "blockchain",
    "web3",
    "defi",
    "nft",
    "airdrop",
    "crypto wallet",
    "crypto mining",
    "stablecoin",
    "binance",
    "coinbase",
    "solana",
    "dogecoin",
    "加密货币",
    "虚拟货币",
    "数字货币",
    "比特币",
    "以太坊",
    "区块链",
    "币安",
    "链上",
)

_CRYPTO_RE = re.compile(r"(?i)(?<![a-z0-9])(" + "|".join(re.escape(t) for t in CRYPTO_TERMS) + r")(?![a-z0-9])")
_CJK_CRYPTO_TERMS = tuple(t for t in CRYPTO_TERMS if any("\u4e00" <= ch <= "\u9fff" for ch in t))


class CryptoQueryError(ValueError):
    """Raised when a query asks for cryptocurrency-related material."""


def contains_crypto(text: str | None) -> bool:
    if not text:
        return False
    if _CRYPTO_RE.search(text):
        return True
    return any(term in text for term in _CJK_CRYPTO_TERMS)


def reject_crypto_query(query: str | None) -> None:
    if contains_crypto(query):
        raise CryptoQueryError("该技能不处理加密货币/区块链/Web3 相关查询")


def filter_crypto_items(items: Iterable[dict], fields: tuple[str, ...] = ("title", "snippet", "url")) -> list[dict]:
    filtered = []
    for item in items:
        haystack = " ".join(str(item.get(field, "")) for field in fields)
        if not contains_crypto(haystack):
            filtered.append(item)
    return filtered
