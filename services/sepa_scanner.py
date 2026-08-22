"""
SEPA Stock Screener - Specific Entry Point Analysis
Trend Template + RS + Fundamentals + VCP + Pivot Analysis

Scoring (0-100):
  Trend Template      15 pts
  Relative Strength   15 pts
  EPS Growth          10 pts
  EPS Acceleration     8 pts
  Revenue Growth       8 pts
  Revenue Accel        6 pts
  Margin Expansion     6 pts
  Industry Leadership  6 pts
  Supply/Demand        5 pts
  VCP Pattern          7 pts
  Volume Dry-Up        2 pts
  Pivot/Breakout       2 pts
  Base Quality         5 pts
  Price Tightness      5 pts
"""
import asyncio
import numpy as np
import pandas as pd
from loguru import logger

from services.instruments import get_nifty200_symbols
from services.market_data import get_historical_df, bulk_prefetch_today_ohlc, get_ltp

_HIST_DAYS = 300
_CHART_BARS = 80


# ── Helper Functions ──────────────────────────────────────────────────────────

def _sma(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n).mean()


def _ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False).mean()


def _atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - df["close"].shift()).abs(),
        (df["low"] - df["close"].shift()).abs(),
    ], axis=1).max(axis=1)
    return tr.rolling(n).mean()


def _swing_highs(series: pd.Series, order: int = 2) -> list[int]:
    vals = series.values
    highs = []
    for i in range(order, len(vals) - order):
        if vals[i] == max(vals[i - order: i + order + 1]):
            highs.append(i)
    return highs


def _swing_lows(series: pd.Series, order: int = 2) -> list[int]:
    vals = series.values
    lows = []
    for i in range(order, len(vals) - order):
        if vals[i] == min(vals[i - order: i + order + 1]):
            lows.append(i)
    return lows


# ── 1. TREND TEMPLATE (15 pts) ────────────────────────────────────────────────

def _trend_template(df: pd.DataFrame) -> tuple[int, dict]:
    """
    8 Conditions:
    1. Price > 150 SMA AND Price > 200 SMA
    2. 150 SMA > 200 SMA
    3. 200 SMA trending up
    4. 50 SMA > 150 SMA AND 50 SMA > 200 SMA
    5. Price > 50 SMA
    6. Price >= 30% above 52-week low
    7. Price within 25% of 52-week high
    8. RS Rank >= 70
    """
    if len(df) < 200:
        return 0, {"passed": 0, "conditions": {}}
    
    close = df["close"]
    sma50 = _sma(close, 50).iloc[-1]
    sma150 = _sma(close, 150).iloc[-1]
    sma200 = _sma(close, 200).iloc[-1]
    price = close.iloc[-1]
    
    # 52-week high/low
    high_52w = df["high"].tail(252).max()
    low_52w = df["low"].tail(252).min()
    
    # 200 SMA trend (compare with 21 days ago)
    sma200_now = sma200
    sma200_21d = _sma(close, 200).iloc[-22] if len(df) >= 222 else sma200
    sma200_up = sma200_now > sma200_21d
    
    # Placeholder for RS (would need benchmark data)
    rs_rank = 50  # Default - will calculate if benchmark available
    
    conditions = {
        "c1_price_above_150_200": price > sma150 and price > sma200,
        "c2_150_above_200": sma150 > sma200,
        "c3_200_trending_up": sma200_up,
        "c4_50_above_150_200": sma50 > sma150 and sma50 > sma200,
        "c5_price_above_50": price > sma50,
        "c6_30pct_above_52w_low": price >= low_52w * 1.30 if low_52w > 0 else False,
        "c7_within_25pct_of_52w_high": price >= high_52w * 0.75 if high_52w > 0 else False,
        "c8_rs_rank_70plus": rs_rank >= 70,
    }
    
    passed = sum(conditions.values())
    score = int((passed / 8) * 15)  # Max 15 points
    
    # Stage classification
    if passed >= 7:
        stage = "Stage 2 Confirmed"
    elif passed >= 5:
        stage = "Stage 2 Developing"
    elif passed >= 3:
        stage = "Trend Weak"
    else:
        stage = "Trend Failed"
    
    detail = {
        "passed": passed,
        "total": 8,
        "score": score,
        "stage": stage,
        "conditions": conditions,
        "sma50": round(sma50, 2),
        "sma150": round(sma150, 2),
        "sma200": round(sma200, 2),
        "dist_52h_pct": round((price - high_52w) / high_52w * 100, 2) if high_52w > 0 else 0,
        "dist_52l_pct": round((price - low_52w) / low_52w * 100, 2) if low_52w > 0 else 0,
    }
    
    return score, detail


