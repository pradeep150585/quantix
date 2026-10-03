"""
Intraday Scanner - 10-minute Heikin-Ashi + EMA Strategy

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
from loguru import logger

from services.instruments import get_nifty200_symbols
from services.market_data import get_quotes, parse_quote


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
        
        # Get TQB (Total Quantity Bought) and TSQ (Total Quantity Sold) from last candle
        # These are typically available in market depth data
        # For now, we'll use volume as proxy (in real implementation, use market depth API)
        last_volume = df.iloc[-1].get('volume', 0)
        
        # Placeholder: In real implementation, fetch from market depth
        # For buy signals, TQB > TSQ; for sell signals, TSQ > TQB
        if is_buy:
            tqb = last_volume * 0.6  # 60% buyers (example)
            tsq = last_volume * 0.4  # 40% sellers
        else:  # is_sell
            tqb = last_volume * 0.4  # 40% buyers
            tsq = last_volume * 0.6  # 60% sellers
        
        tqb_tsq_ratio = tqb / tsq if tsq > 0 else 0
        
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
            "tqb": int(tqb),
            "tsq": int(tsq),
            "tqb_tsq_ratio": round(tqb_tsq_ratio, 4),
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


async def _process_stock(row: pd.Series, sem: asyncio.Semaphore) -> dict | None:
    """Process single stock"""
    async with sem:
        symbol = row.get("symbol", "")
        ikey = row.get("instrument_key", "")
        
        try:
            # Get 1-minute intraday data and aggregate to 10-minute
            from services.market_data import get_intraday_df
            
            # Get 1-minute data (Upstox supports this)
            df_1min = await get_intraday_df(ikey, interval="1minute")
            
            # Log data availability for first few stocks
            if symbol in ['RELIANCE', 'TCS', 'INFY', 'HDFCBANK', 'ICICIBANK']:
                logger.info(f"{symbol}: Got {len(df_1min)} 1-minute candles")
            
            if df_1min.empty:
                if symbol in ['RELIANCE', 'TCS', 'INFY']:
                    logger.warning(f"{symbol}: No 1-minute data available")
                return None
            
            # Aggregate to 10-minute candles
            df = _aggregate_to_10min(df_1min)
            
            if symbol in ['RELIANCE', 'TCS', 'INFY', 'HDFCBANK', 'ICICIBANK']:
                logger.info(f"{symbol}: Aggregated to {len(df)} 10-minute candles")
                if not df.empty:
                    logger.info(f"   Date range: {df['datetime'].min()} to {df['datetime'].max()}")
                    logger.info(f"   Last candle: {df.iloc[-1].to_dict()}")
            
            if df.empty or len(df) < 20:
                if symbol in ['RELIANCE', 'TCS', 'INFY']:
                    logger.warning(f"{symbol}: Insufficient 10-min data - {len(df)} candles (need 20+)")
                return None
            
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
    Returns: DataFrame with BUY and SELL signals including TQB, TSQ, TQB/TSQ ratio
    """
    logger.info("Starting Intraday scan...")
    
    # Get universe
    nifty200 = await get_nifty200_symbols()
    
    # Scan stocks concurrently
    sem = asyncio.Semaphore(20)
    tasks = [_process_stock(row, sem) for _, row in nifty200.iterrows()]
    results = await asyncio.gather(*tasks)
    
    # Filter valid results
    valid = [r for r in results if r is not None]
    logger.info(f"Intraday scan: {len(valid)} signals found")
    
    if not valid:
        return pd.DataFrame()
    
    # Create DataFrame
    df = pd.DataFrame(valid)
    
    # Sort: BUY signals first, then by symbol
    df['signal_order'] = df['signal'].map({'BUY': 0, 'SELL': 1})
    df = df.sort_values(['signal_order', 'symbol']).reset_index(drop=True)
    df = df.drop('signal_order', axis=1)
    
    logger.info(f"Intraday scan: {len(df[df['signal']=='BUY'])} BUY, {len(df[df['signal']=='SELL'])} SELL signals")
    
    return df
