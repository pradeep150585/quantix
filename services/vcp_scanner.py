"""
VCP (Volatility Contraction Pattern) Scanner for AI Picks.

Criteria:
1. Stage-2 uptrend: close > 10 MA > 30 MA
2. 2-4 successive price contractions (each smaller than previous)
3. Volatility squeeze: ATR(14) contracting + BB width near multi-month low
4. Volume dry-up during final contraction
5. Breakout: close > pivot high with volume >= 1.5x avg

Uses daily timeframe for intraday and swing trading setups.
"""
import asyncio
import numpy as np
import pandas as pd
from loguru import logger

try:
    from scipy.signal import argrelextrema
    _HAS_SCIPY = True
except ImportError:
    _HAS_SCIPY = False

from services.instruments import get_nifty200_symbols
from services.market_data import get_historical_df, bulk_prefetch_today_ohlc, get_ltp

_HIST_DAYS        = 250
_CHART_BARS       = 60
_LOOKBACK         = 15
_MIN_CONTRACTIONS = 2
_MAX_CONTRACTIONS = 4


# Removed weekly resampling - now using daily timeframe


# ── Trend ─────────────────────────────────────────────────────────────────────

def _stage2_uptrend(df: pd.DataFrame) -> bool:
    if len(df) < 15:
        return False
    close  = df["close"]
    ma10  = close.rolling(10).mean().iloc[-1]
    ma30  = close.rolling(30).mean().iloc[-1]
    return bool(close.iloc[-1] > ma10 > ma30)


# ── Swing detection ───────────────────────────────────────────────────────────

def _swing_highs(series: np.ndarray, order: int = 3) -> list[int]:
    if _HAS_SCIPY:
        return list(argrelextrema(series, np.greater_equal, order=order)[0])
    out = []
    for i in range(order, len(series) - order):
        if series[i] == max(series[i - order: i + order + 1]):
            out.append(i)
    return out


def _swing_lows(series: np.ndarray, order: int = 3) -> list[int]:
    if _HAS_SCIPY:
        return list(argrelextrema(series, np.less_equal, order=order)[0])
    out = []
    for i in range(order, len(series) - order):
        if series[i] == min(series[i - order: i + order + 1]):
            out.append(i)
    return out


# ── Contraction detection ─────────────────────────────────────────────────────

def _detect_contractions(df: pd.DataFrame) -> tuple[list[float], float, list[int], list[int]]:
    """
    Returns (contraction_pcts, pivot_price, swing_high_indices_in_sub, swing_low_indices_in_sub).
    Indices are relative to df.tail(_LOOKBACK).
    """
    sub   = df.tail(_LOOKBACK).reset_index(drop=True)
    highs = sub["high"].values
    lows  = sub["low"].values

    hi_idx = _swing_highs(highs, order=2)
    lo_idx = _swing_lows(lows, order=2)

    if len(hi_idx) < 2 or len(lo_idx) < 1:
        return [], 0.0, hi_idx, lo_idx

    contractions = []
    used_lows    = set()
    for hi in hi_idx:
        next_lows = [li for li in lo_idx if li > hi and li not in used_lows]
        if not next_lows:
            continue
        li      = next_lows[0]
        swing_h = highs[hi]
        swing_l = lows[li]
        if swing_h <= 0:
            continue
        pct = (swing_h - swing_l) / swing_h * 100
        if pct > 1.0:
            contractions.append(pct)
            used_lows.add(li)

    pivot = float(highs[hi_idx[-1]]) if hi_idx else 0.0
    return contractions, pivot, hi_idx, lo_idx


def _contractions_valid(contractions: list[float]) -> bool:
    n = len(contractions)
    if n < _MIN_CONTRACTIONS or n > _MAX_CONTRACTIONS:
        return False
    for i in range(1, n):
        if contractions[i] >= contractions[i - 1]:
            return False
    return contractions[0] >= 3.0  # Reduced threshold for weekly


# ── Other criteria ────────────────────────────────────────────────────────────

def _volatility_squeeze(df: pd.DataFrame) -> bool:
    if len(df) < 10:
        return False
    close = df["close"]
    hl    = df["high"] - df["low"]
    hc    = (df["high"] - close.shift()).abs()
    lc    = (df["low"]  - close.shift()).abs()
    atr   = pd.concat([hl, hc, lc], axis=1).max(axis=1).rolling(7).mean()
    if len(atr) < 7:
        return False
    if atr.iloc[-1] >= atr.iloc[-5]:
        return False
    sma10    = close.rolling(10).mean()
    std10    = close.rolling(10).std()
    bb_width = (4 * std10 / sma10).dropna()
    if len(bb_width) < 5:
        return True
    return bool(bb_width.iloc[-1] <= bb_width.tail(10).min() * 1.15)


