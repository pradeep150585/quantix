"""
Scanner engine - fetches historical data, computes indicators, scores strategies.
Scan results are cached in SQLite by date - only re-scans if today's result is missing.
"""
import asyncio
import json
import time
from datetime import date
from typing import Optional
import pandas as pd
from loguru import logger

from services.instruments import get_nifty200_symbols
from services.market_data import get_historical_df, get_quotes, parse_quote
from indicators import compute_all
from strategies import score_all, best_strategy, score_color, score_label, get_badges

_scan_cache: Optional[tuple[float, pd.DataFrame]] = None
_SCAN_TTL = 3600
_HIST_DAYS = 260

_SCAN_COLS = [
    "symbol", "company_name", "sector", "industry", "instrument_key",
    "cmp", "pct_change", "best_strategy", "best_score",
    "minervini_score", "qullamaggie_score", "zanger_score",
    "score_color", "score_label", "badges",
    "rsi", "macd", "macd_hist", "ema20", "ema50", "sma150", "sma200",
    "volume_ratio", "relative_strength", "dist_52h_pct", "dist_52l_pct",
    "high_52w", "low_52w", "atr", "adx", "supertrend_dir",
    "stop_loss", "risk_reward", "pivot", "last_updated",
]


def _load_scan_from_db(today: str) -> Optional[pd.DataFrame]:
    """Load today's scan result from SQLite if it exists."""
    try:
        from database import get_conn
        with get_conn() as conn:
            row = conn.execute(
                "SELECT scan_data FROM scan_results_cache WHERE scan_date=?",
                (today,)
            ).fetchone()
        if row and row[0]:
            records = json.loads(row[0])
            df = pd.DataFrame(records)
            for col in ["badges"]:
                if col in df.columns:
                    df[col] = df[col].apply(lambda x: x if isinstance(x, list) else json.loads(x) if x else [])
            return df
    except Exception as e:
        logger.warning(f"Could not load scan from DB: {e}")
    return None


def _save_scan_to_db(today: str, df: pd.DataFrame):
    """Save today's scan result to SQLite."""
    try:
        from database import get_conn
        records = df.copy()
        records["badges"] = records["badges"].apply(
            lambda x: json.dumps(x) if isinstance(x, list) else (x or "[]")
        )
        data = records.to_dict(orient="records")
        with get_conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO scan_results_cache (scan_date, scan_data) VALUES (?,?)",
                (today, json.dumps(data))
            )
    except Exception as e:
        logger.warning(f"Could not save scan to DB: {e}")


