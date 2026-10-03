"""
Intraday Scanner - Heikin-Ashi Reversal Strategy

New Logic:
- Past 3 HA candles are red (bearish)
- Previous candle is green (bullish reversal)
- Current candle has no wick (or minimal wick) and crossed above previous candle close

Works in two modes:
1. Market Hours: Uses live 1-minute data aggregated to 10-minute
2. Market Closed: Uses historical 1-minute data from last trading day, aggregated to 10-minute
"""
import asyncio
import pandas as pd
import numpy as np
from datetime import datetime, time as dt_time, timedelta
from loguru import logger

from services.instruments import get_nifty200_symbols
from services.market_data import get_quotes, parse_quote


def _is_market_open() -> bool:
    """
    Check if market is currently open (9:15 AM - 3:30 PM IST, Mon-Fri)
    """
    now = datetime.now()
    
    # Check if weekday (Monday=0, Sunday=6)
    if now.weekday() >= 5:  # Saturday or Sunday
        return False
    
    # Market hours: 9:15 AM to 3:30 PM
    market_open = dt_time(9, 15)
    market_close = dt_time(15, 30)
    current_time = now.time()
    
    return market_open <= current_time <= market_close


def _aggregate_to_10min(df_1min: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate 1-minute candles to 10-minute candles
    
    Args:
        df_1min: DataFrame with 1-minute OHLCV data
    
    Returns:
        DataFrame with 10-minute OHLCV data
    """
    if df_1min.empty:
        return pd.DataFrame()
    
    # Ensure datetime is the index
    df = df_1min.copy()
    df['datetime'] = pd.to_datetime(df['datetime'])
    df = df.set_index('datetime')
    
    # Aggregate to 10-minute candles
    df_10min = df.resample('10min').agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum'
    })
    
    # Remove empty candles (where all values are NaN)
    df_10min = df_10min.dropna(subset=['open', 'close'])
    
    # Reset index to get datetime as column
    df_10min = df_10min.reset_index()
    
    return df_10min


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


def _is_red_candle(ha_open: float, ha_close: float) -> bool:
    """Check if HA candle is red (bearish)"""
    return ha_close < ha_open


def _is_green_candle(ha_open: float, ha_close: float) -> bool:
    """Check if HA candle is green (bullish)"""
    return ha_close > ha_open


def _has_no_wick(ha_open: float, ha_low: float, tolerance: float = 0.01) -> bool:
    """
    Check if candle has no lower wick (or minimal wick)
    For a bullish candle, HA open should be at or very close to HA low
    """
    return abs(ha_open - ha_low) <= tolerance


def _check_reversal_conditions(ha_df: pd.DataFrame) -> tuple[bool, dict]:
    """
    Check if reversal conditions are met:
    1. Past 3 HA candles [-4, -3, -2] are red (bearish)
    2. Previous candle [-1] is green (bullish reversal)
    3. Current candle [0] is green
    4. Current candle has no lower wick (HA open = HA low)
    5. Current candle crossed above previous candle close
    
    Returns:
        tuple: (conditions_met, debug_info)
    """
    if len(ha_df) < 5:  # Need at least 5 candles
        return False, {"error": "Not enough candles"}
    
    # Get last 5 candles (index -5 to -1)
    candles = []
    for i in range(-5, 0):
        candles.append({
            'open': ha_df.iloc[i]['ha_open'],
            'close': ha_df.iloc[i]['ha_close'],
            'high': ha_df.iloc[i]['ha_high'],
            'low': ha_df.iloc[i]['ha_low'],
        })
    
    # Check conditions
    # Past 3 candles [-5, -4, -3] are red
    cond1_red1 = _is_red_candle(candles[0]['open'], candles[0]['close'])
    cond1_red2 = _is_red_candle(candles[1]['open'], candles[1]['close'])
    cond1_red3 = _is_red_candle(candles[2]['open'], candles[2]['close'])
    cond1 = cond1_red1 and cond1_red2 and cond1_red3
    
    # Previous candle [-2] (index 3) is green
    cond2 = _is_green_candle(candles[3]['open'], candles[3]['close'])
    
    # Current candle [-1] (index 4) is green
    cond3 = _is_green_candle(candles[4]['open'], candles[4]['close'])
    
    # Current candle has no lower wick
    cond4 = _has_no_wick(candles[4]['open'], candles[4]['low'], tolerance=0.01)
    
    # Current candle crossed above previous candle close
    cond5 = candles[4]['close'] > candles[3]['close']
    
    debug_info = {
        'cond1_3_red_candles': cond1,
        'cond2_prev_green': cond2,
        'cond3_curr_green': cond3,
        'cond4_no_wick': cond4,
        'cond5_crossed_above': cond5,
        'candle_-5': f"{'RED' if cond1_red1 else 'GREEN'} O:{candles[0]['open']:.2f} C:{candles[0]['close']:.2f}",
        'candle_-4': f"{'RED' if cond1_red2 else 'GREEN'} O:{candles[1]['open']:.2f} C:{candles[1]['close']:.2f}",
        'candle_-3': f"{'RED' if cond1_red3 else 'GREEN'} O:{candles[2]['open']:.2f} C:{candles[2]['close']:.2f}",
        'candle_-2_prev': f"{'GREEN' if cond2 else 'RED'} O:{candles[3]['open']:.2f} C:{candles[3]['close']:.2f}",
        'candle_-1_curr': f"{'GREEN' if cond3 else 'RED'} O:{candles[4]['open']:.2f} C:{candles[4]['close']:.2f} L:{candles[4]['low']:.2f}",
        'wick_diff': round(abs(candles[4]['open'] - candles[4]['low']), 4),
    }
    
    return cond1 and cond2 and cond3 and cond4 and cond5, debug_info


async def _get_quote_data(instrument_key: str) -> dict:
    """Get current quote data for TBQ and TSQ"""
    try:
        quotes = await get_quotes([instrument_key])
        if quotes and len(quotes) > 0:
            quote = parse_quote(quotes[0])
            return {
                'tbq': quote.get('total_buy_quantity', 0),
                'tsq': quote.get('total_sell_quantity', 0),
            }
    except Exception as e:
        logger.debug(f"Could not fetch quote data: {e}")
    
    return {'tbq': 0, 'tsq': 0}


def _analyse_stock(df: pd.DataFrame, symbol: str, company_name: str,
                   sector: str, instrument_key: str, quote_data: dict) -> dict | None:
    """
    Analyze stock for Intraday reversal strategy
    
    Returns signal dict if conditions are met, None otherwise
    """
    if df.empty or len(df) < 5:  # Need at least 5 candles
        return None
    
    try:
        # Calculate Heikin-Ashi
        ha_df = _calculate_heikin_ashi(df)
        
        # Check reversal conditions
        is_signal, debug = _check_reversal_conditions(ha_df)
        
        if is_signal:
            logger.info(f"✅ {symbol} - BUY SIGNAL FOUND!")
            logger.info(f"   Debug: {debug}")
        
        if not is_signal:
            return None
        
        # Get current price and market data
        current_price = df.iloc[-1]['close']
        prev_close = df.iloc[-2]['close'] if len(df) > 1 else current_price
        pct_change = ((current_price - prev_close) / prev_close * 100) if prev_close > 0 else 0
        
        # Calculate TBQ/TSQ ratio
        tbq = quote_data.get('tbq', 0)
        tsq = quote_data.get('tsq', 0)
        tbq_tsq_ratio = (tbq / tsq) if tsq > 0 else 0
        
        return {
            "symbol": symbol,
            "company_name": company_name,
            "sector": sector,
            "instrument_key": instrument_key,
            "signal": "BUY",  # Only BUY signals for reversal
            "price": round(current_price, 2),
            "change_pct": round(pct_change, 2),
            "ha_open": round(ha_df.iloc[-1]['ha_open'], 2),
            "ha_close": round(ha_df.iloc[-1]['ha_close'], 2),
            "ha_high": round(ha_df.iloc[-1]['ha_high'], 2),
            "ha_low": round(ha_df.iloc[-1]['ha_low'], 2),
            "tbq": tbq,
            "tsq": tsq,
            "tbq_tsq_ratio": round(tbq_tsq_ratio, 2),
        }
        
    except Exception as e:
        logger.error(f"Intraday scan error {symbol}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None


async def _process_stock(row: pd.Series, sem: asyncio.Semaphore, is_market_open: bool) -> dict | None:
    """Process single stock - uses live data if market open, EOD data if closed"""
    async with sem:
        symbol = row.get("symbol", "")
        ikey = row.get("instrument_key", "")
        
        try:
            if is_market_open:
                # Market is open: Use 1-minute live data aggregated to 10-minute
                from services.market_data import get_intraday_df
                
                df_1min = await get_intraday_df(ikey, interval="1minute")
                
                if df_1min.empty:
                    return None
                
                # Aggregate to 10-minute
                df = _aggregate_to_10min(df_1min)
                
                # Need at least 5 candles (50 minutes) to check pattern
                if len(df) < 5:
                    return None
                    
            else:
                # Market is closed: Use 1-minute historical data from last completed day
                from api.upstox_client import get_client
                
                # Get last trading day (try yesterday first, then go back up to 5 days)
                today = datetime.now()
                client = get_client()
                df_1min = pd.DataFrame()
                
                for days_back in range(1, 6):  # Try last 5 days
                    test_date = today - timedelta(days=days_back)
                    
                    # Skip weekends
                    if test_date.weekday() >= 5:
                        continue
                    
                    test_date_str = test_date.strftime('%Y-%m-%d')
                    
                    try:
                        result = await client.get_historical_candles(
                            instrument_key=ikey,
                            interval="1minute",
                            from_date=test_date_str,
                            to_date=test_date_str
                        )
                        
                        if result and result.get("status") == "success":
                            candles = result.get("data", {}).get("candles", [])
                            if candles:
                                # Found data for this date
                                df_1min = pd.DataFrame(
                                    candles, 
                                    columns=["datetime", "open", "high", "low", "close", "volume", "oi"]
                                )
                                df_1min["datetime"] = pd.to_datetime(df_1min["datetime"])
                                df_1min = df_1min.sort_values("datetime").reset_index(drop=True)
                                for col in ["open", "high", "low", "close", "volume"]:
                                    df_1min[col] = pd.to_numeric(df_1min[col], errors="coerce")
                                
                                break  # Found data, stop searching
                    except Exception as e:
                        continue
                
                if df_1min.empty:
                    return None
                
                # Aggregate to 10-minute (same as live mode)
                df = _aggregate_to_10min(df_1min)
                
                # Need at least 5 candles
                if df.empty or len(df) < 5:
                    return None
            
            # Get quote data for TBQ/TSQ (only works in live mode)
            quote_data = await _get_quote_data(ikey) if is_market_open else {'tbq': 0, 'tsq': 0}
            
            # Analyze with same logic regardless of data source
            result = _analyse_stock(
                df, symbol,
                row.get("company_name", symbol),
                row.get("sector", ""),
                ikey,
                quote_data
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Intraday scan error {symbol}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None


async def run_short_term_scan() -> pd.DataFrame:
    """
    Run Intraday HA reversal scan on NIFTY 200
    
    Modes:
    - Market Open (9:15 AM - 3:30 PM): Uses live 1-min data aggregated to 10-min
    - Market Closed: Uses historical 1-min data from last trading day
    
    Returns: DataFrame with BUY signals only
    """
    # Check if market is open
    is_market_open = _is_market_open()
    mode = "LIVE" if is_market_open else "EOD"
    
    logger.info(f"Starting Intraday reversal scan in {mode} mode...")
    
    # Get universe
    nifty200 = await get_nifty200_symbols()
    
    # Scan stocks concurrently
    sem = asyncio.Semaphore(20)
    tasks = [_process_stock(row, sem, is_market_open) for _, row in nifty200.iterrows()]
    results = await asyncio.gather(*tasks)
    
    # Filter valid results
    valid = [r for r in results if r is not None]
    logger.info(f"Intraday reversal scan ({mode}): {len(valid)} BUY signals found")
    
    if not valid:
        return pd.DataFrame()
    
    # Create DataFrame
    df = pd.DataFrame(valid)
    
    # Sort by TBQ/TSQ ratio (highest first) if live mode, otherwise by symbol
    if is_market_open and 'tbq_tsq_ratio' in df.columns:
        df = df.sort_values('tbq_tsq_ratio', ascending=False).reset_index(drop=True)
    else:
        df = df.sort_values('symbol').reset_index(drop=True)
    
    return df