def _volume_dryup(df: pd.DataFrame) -> bool:
    if len(df) < 5:
        return False
    return bool(df["volume"].tail(3).mean() < df["volume"].tail(8).iloc[:-1].mean())


def _breakout_signal(df: pd.DataFrame, pivot: float, live_ltp: float = 0.0) -> tuple[bool, float]:
    if pivot <= 0 or len(df) < 3:
        return False, 0.0
    # Use a longer vol average (exclude last bar which may be partial)
    vol_avg = df["volume"].iloc[:-1].tail(8).mean()
    vol_ratio = df["volume"].iloc[-1] / vol_avg if vol_avg else 0.0
    price = live_ltp if live_ltp > 0 else float(df["close"].iloc[-1])
    is_bo = bool(price > pivot and vol_ratio >= 1.3)
    return is_bo, round(vol_ratio, 2)


def _vcp_score(contractions: list[float], vol_ratio: float,
               is_breakout: bool, squeeze: bool, dryup: bool) -> float:
    score = 0.0
    n = len(contractions)
    if n >= 2: score += 20
    if n >= 3: score += 10
    if n >= 2 and contractions[-1] < 5: score += 10
    if squeeze:     score += 20
    if dryup:       score += 15
    if is_breakout:
        score += 15
        score += min(10, (vol_ratio - 1.3) / 0.5 * 10)
    return round(min(score, 100), 1)


# ── Per-stock analysis ────────────────────────────────────────────────────────

def _analyse_stock(df: pd.DataFrame, symbol: str, company_name: str,
                   sector: str, instrument_key: str,
                   live_ltp: float = 0.0) -> dict | None:
    if df.empty or len(df) < 15:
        return None
    if not _stage2_uptrend(df):
        return None

    contractions, pivot, hi_idx, lo_idx = _detect_contractions(df)
    if not _contractions_valid(contractions):
        return None

    squeeze   = _volatility_squeeze(df)
    dryup     = _volume_dryup(df)
    is_bo, vr = _breakout_signal(df, pivot, live_ltp)
    score     = _vcp_score(contractions, vr, is_bo, squeeze, dryup)

    close  = df["close"]
    # Use live LTP if available, else last close
    cmp    = live_ltp if live_ltp > 0 else float(close.iloc[-1])
    prev   = float(close.iloc[-2]) if len(df) > 1 else cmp
    pct    = round((cmp - prev) / prev * 100, 2) if prev else 0.0

    wma10  = float(close.rolling(10).mean().iloc[-1])
    wma30  = float(close.rolling(30).mean().iloc[-1])
    vol_avg = df["volume"].tail(3).mean()

    hl  = df["high"] - df["low"]
    hc  = (df["high"] - close.shift()).abs()
    lc  = (df["low"]  - close.shift()).abs()
    atr = round(float(pd.concat([hl, hc, lc], axis=1).max(axis=1).rolling(7).mean().iloc[-1]), 2)

    high52  = float(df["high"].tail(52).max())
    low52   = float(df["low"].tail(52).min())
    dist52h = round((cmp - high52) / high52 * 100, 2) if high52 else 0.0

    badges = []
    if is_bo:               badges.append("Breakout")
    if squeeze:             badges.append("Squeeze")
    if dryup:               badges.append("Vol Dry-up")
    if len(contractions) >= 3: badges.append(f"{len(contractions)}-Stage VCP")

    # Chart data: last _CHART_BARS bars, with WMA columns pre-computed
    chart_df = df.tail(_CHART_BARS).copy().reset_index(drop=True)
    chart_df["wma10"]  = close.rolling(10).mean().tail(_CHART_BARS).values
    chart_df["wma30"] = close.rolling(30).mean().tail(_CHART_BARS).values

    # Swing indices relative to chart_df (offset from full df tail)
    offset      = max(0, len(df) - _LOOKBACK)
    chart_start = max(0, len(df) - _CHART_BARS)
    # hi_idx / lo_idx are relative to df.tail(_LOOKBACK), convert to chart_df indices
    lookback_start_in_chart = offset - chart_start  # where lookback window starts in chart_df
    chart_hi = [lookback_start_in_chart + i for i in hi_idx
                if 0 <= lookback_start_in_chart + i < len(chart_df)]
    chart_lo = [lookback_start_in_chart + i for i in lo_idx
                if 0 <= lookback_start_in_chart + i < len(chart_df)]

    return {
        "symbol":           symbol,
        "company_name":     company_name,
        "sector":           sector,
        "instrument_key":   instrument_key,
        "cmp":              round(cmp, 2),
        "pct_change":       pct,
        "vcp_score":        score,
        "contractions":     len(contractions),
        "contraction_pcts": [round(c, 1) for c in contractions],
        "pivot":            round(pivot, 2),
        "entry_price":      round(pivot * 1.005, 2) if pivot > 0 else round(cmp, 2),
        "stop_loss":        round(pivot * (1 - atr / cmp) if cmp > 0 else pivot * 0.95, 2),
        "is_breakout":      is_bo,
        "volume_ratio":     vr if is_bo else round(df["volume"].iloc[-1] / vol_avg, 2) if vol_avg else 1.0,
        "vol_dryup":        dryup,
        "squeeze":          squeeze,
        "wma10":            round(wma10, 2),
        "wma30":            round(wma30, 2),
        "atr":              atr,
        "high_52w":         round(high52, 2),
        "low_52w":          round(low52, 2),
        "dist_52h_pct":     dist52h,
        "badges":           badges,
        # chart payload (not serialised to DB)
        "_chart_df":        chart_df,
        "_swing_hi":        chart_hi,
        "_swing_lo":        chart_lo,
    }


