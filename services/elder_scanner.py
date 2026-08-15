"""
Elder Triple Screen Swing Scanner — NSE 200
Based on Alexander Elder's "Trading for a Living" framework.

Screens:
  1. Weekly trend (MACD Histogram slope, EMA13, ADX, Force Index)
  2. Daily pullback (Force Index 2-EMA, Elder-Ray Bear Power, Stochastic, Williams %R, RSI)
  3. Price trigger + volume + R:R

Scoring (0-100, no double-counting):
  Weekly Trend   30 pts
  Daily Pullback 25 pts
  Price Action   20 pts
  Volume         10 pts
  Risk/Reward    15 pts
"""
from __future__ import annotations

import asyncio
import numpy as np
import pandas as pd
from loguru import logger

from services.instruments import get_nifty200_symbols
from services.market_data import get_historical_df, bulk_prefetch_today_ohlc, get_ltp

_HIST_DAYS  = 365
_CHART_BARS = 120
_MIN_RR     = 1.5


# ── Low-level indicator helpers ───────────────────────────────────────────────

def _ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False).mean()


def _weekly(df: pd.DataFrame) -> pd.DataFrame:
    """Resample daily OHLCV to weekly (week ending Friday)."""
    df = df.set_index("datetime")
    w = df.resample("W-FRI").agg(
        open=("open", "first"), high=("high", "max"),
        low=("low", "min"),   close=("close", "last"),
        volume=("volume", "sum"),
    ).dropna()
    w.index.name = "datetime"
    return w.reset_index()


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


def _stochastic(df: pd.DataFrame, k=5, d=3) -> tuple[pd.Series, pd.Series]:
    lo  = df["low"].rolling(k).min()
    hi  = df["high"].rolling(k).max()
    pct_k = 100 * (df["close"] - lo) / (hi - lo + 1e-9)
    pct_k = pct_k.rolling(d).mean()   # slow %K
    pct_d = pct_k.rolling(d).mean()
    return pct_k, pct_d


def _williams_r(df: pd.DataFrame, n: int = 7) -> pd.Series:
    hi = df["high"].rolling(n).max()
    lo = df["low"].rolling(n).min()
    return -100 * (hi - df["close"]) / (hi - lo + 1e-9)


def _rsi(close: pd.Series, n: int = 14) -> pd.Series:
    delta = close.diff()
    gain  = delta.clip(lower=0).ewm(span=n, adjust=False).mean()
    loss  = (-delta.clip(upper=0)).ewm(span=n, adjust=False).mean()
    return 100 - 100 / (1 + gain / (loss + 1e-9))


def _atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - df["close"].shift()).abs(),
        (df["low"]  - df["close"].shift()).abs(),
    ], axis=1).max(axis=1)
    return tr.rolling(n).mean()


def _swing_lows(series: pd.Series, order: int = 5) -> list[int]:
    vals = series.values
    out  = []
    for i in range(order, len(vals) - order):
        if vals[i] == min(vals[i - order: i + order + 1]):
            out.append(i)
    return out


def _swing_highs(series: pd.Series, order: int = 5) -> list[int]:
    vals = series.values
    out  = []
    for i in range(order, len(vals) - order):
        if vals[i] == max(vals[i - order: i + order + 1]):
            out.append(i)
    return out


# ── Weekly Screen (30 pts) ────────────────────────────────────────────────────