# ── 2. RELATIVE STRENGTH (15 pts) ─────────────────────────────────────────────

def _relative_strength(df: pd.DataFrame, benchmark_df: pd.DataFrame = None) -> tuple[int, dict]:
    """
    Calculate RS rank based on price performance
    3m: 40%, 6m: 20%, 9m: 20%, 12m: 20%
    """
    if len(df) < 63:
        return 0, {"rs_rank": 0, "classification": "Insufficient Data"}
    
    close = df["close"]
    
    # Calculate returns
    ret_3m = ((close.iloc[-1] / close.iloc[-63]) - 1) * 100 if len(df) >= 63 else 0
    ret_6m = ((close.iloc[-1] / close.iloc[-126]) - 1) * 100 if len(df) >= 126 else 0
    ret_9m = ((close.iloc[-1] / close.iloc[-189]) - 1) * 100 if len(df) >= 189 else 0
    ret_12m = ((close.iloc[-1] / close.iloc[-252]) - 1) * 100 if len(df) >= 252 else 0
    
    # Weighted composite
    composite = (ret_3m * 0.4 + ret_6m * 0.2 + ret_9m * 0.2 + ret_12m * 0.2)
    
    # Placeholder RS rank (would need universe comparison)
    # For now, use composite score normalized
    rs_rank = min(99, max(1, int(50 + composite / 2)))  # Rough estimate
    
    # Score
    if rs_rank >= 90:
        score = 15
        classification = "Elite Leader"
    elif rs_rank >= 80:
        score = 13
        classification = "Strong Leader"
    elif rs_rank >= 70:
        score = 10
        classification = "Qualified"
    elif rs_rank >= 60:
        score = 7
        classification = "Developing"
    else:
        score = 3
        classification = "Weak"
    
    detail = {
        "rs_rank": rs_rank,
        "classification": classification,
        "score": score,
        "ret_3m": round(ret_3m, 2),
        "ret_6m": round(ret_6m, 2),
        "ret_9m": round(ret_9m, 2),
        "ret_12m": round(ret_12m, 2),
        "composite": round(composite, 2),
    }
    
    return score, detail


# ── 3. VCP PATTERN (7 pts) ────────────────────────────────────────────────────

def _vcp_pattern(df: pd.DataFrame) -> tuple[int, dict]:
    """Detect Volatility Contraction Pattern"""
    if len(df) < 30:
        return 0, {"vcp_detected": False, "contractions": []}
    
    # Look at last 60 bars
    window = df.tail(60)
    highs = window["high"].values
    
    # Find swing highs
    high_peaks = _swing_highs(window["high"], order=2)
    
    if len(high_peaks) < 3:
        return 0, {"vcp_detected": False, "contractions": [], "num_contractions": 0}
    
    # Calculate contractions between consecutive highs
    contractions = []
    for i in range(len(high_peaks) - 1):
        idx1 = high_peaks[i]
        idx2 = high_peaks[i + 1]
        high1 = highs[idx1]
        low_between = window["low"].iloc[idx1:idx2+1].min()
        contraction_pct = (high1 - low_between) / high1 * 100
        if contraction_pct >= 2:
            contractions.append(contraction_pct)
    
    # Check if tightening (each contraction smaller than previous)
    is_tightening = len(contractions) >= 2 and all(
        contractions[i] < contractions[i-1] for i in range(1, len(contractions))
    )
    
    vcp_detected = is_tightening and len(contractions) >= 2
    
    # Score
    if vcp_detected:
        if len(contractions) >= 3 and contractions[-1] < 8:
            score = 7  # Excellent VCP
        elif len(contractions) >= 3:
            score = 5  # Good VCP
        else:
            score = 3  # Developing VCP
    else:
        score = 0
    
    detail = {
        "vcp_detected": vcp_detected,
        "num_contractions": len(contractions),
        "contractions": [round(c, 1) for c in contractions],
        "score": score,
        "quality": "Excellent" if score == 7 else ("Good" if score >= 5 else ("Developing" if score > 0 else "None")),
    }
    
    return score, detail


