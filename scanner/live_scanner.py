"""
Live scanner – fetches real-time quotes for all Nifty 200 stocks.
Returns a DataFrame with all columns required by the Live Scanner page.
"""
import asyncio
import time
from typing import Optional
import pandas as pd
from loguru import logger

from services.instruments import get_nifty200_symbols
from services.market_data import get_quotes, parse_quote, get_historical_df

_live_cache: Optional[tuple[float, pd.DataFrame]] = None
_avg_vol_cache: dict[str, float] = {}
_LIVE_TTL = 3


async def _get_avg_volumes(symbols_df: pd.DataFrame) -> dict[str, float]:
    """Fetch 20-day average volumes (cached per session)."""
    global _avg_vol_cache
    missing = [row["instrument_key"] for _, row in symbols_df.iterrows()
               if row["instrument_key"] not in _avg_vol_cache]

    if missing:
        semaphore = asyncio.Semaphore(15)

        async def fetch_avg(key: str):
            async with semaphore:
                df = await get_historical_df(key, interval="day", days=30)
                if not df.empty and len(df) >= 5:
                    _avg_vol_cache[key] = df["volume"].tail(20).mean()

        await asyncio.gather(*[fetch_avg(k) for k in missing[:50]])  # limit initial load

    return _avg_vol_cache


async def get_live_scanner_data(force: bool = False) -> pd.DataFrame:
    global _live_cache
    now = time.time()
    if not force and _live_cache and (now - _live_cache[0]) < _LIVE_TTL:
        return _live_cache[1]

    symbols_df = await get_nifty200_symbols()
    if symbols_df.empty:
        return pd.DataFrame()

    instrument_keys = symbols_df["instrument_key"].tolist()
    avg_vols = await _get_avg_volumes(symbols_df)

    # Fetch quotes in batches
    raw_quotes = await get_quotes(instrument_keys)

    records = []
    for _, row in symbols_df.iterrows():
        key = row["instrument_key"]
        raw = raw_quotes.get(key, {})
        q = parse_quote(raw)
        if not q:
            continue

        ltp = q.get("ltp", 0)
        prev_close = q.get("prev_close", 0) or q.get("close", 0)
        pct_change = (ltp - prev_close) / prev_close * 100 if prev_close else 0
        volume = q.get("volume", 0)
        avg_vol = avg_vols.get(key, 0)
        rel_vol = round(volume / avg_vol, 2) if avg_vol else 0
        tbq = q.get("tbq", 0)
        tsq = q.get("tsq", 0)
        tbq_tsq = round(tbq / tsq, 2) if tsq else 0
        bid = q.get("bid", 0)
        ask = q.get("ask", 0)
        spread = round(ask - bid, 2) if ask and bid else 0

        records.append({
            "company_name": row.get("company_name", ""),
            "symbol": row.get("symbol", ""),
            "instrument_key": key,
            "sector": row.get("sector", ""),
            "industry": row.get("industry", ""),
            "cmp": round(ltp, 2),
            "pct_change": round(pct_change, 2),
            "open": q.get("open", 0),
            "high": q.get("high", 0),
            "low": q.get("low", 0),
            "prev_close": round(prev_close, 2),
            "vwap": q.get("avg_price", 0),
            "volume": volume,
            "avg_volume": round(avg_vol, 0),
            "rel_volume": rel_vol,
            "tbq": tbq,
            "tsq": tsq,
            "tbq_tsq": tbq_tsq,
            "bid": bid,
            "ask": ask,
            "spread": spread,
            "atp": q.get("avg_price", 0),
            "upper_circuit": q.get("upper_circuit", 0),
            "lower_circuit": q.get("lower_circuit", 0),
        })

    df = pd.DataFrame(records)
    _live_cache = (now, df)
    return df