async def _process_stock(row: pd.Series, benchmark_df: pd.DataFrame, semaphore: asyncio.Semaphore) -> Optional[dict]:
    async with semaphore:
        symbol = row.get("symbol", "")
        isin = row.get("isin", "")
        instrument_key = row.get("instrument_key", f"NSE_EQ|{isin}")

        try:
            df = await get_historical_df(instrument_key, interval="day", days=_HIST_DAYS)
            if df.empty or len(df) < 50:
                return None

            indicators = compute_all(df, benchmark_df)
            if not indicators:
                return None

            scores = score_all(df, indicators)
            best_name, best_score = best_strategy(scores)
            badges = get_badges(indicators, scores)

            cmp = df["close"].iloc[-1]
            prev_close = df["close"].iloc[-2] if len(df) > 1 else cmp
            pct_change = (cmp - prev_close) / prev_close * 100 if prev_close else 0

            atr_val = indicators.get("atr", 0)
            stop_loss = round(cmp - 2 * atr_val, 2) if atr_val else round(cmp * 0.95, 2)
            risk = cmp - stop_loss
            reward = risk * 2
            rr = round(reward / risk, 2) if risk > 0 else 0

            return {
                "symbol": symbol,
                "company_name": row.get("company_name", symbol),
                "sector": row.get("sector", ""),
                "industry": row.get("industry", ""),
                "instrument_key": instrument_key,
                "cmp": round(cmp, 2),
                "pct_change": round(pct_change, 2),
                "best_strategy": best_name,
                "best_score": best_score,
                "minervini_score": scores.get("Minervini", (0,))[0],
                "qullamaggie_score": scores.get("Qullamaggie", (0,))[0],
                "zanger_score": scores.get("Zanger", (0,))[0],
                "score_color": score_color(best_score),
                "score_label": score_label(best_score),
                "badges": badges,
                "rsi": indicators.get("rsi", 0),
                "macd": indicators.get("macd", 0),
                "macd_hist": indicators.get("macd_hist", 0),
                "ema20": indicators.get("ema20", 0),
                "ema50": indicators.get("ema50", 0),
                "sma150": indicators.get("sma150", 0),
                "sma200": indicators.get("sma200", 0),
                "volume_ratio": indicators.get("volume_ratio", 1),
                "relative_strength": indicators.get("relative_strength", 1),
                "dist_52h_pct": indicators.get("dist_52h_pct", 0),
                "dist_52l_pct": indicators.get("dist_52l_pct", 0),
                "high_52w": indicators.get("high_52w", 0),
                "low_52w": indicators.get("low_52w", 0),
                "atr": indicators.get("atr", 0),
                "adx": indicators.get("adx", 0),
                "supertrend_dir": indicators.get("supertrend_dir", 0),
                "stop_loss": stop_loss,
                "risk_reward": rr,
                "pivot": indicators.get("pivot_pivot", 0),
                "last_updated": pd.Timestamp.now().strftime("%H:%M:%S"),
            }
        except Exception as e:
            logger.warning(f"Scanner error for {symbol}: {e}")
            return None


async def run_scan(force: bool = False) -> pd.DataFrame:
    global _scan_cache
    today = date.today().isoformat()
    now = time.time()

    # 1. In-memory cache (fastest)
    if not force and _scan_cache and (now - _scan_cache[0]) < _SCAN_TTL:
        return _scan_cache[1]

    # 2. SQLite cache — if today's scan exists, return immediately
    if not force:
        db_df = _load_scan_from_db(today)
        if db_df is not None and not db_df.empty:
            logger.info(f"Loaded scan from SQLite cache: {len(db_df)} stocks")
            _scan_cache = (now, db_df)
            return db_df

    # 3. Full scan — fetch + compute + score all 200 stocks
    logger.info("Starting full Nifty 200 strategy scan...")
    symbols_df = await get_nifty200_symbols()
    if symbols_df.empty:
        logger.error("No symbols loaded for scan")
        return pd.DataFrame()

    # Bulk-prefetch today's OHLC for all symbols in ONE API call → fills candle_cache
    # so individual get_historical_df calls below only hit SQLite (no per-stock API calls)
    from services.market_data import bulk_prefetch_today_ohlc
    all_keys = symbols_df["instrument_key"].tolist()
    prefetched = await bulk_prefetch_today_ohlc(all_keys)
    logger.info(f"Bulk prefetch: {prefetched} candles cached")

    benchmark_df = await get_historical_df("NSE_INDEX|Nifty 50", interval="day", days=_HIST_DAYS)
    semaphore = asyncio.Semaphore(50)  # pure SQLite+CPU after prefetch, no API rate limit concern

    tasks = [_process_stock(row, benchmark_df, semaphore) for _, row in symbols_df.iterrows()]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    records = [r for r in results if isinstance(r, dict)]
    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)
    df = df.sort_values("best_score", ascending=False).reset_index(drop=True)

    # Save to SQLite so next load is instant
    _save_scan_to_db(today, df)
    _scan_cache = (now, df)
    logger.info(f"Scan complete: {len(df)} stocks processed and cached")
    return df


def get_cached_scan() -> Optional[pd.DataFrame]:
    """Return in-memory cached scan, or load today's from SQLite."""
    if _scan_cache:
        return _scan_cache[1]
    today = date.today().isoformat()
    return _load_scan_from_db(today)