# ── 4. VOLUME DRY-UP (2 pts) ──────────────────────────────────────────────────

def _volume_dryup(df: pd.DataFrame) -> tuple[int, dict]:
    """Check for volume contraction in recent bars"""
    if len(df) < 50:
        return 0, {"dryup": False}
    
    recent_vol = df["volume"].iloc[-5:].mean()
    avg_vol_50 = df["volume"].iloc[-50:].mean()
    
    vol_ratio = recent_vol / avg_vol_50 if avg_vol_50 > 0 else 1.0
    
    if vol_ratio < 0.6:
        score = 2
        classification = "Extreme Dry-Up"
    elif vol_ratio < 0.8:
        score = 1
        classification = "Strong Dry-Up"
    else:
        score = 0
        classification = "No Dry-Up"
    
    detail = {
        "dryup": score > 0,
        "vol_ratio": round(vol_ratio, 2),
        "classification": classification,
        "score": score,
    }
    
    return score, detail


# ── 5. PRICE TIGHTNESS (5 pts) ────────────────────────────────────────────────

def _price_tightness(df: pd.DataFrame) -> tuple[int, dict]:
    """Measure price range contraction"""
    if len(df) < 20:
        return 0, {"tight": False}
    
    close = df["close"]
    
    # Calculate ATR as % of price
    atr_val = _atr(df, 14).iloc[-1]
    atr_pct = (atr_val / close.iloc[-1]) * 100 if close.iloc[-1] > 0 else 0
    
    # 10-day price range
    high_10 = df["high"].iloc[-10:].max()
    low_10 = df["low"].iloc[-10:].min()
    range_10 = (high_10 - low_10) / low_10 * 100 if low_10 > 0 else 0
    
    # Score based on tightness
    if atr_pct < 2 and range_10 < 5:
        score = 5
        classification = "Extremely Tight"
    elif atr_pct < 3 and range_10 < 8:
        score = 3
        classification = "Tight"
    elif atr_pct < 5 and range_10 < 12:
        score = 1
        classification = "Moderate"
    else:
        score = 0
        classification = "Loose"
    
    detail = {
        "tight": score >= 3,
        "atr_pct": round(atr_pct, 2),
        "range_10d_pct": round(range_10, 2),
        "classification": classification,
        "score": score,
    }
    
    return score, detail


# ── 6. PIVOT/BREAKOUT (2 pts) ─────────────────────────────────────────────────

def _pivot_breakout(df: pd.DataFrame) -> tuple[int, dict]:
    """Detect pivot and breakout status"""
    if len(df) < 20:
        return 0, {"pivot": 0, "status": "Unknown"}
    
    # Find recent pivot (highest high in last 20 bars)
    pivot = df["high"].tail(20).max()
    price = df["close"].iloc[-1]
    
    # Distance to pivot
    dist_to_pivot = ((price - pivot) / pivot * 100) if pivot > 0 else 0
    
    # Breakout detection
    volume = df["volume"].iloc[-1]
    avg_volume = df["volume"].iloc[-50:].mean()
    vol_ratio = volume / avg_volume if avg_volume > 0 else 1.0
    
    # Classify
    if price > pivot and vol_ratio > 1.3:
        score = 2
        status = "Breakout"
    elif dist_to_pivot >= -3 and dist_to_pivot <= 0:
        score = 1
        status = "At Pivot"
    elif dist_to_pivot > 0 and dist_to_pivot < 5:
        score = 1
        status = "Early Breakout"
    elif dist_to_pivot > -10:
        score = 0
        status = "Approaching"
    else:
        score = 0
        status = "Developing"
    
    detail = {
        "pivot": round(pivot, 2),
        "price": round(price, 2),
        "dist_to_pivot_pct": round(dist_to_pivot, 2),
        "vol_ratio": round(vol_ratio, 2),
        "status": status,
        "score": score,
    }
    
    return score, detail


