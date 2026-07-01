#!/usr/bin/env python3
"""Finance search helpers for yfinance and mootdx.

Command handlers emit JSON after argument parsing. Dependencies are imported lazily by command.
"""

from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import io
import json
import math
import re
import sys
from pathlib import Path
from typing import Any, Callable


FREQUENCY_MAP = {
    "5m": 0,
    "15m": 1,
    "30m": 2,
    "1h": 3,
    "days": 4,
    "week": 5,
    "weekly": 5,
    "mon": 6,
    "month": 6,
    "monthly": 6,
    "1m": 8,
    "day": 9,
    "daily": 9,
    "3mon": 10,
    "quarter": 10,
    "year": 11,
    "yearly": 11,
}

MARKET_MAP = {
    "sz": 0,
    "sh": 1,
    "0": 0,
    "1": 1,
}

DEFAULT_PROFILE_FIELDS = [
    "symbol",
    "quoteType",
    "shortName",
    "longName",
    "exchange",
    "currency",
    "market",
    "sector",
    "industry",
    "country",
    "currentPrice",
    "regularMarketPrice",
    "previousClose",
    "marketCap",
    "trailingPE",
    "forwardPE",
    "dividendYield",
    "beta",
    "fiftyTwoWeekLow",
    "fiftyTwoWeekHigh",
    "website",
]


class CliError(RuntimeError):
    pass


def import_yfinance():
    try:
        import yfinance as yf  # type: ignore
    except ImportError as exc:
        skill_dir = Path(__file__).resolve().parents[1]
        requirements = skill_dir / "requirements.txt"
        raise CliError(
            "缺少依赖 yfinance。请安装到当前 Python 环境："
            f"python3 -m pip install -r {requirements}"
        ) from exc
    return yf


def import_mootdx():
    try:
        import mootdx  # type: ignore  # noqa: F401
    except ImportError as exc:
        skill_dir = Path(__file__).resolve().parents[1]
        requirements = skill_dir / "requirements.txt"
        raise CliError(
            "缺少依赖 mootdx。请安装到当前 Python 环境："
            f"python3 -m pip install -r {requirements}"
        ) from exc


def emit(payload: dict[str, Any]) -> None:
    print(json.dumps(normalize(payload), ensure_ascii=False, indent=2))


def emit_ok(source: str, command: str, data: Any, **meta: Any) -> None:
    payload = {"ok": True, "source": source, "command": command, "data": data}
    payload.update({k: v for k, v in meta.items() if v is not None})
    emit(payload)


def emit_error(message: str, command: str | None = None) -> None:
    payload: dict[str, Any] = {"ok": False, "error": message}
    if command:
        payload["command"] = command
    emit(payload)


