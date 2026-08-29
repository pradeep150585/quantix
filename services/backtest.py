"""
Backtest Service - Calculate performance of historical scanner signals
Tracks whether targets were achieved and calculates P&L
"""
import asyncio
import pandas as pd
from datetime import datetime, timedelta
from loguru import logger

from database import get_all_scanner_signals
from services.market_data import get_historical_df, get_quotes, parse_quote


async def calculate_signal_performance(signal: dict, days_to_check: int = 30) -> dict:
    """
    Calculate performance for a single signal
    
    Checks if target was achieved within days_to_check days from signal date
    Returns signal with performance metrics added
    """
    try:
        symbol = signal["symbol"]
        instrument_key = signal["instrument_key"]
        signal_date = signal["signal_date"]
        entry_price = signal["entry_price"]
        target1_price = signal["target1_price"]
        target2_price = signal["target2_price"]
        stop_price = signal["stop_price"]
        
        # Get current price
        quotes = await get_quotes([instrument_key])
        current_price = 0
        if instrument_key in quotes:
            parsed = parse_quote(quotes[instrument_key])
            if parsed:
                current_price = parsed.get("ltp", 0)
        
        # Get historical data from signal date onwards
        signal_datetime = datetime.strptime(signal_date, "%Y-%m-%d")
        days_since = (datetime.now() - signal_datetime).days
        
        # Fetch price history to check if target was hit
        df = await get_historical_df(instrument_key, interval="day", days=min(days_to_check + 10, 60))
        
        if df.empty or entry_price == 0:
            return {
                **signal,
                "current_price": current_price,
                "pnl_pct": 0,
                "target1_achieved": False,
                "target2_achieved": False,
                "stop_hit": False,
                "achieved_date": None,
                "days_to_achieve": None,
                "status": "No Data"
            }
        
        # Filter data from signal date onwards
        df = df[df["datetime"] >= signal_datetime].copy()
        
        if df.empty:
            # Signal is from today or future - no historical data yet
            # Don't mark as achieved without price movement
            return {
                **signal,
                "current_price": current_price,
                "pnl_pct": 0,
                "target1_achieved": False,
                "target2_achieved": False,
                "stop_hit": False,
                "achieved_date": None,
                "days_to_achieve": None,
                "status": "Active"
            }
        
        # Check if targets were achieved
        target1_achieved = False
        target2_achieved = False
        stop_hit = False
        achieved_date = None
        days_to_achieve = None
        
        # Check each day
        for idx, row in df.iterrows():
            high = row["high"]
            low = row["low"]
            date = row["datetime"]
            
            # Check if stop was hit first
            if stop_price > 0 and low <= stop_price:
                stop_hit = True
                achieved_date = date.strftime("%Y-%m-%d")
                days_to_achieve = (date - signal_datetime).days
                break
            
            # Check target 1
            if target1_price > 0 and high >= target1_price and not target1_achieved:
                target1_achieved = True
                if not achieved_date:
                    achieved_date = date.strftime("%Y-%m-%d")
                    days_to_achieve = (date - signal_datetime).days
            
            # Check target 2
            if target2_price > 0 and high >= target2_price and not target2_achieved:
                target2_achieved = True
                achieved_date = date.strftime("%Y-%m-%d")
                days_to_achieve = (date - signal_datetime).days
                break  # T2 achieved, no need to check further
        
        # Calculate current P&L
        exit_price = current_price
        if target2_achieved:
            exit_price = target2_price
        elif target1_achieved:
            exit_price = target1_price
        elif stop_hit:
            exit_price = stop_price
        
        pnl_pct = ((exit_price - entry_price) / entry_price * 100) if entry_price > 0 else 0
        
        # Determine status
        if stop_hit:
            status = "Stop Hit"
        elif target2_achieved:
            status = "T2 Achieved"
        elif target1_achieved:
            status = "T1 Achieved"
        elif days_since > days_to_check:
            status = "Expired"
        else:
            status = "Active"
        
        return {
            **signal,
            "current_price": round(current_price, 2),
            "pnl_pct": round(pnl_pct, 2),
            "target1_achieved": target1_achieved,
            "target2_achieved": target2_achieved,
            "stop_hit": stop_hit,
            "achieved_date": achieved_date,
            "days_to_achieve": days_to_achieve,
            "status": status
        }
        
    except Exception as e:
        logger.warning(f"Error calculating performance for {signal.get('symbol', 'unknown')}: {e}")
        return {
            **signal,
            "current_price": 0,
            "pnl_pct": 0,
            "target1_achieved": False,
            "target2_achieved": False,
            "stop_hit": False,
            "achieved_date": None,
            "days_to_achieve": None,
            "status": "Error"
        }


