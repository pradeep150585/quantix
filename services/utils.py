"""
Shared utilities for Quantix scanners.
"""
import pandas as pd
from loguru import logger


def resample_to_weekly(df: pd.DataFrame) -> pd.DataFrame:
    """Resample daily OHLCV to weekly (week ending Friday)."""
    if df.empty or "datetime" not in df.columns:
        return df
    df = df.set_index("datetime")
    wdf = df.resample("W-FRI").agg(
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        volume=("volume", "sum"),
    ).dropna()
    wdf.index.name = "datetime"
    return wdf.reset_index()


def validate_indicators(indicators: dict, required_keys: list[str] = None) -> bool:
    """Validate that all required indicators were computed."""
    if not indicators or not isinstance(indicators, dict):
        logger.warning("Indicators dict is empty or invalid")
        return False
    
    if required_keys is None:
        required_keys = ['rsi', 'macd', 'macd_hist', 'atr', 'adx', 'ema20', 'ema50']
    
    missing = [k for k in required_keys if k not in indicators]
    if missing:
        logger.warning(f"Missing indicators: {missing}")
        return False
    
    return True


def validate_dataframe(df: pd.DataFrame, min_rows: int = 20, required_cols: list[str] = None) -> bool:
    """Validate DataFrame has sufficient data and required columns."""
    if df is None or df.empty:
        logger.warning("DataFrame is empty")
        return False
    
    if len(df) < min_rows:
        logger.warning(f"DataFrame has only {len(df)} rows, need {min_rows}")
        return False
    
    if required_cols:
        missing = [c for c in required_cols if c not in df.columns]
        if missing:
            logger.warning(f"Missing columns: {missing}")
            return False
    
    return True


def fill_nan_values(df: pd.DataFrame, method: str = 'forward') -> pd.DataFrame:
    """Fill NaN values in DataFrame safely."""
    if df.empty:
        return df
    
    df = df.copy()
    if method == 'forward':
        df = df.fillna(method='ffill')
        df = df.fillna(method='bfill')
    elif method == 'zero':
        df = df.fillna(0)
    
    return df


def normalise_keys(raw: dict) -> dict:
    """
    Store every possible key variant so lookups always hit.
    Handles None and malformed keys gracefully.
    """
    if not raw or not isinstance(raw, dict):
        return {}
    
    result = {}
    for k, v in raw.items():
        if not k or not isinstance(k, str):
            continue
        
        # Store all variants of the key
        for variant in [k, k.replace(":", "|"), k.replace("|", ":")]:
            result[variant] = v
        
        # Also store by instrument token if available
        token = v.get("instrument_token", "")
        if token and isinstance(token, str):
            for variant in [token, token.replace(":", "|"), token.replace("|", ":")]:
                result[variant] = v
    
    return result
