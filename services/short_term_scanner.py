"""
Intraday Scanner - 10-minute Heikin-Ashi + EMA Strategy

Works in two modes:
1. Market Hours: Uses live 1-minute data aggregated to 10-minute (starts after 2 candles = 9:35 AM)
2. Market Closed: Uses historical 1-minute data from last trading day, aggregated to 10-minute

Both modes use the EXACT same 10-minute candle structure for accurate signals.

Sell Conditions:
1. Previous 10-min candle: HA open > 10-min EMA of HA close
2. Previous 10-min candle: HA close < 10-min EMA of HA close
3. Current 10-min candle: HA close < HA open (bearish)
4. Current 10-min candle: HA close < Previous HA close
5. Current 10-min candle: HA open = HA high (no upper wick)

Buy Conditions (reverse of sell):
1. Previous 10-min candle: HA open < 10-min EMA of HA close
2. Previous 10-min candle: HA close > 10-min EMA of HA close
3. Current 10-min candle: HA close > HA open (bullish)
4. Current 10-min candle: HA close > Previous HA close
5. Current 10-min candle: HA open = HA low (no lower wick)
"""
import asyncio
import pandas as pd
import numpy as np
from datetime import datetime, time as dt_time
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


def _calculate_ema_ha_close(ha_df: pd.DataFrame, period: int = 10) -> pd.Series:
    """
    Calculate EMA of Heikin-Ashi close values
    
    Args:
        ha_df: DataFrame with Heikin-Ashi OHLC data
        period: EMA period (default 10)
    
    Returns:
        Series with EMA values
    """
    return ha_df['ha_close'].ewm(span=period, adjust=False).mean()


def _check_buy_conditions(ha_df: pd.DataFrame, ema_ha_close: pd.Series) -> tuple[bool, dict]:
    """
    Check if buy conditions are met (REVERSE OF SELL for Chartink compatibility)
    
    Buy Conditions:
    1. Previous [-1]: HA open < EMA of HA close
    2. Previous [-1]: HA close > EMA of HA close (crossover)
    3. Current [0]: HA close > HA open (bullish candle)
    4. Current [0]: HA close > Previous HA close
    5. Current [0]: HA open = HA low (exact or very close)
    
    Returns:
        tuple: (conditions_met, debug_info)
    """
    if len(ha_df) < 2:
        return False, {}
    
    # Previous candle [-1] (index -2)
    prev_ha_open = ha_df.iloc[-2]['ha_open']
    prev_ha_close = ha_df.iloc[-2]['ha_close']
    prev_ema = ema_ha_close.iloc[-2]
    
    # Current candle [0] (index -1)
    curr_ha_open = ha_df.iloc[-1]['ha_open']
    curr_ha_close = ha_df.iloc[-1]['ha_close']
    curr_ha_low = ha_df.iloc[-1]['ha_low']
    curr_ha_high = ha_df.iloc[-1]['ha_high']
    curr_ema = ema_ha_close.iloc[-1]
    
    # Check all buy conditions
    cond1 = prev_ha_open < prev_ema
    cond2 = prev_ha_close > prev_ema
    cond3 = curr_ha_close > curr_ha_open
    cond4 = curr_ha_close > prev_ha_close
    
    # Condition 5: HA open = HA low (exact match in Chartink)
    # Use very small tolerance (0.01 rupee) for floating point comparison
    cond5 = abs(curr_ha_open - curr_ha_low) <= 0.01
    
    debug_info = {
        'cond1': cond1,
        'cond2': cond2,
        'cond3': cond3,
        'cond4': cond4,
        'cond5': cond5,
        'prev_open': round(prev_ha_open, 2),
        'prev_close': round(prev_ha_close, 2),
        'prev_ema': round(prev_ema, 2),
        'curr_open': round(curr_ha_open, 2),
        'curr_close': round(curr_ha_close, 2),
        'curr_low': round(curr_ha_low, 2),
        'curr_high': round(curr_ha_high, 2),
        'open_low_diff': round(abs(curr_ha_open - curr_ha_low), 4)
    }
    
    return cond1 and cond2 and cond3 and cond4 and cond5, debug_info