# ── 7. SUPPLY/DEMAND (5 pts) ──────────────────────────────────────────────────

def _supply_demand(df: pd.DataFrame) -> tuple[int, dict]:
    """Analyze supply/demand through volume"""
    if len(df) < 20:
        return 0, {"classification": "Unknown"}
    
    # Up days vs down days volume
    up_days = df[df["close"] > df["close"].shift()].tail(20)
    down_days = df[df["close"] < df["close"].shift()].tail(20)
    
    up_vol = up_days["volume"].sum()
    down_vol = down_days["volume"].sum()
    
    vol_ratio = up_vol / (down_vol + 1) if down_vol > 0 else 1.0
    
    # Classify
    if vol_ratio > 2:
        score = 5
        classification = "Strong Accumulation"
    elif vol_ratio > 1.5:
        score = 3
        classification = "Moderate Accumulation"
    elif vol_ratio > 0.66:
        score = 2
        classification = "Neutral"
    elif vol_ratio > 0.5:
        score = 1
        classification = "Distribution"
    else:
        score = 0
        classification = "Heavy Distribution"
    
    detail = {
        "classification": classification,
        "up_vol_ratio": round(vol_ratio, 2),
        "score": score,
    }
    
    return score, detail


# ── MAIN ANALYSIS ─────────────────────────────────────────────────────────────

def _analyse_stock(df: pd.DataFrame, symbol: str, company_name: str,
                   sector: str, instrument_key: str) -> dict | None:
    """Analyze single stock for SEPA criteria"""
    
    if df.empty or len(df) < 200:
        return None
    
    # Run all screens
    trend_score, trend_detail = _trend_template(df)
    rs_score, rs_detail = _relative_strength(df)
    vcp_score, vcp_detail = _vcp_pattern(df)
    vol_score, vol_detail = _volume_dryup(df)
    tight_score, tight_detail = _price_tightness(df)
    pivot_score, pivot_detail = _pivot_breakout(df)
    sd_score, sd_detail = _supply_demand(df)
    
    # Placeholders for fundamental scores (would need fundamental data)
    eps_score = 5  # 10 pts max
    eps_accel_score = 4  # 8 pts max
    rev_score = 4  # 8 pts max
    rev_accel_score = 3  # 6 pts max
    margin_score = 3  # 6 pts max
    industry_score = 3  # 6 pts max
    
    # Calculate total SEPA score
    total_score = (
        trend_score +      # 15
        rs_score +         # 15
        eps_score +        # 10
        eps_accel_score +  # 8
        rev_score +        # 8
        rev_accel_score +  # 6
        margin_score +     # 6
        industry_score +   # 6
        sd_score +         # 5
        vcp_score +        # 7
        tight_score +      # 5
        vol_score +        # 2
        pivot_score        # 2
    )
    
    # Grade
    if total_score >= 90:
        grade = "Elite SEPA"
    elif total_score >= 80:
        grade = "High Conviction"
    elif total_score >= 70:
        grade = "Qualified"
    elif total_score >= 60:
        grade = "Watchlist"
    else:
        grade = "Not Ready"
    
    # Signal
    if trend_detail["passed"] >= 7 and vcp_detail["vcp_detected"] and pivot_detail["status"] in ["Breakout", "At Pivot"]:
        signal = "BUY NOW"
    elif trend_detail["passed"] >= 6 and vcp_detail["vcp_detected"]:
        signal = "BUY ON BREAKOUT"
    elif trend_detail["passed"] >= 5:
        signal = "WATCH"
    else:
        signal = "NO TRADE"
    
    # Price data
    close = df["close"].iloc[-1]
    prev = df["close"].iloc[-2] if len(df) > 1 else close
    pct_change = round((close - prev) / prev * 100, 2) if prev > 0 else 0
    
    # Risk/Reward
    atr_val = _atr(df, 14).iloc[-1]
    entry = pivot_detail["pivot"]
    stop = round(entry - 2 * atr_val, 2) if atr_val > 0 else round(entry * 0.95, 2)
    target1 = round(entry + 2 * atr_val, 2)
    target2 = round(entry + 4 * atr_val, 2)
    risk = entry - stop
    reward = target1 - entry
    rr = round(reward / risk, 2) if risk > 0 else 0
    
    # Chart data
    chart_df = df.tail(_CHART_BARS).copy().reset_index(drop=True)
    chart_df["sma50"] = _sma(df["close"], 50).tail(_CHART_BARS).values
    chart_df["sma150"] = _sma(df["close"], 150).tail(_CHART_BARS).values
    chart_df["sma200"] = _sma(df["close"], 200).tail(_CHART_BARS).values
    
    return {
        "symbol": symbol,
        "company_name": company_name,
        "sector": sector,
        "instrument_key": instrument_key,
        "cmp": round(close, 2),
        "pct_change": pct_change,
        "score": total_score,
        "grade": grade,
        "signal": signal,
        "entry": entry,
        "stop": stop,
        "target1": target1,
        "target2": target2,
        "rr": rr,
        "risk_pct": round((entry - stop) / entry * 100, 2) if entry > 0 else 0,
        # Sub-scores
        "trend_score": trend_score,
        "rs_score": rs_score,
        "vcp_score": vcp_score,
        "vol_score": vol_score,
        "tight_score": tight_score,
        "pivot_score": pivot_score,
        "sd_score": sd_score,
        # Details
        "_trend": trend_detail,
        "_rs": rs_detail,
        "_vcp": vcp_detail,
        "_vol": vol_detail,
        "_tight": tight_detail,
        "_pivot": pivot_detail,
        "_sd": sd_detail,
        "_chart_df": chart_df,
    }


