"""
Elder Triple Screen Swing Scanner — NSE 200
Based on Alexander Elder's "Trading for a Living" framework.

Screens (all on daily timeframe):
  1. Daily trend (MACD Histogram slope, EMA13, ADX, Force Index)
  2. Price action (higher lows, breakout structure)
  3. Volume confirmation
  4. Risk/Reward ratio

Scoring (0-100):
  Daily Trend    35 pts
  Price Action   30 pts
  Volume         20 pts
  Risk/Reward    15 pts

Uses daily timeframe for intraday and swing trading setups.
"""
from __future__ import annotations

import asyncio
import numpy as np
import pandas as pd
from loguru import logger

from services.instruments import get_nifty200_symbols
from services.market_data import get_historical_df, bulk_prefetch_today_ohlc, get_ltp, get_quotes, parse_quote

_HIST_DAYS  = 700  # ~100 weeks of data (weekly timeframe)
_CHART_BARS = 80
_MIN_RR     = 1.5


# Removed weekly resampling - now using daily timeframe


# ── Low-level indicator helpers ───────────────────────────────────────────────

def _ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False).mean()


def _macd_hist(close: pd.Series, fast=12, slow=26, sig=9) -> pd.Series:
    macd  = _ema(close, fast) - _ema(close, slow)
    signal = _ema(macd, sig)
    return macd - signal


def _force_index(df: pd.DataFrame) -> pd.Series:
    return df["volume"] * df["close"].diff()


def _adx(df: pd.DataFrame, n: int = 13) -> tuple[pd.Series, pd.Series, pd.Series]:
    high, low, close = df["high"], df["low"], df["close"]
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low  - close.shift()).abs(),
    ], axis=1).max(axis=1)
    dm_plus  = (high.diff()).clip(lower=0).where(high.diff() > (-low.diff()), 0)
    dm_minus = (-low.diff()).clip(lower=0).where(-low.diff() > high.diff(), 0)
    atr14    = tr.ewm(span=n, adjust=False).mean()
    di_plus  = 100 * _ema(dm_plus,  n) / atr14
    di_minus = 100 * _ema(dm_minus, n) / atr14
    dx       = (100 * (di_plus - di_minus).abs() / (di_plus + di_minus + 1e-9))
    adx_val  = _ema(dx, n)
    return adx_val, di_plus, di_minus


def _atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - df["close"].shift()).abs(),
        (df["low"]  - df["close"].shift()).abs(),
    ], axis=1).max(axis=1)
    return tr.rolling(n).mean()


def _swing_lows(series: pd.Series, order: int = 2) -> list[int]:
    vals = series.values
    out  = []
    for i in range(order, len(vals) - order):
        if vals[i] == min(vals[i - order: i + order + 1]):
            out.append(i)
    return out


def _swing_highs(series: pd.Series, order: int = 2) -> list[int]:
    vals = series.values
    out  = []
    for i in range(order, len(vals) - order):
        if vals[i] == max(vals[i - order: i + order + 1]):
            out.append(i)
    return out


# ── Daily Trend Screen (35 pts) ──────────────────────────────────────────────

def _daily_screen(df: pd.DataFrame) -> tuple[int, dict]:
    """Returns (score 0-35, detail dict)."""
    if len(df) < 15:
        return 0, {}

    close  = df["close"]
    hist   = _macd_hist(close)
    ema13  = _ema(close, 13)
    adx_v, di_plus, di_minus = _adx(df, 13)
    fi     = _force_index(df)
    fi13   = _ema(fi, 13)

    h_now  = float(hist.iloc[-1])
    h_prev = float(hist.iloc[-2])
    hist_rising = h_now > h_prev

    ema13_now   = float(ema13.iloc[-1])
    ema13_prev  = float(ema13.iloc[-2])
    ema13_rising = ema13_now > ema13_prev

    price_above_ema13 = float(close.iloc[-1]) > ema13_now
    di_bull  = float(di_plus.iloc[-1]) > float(di_minus.iloc[-1])
    adx_now  = float(adx_v.iloc[-1])
    adx_prev = float(adx_v.iloc[-2])
    adx_rising = adx_now > adx_prev
    fi13_pos = float(fi13.iloc[-1]) > 0

    score = 0
    if hist_rising:
        score += 10
    if ema13_rising:
        score += 8
    if price_above_ema13:
        score += 8
    if di_bull:
        score += 5
    if adx_rising:
        score += 4

    detail = {
        "daily_score":        score,
        "macd_hist_rising":   hist_rising,
        "macd_hist_now":      round(h_now, 4),
        "ema13_rising":       ema13_rising,
        "ema13":              round(ema13_now, 2),
        "price_above_ema13":  price_above_ema13,
        "di_bull":            di_bull,
        "di_plus":            round(float(di_plus.iloc[-1]), 2),
        "di_minus":           round(float(di_minus.iloc[-1]), 2),
        "adx":                round(adx_now, 2),
        "adx_rising":         adx_rising,
    }
    return min(score, 35), detail