def _check_sell_conditions(ha_df: pd.DataFrame, ema_ha_close: pd.Series) -> tuple[bool, dict]:
    """
    Check if sell conditions are met (MATCHES CHARTINK CONDITION EXACTLY)
    
    Sell Conditions (from Chartink):
    1. Previous [-1]: HA open > EMA of HA close
    2. Previous [-1]: HA close < EMA of HA close (crossover)
    3. Current [0]: HA close < HA open (bearish candle)
    4. Current [0]: HA close < Previous HA close
    5. Current [0]: HA open = HA high (exact or very close)
    
    Returns:
        tuple: (conditions_met, debug_info)
    """
    if len(ha_df) < 2:
        return False, {}
    
    # Previous candle [-1] (index -2)
    prev_ha_open = ha_df.iloc[-2]['ha_open']
    prev_ha_close = ha_df.iloc[-2]['ha_close']
    prev_ema = ema_ha_close.iloc[-2]
    
    # Current candle [0] (index -1)
    curr_ha_open = ha_df.iloc[-1]['ha_open']
    curr_ha_close = ha_df.iloc[-1]['ha_close']
    curr_ha_high = ha_df.iloc[-1]['ha_high']
    curr_ha_low = ha_df.iloc[-1]['ha_low']
    curr_ema = ema_ha_close.iloc[-1]
    
    # Check all sell conditions
    cond1 = prev_ha_open > prev_ema
    cond2 = prev_ha_close < prev_ema
    cond3 = curr_ha_close < curr_ha_open
    cond4 = curr_ha_close < prev_ha_close
    
    # Condition 5: HA open = HA high (exact match in Chartink)
    # Use very small tolerance (0.01 rupee) for floating point comparison
    cond5 = abs(curr_ha_open - curr_ha_high) <= 0.01
    
    debug_info = {
        'cond1': cond1,
        'cond2': cond2,
        'cond3': cond3,
        'cond4': cond4,
        'cond5': cond5,
        'prev_open': round(prev_ha_open, 2),
        'prev_close': round(prev_ha_close, 2),
        'prev_ema': round(prev_ema, 2),
        'curr_open': round(curr_ha_open, 2),
        'curr_close': round(curr_ha_close, 2),
        'curr_high': round(curr_ha_high, 2),
        'curr_low': round(curr_ha_low, 2),
        'open_high_diff': round(abs(curr_ha_open - curr_ha_high), 4)
    }
    
    return cond1 and cond2 and cond3 and cond4 and cond5, debug_info