async def get_backtest_results(days: int = 30, scanner_type: str = None) -> pd.DataFrame:
    """
    Get backtest results for all scanner signals from last N days
    
    Args:
        days: Number of days to look back
        scanner_type: Filter by scanner type (Elder/SEPA/Swing) or None for all
    
    Returns:
        DataFrame with signals and their performance metrics
    """
    logger.info(f"Fetching backtest results for last {days} days, scanner: {scanner_type or 'All'}")
    
    # Get signals from database
    from_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    signals_df = get_all_scanner_signals(from_date=from_date)
    
    if signals_df.empty:
        logger.info("No historical signals found")
        return pd.DataFrame()
    
    # Filter by scanner type if specified
    if scanner_type:
        signals_df = signals_df[signals_df["scanner_type"] == scanner_type]
    
    if signals_df.empty:
        logger.info(f"No signals found for scanner type: {scanner_type}")
        return pd.DataFrame()
    
    logger.info(f"Found {len(signals_df)} signals to backtest")
    
    # Calculate performance for each signal
    signals_list = signals_df.to_dict("records")
    
    # Process in batches to avoid overwhelming the API
    sem = asyncio.Semaphore(10)
    
    async def process_with_semaphore(signal):
        async with sem:
            return await calculate_signal_performance(signal, days_to_check=30)
    
    tasks = [process_with_semaphore(signal) for signal in signals_list]
    results = await asyncio.gather(*tasks)
    
    # Convert to DataFrame
    results_df = pd.DataFrame(results)
    
    # Sort by signal date (newest first)
    results_df = results_df.sort_values("signal_date", ascending=False).reset_index(drop=True)
    
    logger.info(f"Backtest complete: {len(results_df)} signals analyzed")
    
    return results_df


async def get_backtest_summary(days: int = 30) -> dict:
    """
    Get summary statistics for backtest results
    
    Returns dict with:
    - Total signals
    - Win rate (T1 or T2 achieved)
    - Average P&L
    - By scanner type breakdown
    """
    results_df = await get_backtest_results(days=days)
    
    if results_df.empty:
        return {
            "total_signals": 0,
            "active": 0,
            "target1_hit": 0,
            "target2_hit": 0,
            "stop_hit": 0,
            "expired": 0,
            "win_rate": 0,
            "avg_pnl": 0,
            "by_scanner": {}
        }
    
    # Calculate statistics
    total = len(results_df)
    active = len(results_df[results_df["status"] == "Active"])
    t1_hit = len(results_df[results_df["target1_achieved"] == True])
    t2_hit = len(results_df[results_df["target2_achieved"] == True])
    stop_hit = len(results_df[results_df["stop_hit"] == True])
    expired = len(results_df[results_df["status"] == "Expired"])
    
    # Win rate = (T1 or T2 achieved) / (Closed positions)
    closed = total - active
    wins = t1_hit  # Any signal that hit T1 counts as win
    win_rate = (wins / closed * 100) if closed > 0 else 0
    
    # Average P&L for closed positions
    closed_df = results_df[results_df["status"] != "Active"]
    avg_pnl = closed_df["pnl_pct"].mean() if not closed_df.empty else 0
    
    # By scanner breakdown
    by_scanner = {}
    for scanner in results_df["scanner_type"].unique():
        scanner_df = results_df[results_df["scanner_type"] == scanner]
        scanner_closed = scanner_df[scanner_df["status"] != "Active"]
        scanner_wins = len(scanner_df[scanner_df["target1_achieved"] == True])
        scanner_total_closed = len(scanner_closed)
        
        by_scanner[scanner] = {
            "total": len(scanner_df),
            "wins": scanner_wins,
            "win_rate": (scanner_wins / scanner_total_closed * 100) if scanner_total_closed > 0 else 0,
            "avg_pnl": scanner_closed["pnl_pct"].mean() if not scanner_closed.empty else 0
        }
    
    return {
        "total_signals": total,
        "active": active,
        "target1_hit": t1_hit,
        "target2_hit": t2_hit,
        "stop_hit": stop_hit,
        "expired": expired,
        "win_rate": round(win_rate, 1),
        "avg_pnl": round(avg_pnl, 2),
        "by_scanner": by_scanner
    }