def _weekly_screen(wdf: pd.DataFrame) -> tuple[int, dict]:
    """Returns (score 0-30, detail dict)."""
    if len(wdf) < 30:
        return 0, {}

    close  = wdf["close"]
    hist   = _macd_hist(close)
    ema13  = _ema(close, 13)
    ema26  = _ema(close, 26)
    adx_v, di_plus, di_minus = _adx(wdf, 13)
    fi     = _force_index(wdf)
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

    # Scoring (no double-count: MACD hist 10, EMA13 slope 5, price vs EMA 5, DI 4, ADX 3, FI 3)
    score = 0
    # MACD Histogram slope (10 pts)
    if hist_rising:
        score += 10
        if h_now < 0:   # bullish turn below zero — extra quality
            score += 0  # already counted; flag it in detail
    # EMA13 slope (5 pts)
    if ema13_rising:
        score += 5
    # Price vs EMA13 (5 pts)
    if price_above_ema13:
        score += 5
    # +DI/-DI (4 pts)
    if di_bull:
        score += 4
    # ADX (3 pts)
    if adx_rising:
        score += 3
    # Force Index 13 (3 pts)
    if fi13_pos:
        score += 3

    # Classify trend
    if score >= 24:
        trend = "STRONG BULLISH"
    elif score >= 16:
        trend = "BULLISH"
    elif score >= 10:
        trend = "NEUTRAL"
    elif score >= 5:
        trend = "BEARISH"
    else:
        trend = "STRONG BEARISH"

    detail = {
        "weekly_score":       score,
        "weekly_trend":       trend,
        "macd_hist_rising":   hist_rising,
        "macd_hist_now":      round(h_now, 4),
        "macd_hist_below_zero": h_now < 0,
        "ema13_rising":       ema13_rising,
        "ema13":              round(ema13_now, 2),
        "price_above_ema13":  price_above_ema13,
        "di_bull":            di_bull,
        "di_plus":            round(float(di_plus.iloc[-1]), 2),
        "di_minus":           round(float(di_minus.iloc[-1]), 2),
        "adx":                round(adx_now, 2),
        "adx_rising":         adx_rising,
        "weekly_fi13_pos":    fi13_pos,
    }
    return score, detail


# ── Daily Screen (25 pts) ─────────────────────────────────────────────────────

def _daily_screen(df: pd.DataFrame) -> tuple[int, dict]:
    """Returns (score 0-25, detail dict)."""
    if len(df) < 30:
        return 0, {}

    close  = df["close"]
    ema13  = _ema(close, 13)
    fi_raw = _force_index(df)
    fi2    = _ema(fi_raw, 2)
    fi13   = _ema(fi_raw, 13)

    # Elder-Ray
    bull_power = df["high"] - ema13
    bear_power = df["low"]  - ema13

    bp_now  = float(bear_power.iloc[-1])
    bp_prev = float(bear_power.iloc[-2])
    bear_power_rising = bp_now > bp_prev

    fi2_now  = float(fi2.iloc[-1])
    fi2_prev = float(fi2.iloc[-2])
    fi2_neg_turning_up = fi2_now < 0 and fi2_now > fi2_prev

    stoch_k, stoch_d = _stochastic(df)
    sk_now = float(stoch_k.iloc[-1])
    sd_now = float(stoch_d.iloc[-1])
    stoch_oversold_turning = sk_now < 30 and sk_now > float(stoch_k.iloc[-2])

    wr  = _williams_r(df)
    wr_now  = float(wr.iloc[-1])
    wr_prev = float(wr.iloc[-2])
    wr_oversold_turning = wr_now < -80 and wr_now > wr_prev

    rsi_s   = _rsi(close)
    rsi_now = float(rsi_s.iloc[-1])
    rsi_ok  = 40 <= rsi_now <= 70

    daily_hist = _macd_hist(close)
    dh_now  = float(daily_hist.iloc[-1])
    dh_prev = float(daily_hist.iloc[-2])
    daily_hist_turning = dh_now > dh_prev and dh_now < 0

    # Scoring (FI2: 8, Bear Power: 6, Stoch: 4, WR: 3, RSI: 2, MACD hist: 2)
    score = 0
    if fi2_neg_turning_up:
        score += 8
    elif fi2_now < 0:
        score += 4   # negative but not yet turning
    if bp_now < 0 and bear_power_rising:
        score += 6
    elif bp_now < 0:
        score += 3
    if stoch_oversold_turning:
        score += 4
    elif sk_now < 40:
        score += 2
    if wr_oversold_turning:
        score += 3
    elif wr_now < -70:
        score += 1
    if rsi_ok:
        score += 2
    if daily_hist_turning:
        score += 2

    score = min(score, 25)

    detail = {
        "daily_score":           score,
        "fi2_now":               round(fi2_now, 2),
        "fi2_neg_turning_up":    fi2_neg_turning_up,
        "bear_power":            round(bp_now, 2),
        "bear_power_rising":     bear_power_rising,
        "stoch_k":               round(sk_now, 1),
        "stoch_d":               round(sd_now, 1),
        "stoch_oversold_turning": stoch_oversold_turning,
        "williams_r":            round(wr_now, 1),
        "wr_oversold_turning":   wr_oversold_turning,
        "rsi":                   round(rsi_now, 1),
        "daily_hist_turning":    daily_hist_turning,
        "ema13_daily":           round(float(ema13.iloc[-1]), 2),
    }
    return score, detail


