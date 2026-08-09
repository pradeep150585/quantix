"""
VCP (Volatility Contraction Pattern) Scanner for AI Picks.

Criteria:
1. Stage-2 uptrend: close > 50 DMA > 150 DMA
2. 2-4 successive price contractions (each smaller than previous)
3. Volatility squeeze: ATR(14) contracting + BB width near multi-month low
4. Volume dry-up during final contraction vs 50-day avg
5. Breakout: close > pivot high with volume >= 1.5x 20-day avg
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
from services.market_data import get_historical_df, bulk_prefetch_today_ohlc

_HIST_DAYS = 300
_LOOKBACK  = 60   # swing detection window
_MIN_CONTRACTIONS = 2
_MAX_CONTRACTIONS = 4


def _stage2_uptrend(df: pd.DataFrame) -> bool:
    """Close > 50 DMA and 50 DMA > 150 DMA."""
    if len(df) < 150:
        return False
    close   = df["close"]
    sma50   = close.rolling(50).mean().iloc[-1]
    sma150  = close.rolling(150).mean().iloc[-1]
    cmp     = close.iloc[-1]
    return bool(cmp > sma50 > sma150)


def _find_swing_highs(df: pd.DataFrame, order: int = 5) -> list[int]:
    """Return indices of swing highs in the last _LOOKBACK bars."""
    sub = df.tail(_LOOKBACK).reset_index(drop=True)
    highs = sub["high"].values
    if _HAS_SCIPY:
        idx = argrelextrema(highs, np.greater_equal, order=order)[0]
    else:
        idx = []
        for i in range(order, len(highs) - order):
            if highs[i] == max(highs[i - order: i + order + 1]):
                idx.append(i)
    return list(idx)


def _find_swing_lows(df: pd.DataFrame, order: int = 5) -> list[int]:
    """Return indices of swing lows in the last _LOOKBACK bars."""
    sub = df.tail(_LOOKBACK).reset_index(drop=True)
    lows = sub["low"].values
    if _HAS_SCIPY:
        idx = argrelextrema(lows, np.less_equal, order=order)[0]
    else:
        idx = []
        for i in range(order, len(lows) - order):
            if lows[i] == min(lows[i - order: i + order + 1]):
                idx.append(i)
    return list(idx)


def _detect_contractions(df: pd.DataFrame) -> tuple[list[float], float]:
    """
    Identify successive price contractions using swing highs/lows.
    Returns (list_of_contraction_pcts, pivot_high).
    A contraction = (swing_high - swing_low) / swing_high * 100.
    """
    sub = df.tail(_LOOKBACK).reset_index(drop=True)
    high_idx = _find_swing_highs(df)
    low_idx  = _find_swing_lows(df)

    if len(high_idx) < 2 or len(low_idx) < 1:
        return [], 0.0

    highs = sub["high"].values
    lows  = sub["low"].values

    # Pair each swing high with the nearest subsequent swing low
    contractions = []
    used_lows = set()
    for hi in high_idx:
        subsequent_lows = [li for li in low_idx if li > hi and li not in used_lows]
        if not subsequent_lows:
            continue
        li = subsequent_lows[0]
        swing_h = highs[hi]
        swing_l = lows[li]
        if swing_h <= 0:
            continue
        pct = (swing_h - swing_l) / swing_h * 100
        if pct > 1.0:  # ignore noise < 1%
            contractions.append(pct)
            used_lows.add(li)

    pivot = highs[high_idx[-1]] if high_idx else 0.0
    return contractions, pivot


def _contractions_valid(contractions: list[float]) -> bool:
    """
    Check 2-4 successive contractions, each smaller than the previous.
    Rough size bands: first ~15-20%, last ~4-6%.
    """
    n = len(contractions)
    if n < _MIN_CONTRACTIONS or n > _MAX_CONTRACTIONS:
        return False
    # Each must be smaller than the previous
    for i in range(1, n):
        if contractions[i] >= contractions[i - 1]:
            return False
    # First contraction should be meaningful (>= 4%)
    if contractions[0] < 4.0:
        return False
    return True


def _volatility_squeeze(df: pd.DataFrame) -> bool:
    """ATR(14) contracting and/or BB width near multi-month low."""
    if len(df) < 60:
        return False
    close = df["close"]
    high  = df["high"]
    low   = df["low"]

    # ATR contraction: current ATR vs 20 days ago
    hl   = high - low
    hc   = (high - close.shift()).abs()
    lc   = (low  - close.shift()).abs()
    tr   = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    atr  = tr.rolling(14).mean()
    if atr.iloc[-1] >= atr.iloc[-20]:
        return False  # ATR not contracting

    # BB width near multi-month low (last 60 bars)
    sma20 = close.rolling(20).mean()
    std20 = close.rolling(20).std()
    bb_width = (4 * std20 / sma20).dropna()
    if len(bb_width) < 60:
        return True  # ATR check already passed
    current_bw = bb_width.iloc[-1]
    min_bw_60  = bb_width.tail(60).min()
    return current_bw <= min_bw_60 * 1.15  # within 15% of 60-bar low


def _volume_dryup(df: pd.DataFrame) -> bool:
    """Avg volume in last 10 bars < 50-day avg volume."""
    if len(df) < 50:
        return False
    vol_50avg    = df["volume"].tail(51).iloc[:-1].mean()
    vol_recent   = df["volume"].tail(10).mean()
    return bool(vol_recent < vol_50avg)


def _breakout_signal(df: pd.DataFrame, pivot: float) -> tuple[bool, float]:
    """
    Close breaks above pivot with volume >= 1.5x 20-day avg.
    Returns (is_breakout, volume_ratio).
    """
    if pivot <= 0 or len(df) < 21:
        return False, 0.0
    cmp        = df["close"].iloc[-1]
    vol_today  = df["volume"].iloc[-1]
    vol_20avg  = df["volume"].tail(21).iloc[:-1].mean()
    vol_ratio  = vol_today / vol_20avg if vol_20avg else 0.0
    is_bo      = bool(cmp > pivot and vol_ratio >= 1.5)
    return is_bo, round(vol_ratio, 2)


def _vcp_score(contractions: list[float], vol_ratio: float,
               is_breakout: bool, squeeze: bool, dryup: bool) -> float:
    """Composite VCP score 0-100."""
    score = 0.0
    n = len(contractions)
    # Contraction quality (40 pts)
    if n >= 2:
        score += 20
    if n >= 3:
        score += 10
    if n >= 2 and contractions[-1] < 6:
        score += 10  # tight final contraction
    # Squeeze (20 pts)
    if squeeze:
        score += 20
    # Volume dry-up (15 pts)
    if dryup:
        score += 15
    # Breakout (25 pts)
    if is_breakout:
        score += 15
        score += min(10, (vol_ratio - 1.5) / 0.5 * 10)  # up to 10 extra for strong vol
    return round(min(score, 100), 1)


def _analyse_stock(df: pd.DataFrame, symbol: str, company_name: str,
                   sector: str, instrument_key: str) -> dict | None:
    if df.empty or len(df) < 150:
        return None

    if not _stage2_uptrend(df):
        return None

    contractions, pivot = _detect_contractions(df)
    if not _contractions_valid(contractions):
        return None

    squeeze    = _volatility_squeeze(df)
    dryup      = _volume_dryup(df)
    is_bo, vr  = _breakout_signal(df, pivot)
    vcp_score  = _vcp_score(contractions, vr, is_bo, squeeze, dryup)

    close   = df["close"]
    cmp     = close.iloc[-1]
    prev    = close.iloc[-2] if len(df) > 1 else cmp
    pct_chg = round((cmp - prev) / prev * 100, 2) if prev else 0

    sma50   = close.rolling(50).mean().iloc[-1]
    sma150  = close.rolling(150).mean().iloc[-1]
    vol_50  = df["volume"].tail(51).iloc[:-1].mean()
    vol_20  = df["volume"].tail(21).iloc[:-1].mean()

    hl   = df["high"] - df["low"]
    hc   = (df["high"] - close.shift()).abs()
    lc   = (df["low"]  - close.shift()).abs()
    tr   = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    atr  = round(tr.rolling(14).mean().iloc[-1], 2)

    high52 = df["high"].tail(252).max()
    low52  = df["low"].tail(252).min()
    dist52h = round((cmp - high52) / high52 * 100, 2) if high52 else 0

    badges = []
    if is_bo:
        badges.append("Breakout")
    if squeeze:
        badges.append("Squeeze")
    if dryup:
        badges.append("Vol Dry-up")
    if len(contractions) >= 3:
        badges.append(f"{len(contractions)}-Stage VCP")

    return {
        "symbol":          symbol,
        "company_name":    company_name,
        "sector":          sector,
        "instrument_key":  instrument_key,
        "cmp":             round(cmp, 2),
        "pct_change":      pct_chg,
        "vcp_score":       vcp_score,
        "contractions":    len(contractions),
        "contraction_pcts": [round(c, 1) for c in contractions],
        "pivot":           round(pivot, 2),
        "is_breakout":     is_bo,
        "volume_ratio":    vr if is_bo else round(df["volume"].iloc[-1] / vol_20, 2) if vol_20 else 1.0,
        "vol_dryup":       dryup,
        "squeeze":         squeeze,
        "sma50":           round(sma50, 2),
        "sma150":          round(sma150, 2),
        "atr":             atr,
        "high_52w":        round(high52, 2),
        "low_52w":         round(low52, 2),
        "dist_52h_pct":    dist52h,
        "badges":          badges,
    }


async def _process(row: pd.Series, benchmark_df: pd.DataFrame,
                   sem: asyncio.Semaphore) -> dict | None:
    async with sem:
        symbol  = row.get("symbol", "")
        isin    = row.get("isin", "")
        ikey    = row.get("instrument_key", f"NSE_EQ|{isin}")
        try:
            df = await get_historical_df(ikey, interval="day", days=_HIST_DAYS)
            return _analyse_stock(df, symbol, row.get("company_name", symbol),
                                  row.get("sector", ""), ikey)
        except Exception as e:
            logger.debug(f"VCP scan error {symbol}: {e}")
            return None


async def run_vcp_scan() -> pd.DataFrame:
    """Scan all Nifty 200 stocks for VCP setups. Returns sorted DataFrame."""
    symbols_df = await get_nifty200_symbols()
    if symbols_df.empty:
        return pd.DataFrame()

    all_keys = symbols_df["instrument_key"].tolist()
    await bulk_prefetch_today_ohlc(all_keys)

    benchmark_df = await get_historical_df("NSE_INDEX|Nifty 50", interval="day", days=_HIST_DAYS)
    sem = asyncio.Semaphore(50)
    tasks = [_process(row, benchmark_df, sem) for _, row in symbols_df.iterrows()]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    records = [r for r in results if isinstance(r, dict)]
    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records).sort_values("vcp_score", ascending=False).reset_index(drop=True)
    logger.info(f"VCP scan complete: {len(df)} setups found from {len(symbols_df)} stocks")
    return df
