"""
SEPA Stock Screener - Mark Minervini's Specific Entry Point Analysis
From "Trade Like a Stock Market Wizard"

Minervini's SEPA Criteria:
1. Trend Template (Stage 2 uptrend) - 25 pts
2. Relative Strength vs Market - 20 pts  
3. Volatility Contraction Pattern (VCP) - 25 pts
4. Pivot Point / Constructive Base - 15 pts
5. Volume Characteristics - 15 pts

Total: 100 pts
Display: Top 10 stocks only
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


# ── 1. MINERVINI TREND TEMPLATE (25 pts) ──────────────────────────────────────

def _trend_template(df: pd.DataFrame) -> tuple[int, dict]:
    """
    Minervini's 8-Point Trend Template (Stage 2 Uptrend):
    1. Price > 150-day MA and Price > 200-day MA
    2. 150-day MA > 200-day MA
    3. 200-day MA trending up for at least 1 month
    4. 50-day MA > 150-day MA and 50-day MA > 200-day MA
    5. Price > 50-day MA
    6. Price at least 30% above 52-week low
    7. Price within 25% of 52-week high
    8. Strong relative performance (RS >= 70)
    
    Each condition ~3 points, Total = 25 pts
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
    
    # Calculate conditions
    cond1 = price > sma150 and price > sma200
    cond2 = sma150 > sma200
    cond3 = sma200_up
    cond4 = sma50 > sma150 and sma50 > sma200
    cond5 = price > sma50
    cond6 = price >= low_52w * 1.30
    cond7 = price >= high_52w * 0.75
    
    # RS placeholder (use 3/6 month performance as proxy)
    ret_3m = ((close.iloc[-1] / close.iloc[-63]) - 1) * 100 if len(df) >= 63 else 0
    ret_6m = ((close.iloc[-1] / close.iloc[-126]) - 1) * 100 if len(df) >= 126 else 0
    cond8 = ret_3m > 15 and ret_6m > 25  # Strong performance
    
    conditions = [cond1, cond2, cond3, cond4, cond5, cond6, cond7, cond8]
    passed = sum(conditions)
    
    # Score: 3 points per condition (8 conditions = 24, round to 25)
    score = int(passed * 3.125)
    
    detail = {
        "passed": passed,
        "total": 8,
        "score": score,
        "conditions": {
            "price_above_ma": cond1,
            "ma150_above_ma200": cond2,
            "ma200_trending_up": cond3,
            "ma50_above_long_ma": cond4,
            "price_above_ma50": cond5,
            "30pct_above_low": cond6,
            "within_25pct_high": cond7,
            "strong_rs": cond8,
        },
        "values": {
            "price": round(price, 2),
            "sma50": round(sma50, 2),
            "sma150": round(sma150, 2),
            "sma200": round(sma200, 2),
            "high_52w": round(high_52w, 2),
            "low_52w": round(low_52w, 2),
            "dist_from_high_pct": round(((price - high_52w) / high_52w) * 100, 1),
            "dist_from_low_pct": round(((price - low_52w) / low_52w) * 100, 1),
        },
    }
    
    return score, detail


# ── 2. RELATIVE STRENGTH (20 pts) ─────────────────────────────────────────────

def _relative_strength(df: pd.DataFrame) -> tuple[int, dict]:
    """
    Minervini's Relative Strength:
    - IBD RS Rating equivalent (0-99 scale)
    - Weighted average of 3/6/9/12 month returns
    - Weights recent performance higher
    
    RS > 80: 20 pts (Top 20%)
    RS 70-80: 15 pts (Top 30%)
    RS 60-70: 10 pts
    RS 50-60: 5 pts
    RS < 50: 0 pts
    """
    if len(df) < 63:
        return 0, {"rs_rating": 0}
    
    close = df["close"]
    
    # Calculate returns
    ret_3m = ((close.iloc[-1] / close.iloc[-63]) - 1) * 100 if len(df) >= 63 else 0
    ret_6m = ((close.iloc[-1] / close.iloc[-126]) - 1) * 100 if len(df) >= 126 else 0
    ret_9m = ((close.iloc[-1] / close.iloc[-189]) - 1) * 100 if len(df) >= 189 else 0
    ret_12m = ((close.iloc[-1] / close.iloc[-252]) - 1) * 100 if len(df) >= 252 else 0
    
    # Weighted RS (Minervini weights recent performance higher)
    # 40% last 3m, 30% last 6m, 20% last 9m, 10% last 12m
    weighted_return = (ret_3m * 0.4) + (ret_6m * 0.3) + (ret_9m * 0.2) + (ret_12m * 0.1)
    
    # Convert to RS rating (approximate IBD RS)
    if weighted_return >= 40:
        rs_rating = min(99, 80 + (weighted_return - 40) / 3)
    elif weighted_return >= 20:
        rs_rating = 60 + (weighted_return - 20)
    elif weighted_return >= 0:
        rs_rating = 50 + (weighted_return / 2)
    else:
        rs_rating = max(0, 50 + weighted_return)
    
    # Score based on RS rating
    if rs_rating >= 80:
        score = 20
    elif rs_rating >= 70:
        score = 15
    elif rs_rating >= 60:
        score = 10
    elif rs_rating >= 50:
        score = 5
    else:
        score = 0
    
    detail = {
        "rs_rating": round(rs_rating, 0),
        "weighted_return": round(weighted_return, 1),
        "ret_3m": round(ret_3m, 1),
        "ret_6m": round(ret_6m, 1),
        "ret_9m": round(ret_9m, 1),
        "ret_12m": round(ret_12m, 1),
        "score": score,
    }
    
    return score, detail


