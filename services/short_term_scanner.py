"""
Short Term Scanner - Heikin-Ashi + Supertrend Strategy

Buy Conditions:
1. 1 day ago: HA open < Supertrend(10,2)
2. 1 day ago: HA close > Supertrend(10,2) [bullish crossover]
3. Current: HA open > Supertrend(10,2)
4. Current: HA close > HA open [bullish candle]
5. Current: Small lower wick (< 20% of candle range)

Sell Conditions:
1. 1 day ago: HA open > Supertrend(10,2)
2. 1 day ago: HA close < Supertrend(10,2) [bearish crossover]
3. Current: HA open < Supertrend(10,2)
4. Current: HA close < HA open [bearish candle]
5. Current: Small upper wick (< 20% of candle range)

Note: Condition 5 relaxed from "HA open == HA low/high" to "small wick < 20%"
      for daily timeframes where exact equality is too strict.
"""
import asyncio
import pandas as pd
import numpy as np
from loguru import logger

from services.instruments import get_nifty200_symbols
from services.market_data import get_historical_df, get_quotes, parse_quote


def _calculate_heikin_ashi(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate Heikin-Ashi candles"""
    ha_df = df.copy()
    
    # HA Close = (Open + High + Low + Close) / 4
    ha_df['ha_close'] = (df['open'] + df['high'] + df['low'] + df['close']) / 4
    
    # HA Open = (Previous HA Open + Previous HA Close) / 2
    ha_df['ha_open'] = 0.0
    ha_df.iloc[0, ha_df.columns.get_loc('ha_open')] = (df.iloc[0]['open'] + df.iloc[0]['close']) / 2
    
    for i in range(1, len(df)):
        ha_df.iloc[i, ha_df.columns.get_loc('ha_open')] = (
            ha_df.iloc[i-1]['ha_open'] + ha_df.iloc[i-1]['ha_close']
        ) / 2
    
    # HA High = Max(High, HA Open, HA Close)
    ha_df['ha_high'] = ha_df[['high', 'ha_open', 'ha_close']].max(axis=1)
    
    # HA Low = Min(Low, HA Open, HA Close)
    ha_df['ha_low'] = ha_df[['low', 'ha_open', 'ha_close']].min(axis=1)
    
    return ha_df


def _calculate_supertrend(df: pd.DataFrame, period: int = 10, multiplier: float = 2.0) -> pd.Series:
    """
    Calculate Supertrend indicator
    
    Args:
        df: DataFrame with OHLC data
        period: ATR period (default 10)
        multiplier: ATR multiplier (default 2.0)
    
    Returns:
        Series with Supertrend values
    """
    high = df['high']
    low = df['low']
    close = df['close']
    
    # Calculate ATR
    tr1 = high - low
    tr2 = abs(high - close.shift())
    tr3 = abs(low - close.shift())
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean()
    
    # Calculate basic upper and lower bands
    hl_avg = (high + low) / 2
    upper_band = hl_avg + (multiplier * atr)
    lower_band = hl_avg - (multiplier * atr)
    
    # Initialize Supertrend
    supertrend = pd.Series(index=df.index, dtype=float)
    direction = pd.Series(index=df.index, dtype=int)
    
    # First value
    supertrend.iloc[0] = lower_band.iloc[0]
    direction.iloc[0] = 1
    
    for i in range(1, len(df)):
        # Adjust bands based on previous values
        if close.iloc[i] > upper_band.iloc[i-1]:
            direction.iloc[i] = 1
        elif close.iloc[i] < lower_band.iloc[i-1]:
            direction.iloc[i] = -1
        else:
            direction.iloc[i] = direction.iloc[i-1]
            
            if direction.iloc[i] == 1 and lower_band.iloc[i] < lower_band.iloc[i-1]:
                lower_band.iloc[i] = lower_band.iloc[i-1]
            if direction.iloc[i] == -1 and upper_band.iloc[i] > upper_band.iloc[i-1]:
                upper_band.iloc[i] = upper_band.iloc[i-1]
        
        # Set Supertrend value
        if direction.iloc[i] == 1:
            supertrend.iloc[i] = lower_band.iloc[i]
        else:
            supertrend.iloc[i] = upper_band.iloc[i]
    
    return supertrend


def _check_buy_conditions(ha_df: pd.DataFrame, supertrend: pd.Series) -> tuple[bool, dict]:
    """
    Check if buy conditions are met
    
    Buy Conditions:
    1. 1 day ago: HA open < Supertrend
    2. 1 day ago: HA close > Supertrend (crossover)
    3. Current: HA open > Supertrend
    4. Current: HA close > HA open (bullish candle)
    5. Current: HA open close to HA low (small lower wick - relaxed for daily)
    
    Returns:
        tuple: (conditions_met, debug_info)
    """
    if len(ha_df) < 2:
        return False, {}
    
    # Previous day (index -2)
    prev_ha_open = ha_df.iloc[-2]['ha_open']
    prev_ha_close = ha_df.iloc[-2]['ha_close']
    prev_supertrend = supertrend.iloc[-2]
    
    # Current day (index -1)
    curr_ha_open = ha_df.iloc[-1]['ha_open']
    curr_ha_close = ha_df.iloc[-1]['ha_close']
    curr_ha_low = ha_df.iloc[-1]['ha_low']
    curr_ha_high = ha_df.iloc[-1]['ha_high']
    curr_supertrend = supertrend.iloc[-1]
    
    # Calculate candle range and lower wick size
    candle_range = curr_ha_high - curr_ha_low
    lower_wick = curr_ha_open - curr_ha_low
    lower_wick_pct = (lower_wick / candle_range * 100) if candle_range > 0 else 0
    
    # Check all buy conditions
    cond1 = prev_ha_open < prev_supertrend
    cond2 = prev_ha_close > prev_supertrend
    cond3 = curr_ha_open > curr_supertrend
    cond4 = curr_ha_close > curr_ha_open
    # Relaxed: lower wick should be < 20% of candle range (small wick acceptable)
    cond5 = lower_wick_pct < 20
    
    debug_info = {
        'cond1_prev_open_lt_st': cond1,
        'cond2_prev_close_gt_st': cond2,
        'cond3_curr_open_gt_st': cond3,
        'cond4_bullish_candle': cond4,
        'cond5_small_lower_wick': cond5,
        'lower_wick': round(lower_wick, 2),
        'lower_wick_pct': round(lower_wick_pct, 2),
        'candle_range': round(candle_range, 2)
    }
    
    return cond1 and cond2 and cond3 and cond4 and cond5, debug_info


def _check_sell_conditions(ha_df: pd.DataFrame, supertrend: pd.Series) -> tuple[bool, dict]:
    """
    Check if sell conditions are met
    
    Sell Conditions:
    1. 1 day ago: HA open > Supertrend
    2. 1 day ago: HA close < Supertrend (crossover)
    3. Current: HA open < Supertrend
    4. Current: HA close < HA open (bearish candle)
    5. Current: HA open close to HA high (small upper wick - relaxed for daily)
    
    Returns:
        tuple: (conditions_met, debug_info)
    """
    if len(ha_df) < 2:
        return False, {}
    
    # Previous day (index -2)
    prev_ha_open = ha_df.iloc[-2]['ha_open']
    prev_ha_close = ha_df.iloc[-2]['ha_close']
    prev_supertrend = supertrend.iloc[-2]
    
    # Current day (index -1)
    curr_ha_open = ha_df.iloc[-1]['ha_open']
    curr_ha_close = ha_df.iloc[-1]['ha_close']
    curr_ha_high = ha_df.iloc[-1]['ha_high']
    curr_ha_low = ha_df.iloc[-1]['ha_low']
    curr_supertrend = supertrend.iloc[-1]
    
    # Calculate candle range and upper wick size
    candle_range = curr_ha_high - curr_ha_low
    upper_wick = curr_ha_high - curr_ha_open
    upper_wick_pct = (upper_wick / candle_range * 100) if candle_range > 0 else 0
    
    # Check all sell conditions
    cond1 = prev_ha_open > prev_supertrend
    cond2 = prev_ha_close < prev_supertrend
    cond3 = curr_ha_open < curr_supertrend
    cond4 = curr_ha_close < curr_ha_open
    # Relaxed: upper wick should be < 20% of candle range (small wick acceptable)
    cond5 = upper_wick_pct < 20
    
    debug_info = {
        'cond1_prev_open_gt_st': cond1,
        'cond2_prev_close_lt_st': cond2,
        'cond3_curr_open_lt_st': cond3,
        'cond4_bearish_candle': cond4,
        'cond5_small_upper_wick': cond5,
        'upper_wick': round(upper_wick, 2),
        'upper_wick_pct': round(upper_wick_pct, 2),
        'candle_range': round(candle_range, 2)
    }
    
    return cond1 and cond2 and cond3 and cond4 and cond5, debug_info


def _analyse_stock(df: pd.DataFrame, symbol: str, company_name: str,
                   sector: str, instrument_key: str) -> dict | None:
    """
    Analyze stock for Short Term strategy
    
    Returns signal dict if conditions are met, None otherwise
    """
    if df.empty or len(df) < 20:
        return None
    
    try:
        # Calculate Heikin-Ashi
        ha_df = _calculate_heikin_ashi(df)
        
        # Calculate Supertrend (10, 2)
        supertrend = _calculate_supertrend(df, period=10, multiplier=2.0)
        
        # Check conditions with debug info
        is_buy, buy_debug = _check_buy_conditions(ha_df, supertrend)
        is_sell, sell_debug = _check_sell_conditions(ha_df, supertrend)
        
        # Log first few stocks for debugging
        if symbol in ['RELIANCE', 'TCS', 'INFY', 'HDFCBANK', 'ICICIBANK']:
            logger.info(f"{symbol} - BUY debug: {buy_debug}")
            logger.info(f"{symbol} - SELL debug: {sell_debug}")
        
        if not is_buy and not is_sell:
            return None
        
        # Get current price
        current_price = df.iloc[-1]['close']
        prev_close = df.iloc[-2]['close'] if len(df) > 1 else current_price
        pct_change = ((current_price - prev_close) / prev_close * 100) if prev_close > 0 else 0
        
        # Determine signal
        signal = "BUY" if is_buy else "SELL"
        
        # Calculate stop loss and target
        curr_supertrend = supertrend.iloc[-1]
        
        if is_buy:
            entry = current_price
            stop = curr_supertrend
            target = entry + (entry - stop) * 2  # 2:1 risk-reward
        else:  # is_sell
            entry = current_price
            stop = curr_supertrend
            target = entry - (stop - entry) * 2  # 2:1 risk-reward
        
        return {
            "symbol": symbol,
            "company_name": company_name,
            "sector": sector,
            "instrument_key": instrument_key,
            "signal": signal,
            "entry": round(entry, 2),
            "stop": round(stop, 2),
            "target": round(target, 2),
            "price": round(current_price, 2),
            "change_pct": round(pct_change, 2),
            "supertrend": round(curr_supertrend, 2),
            "ha_open": round(ha_df.iloc[-1]['ha_open'], 2),
            "ha_close": round(ha_df.iloc[-1]['ha_close'], 2),
            "ha_high": round(ha_df.iloc[-1]['ha_high'], 2),
            "ha_low": round(ha_df.iloc[-1]['ha_low'], 2),
        }
        
    except Exception as e:
        logger.debug(f"Short term scan error {symbol}: {e}")
        return None


async def _process_stock(row: pd.Series, sem: asyncio.Semaphore) -> dict | None:
    """Process single stock"""
    async with sem:
        symbol = row.get("symbol", "")
        ikey = row.get("instrument_key", "")
        
        try:
            # Get daily data for last 30 days
            df = await get_historical_df(ikey, interval="day", days=30)
            if df.empty or len(df) < 20:
                return None
            
            result = _analyse_stock(
                df, symbol,
                row.get("company_name", symbol),
                row.get("sector", ""),
                ikey
            )
            
            return result
        except Exception as e:
            logger.debug(f"Short term scan error {symbol}: {e}")
            return None


async def run_short_term_scan() -> pd.DataFrame:
    """
    Run Short Term HA + Supertrend scan on NIFTY 200
    Returns: DataFrame with BUY and SELL signals
    """
    logger.info("Starting Short Term scan...")
    
    # Get universe
    nifty200 = await get_nifty200_symbols()
    
    # Scan stocks concurrently
    sem = asyncio.Semaphore(20)
    tasks = [_process_stock(row, sem) for _, row in nifty200.iterrows()]
    results = await asyncio.gather(*tasks)
    
    # Filter valid results
    valid = [r for r in results if r is not None]
    logger.info(f"Short term scan: {len(valid)} signals found")
    
    if not valid:
        return pd.DataFrame()
    
    # Create DataFrame
    df = pd.DataFrame(valid)
    
    # Sort: BUY signals first, then by symbol
    df['signal_order'] = df['signal'].map({'BUY': 0, 'SELL': 1})
    df = df.sort_values(['signal_order', 'symbol']).reset_index(drop=True)
    df = df.drop('signal_order', axis=1)
    
    logger.info(f"Short term scan: {len(df[df['signal']=='BUY'])} BUY, {len(df[df['signal']=='SELL'])} SELL signals")
    
    return df