def quiet_call(func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        return func(*args, **kwargs)


def normalize(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (dt.date, dt.datetime)):
        return value.isoformat()
    if hasattr(value, "item"):
        try:
            return normalize(value.item())
        except Exception:
            pass
    if hasattr(value, "to_pydatetime"):
        try:
            return value.to_pydatetime().isoformat()
        except Exception:
            pass
    if isinstance(value, dict):
        return {str(normalize(k)): normalize(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [normalize(v) for v in value]
    return str(value)


def frame_to_records(frame: Any, *, limit: int | None = None, reset_index: bool = True) -> list[dict[str, Any]]:
    if frame is None:
        return []
    if hasattr(frame, "empty") and frame.empty:
        return []

    df = frame
    if limit is not None and hasattr(df, "head"):
        df = df.head(limit)
    if reset_index and hasattr(df, "reset_index") and not index_name_conflicts_with_columns(df):
        df = df.reset_index()
    if hasattr(df, "columns"):
        df = df.copy()
        df.columns = [flatten_column(col) for col in df.columns]
    if hasattr(df, "to_json"):
        raw = df.to_json(orient="records", date_format="iso", force_ascii=False)
        return json.loads(raw)
    return normalize(df)


def index_name_conflicts_with_columns(df: Any) -> bool:
    columns = {str(column) for column in getattr(df, "columns", [])}
    names = getattr(getattr(df, "index", None), "names", None)
    if names is None:
        names = [getattr(getattr(df, "index", None), "name", None)]
    return any(name is not None and str(name) in columns for name in names)


def series_to_records(series: Any, *, limit: int | None = None) -> list[dict[str, Any]]:
    if series is None:
        return []
    obj = series
    if limit is not None and hasattr(obj, "head"):
        obj = obj.head(limit)
    if hasattr(obj, "reset_index"):
        return frame_to_records(obj.reset_index(), reset_index=False)
    return normalize(obj)


def flatten_column(column: Any) -> str:
    if isinstance(column, tuple):
        parts = [str(part) for part in column if str(part) not in ("", "None")]
        return "__".join(parts) if parts else "value"
    return str(column)


def parse_fields(value: str | None) -> list[str] | None:
    if not value:
        return None
    fields = [part.strip() for part in value.split(",") if part.strip()]
    return fields or None


def normalize_yahoo_symbol(symbol: str, *, enabled: bool = True) -> str:
    value = symbol.strip()
    if not enabled:
        return value
    upper = value.upper()
    if upper.endswith(".SH"):
        return f"{upper[:-3]}.SS"
    if upper.endswith(".SS") or upper.endswith(".SZ") or upper.endswith(".HK"):
        return upper
    if re.fullmatch(r"\d{6}", upper):
        if upper.startswith(("5", "6", "9")):
            return f"{upper}.SS"
        if upper.startswith(("0", "1", "2", "3")):
            return f"{upper}.SZ"
    if re.fullmatch(r"\d{4,5}", upper):
        return f"{int(upper):04d}.HK"
    return upper


def normalize_tdx_symbol(symbol: str) -> str:
    value = symbol.strip().upper()
    for suffix in (".SH", ".SS", ".SZ", ".BJ"):
        if value.endswith(suffix):
            return value[: -len(suffix)]
    return value


def parse_frequency(value: str) -> int:
    text = str(value).strip().lower()
    if text in FREQUENCY_MAP:
        return FREQUENCY_MAP[text]
    try:
        return int(text)
    except ValueError as exc:
        choices = ", ".join(sorted(FREQUENCY_MAP))
        raise CliError(f"未知 frequency: {value}。可用值：{choices}，或直接传数字。") from exc


def parse_market(value: str) -> int:
    text = str(value).strip().lower()
    if text in MARKET_MAP:
        return MARKET_MAP[text]
    raise CliError("market 只支持 sh/sz 或 1/0。")


def parse_threads(value: str) -> bool | int:
    text = str(value).strip().lower()
    if text in ("true", "yes", "y", "1"):
        return True
    if text in ("false", "no", "n", "0"):
        return False
    try:
        number = int(text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("--threads 只支持 true/false 或正整数。") from exc
    if number < 1:
        raise argparse.ArgumentTypeError("--threads 数字必须大于 0。")
    return number


def yahoo_quote_url(symbol: str, path: str = "") -> str:
    suffix = f"/{path.strip('/')}" if path else ""
    return f"https://finance.yahoo.com/quote/{symbol}{suffix}"


def pick_dict(data: dict[str, Any], fields: list[str] | None) -> dict[str, Any]:
    keys = fields or DEFAULT_PROFILE_FIELDS
    return {key: data.get(key) for key in keys if key in data}


def cmd_yf_search(args: argparse.Namespace) -> None:
    yf = import_yfinance()
    search_cls = getattr(yf, "Search", None)
    if search_cls is None:
        raise CliError("当前 yfinance 版本没有 Search 类，请升级 yfinance。")

    search = search_cls(
        args.query,
        max_results=args.limit,
        news_count=args.news_count,
        include_research=args.include_research,
        enable_fuzzy_query=args.fuzzy,
        timeout=args.timeout,
        raise_errors=False,
    )
    if hasattr(search, "search"):
        search.search()
    emit_ok(
        "Yahoo Finance / yfinance.Search",
        "yf-search",
        {
            "quotes": normalize(getattr(search, "quotes", [])),
            "news": normalize(getattr(search, "news", [])),
            "research": normalize(getattr(search, "research", [])),
            "nav": normalize(getattr(search, "nav", [])),
            "lists": normalize(getattr(search, "lists", [])),
        },
        query=args.query,
    )


def cmd_yf_lookup(args: argparse.Namespace) -> None:
    yf = import_yfinance()
    lookup_cls = getattr(yf, "Lookup", None)
    if lookup_cls is None:
        raise CliError("当前 yfinance 版本没有 Lookup 类，请升级 yfinance。")

    lookup = lookup_cls(args.query, timeout=args.timeout, raise_errors=False)
    method_name = {
        "all": "get_all",
        "stock": "get_stock",
        "etf": "get_etf",
        "index": "get_index",
        "fund": "get_mutualfund",
        "mutualfund": "get_mutualfund",
        "future": "get_future",
        "currency": "get_currency",
        "crypto": "get_cryptocurrency",
    }[args.type]
    data = getattr(lookup, method_name)(count=args.limit)
    emit_ok("Yahoo Finance / yfinance.Lookup", "yf-lookup", frame_to_records(data), query=args.query, type=args.type)


def cmd_yf_profile(args: argparse.Namespace) -> None:
    yf = import_yfinance()
    symbol = normalize_yahoo_symbol(args.symbol, enabled=not args.no_normalize)
    ticker = yf.Ticker(symbol)
    fields = parse_fields(args.fields)

    info = {}
    fast_info = {}
    if not args.fast_only:
        info = getattr(ticker, "info", {}) or {}
    if not args.info_only:
        try:
            fast_info_obj = getattr(ticker, "fast_info", {}) or {}
            fast_info = dict(fast_info_obj)
        except Exception:
            fast_info = {}

    data = {
        "symbol": symbol,
        "info": pick_dict(info, fields) if fields else pick_dict(info, None),
        "fast_info": pick_dict(fast_info, fields) if fields else fast_info,
    }
    emit_ok("Yahoo Finance / yfinance.Ticker", "yf-profile", data, symbol=symbol, url=yahoo_quote_url(symbol))


def cmd_yf_history(args: argparse.Namespace) -> None:
    yf = import_yfinance()
    symbol = normalize_yahoo_symbol(args.symbol, enabled=not args.no_normalize)
    ticker = yf.Ticker(symbol)
    kwargs = {
        "period": args.period,
        "interval": args.interval,
        "start": args.start,
        "end": args.end,
        "actions": args.actions,
        "auto_adjust": args.auto_adjust,
        "prepost": args.prepost,
        "timeout": args.timeout,
    }
    kwargs = {k: v for k, v in kwargs.items() if v is not None}
    data = ticker.history(**kwargs)
    emit_ok(
        "Yahoo Finance / yfinance.Ticker.history",
        "yf-history",
        frame_to_records(data, limit=args.limit),
        symbol=symbol,
        url=yahoo_quote_url(symbol, "history"),
    )


def cmd_yf_download(args: argparse.Namespace) -> None:
    yf = import_yfinance()
    symbols = [normalize_yahoo_symbol(item, enabled=not args.no_normalize) for item in args.symbols]
    kwargs = {
        "period": args.period,
        "interval": args.interval,
        "start": args.start,
        "end": args.end,
        "actions": args.actions,
        "auto_adjust": args.auto_adjust,
        "prepost": args.prepost,
        "threads": args.threads,
        "group_by": args.group_by,
        "timeout": args.timeout,
        "progress": False,
    }
    kwargs = {k: v for k, v in kwargs.items() if v is not None}
    data = yf.download(symbols, **kwargs)
    emit_ok("Yahoo Finance / yfinance.download", "yf-download", frame_to_records(data, limit=args.limit), symbols=symbols)


def cmd_yf_financials(args: argparse.Namespace) -> None:
    yf = import_yfinance()
    symbol = normalize_yahoo_symbol(args.symbol, enabled=not args.no_normalize)
    ticker = yf.Ticker(symbol)
    methods: dict[str, Callable[..., Any]] = {
        "income": ticker.get_income_stmt,
        "balance": ticker.get_balance_sheet,
        "cashflow": ticker.get_cashflow,
        "earnings": ticker.get_earnings,
    }
    kwargs = {"freq": args.freq, "pretty": args.pretty}
    if args.statement == "earnings":
        kwargs = {"freq": args.freq}
    data = methods[args.statement](**kwargs)
    emit_ok(
        "Yahoo Finance / yfinance.Ticker financials",
        "yf-financials",
        frame_to_records(data, limit=args.limit),
        symbol=symbol,
        statement=args.statement,
        url=yahoo_quote_url(symbol, "financials"),
    )


def cmd_yf_news(args: argparse.Namespace) -> None:
    yf = import_yfinance()
    symbol = normalize_yahoo_symbol(args.symbol, enabled=not args.no_normalize)
    ticker = yf.Ticker(symbol)
    data = ticker.get_news(count=args.limit, tab=args.tab)
    emit_ok(
        "Yahoo Finance / yfinance.Ticker.get_news",
        "yf-news",
        normalize(data),
        symbol=symbol,
        tab=args.tab,
        url=yahoo_quote_url(symbol, "news"),
    )


def cmd_yf_sec_filings(args: argparse.Namespace) -> None:
    yf = import_yfinance()
    symbol = normalize_yahoo_symbol(args.symbol, enabled=not args.no_normalize)
    ticker = yf.Ticker(symbol)
    data = ticker.get_sec_filings()
    emit_ok(
        "Yahoo Finance / yfinance.Ticker.get_sec_filings",
        "yf-sec-filings",
        normalize(data),
        symbol=symbol,
        url=yahoo_quote_url(symbol, "sec-filings"),
    )


def tdx_client(args: argparse.Namespace):
    import_mootdx()
    from mootdx.quotes import Quotes  # type: ignore

    return quiet_call(
        Quotes.factory,
        market="std",
        multithread=args.multithread,
        heartbeat=args.heartbeat,
        bestip=args.bestip,
        timeout=args.timeout,
    )


def cmd_tdx_quotes(args: argparse.Namespace) -> None:
    client = tdx_client(args)
    symbols = [normalize_tdx_symbol(symbol) for symbol in args.symbols]
    data = quiet_call(client.quotes, symbol=symbols)
    emit_ok("通达信 / mootdx.quotes", "tdx-quotes", frame_to_records(data), symbols=symbols)


def cmd_tdx_bars(args: argparse.Namespace) -> None:
    client = tdx_client(args)
    symbol = normalize_tdx_symbol(args.symbol)
    kwargs = {
        "symbol": symbol,
        "frequency": parse_frequency(args.frequency),
        "start": args.start,
        "offset": args.offset,
        "adjust": args.adjust,
    }
    kwargs = {k: v for k, v in kwargs.items() if v not in (None, "")}
    data = quiet_call(client.bars, **kwargs)
    emit_ok("通达信 / mootdx.bars", "tdx-bars", frame_to_records(data), symbol=symbol, frequency=args.frequency)


def cmd_tdx_index(args: argparse.Namespace) -> None:
    client = tdx_client(args)
    symbol = normalize_tdx_symbol(args.symbol)
    data = quiet_call(
        client.index,
        symbol=symbol,
        market=parse_market(args.market),
        frequency=parse_frequency(args.frequency),
        start=args.start,
        offset=args.offset,
    )
    emit_ok("通达信 / mootdx.index", "tdx-index", frame_to_records(data), symbol=symbol, market=args.market)


def cmd_tdx_stocks(args: argparse.Namespace) -> None:
    client = tdx_client(args)
    data = quiet_call(client.stocks, market=parse_market(args.market))
    emit_ok("通达信 / mootdx.stocks", "tdx-stocks", frame_to_records(data, limit=args.limit), market=args.market)


def cmd_tdx_finance(args: argparse.Namespace) -> None:
    client = tdx_client(args)
    symbol = normalize_tdx_symbol(args.symbol)
    data = quiet_call(client.finance, symbol=symbol)
    emit_ok("通达信 / mootdx.finance", "tdx-finance", frame_to_records(data, limit=args.limit), symbol=symbol)


def cmd_tdx_xdxr(args: argparse.Namespace) -> None:
    client = tdx_client(args)
    symbol = normalize_tdx_symbol(args.symbol)
    data = quiet_call(client.xdxr, symbol=symbol)
    emit_ok("通达信 / mootdx.xdxr", "tdx-xdxr", frame_to_records(data, limit=args.limit), symbol=symbol)


def cmd_tdx_affair_files(args: argparse.Namespace) -> None:
    import_mootdx()
    from mootdx.affair import Affair  # type: ignore

    data = quiet_call(Affair.files)
    files = data[: args.limit] if args.limit is not None else data
    emit_ok("通达信 / mootdx.affair.files", "tdx-affair-files", normalize(files))


def cmd_tdx_affair_fetch(args: argparse.Namespace) -> None:
    import_mootdx()
    from mootdx.affair import Affair  # type: ignore

    result = quiet_call(Affair.fetch, downdir=args.downdir, filename=args.filename)
    emit_ok("通达信 / mootdx.affair.fetch", "tdx-affair-fetch", normalize(result), downdir=args.downdir, filename=args.filename)


def cmd_tdx_affair_parse(args: argparse.Namespace) -> None:
    import_mootdx()
    from mootdx.affair import Affair  # type: ignore

    data = quiet_call(Affair.parse, downdir=args.downdir, filename=args.filename)
    emit_ok("通达信 / mootdx.affair.parse", "tdx-affair-parse", frame_to_records(data, limit=args.limit), filename=args.filename)


def add_common_yf_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--no-normalize", action="store_true", help="不自动转换 A股/H股代码后缀。")


def add_common_history_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--period", default="1mo", help="1d,5d,1mo,3mo,6mo,1y,2y,5y,10y,ytd,max。")
    parser.add_argument("--interval", default="1d", help="1m,2m,5m,15m,30m,60m,90m,1h,1d,5d,1wk,1mo,3mo。")
    parser.add_argument("--start", help="YYYY-MM-DD。设置后可替代 period。")
    parser.add_argument("--end", help="YYYY-MM-DD，结束日不包含。")
    parser.add_argument("--actions", action="store_true", help="包含股息和拆股。")
    parser.add_argument("--auto-adjust", action=argparse.BooleanOptionalAction, default=None)
    parser.add_argument("--prepost", action="store_true", help="包含盘前盘后。")
    parser.add_argument("--limit", type=int, default=120)


def add_common_tdx_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--timeout", type=int, default=15)
    parser.add_argument("--bestip", action="store_true", help="重新测试最快服务器。")
    parser.add_argument("--multithread", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--heartbeat", action=argparse.BooleanOptionalAction, default=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Finance search helper using yfinance and mootdx.")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("yf-search", help="Yahoo Finance 搜索：代码、公司、新闻、研究。")
    p.add_argument("query")
    p.add_argument("--limit", type=int, default=8)
    p.add_argument("--news-count", type=int, default=8)
    p.add_argument("--include-research", action="store_true")
    p.add_argument("--fuzzy", action="store_true")
    p.add_argument("--timeout", type=int, default=30)
    p.set_defaults(func=cmd_yf_search)

    p = sub.add_parser("yf-lookup", help="Yahoo Finance 金融工具查找。")
    p.add_argument("query")
    p.add_argument("--type", choices=["all", "stock", "etf", "index", "fund", "mutualfund", "future", "currency", "crypto"], default="all")
    p.add_argument("--limit", type=int, default=25)
    p.add_argument("--timeout", type=int, default=30)
    p.set_defaults(func=cmd_yf_lookup)

    p = sub.add_parser("yf-profile", help="查询 ticker 基本信息和 fast_info。")
    p.add_argument("symbol")
    p.add_argument("--fields", help="逗号分隔字段；默认返回常用画像字段。")
    p.add_argument("--fast-only", action="store_true")
    p.add_argument("--info-only", action="store_true")
    add_common_yf_args(p)
    p.set_defaults(func=cmd_yf_profile)

    p = sub.add_parser("yf-history", help="查询单个 ticker 历史行情。")
    p.add_argument("symbol")
    add_common_history_args(p)
    add_common_yf_args(p)
    p.set_defaults(func=cmd_yf_history)

    p = sub.add_parser("yf-download", help="批量下载多个 ticker 历史行情。")
    p.add_argument("symbols", nargs="+")
    p.add_argument("--threads", type=parse_threads, default=True)
    p.add_argument("--group-by", choices=["column", "ticker"], default="column")
    add_common_history_args(p)
    add_common_yf_args(p)
    p.set_defaults(func=cmd_yf_download)

    p = sub.add_parser("yf-financials", help="查询财务报表。")
    p.add_argument("symbol")
    p.add_argument("--statement", choices=["income", "balance", "cashflow", "earnings"], default="income")
    p.add_argument("--freq", choices=["yearly", "quarterly", "trailing"], default="yearly")
    p.add_argument("--pretty", action="store_true")
    p.add_argument("--limit", type=int, default=120)
    add_common_yf_args(p)
    p.set_defaults(func=cmd_yf_financials)

    p = sub.add_parser("yf-news", help="查询 ticker 新闻。")
    p.add_argument("symbol")
    p.add_argument("--limit", type=int, default=10)
    p.add_argument("--tab", choices=["news", "all", "press releases"], default="news")
    add_common_yf_args(p)
    p.set_defaults(func=cmd_yf_news)

    p = sub.add_parser("yf-sec-filings", help="查询 SEC filings。")
    p.add_argument("symbol")
    add_common_yf_args(p)
    p.set_defaults(func=cmd_yf_sec_filings)

    p = sub.add_parser("tdx-quotes", help="通达信实时行情。")
    p.add_argument("symbols", nargs="+")
    add_common_tdx_args(p)
    p.set_defaults(func=cmd_tdx_quotes)

    p = sub.add_parser("tdx-bars", help="通达信 K 线。")
    p.add_argument("symbol")
    p.add_argument("--frequency", default="day")
    p.add_argument("--start", type=int, default=0)
    p.add_argument("--offset", type=int, default=100)
    p.add_argument("--adjust", choices=["qfq", "hfq", "before", "after", ""], default="")
    add_common_tdx_args(p)
    p.set_defaults(func=cmd_tdx_bars)

    p = sub.add_parser("tdx-index", help="通达信指数 K 线。")
    p.add_argument("symbol")
    p.add_argument("--market", choices=["sh", "sz", "1", "0"], default="sh")
    p.add_argument("--frequency", default="day")
    p.add_argument("--start", type=int, default=0)
    p.add_argument("--offset", type=int, default=100)
    add_common_tdx_args(p)
    p.set_defaults(func=cmd_tdx_index)

    p = sub.add_parser("tdx-stocks", help="通达信股票列表。")
    p.add_argument("--market", choices=["sh", "sz", "1", "0"], default="sh")
    p.add_argument("--limit", type=int, default=200)
    add_common_tdx_args(p)
    p.set_defaults(func=cmd_tdx_stocks)

    p = sub.add_parser("tdx-finance", help="通达信财务信息。")
    p.add_argument("symbol")
    p.add_argument("--limit", type=int, default=200)
    add_common_tdx_args(p)
    p.set_defaults(func=cmd_tdx_finance)

    p = sub.add_parser("tdx-xdxr", help="通达信除权除息信息。")
    p.add_argument("symbol")
    p.add_argument("--limit", type=int, default=200)
    add_common_tdx_args(p)
    p.set_defaults(func=cmd_tdx_xdxr)

    p = sub.add_parser("tdx-affair-files", help="通达信历史专业财务数据文件列表。")
    p.add_argument("--limit", type=int, default=20)
    p.set_defaults(func=cmd_tdx_affair_files)

    p = sub.add_parser("tdx-affair-fetch", help="下载通达信专业财务数据文件。")
    p.add_argument("filename")
    p.add_argument("--downdir", default="tmp")
    p.set_defaults(func=cmd_tdx_affair_fetch)

    p = sub.add_parser("tdx-affair-parse", help="解析本地通达信专业财务数据文件。")
    p.add_argument("filename")
    p.add_argument("--downdir", default="tmp")
    p.add_argument("--limit", type=int, default=200)
    p.set_defaults(func=cmd_tdx_affair_parse)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    try:
        args.func(args)
    except BrokenPipeError:
        raise
    except Exception as exc:
        emit_error(str(exc), command=getattr(args, "command", None))
        sys.exit(1)


if __name__ == "__main__":
    main()