# ── Price Action Screen (30 pts) ──────────────────────────────────────────────

def _price_action_screen(df: pd.DataFrame) -> tuple[int, dict, float, float, float]:
    """Returns (score 0-30, detail, entry, stop, resistance)."""
    if len(df) < 10:
        return 0, {}, 0.0, 0.0, 0.0

    close = df["close"]
    high  = df["high"]
    low   = df["low"]
    cmp   = float(close.iloc[-1])

    # Swing structure
    sh_idx = _swing_highs(high, order=2)
    sl_idx = _swing_lows(low, order=2)

    recent_sh = float(high.iloc[sh_idx[-1]]) if sh_idx else cmp * 1.05
    recent_sl = float(low.iloc[sl_idx[-1]])  if sl_idx else cmp * 0.95

    # Higher-low structure
    higher_low = False
    if len(sl_idx) >= 2:
        higher_low = float(low.iloc[sl_idx[-1]]) > float(low.iloc[sl_idx[-2]])

    # 5-bar high breakout
    high5 = float(high.tail(5).max())
    breakout_5b = cmp >= high5 * 0.995

    # Resistance
    resistance = max(recent_sh, high5)
    entry = round(resistance * 1.002, 2)
    stop = round(recent_sl * 0.998, 2)

    # False breakout check
    intraday_spike = float(high.iloc[-1]) > resistance and cmp < resistance
    false_bo_risk = "HIGH" if intraday_spike else (
        "MEDIUM" if breakout_5b and cmp < resistance else "LOW"
    )

    # Scoring
    score = 0
    if higher_low:
        score += 10
    if breakout_5b:
        score += 10
    if not intraday_spike:
        score += 5
    if cmp > float(_ema(close, 13).iloc[-1]):
        score += 5

    detail = {
        "pa_score":       min(score, 30),
        "higher_low":     higher_low,
        "breakout_5b":    breakout_5b,
        "recent_sh":      round(recent_sh, 2),
        "recent_sl":      round(recent_sl, 2),
        "resistance":     round(resistance, 2),
        "false_bo_risk":  false_bo_risk,
        "entry":          entry,
        "stop":           round(stop, 2),
    }
    return min(score, 30), detail, entry, stop, resistance


# ── Volume Screen (20 pts) ────────────────────────────────────────────────────

def _volume_screen(df: pd.DataFrame, breakout: bool) -> tuple[int, dict]:
    if len(df) < 5:
        return 0, {}
    vol     = df["volume"]
    vol_now = float(vol.iloc[-1])
    vol_avg = float(vol.tail(5).mean())
    rvol    = vol_now / vol_avg if vol_avg else 1.0

    vol_declining = float(vol.tail(3).mean()) < vol_avg

    score = 0
    if breakout and rvol >= 1.3:
        score += 15
    elif breakout and rvol >= 1.1:
        score += 10
    elif not breakout and vol_declining:
        score += 12
    elif not breakout:
        score += 8

    detail = {
        "vol_score":        min(score, 20),
        "rvol":             round(rvol, 2),
        "vol_avg":          round(vol_avg, 0),
        "vol_declining":    vol_declining,
    }
    return min(score, 20), detail


# ── Risk/Reward Screen (15 pts) ───────────────────────────────────────────────