# ── 3. VCP PATTERN (25 pts) ───────────────────────────────────────────────────

def _vcp_pattern(df: pd.DataFrame) -> tuple[int, dict]:
    """
    Minervini's Volatility Contraction Pattern:
    - 2-4+ contractions (pullbacks getting tighter)
    - Each pullback smaller than previous
    - Volume drying up on pullbacks
    - Tight price action near highs
    - Proper base structure (3+ weeks minimum)
    
    Perfect VCP (tight, 3-4 contractions): 25 pts
    Good VCP (2-3 contractions): 15-20 pts
    Developing VCP: 5-10 pts
    No VCP: 0 pts
    """
    if len(df) < 60:
        return 0, {"vcp_detected": False, "contractions": []}
    
    # Look at last 60-100 bars for base
    window = df.tail(100)
    highs = window["high"].values
    
    # Find swing highs
    high_peaks = _swing_highs(window["high"], order=3)
    
    if len(high_peaks) < 3:
        return 0, {"vcp_detected": False, "contractions": [], "num_contractions": 0}
    
    # Calculate contraction depths between consecutive highs
    contractions = []
    for i in range(len(high_peaks) - 1):
        idx1 = high_peaks[i]
        idx2 = high_peaks[i + 1]
        high1 = highs[idx1]
        low_between = window["low"].iloc[idx1:idx2+1].min()
        contraction_pct = ((high1 - low_between) / high1) * 100
        
        # Minervini looks for contractions 8-25%
        if 3 <= contraction_pct <= 30:
            contractions.append(contraction_pct)
    
    if len(contractions) < 2:
        return 0, {"vcp_detected": False, "contractions": contractions, "num_contractions": len(contractions)}
    
    # Check if contractions are tightening (each smaller than previous)
    is_tightening = all(contractions[i] < contractions[i-1] for i in range(1, len(contractions)))
    
    # Check tightness of last contraction
    last_contraction = contractions[-1] if contractions else 0
    
    vcp_detected = is_tightening and len(contractions) >= 2
    
    # Score based on VCP quality
    if vcp_detected:
        if len(contractions) >= 4 and last_contraction < 8:
            score = 25  # Perfect VCP
        elif len(contractions) >= 3 and last_contraction < 12:
            score = 20  # Strong VCP
        elif len(contractions) >= 3:
            score = 15  # Good VCP
        elif len(contractions) >= 2 and last_contraction < 15:
            score = 10  # Developing VCP
        else:
            score = 5   # Weak VCP
    else:
        score = 0
    
    detail = {
        "vcp_detected": vcp_detected,
        "num_contractions": len(contractions),
        "contractions": [round(c, 1) for c in contractions[-4:]],  # Last 4
        "is_tightening": is_tightening,
        "last_contraction_pct": round(last_contraction, 1),
        "score": score,
        "quality": "Perfect" if score >= 20 else ("Good" if score >= 15 else ("Developing" if score > 0 else "None")),
    }
    
    return score, detail


# ── 4. PIVOT POINT & BASE (15 pts) ────────────────────────────────────────────

