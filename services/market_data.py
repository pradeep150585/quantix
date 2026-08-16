"""
Market data service – wraps UpstoxClient with in-memory caching and batch fetching.
"""
import time
import pandas as pd
from loguru import logger
from api.upstox_client import get_client

_hist_cache: dict[str, tuple[float, pd.DataFrame]] = {}
_HIST_TTL = 3600  # 1 hour — EOD candles don't change intraday


def _normalise_keys(raw: dict) -> dict:
    """
    Store every possible key variant so lookups always hit.
    Upstox returns keys as 'NSE_EQ:SYMBOL'; instrument_token is also symbol-based.
    We index by original, colon↔pipe swaps, and instrument_token variants.
    """
    result = {}
    for k, v in raw.items():
        for variant in [k, k.replace(":", "|"), k.replace("|", ":")]:
            result[variant] = v
        token = v.get("instrument_token", "")
        if token:
            for variant in [token, token.replace(":", "|"), token.replace("|", ":")]:
                result[variant] = v
    return result


async def get_quotes(instrument_keys: list[str]) -> dict:
    client = get_client()
    result = await client.get_market_quotes(instrument_keys)
    return _normalise_keys(result) if result else {}


async def get_ltp(instrument_keys: list[str]) -> dict:
    client = get_client()
    result = await client.get_ltp(instrument_keys)
    return _normalise_keys(result) if result else {}


async def get_ohlc(instrument_keys: list[str]) -> dict:
    client = get_client()
    result = await client.get_ohlc(instrument_keys)
    return _normalise_keys(result) if result else {}


async def get_historical_df(
    instrument_key: str,
    interval: str = "day",
    days: int = 365,
) -> pd.DataFrame:
    from datetime import date, timedelta
    from database import get_cached_candles, get_latest_cached_date, save_candles

    today = date.today()
    today_str = today.strftime("%Y-%m-%d")
    from_date = (today - timedelta(days=days)).strftime("%Y-%m-%d")

    # Check in-memory cache first (avoids DB hit on repeated calls within same run)
    cache_key = f"{instrument_key}:{interval}:{days}"
    now = time.time()
    if cache_key in _hist_cache and (now - _hist_cache[cache_key][0]) < _HIST_TTL:
        return _hist_cache[cache_key][1]

    # Check SQLite — if today's data already exists, return from DB
    latest = get_latest_cached_date(instrument_key, interval)
    if latest >= today_str:
        df = get_cached_candles(instrument_key, interval, from_date)
        if not df.empty and len(df) >= 50:
            _hist_cache[cache_key] = (now, df)
            return df

    # Fetch from API — only missing days if we have some cached data
    if latest and latest >= from_date:
        # We have historical data; only fetch from day after latest
        fetch_from = (date.fromisoformat(latest) + timedelta(days=1)).strftime("%Y-%m-%d")
    else:
        fetch_from = from_date

    client = get_client()
    result = await client.get_historical_candles(instrument_key, interval, fetch_from, today_str)
    if result and result.get("status") == "success":
        candles = result.get("data", {}).get("candles", [])
        if candles:
            new_df = pd.DataFrame(candles, columns=["datetime", "open", "high", "low", "close", "volume", "oi"])
            new_df["datetime"] = pd.to_datetime(new_df["datetime"])
            new_df = new_df.sort_values("datetime").reset_index(drop=True)
            for col in ["open", "high", "low", "close", "volume"]:
                new_df[col] = pd.to_numeric(new_df[col], errors="coerce")
            save_candles(instrument_key, interval, new_df)

    # Return full range from SQLite (now includes newly saved rows)
    df = get_cached_candles(instrument_key, interval, from_date)
    if df.empty:
        return pd.DataFrame()

    _hist_cache[cache_key] = (now, df)
    return df


async def bulk_prefetch_today_ohlc(instrument_keys: list[str]) -> int:
    """
    Fetch today's OHLC for all instruments in one API call and upsert into candle_cache.
    Returns number of candles saved.
    """
    from datetime import date
    from database import save_candles

    today_str = date.today().strftime("%Y-%m-%d")
    client = get_client()
    raw = await client.get_ohlc(instrument_keys)
    if not raw:
        return 0

    saved = 0
    for key, data in raw.items():
        try:
            ohlc = data.get("ohlc", {})
            o = ohlc.get("open", 0)
            h = ohlc.get("high", 0)
            l = ohlc.get("low", 0)
            c = ohlc.get("close", 0) or data.get("last_price", 0)
            v = data.get("volume", 0)
            if not c:
                continue
            # Normalise key to storage format (pipe-separated)
            norm_key = key.replace(":", "|")
            row_df = pd.DataFrame([{
                "datetime": pd.Timestamp(today_str),
                "open": float(o), "high": float(h),
                "low": float(l), "close": float(c), "volume": float(v)
            }])
            save_candles(norm_key, "day", row_df)
            saved += 1
        except Exception:
            pass
    return saved


async def get_intraday_df(instrument_key: str, interval: str = "30minute") -> pd.DataFrame:
    client = get_client()
    result = await client.get_intraday_candles(instrument_key, interval)
    if not result or result.get("status") != "success":
        return pd.DataFrame()
    candles = result.get("data", {}).get("candles", [])
    if not candles:
        return pd.DataFrame()
    df = pd.DataFrame(candles, columns=["datetime", "open", "high", "low", "close", "volume", "oi"])
    df["datetime"] = pd.to_datetime(df["datetime"])
    df = df.sort_values("datetime").reset_index(drop=True)
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def parse_quote(raw: dict) -> dict:
    if not raw:
        return {}
    d = raw.get("depth", {})
    buy_orders = d.get("buy", [])
    sell_orders = d.get("sell", [])
    ohlc = raw.get("ohlc", {})
    ltp = raw.get("last_price", 0)
    net_change = raw.get("net_change", 0)
    prev_close = round(ltp - net_change, 2) if net_change else (ohlc.get("close") or raw.get("close_price", 0))
    return {
        "ltp": ltp,
        "open": ohlc.get("open", 0),
        "high": ohlc.get("high", 0),
        "low": ohlc.get("low", 0),
        "close": ohlc.get("close", 0),
        "prev_close": prev_close,
        "volume": raw.get("volume", 0),
        "avg_price": raw.get("average_price", 0),
        "bid": buy_orders[0].get("price", 0) if buy_orders else 0,
        "ask": sell_orders[0].get("price", 0) if sell_orders else 0,
        "tbq": raw.get("total_buy_quantity") or sum(o.get("quantity", 0) for o in buy_orders),
        "tsq": raw.get("total_sell_quantity") or sum(o.get("quantity", 0) for o in sell_orders),
        "upper_circuit": raw.get("upper_circuit_limit", 0),
        "lower_circuit": raw.get("lower_circuit_limit", 0),
        "net_change": net_change,
        "pct_change": (ltp - prev_close) / prev_close * 100 if prev_close else 0,
    }