def _rr_screen(cmp: float, entry: float, stop: float,
               resistance: float) -> tuple[int, dict]:
    if stop >= entry or entry <= 0:
        return 0, {"rr_score": 0, "rr": 0.0, "signal": "NO TRADE"}

    risk_pct   = (entry - stop) / entry * 100
    target1    = entry + 1.5 * (entry - stop)
    target2    = entry + 2.5 * (entry - stop)
    rr         = (target1 - entry) / (entry - stop)

    dist_to_res = (resistance - entry) / entry * 100 if resistance > entry else 100.0

    score = 0
    if rr >= 2.0:
        score += 15
    elif rr >= 1.5:
        score += 10
    elif rr >= 1.0:
        score += 5

    if dist_to_res < 2.0:
        score = max(0, score - 8)
    elif dist_to_res < 4.0:
        score = max(0, score - 4)

    if rr >= 2.0 and dist_to_res >= 4.0:
        signal = "BUY ON BREAKOUT"
    elif rr >= 1.5 and dist_to_res >= 3.0:
        signal = "BUY ON BREAKOUT"
    elif rr >= 1.0:
        signal = "WATCH"
    else:
        signal = "NO TRADE"

    detail = {
        "rr_score":      min(score, 15),
        "rr":            round(rr, 2),
        "risk_pct":      round(risk_pct, 2),
        "target1":       round(target1, 2),
        "target2":       round(target2, 2),
        "dist_to_res":   round(dist_to_res, 2),
        "signal":        signal,
    }
    return min(score, 15), detail


# ── Final grade ───────────────────────────────────────────────────────────────

def _grade(score: int) -> str:
    if score >= 90: return "A+"
    if score >= 80: return "A"
    if score >= 70: return "B"
    if score >= 60: return "WATCHLIST"
    return "NO TRADE"


# ── Per-stock analysis ────────────────────────────────────────────────────────

def _analyse(df: pd.DataFrame, symbol: str, company: str,
             sector: str, ikey: str, live_ltp: float) -> dict | None:
    if df.empty or len(df) < 15:
        return None

    d_score, d_det = _daily_screen(df)
    if d_score < 15:
        return None

    pa_score, pa_det, entry, stop, resistance = _price_action_screen(df)
    if pa_score < 10:
        return None

    breakout = pa_det.get("breakout_5b", False)
    v_score,  v_det  = _volume_screen(df, breakout)

    close = df["close"]
    cmp = live_ltp if live_ltp > 0 else float(close.iloc[-1])
    rr_score, rr_det = _rr_screen(cmp, entry, stop, resistance)

    if rr_det.get("signal") == "NO TRADE":
        return None

    total = d_score + pa_score + v_score + rr_score

    prev   = float(close.iloc[-2]) if len(df) > 1 else cmp
    pct    = round((cmp - prev) / prev * 100, 2) if prev else 0.0

    atr_s  = _atr(df)
    atr_v  = round(float(atr_s.iloc[-1]), 2)

    high52 = float(df["high"].tail(52).max())
    low52  = float(df["low"].tail(52).min())
    dist52h = round((cmp - high52) / high52 * 100, 2) if high52 else 0.0

    # Chart data
    chart_df = df.tail(_CHART_BARS).copy().reset_index(drop=True)
    chart_df["ema13"]  = _ema(close, 13).tail(_CHART_BARS).values
    chart_df["ema26"]  = _ema(close, 26).tail(_CHART_BARS).values
    chart_df["fi2"]    = _ema(_force_index(df), 2).tail(_CHART_BARS).values
    chart_df["macd_h"] = _macd_hist(close).tail(_CHART_BARS).values

    return {
        "symbol":        symbol,
        "company_name":  company,
        "sector":        sector,
        "instrument_key": ikey,
        "cmp":           round(cmp, 2),
        "pct_change":    pct,
        "score":         total,
        "grade":         _grade(total),
        "signal":        rr_det["signal"],
        "entry":         entry,
        "stop":          pa_det["stop"],
        "target1":       rr_det["target1"],
        "target2":       rr_det["target2"],
        "rr":            rr_det["rr"],
        "risk_pct":      rr_det["risk_pct"],
        "atr":           atr_v,
        "high_52w":      round(high52, 2),
        "low_52w":       round(low52, 2),
        "dist_52h_pct":  dist52h,
        "false_bo_risk": pa_det["false_bo_risk"],
        # sub-scores
        "daily_score":   d_score,
        "pa_score":      pa_score,
        "vol_score":     v_score,
        "rr_score":      rr_score,
        # detail dicts
        "_daily":        d_det,
        "_pa":           pa_det,
        "_vol":          v_det,
        "_rr":           rr_det,
        "_chart_df":     chart_df,
    }