def _pivot_point(df: pd.DataFrame) -> tuple[int, dict]:
    """
    Minervini's Pivot Point:
    - Constructive base (3-12 weeks ideal)
    - Price near pivot (within 5%)
    - Breakout with volume
    - Proper base depth (10-40% ideal)
    
    At Pivot + Volume: 15 pts
    Near Pivot (within 5%): 10 pts
    In Base: 5 pts
    Extended: 0 pts
    """
    if len(df) < 50:
        return 0, {"status": "Unknown"}
    
    # Find recent high (pivot point)
    window = df.tail(60)
    pivot = window["high"].max()
    
    price = df["close"].iloc[-1]
    vol_recent = df["volume"].iloc[-5:].mean()
    vol_avg = df["volume"].iloc[-50:].mean()
    vol_ratio = vol_recent / vol_avg if vol_avg > 0 else 1.0
    
    dist_to_pivot = ((price - pivot) / pivot) * 100
    
    # Check if breaking out
    if dist_to_pivot >= -1 and dist_to_pivot <= 2 and vol_ratio > 1.2:
        score = 15
        status = "Breakout"
    elif dist_to_pivot >= -5 and dist_to_pivot <= 0:
        score = 10
        status = "At Pivot"
    elif dist_to_pivot >= -15 and dist_to_pivot < -5:
        score = 5
        status = "In Base"
    elif dist_to_pivot < -15:
        score = 2
        status = "Deep Base"
    else:
        score = 0
        status = "Extended"
    
    detail = {
        "pivot": round(pivot, 2),
        "price": round(price, 2),
        "dist_to_pivot_pct": round(dist_to_pivot, 2),
        "vol_ratio": round(vol_ratio, 2),
        "status": status,
        "score": score,
    }
    
    return score, detail


# ── 5. VOLUME ANALYSIS (15 pts) ───────────────────────────────────────────────

def _volume_analysis(df: pd.DataFrame) -> tuple[int, dict]:
    """
    Minervini Volume Characteristics:
    - Dry-up on pullbacks (volume below average)
    - Accumulation (up days on higher volume)
    - Pocket pivot characteristics
    
    Excellent volume profile: 15 pts
    Good: 10 pts
    Average: 5 pts
    Poor: 0 pts
    """
    if len(df) < 50:
        return 0, {"classification": "Unknown"}
    
    # Volume dry-up on recent bars
    vol_recent = df["volume"].iloc[-10:].mean()
    vol_avg = df["volume"].iloc[-50:].mean()
    dryup_ratio = vol_recent / vol_avg if vol_avg > 0 else 1.0
    
    # Accumulation/Distribution (up days vs down days volume)
    recent_20 = df.tail(20).copy()
    recent_20["price_change"] = recent_20["close"].diff()
    up_days = recent_20[recent_20["price_change"] > 0]
    down_days = recent_20[recent_20["price_change"] < 0]
    
    up_vol = up_days["volume"].sum() if len(up_days) > 0 else 1
    down_vol = down_days["volume"].sum() if len(down_days) > 0 else 1
    accum_ratio = up_vol / (down_vol + 1)
    
    # Score
    if dryup_ratio < 0.7 and accum_ratio > 1.5:
        score = 15  # Excellent: dry-up + accumulation
    elif dryup_ratio < 0.8 and accum_ratio > 1.2:
        score = 10  # Good
    elif dryup_ratio < 1.0 or accum_ratio > 1.0:
        score = 5   # Average
    else:
        score = 0   # Poor
    
    detail = {
        "dryup_ratio": round(dryup_ratio, 2),
        "accum_ratio": round(accum_ratio, 2),
        "classification": "Excellent" if score >= 15 else ("Good" if score >= 10 else ("Average" if score > 0 else "Poor")),
        "score": score,
    }
    
    return score, detail


# ── MAIN ANALYSIS ─────────────────────────────────────────────────────────────