def _analyse_stock(df: pd.DataFrame, symbol: str, company_name: str,
                   sector: str, instrument_key: str) -> dict | None:
    """
    Analyze stock for Intraday strategy (10-min HA + EMA)
    
    Returns signal dict if conditions are met, None otherwise
    """
    if df.empty or len(df) < 20:
        return None
    
    try:
        # Calculate Heikin-Ashi
        ha_df = _calculate_heikin_ashi(df)
        
        # Calculate 10-period EMA of HA close
        ema_ha_close = _calculate_ema_ha_close(ha_df, period=10)
        
        # Check conditions with debug info
        is_buy, buy_debug = _check_buy_conditions(ha_df, ema_ha_close)
        is_sell, sell_debug = _check_sell_conditions(ha_df, ema_ha_close)
        
        # Enhanced logging for ALL stocks to see what's happening
        if is_sell or is_buy:
            logger.info(f"✅ {symbol} - SIGNAL FOUND!")
            logger.info(f"   BUY: {is_buy} | SELL: {is_sell}")
            if is_sell:
                logger.info(f"   SELL Debug: {sell_debug}")
            if is_buy:
                logger.info(f"   BUY Debug: {buy_debug}")
        
        # Log failures for first 5 stocks to debug
        if not is_buy and not is_sell and symbol in ['RELIANCE', 'TCS', 'INFY', 'HDFCBANK', 'ICICIBANK']:
            logger.info(f"❌ {symbol} - No signal")
            logger.info(f"   SELL conditions: {sell_debug}")
            logger.info(f"   BUY conditions: {buy_debug}")
        
        if not is_buy and not is_sell:
            return None
        
        # Get current price and market data
        current_price = df.iloc[-1]['close']
        prev_close = df.iloc[-2]['close'] if len(df) > 1 else current_price
        pct_change = ((current_price - prev_close) / prev_close * 100) if prev_close > 0 else 0
        
        # Determine signal
        signal = "BUY" if is_buy else "SELL"
        
        return {
            "symbol": symbol,
            "company_name": company_name,
            "sector": sector,
            "instrument_key": instrument_key,
            "signal": signal,
            "price": round(current_price, 2),
            "change_pct": round(pct_change, 2),
            "ema_ha_close": round(ema_ha_close.iloc[-1], 2),
            "ha_open": round(ha_df.iloc[-1]['ha_open'], 2),
            "ha_close": round(ha_df.iloc[-1]['ha_close'], 2),
            "ha_high": round(ha_df.iloc[-1]['ha_high'], 2),
            "ha_low": round(ha_df.iloc[-1]['ha_low'], 2),
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
                
                if symbol in ['RELIANCE', 'TCS', 'INFY', 'HDFCBANK', 'ICICIBANK']:
                    logger.info(f"{symbol}: Got {len(df_1min)} 1-minute candles (LIVE)")
                
                if df_1min.empty:
                    return None
                
                # Aggregate to 10-minute
                df = _aggregate_to_10min(df_1min)
                
                if symbol in ['RELIANCE', 'TCS', 'INFY']:
                    logger.info(f"{symbol}: Aggregated to {len(df)} 10-minute candles")
                
                # Need at least 2 candles (20 minutes) to start showing signals
                if len(df) < 2:
                    return None
                    
            else:
                # Market is closed: Use 1-minute historical data from last completed day
                # and aggregate to 10-minute (same as Chartink does)
                from datetime import timedelta
                from api.upstox_client import get_client
                
                # Get last trading day (try yesterday first, then go back up to 5 days to skip weekends/holidays)
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
                                
                                if symbol in ['RELIANCE', 'TCS', 'INFY', 'GAIL', 'ADANIGREEN']:
                                    logger.info(f"{symbol}: Got {len(df_1min)} 1-minute historical candles for {test_date_str} (EOD mode)")
                                
                                break  # Found data, stop searching
                    except Exception as e:
                        if symbol in ['RELIANCE', 'TCS']:
                            logger.debug(f"{symbol}: No data for {test_date_str}: {e}")
                        continue
                
                if df_1min.empty:
                    return None
                
                # Aggregate to 10-minute (same as live mode)
                df = _aggregate_to_10min(df_1min)
                
                if symbol in ['RELIANCE', 'TCS', 'INFY', 'GAIL', 'ADANIGREEN']:
                    logger.info(f"{symbol}: Aggregated to {len(df)} 10-minute candles (EOD mode)")
                
                # Need at least 20 candles for EMA calculation
                if df.empty or len(df) < 20:
                    return None
            
            # Analyze with same logic regardless of data source
            result = _analyse_stock(
                df, symbol,
                row.get("company_name", symbol),
                row.get("sector", ""),
                ikey
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Intraday scan error {symbol}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None


async def run_short_term_scan() -> pd.DataFrame:
    """
    Run Intraday 10-min HA + EMA scan on NIFTY 200
    
    Modes:
    - Market Open (9:15 AM - 3:30 PM): Uses live 1-min data aggregated to 10-min
    - Market Closed: Uses EOD daily data for analysis/backtesting
    
    Returns: DataFrame with BUY and SELL signals
    """
    # Check if market is open
    is_market_open = _is_market_open()
    mode = "LIVE" if is_market_open else "EOD"
    
    logger.info(f"Starting Intraday scan in {mode} mode...")
    
    # Get universe
    nifty200 = await get_nifty200_symbols()
    
    # Scan stocks concurrently
    sem = asyncio.Semaphore(20)
    tasks = [_process_stock(row, sem, is_market_open) for _, row in nifty200.iterrows()]
    results = await asyncio.gather(*tasks)
    
    # Filter valid results
    valid = [r for r in results if r is not None]
    logger.info(f"Intraday scan ({mode}): {len(valid)} signals found")
    
    if not valid:
        return pd.DataFrame()
    
    # Create DataFrame
    df = pd.DataFrame(valid)
    
    # Sort: BUY signals first, then by symbol
    df['signal_order'] = df['signal'].map({'BUY': 0, 'SELL': 1})
    df = df.sort_values(['signal_order', 'symbol']).reset_index(drop=True)
    df = df.drop('signal_order', axis=1)
    
    logger.info(f"Intraday scan ({mode}): {len(df[df['signal']=='BUY'])} BUY, {len(df[df['signal']=='SELL'])} SELL signals")
    
    return df