# ── Async scan ────────────────────────────────────────────────────────────────

async def _process(row: pd.Series, ltp_map: dict,
                   sem: asyncio.Semaphore) -> dict | None:
    async with sem:
        symbol = row.get("symbol", "")
        isin   = row.get("isin", "")
        ikey   = row.get("instrument_key", f"NSE_EQ|{isin}")
        try:
            df       = await get_historical_df(ikey, interval="week", days=_HIST_DAYS)
            if df.empty or len(df) < 15:
                return None
            live_ltp = ltp_map.get(ikey, {}).get("last_price", 0.0)
            return _analyse(df, symbol, row.get("company_name", symbol),
                            row.get("sector", ""), ikey, live_ltp)
        except Exception as e:
            logger.debug(f"Elder scan error {symbol}: {e}")
            return None


async def run_elder_scan() -> tuple[pd.DataFrame, dict]:
    """
    Dr. Alexander Elder's Triple Screen Trading System
    Returns (top 5 stocks DataFrame, chart_store dict)
    
    Methodology from "Trading for a Living":
    - Screen 1: Market tide (trend-following indicator on weekly)
    - Screen 2: Wave (oscillator on weekly for pullback)
    - Screen 3: Weekly breakout (entry timing)
    
    Now using weekly timeframe as per user request
    """
    from datetime import date
    from database import save_scanner_signal
    
    symbols_df = await get_nifty200_symbols()
    if symbols_df.empty:
        return pd.DataFrame(), {}

    all_keys = symbols_df["instrument_key"].tolist()
    # Fetch live quotes instead of just LTP
    live_quotes = await get_quotes(all_keys)
    ltp_raw = {}
    for key, quote_data in live_quotes.items():
        parsed = parse_quote(quote_data)
        if parsed:
            ltp_raw[key] = {"last_price": parsed.get("ltp", 0)}

    sem     = asyncio.Semaphore(100)
    tasks   = [_process(row, ltp_raw, sem) for _, row in symbols_df.iterrows()]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    records     = [r for r in results if isinstance(r, dict)]
    chart_store = {}
    clean       = []

    for r in records:
        chart_store[r["symbol"]] = r.pop("_chart_df")
        clean.append(r)

    if not clean:
        return pd.DataFrame(), {}

    df = pd.DataFrame(clean).sort_values("score", ascending=False).reset_index(drop=True)
    
    # Return TOP 5 ONLY (Elder's focus on quality over quantity)
    top5 = df.head(5)
    top5_chart_store = {sym: chart_store[sym] for sym in top5["symbol"].values if sym in chart_store}
    
    # Save signals to database for backtesting
    today = str(date.today())
    for _, row in top5.iterrows():
        try:
            save_scanner_signal(
                signal_date=today,
                scanner_type="Elder",
                symbol=row["symbol"],
                company_name=row.get("company_name", ""),
                instrument_key=row.get("instrument_key", ""),
                entry_price=row.get("entry", 0),
                stop_price=row.get("stop", 0),
                target1_price=row.get("target1", 0),
                target2_price=row.get("target2", 0),
                score=row.get("score", 0),
                signal=row.get("signal", ""),
                sector=row.get("sector", "")
            )
        except Exception as e:
            logger.warning(f"Failed to save Elder signal for {row['symbol']}: {e}")
    
    logger.info(f"Elder Triple Screen: {len(top5)} top stocks from {len(df)} setups analyzed")
    
    return top5, top5_chart_store