# ── Price Action Screen (20 pts) ──────────────────────────────────────────────

def _price_action_screen(df: pd.DataFrame) -> tuple[int, dict, float, float, float]:
    """
    Returns (score 0-20, detail, entry_trigger, stop_price, nearest_resistance).
    """
    if len(df) < 30:
        return 0, {}, 0.0, 0.0, 0.0

    close = df["close"]
    high  = df["high"]
    low   = df["low"]
    cmp   = float(close.iloc[-1])

    # Swing structure
    sh_idx = _swing_highs(high, order=5)
    sl_idx = _swing_lows(low,   order=5)

    recent_sh = float(high.iloc[sh_idx[-1]]) if sh_idx else cmp * 1.05
    recent_sl = float(low.iloc[sl_idx[-1]])  if sl_idx else cmp * 0.95

    # Higher-low structure: last swing low > second-last swing low
    higher_low = False
    if len(sl_idx) >= 2:
        higher_low = float(low.iloc[sl_idx[-1]]) > float(low.iloc[sl_idx[-2]])

    # 20-day high breakout
    high20 = float(high.tail(20).max())
    breakout_20d = cmp >= high20 * 0.995

    # Resistance = recent swing high or 20-day high
    resistance = max(recent_sh, high20)

    # Entry trigger = recent swing high + 0.2% buffer
    entry = round(resistance * 1.002, 2)

    # Stop = recent swing low
    stop = round(recent_sl * 0.998, 2)

    # False breakout check
    prev_close = float(close.iloc[-2])
    intraday_spike = float(high.iloc[-1]) > resistance and cmp < resistance
    false_bo_risk = "HIGH" if intraday_spike else ("MEDIUM" if breakout_20d and cmp < resistance else "LOW")

    # Scoring
    score = 0
    if higher_low:
        score += 6
    if breakout_20d:
        score += 6
    if not intraday_spike:
        score += 4
    if cmp > float(_ema(close, 13).iloc[-1]):
        score += 4
    score = min(score, 20)

    detail = {
        "pa_score":       score,
        "higher_low":     higher_low,
        "breakout_20d":   breakout_20d,
        "recent_sh":      round(recent_sh, 2),
        "recent_sl":      round(recent_sl, 2),
        "resistance":     round(resistance, 2),
        "false_bo_risk":  false_bo_risk,
        "entry":          entry,
        "stop":           round(stop, 2),
    }
    return score, detail, entry, stop, resistance


# ── Volume Screen (10 pts) ────────────────────────────────────────────────────

def _volume_screen(df: pd.DataFrame, breakout: bool) -> tuple[int, dict]:
    if len(df) < 21:
        return 0, {}
    vol     = df["volume"]
    vol_now = float(vol.iloc[-1])
    vol20   = float(vol.tail(21).iloc[:-1].mean())
    rvol    = vol_now / vol20 if vol20 else 1.0

    # Pullback: volume should be declining
    vol5    = float(vol.tail(5).mean())
    pullback_vol_ok = vol5 < vol20

    score = 0
    if breakout and rvol >= 1.5:
        score += 10
    elif breakout and rvol >= 1.2:
        score += 6
    elif not breakout and pullback_vol_ok:
        score += 7
    elif not breakout:
        score += 4

    detail = {
        "vol_score":        min(score, 10),
        "rvol":             round(rvol, 2),
        "vol20_avg":        round(vol20, 0),
        "pullback_vol_ok":  pullback_vol_ok,
    }
    return min(score, 10), detail


# ── Risk/Reward Screen (15 pts) ───────────────────────────────────────────────