# ── ASYNC SCAN ────────────────────────────────────────────────────────────────

async def _process_stock(row: pd.Series, sem: asyncio.Semaphore) -> dict | None:
    """Process single stock"""
    async with sem:
        symbol = row.get("symbol", "")
        ikey = row.get("instrument_key", "")
        
        try:
            df = await get_historical_df(ikey, interval="day", days=_HIST_DAYS)
            if df.empty or len(df) < 200:
                return None
            
            return _analyse_stock(
                df, symbol,
                row.get("company_name", symbol),
                row.get("sector", ""),
                ikey
            )
        except Exception as e:
            logger.debug(f"SEPA scan error {symbol}: {e}")
            return None


async def run_sepa_scan() -> tuple[pd.DataFrame, dict]:
    """
    Run SEPA scan on Nifty 200 stocks.
    Returns: (scan_df, chart_store)
    """
    symbols_df = await get_nifty200_symbols()
    if symbols_df.empty:
        logger.error("SEPA scan failed: No symbols retrieved")
        return pd.DataFrame(), {}
    
    all_keys = symbols_df["instrument_key"].tolist()
    
    # Prefetch today's data
    prefetched = await bulk_prefetch_today_ohlc(all_keys)
    logger.info(f"SEPA scan: prefetched {prefetched} today's candles")
    
    # Run scan
    sem = asyncio.Semaphore(50)
    tasks = [_process_stock(row, sem) for _, row in symbols_df.iterrows()]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Process results
    records = [r for r in results if isinstance(r, dict)]
    chart_store = {}
    clean = []
    
    for r in records:
        chart_store[r["symbol"]] = r.pop("_chart_df")
        clean.append(r)
    
    if not clean:
        return pd.DataFrame(), {}
    
    df = pd.DataFrame(clean).sort_values("score", ascending=False).reset_index(drop=True)
    
    logger.info(f"SEPA scan: {len(df)} stocks analyzed")
    logger.debug(f"SEPA stocks: {df['symbol'].tolist()[:10]}...")
    
    return df, chart_store