def _analyse_stock(df: pd.DataFrame, symbol: str, company_name: str,
                   sector: str, instrument_key: str) -> dict | None:
    """
    Minervini SEPA Analysis
    
    Score breakdown (0-100):
    - Trend Template: 25 pts
    - Relative Strength: 20 pts
    - VCP Pattern: 25 pts
    - Pivot Point: 15 pts
    - Volume: 15 pts
    """
    
    if df.empty or len(df) < 60:
        logger.debug(f"{symbol}: Insufficient data ({len(df)} bars)")
        return None
    
    # Run all SEPA components
    trend_score, trend_detail = _trend_template(df)
    rs_score, rs_detail = _relative_strength(df)
    vcp_score, vcp_detail = _vcp_pattern(df)
    pivot_score, pivot_detail = _pivot_point(df)
    volume_score, volume_detail = _volume_analysis(df)
    
    # Calculate total SEPA score (0-100)
    total_score = trend_score + rs_score + vcp_score + pivot_score + volume_score
    
    # Minervini's grading
    if total_score >= 80:
        grade = "Superperformer"  # Elite SEPA setup
    elif total_score >= 70:
        grade = "Strong Buy"      # High probability
    elif total_score >= 60:
        grade = "Buy"             # Good setup
    elif total_score >= 50:
        grade = "Watchlist"       # Potential
    else:
        grade = "Pass"            # Not ready
    
    # Minervini's entry signal
    trend_passed = trend_detail["passed"]
    vcp_detected = vcp_detail["vcp_detected"]
    at_pivot = pivot_detail["status"] in ["Breakout", "At Pivot"]
    
    if trend_passed >= 7 and vcp_detected and at_pivot and volume_score >= 10:
        signal = "BUY NOW"
    elif trend_passed >= 6 and vcp_detected and pivot_detail["dist_to_pivot_pct"] >= -10:
        signal = "BUY ON BREAKOUT"
    elif trend_passed >= 5 and total_score >= 60:
        signal = "WATCH"
    else:
        signal = "PASS"
    
    # Price data
    close = df["close"].iloc[-1]
    prev = df["close"].iloc[-2] if len(df) > 1 else close
    pct_change = round((close - prev) / prev * 100, 2) if prev > 0 else 0
    
    # Risk/Reward (Minervini style: 2-3 ATR stop)
    atr_val = _atr(df, 14).iloc[-1]
    entry = pivot_detail["pivot"]
    stop = round(entry - 2.5 * atr_val, 2) if atr_val > 0 else round(entry * 0.92, 2)
    target1 = round(entry * 1.20, 2)  # 20% profit target
    target2 = round(entry * 1.40, 2)  # 40% extended target
    risk = entry - stop
    reward = target1 - entry
    risk_reward = round(reward / risk, 2) if risk > 0 else 0
    
    return {
        "symbol": symbol,
        "company_name": company_name,
        "sector": sector,
        "instrument_key": instrument_key,
        "score": total_score,
        "grade": grade,
        "signal": signal,
        
        "price": round(close, 2),
        "change_pct": pct_change,
        
        # SEPA components
        "trend_score": trend_score,
        "trend_detail": trend_detail,
        "rs_score": rs_score,
        "rs_detail": rs_detail,
        "vcp_score": vcp_score,
        "vcp_detail": vcp_detail,
        "pivot_score": pivot_score,
        "pivot_detail": pivot_detail,
        "volume_score": volume_score,
        "volume_detail": volume_detail,
        
        # Trade setup
        "entry": entry,
        "stop": stop,
        "target1": target1,
        "target2": target2,
        "risk_reward": risk_reward,
        "risk_pct": round((risk / entry) * 100, 1) if entry > 0 else 0,
    }


# ── SCANNER EXECUTION ─────────────────────────────────────────────────────────

async def _process_stock(row: pd.Series, sem: asyncio.Semaphore) -> dict | None:
    """Process single stock"""
    async with sem:
        symbol = row.get("symbol", "")
        ikey = row.get("instrument_key", "")
        
        try:
            df = await get_historical_df(ikey, interval="day", days=_HIST_DAYS)
            if df.empty or len(df) < 60:
                return None
            
            result = _analyse_stock(
                df, symbol,
                row.get("company_name", symbol),
                row.get("sector", ""),
                ikey
            )
            
            return result
        except Exception as e:
            logger.debug(f"SEPA scan error {symbol}: {e}")
            return None


async def run_sepa_scan() -> tuple[pd.DataFrame, dict]:
    """
    Run Minervini SEPA scan on NIFTY 200
    Returns: (DataFrame of TOP 10 stocks, chart_store dict)
    """
    logger.info("Starting Minervini SEPA scan...")
    
    # Get universe
    nifty200 = await get_nifty200_symbols()
    
    # Prefetch today's prices
    ikeys = nifty200["instrument_key"].tolist()
    today_map = await bulk_prefetch_today_ohlc(ikeys)
    today_count = today_map if isinstance(today_map, int) else len(today_map)
    logger.info(f"SEPA scan: prefetched {today_count} today's candles")
    
    # Scan stocks concurrently
    sem = asyncio.Semaphore(20)
    tasks = [_process_stock(row, sem) for _, row in nifty200.iterrows()]
    results = await asyncio.gather(*tasks)
    
    # Filter valid results
    valid = [r for r in results if r is not None]
    logger.info(f"SEPA scan: {len(valid)} stocks analyzed")
    
    if not valid:
        return pd.DataFrame(), {}
    
    # Create DataFrame and sort by score
    df = pd.DataFrame(valid)
    df = df.sort_values("score", ascending=False).reset_index(drop=True)
    
    # Return TOP 10 ONLY (Minervini-style focus on best setups)
    top10 = df.head(10)
    
    logger.info(f"SEPA scan: Returning top 10 stocks out of {len(valid)} analyzed")
    
    # Fetch chart data for top 10
    chart_store = {}
    for _, row in top10.iterrows():
        symbol = row["symbol"]
        ikey = row["instrument_key"]
        try:
            cdf = await get_historical_df(ikey, interval="day", days=_CHART_BARS)
            if not cdf.empty:
                chart_store[symbol] = cdf.tail(_CHART_BARS)
        except Exception as e:
            logger.warning(f"SEPA: Could not fetch chart for {symbol}: {e}")
    
    logger.info(f"SEPA scan: Fetched charts for {len(chart_store)}/{len(top10)} stocks")
    
    return top10, chart_store
