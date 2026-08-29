"""
Master Swing Trader Scanner - Alan Farley's Methodology
From "The Master Swing Trader"

Farley's Core Swing Trading Principles:
1. Pattern Cycles (3D Charting - Price/Time/Volume)
2. Support/Resistance zones
3. Fibonacci retracements
4. Gap strategies
5. Momentum oscillators
6. Trend alignment across timeframes

Score breakdown (0-100):
- Trend Alignment: 25 pts
- Pattern Recognition: 25 pts  
- Support/Resistance: 20 pts
- Momentum/Volume: 15 pts
- Risk/Reward Setup: 15 pts

Returns: Top 5 stocks
"""
import asyncio
import numpy as np
import pandas as pd
from loguru import logger

from services.instruments import get_nifty200_symbols
from services.market_data import get_historical_df, bulk_prefetch_today_ohlc, get_quotes, parse_quote

_HIST_DAYS = 700  # ~100 weeks of data (weekly timeframe)
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


def _rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Calculate RSI"""
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))


def _stochastic(df: pd.DataFrame, period: int = 14) -> tuple[pd.Series, pd.Series]:
    """Calculate Stochastic Oscillator"""
    low_min = df["low"].rolling(window=period).min()
    high_max = df["high"].rolling(window=period).max()
    k = 100 * (df["close"] - low_min) / (high_max - low_min)
    d = k.rolling(window=3).mean()
    return k, d


def _fibonacci_levels(high: float, low: float) -> dict:
    """Calculate Fibonacci retracement levels"""
    diff = high - low
    return {
        "0.0": high,
        "23.6": high - 0.236 * diff,
        "38.2": high - 0.382 * diff,
        "50.0": high - 0.500 * diff,
        "61.8": high - 0.618 * diff,
        "78.6": high - 0.786 * diff,
        "100.0": low,
    }


def _swing_highs(series: pd.Series, order: int = 3) -> list[int]:
    vals = series.values
    highs = []
    for i in range(order, len(vals) - order):
        if vals[i] == max(vals[i - order: i + order + 1]):
            highs.append(i)
    return highs


def _swing_lows(series: pd.Series, order: int = 3) -> list[int]:
    vals = series.values
    lows = []
    for i in range(order, len(vals) - order):
        if vals[i] == min(vals[i - order: i + order + 1]):
            lows.append(i)
    return lows


# ── 1. TREND ALIGNMENT (25 pts) ───────────────────────────────────────────────

def _trend_alignment(df: pd.DataFrame) -> tuple[int, dict]:
    """
    Farley's trend alignment across multiple timeframes
    - Price vs moving averages (20, 50, 200 EMA)
    - Trend consistency
    - ADX for trend strength
    """
    if len(df) < 200:
        return 0, {"score": 0}
    
    close = df["close"]
    price = close.iloc[-1]
    
    ema20 = _ema(close, 20).iloc[-1]
    ema50 = _ema(close, 50).iloc[-1]
    ema200 = _ema(close, 200).iloc[-1]
    
    # Trend alignment checks
    price_above_20 = price > ema20
    price_above_50 = price > ema50
    price_above_200 = price > ema200
    ema20_above_50 = ema20 > ema50
    ema50_above_200 = ema50 > ema200
    
    # Recent price action (last 5 bars)
    recent_trend = (close.iloc[-1] > close.iloc[-6])
    
    # ADX for trend strength
    high, low = df["high"], df["low"]
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low - close.shift()).abs(),
    ], axis=1).max(axis=1)
    
    dm_plus = (high.diff()).clip(lower=0).where(high.diff() > (-low.diff()), 0)
    dm_minus = (-low.diff()).clip(lower=0).where(-low.diff() > high.diff(), 0)
    
    atr14 = tr.ewm(span=14, adjust=False).mean()
    di_plus = 100 * _ema(dm_plus, 14) / atr14
    di_minus = 100 * _ema(dm_minus, 14) / atr14
    dx = (100 * (di_plus - di_minus).abs() / (di_plus + di_minus + 1e-9))
    adx = _ema(dx, 14).iloc[-1]
    
    strong_trend = adx > 25
    
    # Score
    score = 0
    if price_above_20:
        score += 5
    if price_above_50:
        score += 5
    if price_above_200:
        score += 5
    if ema20_above_50 and ema50_above_200:
        score += 5
    if recent_trend:
        score += 3
    if strong_trend:
        score += 2
    
    detail = {
        "score": score,
        "price_above_emas": f"{int(price_above_20)}/{int(price_above_50)}/{int(price_above_200)}",
        "ema_alignment": ema20_above_50 and ema50_above_200,
        "adx": round(adx, 1),
        "trend_strength": "Strong" if strong_trend else "Weak",
    }
    
    return score, detail


# ── 2. PATTERN RECOGNITION (25 pts) ───────────────────────────────────────────

def _pattern_recognition(df: pd.DataFrame) -> tuple[int, dict]:
    """
    Farley's pattern cycles (adapted for weekly timeframe):
    - Bull/Bear flags
    - Cup and handle
    - Ascending/Descending triangles
    - Double bottom/top
    - Consolidation patterns
    """
    if len(df) < 30:
        return 0, {"score": 0, "pattern": "None"}
    
    close = df["close"]
    high = df["high"]
    low = df["low"]
    
    # Find swing points
    sh_idx = _swing_highs(high, order=2)  # Weekly: less strict order
    sl_idx = _swing_lows(low, order=2)
    
    if len(sh_idx) < 2 or len(sl_idx) < 2:
        return 0, {"score": 0, "pattern": "Insufficient data"}
    
    # Check for consolidation (tight range) - weekly: last 8-12 weeks
    recent_bars = min(12, len(df))
    recent_high = high.tail(recent_bars).max()
    recent_low = low.tail(recent_bars).min()
    range_pct = ((recent_high - recent_low) / recent_low) * 100
    
    consolidating = range_pct < 15  # Weekly: slightly wider range acceptable
    
    # Check for ascending pattern (higher lows) - need at least 2
    recent_lows = [low.iloc[idx] for idx in sl_idx[-2:]] if len(sl_idx) >= 2 else []
    ascending = False
    if len(recent_lows) >= 2:
        ascending = recent_lows[-1] > recent_lows[-2]
    
    # Check for uptrend (price action over last 20 weeks)
    lookback = min(20, len(df))
    price_20w_ago = close.iloc[-lookback] if len(df) >= lookback else close.iloc[0]
    uptrend = close.iloc[-1] > price_20w_ago * 1.05  # Up at least 5% over period
    
    # Check for pullback and recovery
    lookback_short = min(8, len(df))
    recent_low_price = low.tail(lookback_short).min()
    recent_high_price = high.tail(lookback_short).max()
    current_price = close.iloc[-1]
    
    # Near recent highs after pullback
    near_highs = current_price > recent_high_price * 0.92
    had_pullback = (recent_high_price - recent_low_price) / recent_high_price > 0.08
    
    pullback_recovery = near_highs and had_pullback
    
    # Volume pattern (decreasing during consolidation)
    vol_recent = df["volume"].tail(4).mean()  # Last 4 weeks
    vol_avg = df["volume"].tail(20).mean()    # 20 week average
    vol_drying_up = vol_recent < vol_avg * 0.85
    
    # Price above key moving average (bullish structure)
    ema50 = _ema(close, 50)
    price_above_ema50 = close.iloc[-1] > ema50.iloc[-1] if len(ema50) > 0 else False
    
    # Determine pattern and score
    pattern = "None"
    score = 0
    
    # Best setups (score well)
    if pullback_recovery and uptrend and consolidating:
        pattern = "Pullback in Uptrend"
        score = 22
    elif ascending and consolidating and price_above_ema50:
        pattern = "Ascending Base"
        score = 20
    elif uptrend and consolidating:
        pattern = "Bull Flag"
        score = 18
    elif pullback_recovery and uptrend:
        pattern = "Bounce Setup"
        score = 15
    elif ascending and price_above_ema50:
        pattern = "Higher Lows"
        score = 12
    elif consolidating and price_above_ema50:
        pattern = "Consolidation"
        score = 10
    elif uptrend:
        pattern = "Uptrend"
        score = 8
    
    # Bonus for volume contraction during consolidation
    if consolidating and vol_drying_up and score > 0:
        score = min(25, score + 3)
    
    detail = {
        "score": score,
        "pattern": pattern,
        "consolidating": consolidating,
        "range_pct": round(range_pct, 1),
        "ascending": ascending,
        "uptrend": uptrend,
        "vol_drying_up": vol_drying_up,
    }
    
    return score, detail


# ── 3. SUPPORT/RESISTANCE (20 pts) ────────────────────────────────────────────

def _support_resistance(df: pd.DataFrame) -> tuple[int, dict]:
    """
    Farley's S/R analysis with Fibonacci
    - Key support/resistance levels
    - Fibonacci retracements
    - Distance from support
    """
    if len(df) < 50:
        return 0, {"score": 0}
    
    close = df["close"]
    high = df["high"]
    low = df["low"]
    price = close.iloc[-1]
    
    # Recent swing high/low
    lookback = min(100, len(df))
    swing_high = high.tail(lookback).max()
    swing_low = low.tail(lookback).min()
    
    # Fibonacci levels
    fib = _fibonacci_levels(swing_high, swing_low)
    
    # Find closest Fibonacci level
    fib_distances = {level: abs(price - value) / price * 100 
                     for level, value in fib.items()}
    closest_fib = min(fib_distances, key=fib_distances.get)
    closest_dist = fib_distances[closest_fib]
    
    # Find support (highest swing low below price)
    swing_lows = [low.iloc[idx] for idx in _swing_lows(low, order=3) if low.iloc[idx] < price]
    support = max(swing_lows) if swing_lows else swing_low
    
    # Find resistance (lowest swing high above price)
    swing_highs = [high.iloc[idx] for idx in _swing_highs(high, order=3) if high.iloc[idx] > price]
    resistance = min(swing_highs) if swing_highs else swing_high
    
    # Distance from support
    dist_from_support = ((price - support) / support) * 100
    dist_to_resistance = ((resistance - price) / price) * 100
    
    # Score based on position
    score = 0
    
    # Near support (good risk/reward)
    if dist_from_support < 5:
        score += 10
    elif dist_from_support < 10:
        score += 7
    
    # Room to resistance
    if dist_to_resistance > 10:
        score += 10
    elif dist_to_resistance > 5:
        score += 5
    
    # Near key Fibonacci level
    if closest_dist < 2 and closest_fib in ["38.2", "50.0", "61.8"]:
        score += 5
    
    detail = {
        "score": min(20, score),
        "support": round(support, 2),
        "resistance": round(resistance, 2),
        "dist_from_support_pct": round(dist_from_support, 1),
        "dist_to_resistance_pct": round(dist_to_resistance, 1),
        "closest_fib": closest_fib,
        "fib_levels": {k: round(v, 2) for k, v in fib.items()},
    }
    
    return min(20, score), detail


# ── 4. MOMENTUM/VOLUME (15 pts) ───────────────────────────────────────────────

def _momentum_volume(df: pd.DataFrame) -> tuple[int, dict]:
    """
    Farley's momentum and volume analysis (adapted for weekly)
    - RSI (40-70 range ideal for swing longs)
    - Stochastic crossovers
    - Volume trend
    """
    if len(df) < 20:
        return 0, {"score": 0}
    
    close = df["close"]
    
    # RSI - on weekly, look for not overbought but positive
    rsi = _rsi(close, 14).iloc[-1]
    rsi_bullish = 35 < rsi < 75  # Slightly wider range for weekly
    rsi_very_bullish = 50 < rsi < 65  # Sweet spot
    
    # Stochastic - weekly timeframe
    k, d = _stochastic(df, 14)
    k_now = k.iloc[-1]
    d_now = d.iloc[-1]
    k_prev = k.iloc[-2] if len(k) > 1 else k_now
    d_prev = d.iloc[-2] if len(d) > 1 else d_now
    
    stoch_bullish_cross = k_now > d_now and k_prev <= d_prev and k_now < 80
    stoch_in_bullish_zone = k_now > 50 and k_now < 80
    
    # Volume - weekly
    vol = df["volume"]
    vol_recent = vol.tail(4).mean()   # Last 4 weeks
    vol_avg = vol.tail(20).mean()     # 20 week average
    vol_ratio = vol_recent / vol_avg if vol_avg > 0 else 1.0
    
    vol_increasing = vol_ratio > 1.1  # 10% above average
    vol_strong = vol_ratio > 1.3      # 30% above average
    
    # Price momentum (last 8 weeks)
    lookback = min(8, len(close))
    price_momentum = ((close.iloc[-1] - close.iloc[-lookback]) / close.iloc[-lookback]) * 100
    positive_momentum = price_momentum > 3  # Up 3%+ in 8 weeks
    strong_momentum = price_momentum > 8    # Up 8%+ in 8 weeks
    
    # Score
    score = 0
    if rsi_very_bullish:
        score += 6
    elif rsi_bullish:
        score += 4
    
    if stoch_bullish_cross:
        score += 4
    elif stoch_in_bullish_zone:
        score += 2
    
    if vol_strong:
        score += 3
    elif vol_increasing:
        score += 2
    
    if strong_momentum:
        score += 2
    elif positive_momentum:
        score += 1
    
    detail = {
        "score": min(15, score),
        "rsi": round(rsi, 1),
        "stoch_k": round(k_now, 1),
        "stoch_d": round(d_now, 1),
        "vol_ratio": round(vol_ratio, 2),
        "momentum_8w": round(price_momentum, 1),
    }
    
    return min(15, score), detail


# ── 5. RISK/REWARD SETUP (15 pts) ─────────────────────────────────────────────

def _risk_reward_setup(df: pd.DataFrame, support: float, resistance: float) -> tuple[int, dict]:
    """
    Farley's risk/reward analysis
    - Proper stop placement
    - Target potential
    - Risk/reward ratio >= 2:1
    """
    if len(df) < 10:
        return 0, {"score": 0, "signal": "NO TRADE"}
    
    close = df["close"]
    price = close.iloc[-1]
    
    # Entry and stop based on support
    entry = price
    atr = _atr(df, 14).iloc[-1]
    
    # Stop below support with 2% buffer OR 2 ATR below entry (whichever is CLOSER to entry)
    stop_at_support = support * 0.98
    stop_at_atr = entry - 2 * atr
    stop = max(stop_at_support, stop_at_atr)  # BUG FIX: was min(), should be max() to get tighter stop
    
    # Targets based on resistance and ATR
    target1 = min(resistance * 0.98, entry + 3 * atr)
    target2 = resistance * 1.02
    
    # Risk/Reward calculation
    risk = entry - stop
    reward1 = target1 - entry
    reward2 = target2 - entry
    
    if risk <= 0:
        return 0, {"score": 0, "signal": "NO TRADE", "rr": 0}
    
    rr1 = reward1 / risk
    rr2 = reward2 / risk
    risk_pct = (risk / entry) * 100
    
    # Score based on R:R
    score = 0
    if rr1 >= 3:
        score = 15
        signal = "STRONG BUY"
    elif rr1 >= 2:
        score = 12
        signal = "BUY"
    elif rr1 >= 1.5:
        score = 8
        signal = "WATCH"
    else:
        score = 0
        signal = "NO TRADE"
    
    # Penalty for high risk
    if risk_pct > 10:
        score = max(0, score - 5)
    
    detail = {
        "score": score,
        "entry": round(entry, 2),
        "stop": round(stop, 2),
        "target1": round(target1, 2),
        "target2": round(target2, 2),
        "risk_reward": round(rr1, 2),
        "risk_pct": round(risk_pct, 1),
        "signal": signal,
    }
    
    return score, detail


# ── MAIN ANALYSIS ─────────────────────────────────────────────────────────────

def _analyse_stock(df: pd.DataFrame, symbol: str, company_name: str,
                   sector: str, instrument_key: str) -> dict | None:
    """
    Farley Master Swing Trader Analysis
    
    Score breakdown (0-100):
    - Trend Alignment: 25 pts
    - Pattern Recognition: 25 pts
    - Support/Resistance: 20 pts
    - Momentum/Volume: 15 pts
    - Risk/Reward: 15 pts
    """
    
    if df.empty or len(df) < 50:
        return None
    
    # Run all swing trading components
    trend_score, trend_detail = _trend_alignment(df)
    pattern_score, pattern_detail = _pattern_recognition(df)
    sr_score, sr_detail = _support_resistance(df)
    momentum_score, momentum_detail = _momentum_volume(df)
    
    support = sr_detail.get("support", 0)
    resistance = sr_detail.get("resistance", 0)
    rr_score, rr_detail = _risk_reward_setup(df, support, resistance)
    
    # Calculate total score
    total_score = trend_score + pattern_score + sr_score + momentum_score + rr_score
    
    # Farley's grading
    if total_score >= 80:
        grade = "Master Setup"
    elif total_score >= 70:
        grade = "Strong Setup"
    elif total_score >= 60:
        grade = "Good Setup"
    elif total_score >= 50:
        grade = "Watchlist"
    elif total_score >= 40:
        grade = "Monitor"
    else:
        grade = "Pass"
    
    # Signal determination
    signal = rr_detail.get("signal", "NO TRADE")
    
    # Return stocks with score 40+ so user can evaluate
    # Focus on those 50+ for actual trades, but show 40-49 for monitoring
    if total_score < 40:
        return None
    
    # Price data
    close = df["close"].iloc[-1]
    prev = df["close"].iloc[-2] if len(df) > 1 else close
    pct_change = round((close - prev) / prev * 100, 2) if prev > 0 else 0
    
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
        
        # Swing components
        "trend_score": trend_score,
        "trend_detail": trend_detail,
        "pattern_score": pattern_score,
        "pattern_detail": pattern_detail,
        "sr_score": sr_score,
        "sr_detail": sr_detail,
        "momentum_score": momentum_score,
        "momentum_detail": momentum_detail,
        "rr_score": rr_score,
        "rr_detail": rr_detail,
        
        # Trade setup
        "entry": rr_detail.get("entry", close),
        "stop": rr_detail.get("stop", close * 0.95),
        "target1": rr_detail.get("target1", close * 1.10),
        "target2": rr_detail.get("target2", close * 1.20),
        "risk_reward": rr_detail.get("risk_reward", 0),
        "risk_pct": rr_detail.get("risk_pct", 0),
    }


# ── SCANNER EXECUTION ─────────────────────────────────────────────────────────

async def _process_stock(row: pd.Series, sem: asyncio.Semaphore) -> dict | None:
    """Process single stock"""
    async with sem:
        symbol = row.get("symbol", "")
        ikey = row.get("instrument_key", "")
        
        try:
            df = await get_historical_df(ikey, interval="week", days=_HIST_DAYS)
            if df.empty or len(df) < 50:
                return None
            
            result = _analyse_stock(
                df, symbol,
                row.get("company_name", symbol),
                row.get("sector", ""),
                ikey
            )
            
            return result
        except Exception as e:
            logger.debug(f"Swing scan error {symbol}: {e}")
            return None


async def run_swing_scan() -> tuple[pd.DataFrame, dict]:
    """
    Run Farley Master Swing Trader scan on NIFTY 200
    Returns: (DataFrame of TOP 5 stocks, metadata dict)
    """
    from datetime import date
    from database import save_scanner_signal
    
    logger.info("Starting Master Swing Trader scan...")
    
    # Get universe
    nifty200 = await get_nifty200_symbols()
    
    # Fetch live quotes instead of just today's OHLC
    ikeys = nifty200["instrument_key"].tolist()
    live_quotes = await get_quotes(ikeys)
    logger.info(f"Swing scan: fetched {len(live_quotes)} live quotes")
    
    # Scan stocks concurrently
    sem = asyncio.Semaphore(20)
    tasks = [_process_stock(row, sem) for _, row in nifty200.iterrows()]
    results = await asyncio.gather(*tasks)
    
    # Filter valid results
    valid = [r for r in results if r is not None]
    logger.info(f"Swing scan: {len(valid)} stocks analyzed")
    
    if not valid:
        return pd.DataFrame(), {}
    
    # Create DataFrame and sort by score
    df = pd.DataFrame(valid)
    df = df.sort_values("score", ascending=False).reset_index(drop=True)
    
    # Return TOP 5 ONLY (Farley-style focus on best setups)
    top5 = df.head(5)
    
    logger.info(f"Swing scan: Returning top 5 stocks out of {len(valid)} analyzed")
    
    # Fetch chart data for top 5
    chart_store = {}
    for _, row in top5.iterrows():
        symbol = row["symbol"]
        ikey = row["instrument_key"]
        try:
            cdf = await get_historical_df(ikey, interval="week", days=_CHART_BARS*7)
            if not cdf.empty:
                chart_store[symbol] = cdf.tail(_CHART_BARS)
        except Exception as e:
            logger.warning(f"Swing: Could not fetch chart for {symbol}: {e}")
    
    logger.info(f"Swing scan: Fetched charts for {len(chart_store)}/{len(top5)} stocks")
    
    # Save signals to database for backtesting
    today = str(date.today())
    for _, row in top5.iterrows():
        try:
            save_scanner_signal(
                signal_date=today,
                scanner_type="Swing",
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
            logger.warning(f"Failed to save Swing signal for {row['symbol']}: {e}")
    
    return top5, chart_store