def _rr_screen(cmp: float, entry: float, stop: float,
               resistance: float) -> tuple[int, dict]:
    if stop >= entry or entry <= 0:
        return 0, {"rr_score": 0, "rr": 0.0, "signal": "NO TRADE"}

    risk_pct   = (entry - stop) / entry * 100
    target1    = entry + 1.5 * (entry - stop)
    target2    = entry + 2.5 * (entry - stop)
    rr         = (target1 - entry) / (entry - stop)

    # Resistance check: is target1 blocked by resistance?
    dist_to_res = (resistance - entry) / entry * 100 if resistance > entry else 100.0

    score = 0
    if rr >= 2.0:
        score += 15
    elif rr >= 1.5:
        score += 10
    elif rr >= 1.0:
        score += 5

    # Penalise if resistance is too close
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
    if df.empty or len(df) < 60:
        return None

    wdf = _weekly(df)
    if len(wdf) < 15:
        return None

    w_score, w_det = _weekly_screen(wdf)
    trend = w_det.get("weekly_trend", "NEUTRAL")

    # Reject non-bullish weekly trends
    if trend in ("BEARISH", "STRONG BEARISH", "NEUTRAL"):
        return None

    d_score, d_det = _daily_screen(df)
    # Require at least one strong daily pullback signal
    if d_score < 6:
        return None

    pa_score, pa_det, entry, stop, resistance = _price_action_screen(df)
    breakout = pa_det.get("breakout_20d", False)
    v_score,  v_det  = _volume_screen(df, breakout)

    cmp = live_ltp if live_ltp > 0 else float(df["close"].iloc[-1])
    rr_score, rr_det = _rr_screen(cmp, entry, stop, resistance)

    if rr_det.get("signal") == "NO TRADE":
        return None

    total = w_score + d_score + pa_score + v_score + rr_score

    close  = df["close"]
    prev   = float(close.iloc[-2]) if len(df) > 1 else cmp
    pct    = round((cmp - prev) / prev * 100, 2) if prev else 0.0

    atr_s  = _atr(df)
    atr_v  = round(float(atr_s.iloc[-1]), 2)

    high52 = float(df["high"].tail(252).max())
    low52  = float(df["low"].tail(252).min())
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
        "weekly_score":  w_score,
        "daily_score":   d_score,
        "pa_score":      pa_score,
        "vol_score":     v_score,
        "rr_score":      rr_score,
        # detail dicts for explanation panel
        "_weekly":       w_det,
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
            df       = await get_historical_df(ikey, interval="day", days=_HIST_DAYS)
            live_ltp = ltp_map.get(ikey, {}).get("last_price", 0.0)
            return _analyse(df, symbol, row.get("company_name", symbol),
                            row.get("sector", ""), ikey, live_ltp)
        except Exception as e:
            logger.debug(f"Elder scan error {symbol}: {e}")
            return None


async def run_elder_scan() -> tuple[pd.DataFrame, dict]:
    """
    Returns (scan_df, chart_store).
    scan_df: one row per qualifying stock, sorted by score desc.
    chart_store: {symbol: chart_df_with_indicators}
    """
    symbols_df = await get_nifty200_symbols()
    if symbols_df.empty:
        return pd.DataFrame(), {}

    all_keys = symbols_df["instrument_key"].tolist()
    await bulk_prefetch_today_ohlc(all_keys)
    ltp_raw = await get_ltp(all_keys)

    sem     = asyncio.Semaphore(50)
    tasks   = [_process(row, ltp_raw, sem) for _, row in symbols_df.iterrows()]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    records     = [r for r in results if isinstance(r, dict)]
    chart_store = {}
    clean       = []

    for r in records:
        chart_store[r["symbol"]] = r.pop("_chart_df")
        # keep detail dicts in the record for the explanation panel
        clean.append(r)

    if not clean:
        return pd.DataFrame(), {}

    df = pd.DataFrame(clean).sort_values("score", ascending=False).reset_index(drop=True)
    logger.info(f"Elder scan: {len(df)} setups from {len(symbols_df)} stocks")
    return df, chart_store