# ── Async scan ────────────────────────────────────────────────────────────────

async def _process(row: pd.Series, ltp_map: dict,
                   sem: asyncio.Semaphore) -> dict | None:
    async with sem:
        symbol = row.get("symbol", "")
        isin   = row.get("isin", "")
        ikey   = row.get("instrument_key", f"NSE_EQ|{isin}")
        try:
            df       = await get_historical_df(ikey, interval="day", days=_HIST_DAYS)
            if df.empty or len(df) < 15:
                return None
            live_ltp = ltp_map.get(ikey, {}).get("last_price", 0.0)
            return _analyse_stock(df, symbol, row.get("company_name", symbol),
                                row.get("sector", ""), ikey, live_ltp)
        except Exception as e:
            logger.debug(f"VCP scan error {symbol}: {e}")
            return None


async def run_vcp_scan() -> tuple[pd.DataFrame, dict]:
    """
    Returns (scan_df, chart_store).
    scan_df: one row per VCP setup (no chart columns).
    chart_store: {symbol: {"df": chart_df, "hi": [...], "lo": [...]}}
    """
    symbols_df = await get_nifty200_symbols()
    if symbols_df.empty:
        logger.error("VCP scan failed: No symbols retrieved from Nifty200")
        return pd.DataFrame(), {}

    all_keys = symbols_df["instrument_key"].tolist()
    
    # Fetch today's OHLC to ensure latest data
    prefetched = await bulk_prefetch_today_ohlc(all_keys)
    logger.info(f"VCP scan: prefetched {prefetched} today's candles")

    # Use empty ltp_raw - prices will be from historical close (consistent)
    ltp_raw = {}

    # Reduced semaphore for better stability in Streamlit
    sem     = asyncio.Semaphore(50)
    tasks   = [_process(row, ltp_raw, sem) for _, row in symbols_df.iterrows()]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    records     = [r for r in results if isinstance(r, dict)]
    chart_store = {}
    clean       = []

    for r in records:
        chart_store[r["symbol"]] = {
            "df": r.pop("_chart_df"),
            "hi": r.pop("_swing_hi"),
            "lo": r.pop("_swing_lo"),
        }
        clean.append(r)

    if not clean:
        return pd.DataFrame(), {}

    df = pd.DataFrame(clean).sort_values("vcp_score", ascending=False).reset_index(drop=True)
    
    breakouts = df[df["is_breakout"] == True]
    logger.info(f"VCP scan: {len(df)} setups, {len(breakouts)} breakouts")
    logger.debug(f"VCP DataFrame columns: {df.columns.tolist()}")
    logger.debug(f"VCP DataFrame shape: {df.shape}")
    
    return df, chart_store
