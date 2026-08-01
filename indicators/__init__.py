"""
Technical indicators – computed on a OHLCV DataFrame using pandas_ta.
All functions return scalar values or Series; they never mutate the input df.
"""
import numpy as np
import pandas as pd

try:
    import pandas_ta as ta
    _HAS_TA = True
except ImportError:
    _HAS_TA = False


# ── helpers ──────────────────────────────────────────────────────────────────

def _safe(val, default=0.0):
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return default
    return float(val)


def _ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def _sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(period).mean()


# ── individual indicators ─────────────────────────────────────────────────────

def rsi(df: pd.DataFrame, period: int = 14) -> float:
    if len(df) < period + 1:
        return 50.0
    if _HAS_TA:
        r = ta.rsi(df["close"], length=period)
        return _safe(r.iloc[-1])
    delta = df["close"].diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    val = 100 - (100 / (1 + rs))
    return _safe(val.iloc[-1])


def macd(df: pd.DataFrame, fast=12, slow=26, signal=9) -> tuple[float, float, float]:
    """Returns (macd_line, signal_line, histogram)"""
    if len(df) < slow + signal:
        return 0.0, 0.0, 0.0
    if _HAS_TA:
        m = ta.macd(df["close"], fast=fast, slow=slow, signal=signal)
        if m is None or m.empty:
            return 0.0, 0.0, 0.0
        cols = m.columns.tolist()
        return _safe(m[cols[0]].iloc[-1]), _safe(m[cols[2]].iloc[-1]), _safe(m[cols[1]].iloc[-1])
    ema_fast = _ema(df["close"], fast)
    ema_slow = _ema(df["close"], slow)
    macd_line = ema_fast - ema_slow
    sig = _ema(macd_line, signal)
    hist = macd_line - sig
    return _safe(macd_line.iloc[-1]), _safe(sig.iloc[-1]), _safe(hist.iloc[-1])


def ema(df: pd.DataFrame, period: int) -> float:
    if len(df) < period:
        return _safe(df["close"].iloc[-1])
    return _safe(_ema(df["close"], period).iloc[-1])


def sma(df: pd.DataFrame, period: int) -> float:
    if len(df) < period:
        return _safe(df["close"].iloc[-1])
    return _safe(_sma(df["close"], period).iloc[-1])


def atr(df: pd.DataFrame, period: int = 14) -> float:
    if len(df) < period + 1:
        return 0.0
    if _HAS_TA:
        r = ta.atr(df["high"], df["low"], df["close"], length=period)
        return _safe(r.iloc[-1])
    hl = df["high"] - df["low"]
    hc = (df["high"] - df["close"].shift()).abs()
    lc = (df["low"] - df["close"].shift()).abs()
    tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    return _safe(tr.rolling(period).mean().iloc[-1])


def adx(df: pd.DataFrame, period: int = 14) -> float:
    if len(df) < period * 2:
        return 0.0
    if _HAS_TA:
        r = ta.adx(df["high"], df["low"], df["close"], length=period)
        if r is None or r.empty:
            return 0.0
        col = [c for c in r.columns if c.startswith("ADX_")]
        return _safe(r[col[0]].iloc[-1]) if col else 0.0
    return 0.0


def cci(df: pd.DataFrame, period: int = 20) -> float:
    if len(df) < period:
        return 0.0
    if _HAS_TA:
        r = ta.cci(df["high"], df["low"], df["close"], length=period)
        return _safe(r.iloc[-1])
    tp = (df["high"] + df["low"] + df["close"]) / 3
    sma_tp = tp.rolling(period).mean()
    mad = tp.rolling(period).apply(lambda x: np.mean(np.abs(x - x.mean())), raw=True)
    val = (tp - sma_tp) / (0.015 * mad)
    return _safe(val.iloc[-1])


def williams_r(df: pd.DataFrame, period: int = 14) -> float:
    if len(df) < period:
        return -50.0
    if _HAS_TA:
        r = ta.willr(df["high"], df["low"], df["close"], length=period)
        return _safe(r.iloc[-1])
    hh = df["high"].rolling(period).max()
    ll = df["low"].rolling(period).min()
    val = -100 * (hh - df["close"]) / (hh - ll).replace(0, np.nan)
    return _safe(val.iloc[-1])


def stoch_rsi(df: pd.DataFrame, period: int = 14) -> tuple[float, float]:
    if len(df) < period * 2:
        return 50.0, 50.0
    if _HAS_TA:
        r = ta.stochrsi(df["close"], length=period)
        if r is None or r.empty:
            return 50.0, 50.0
        cols = r.columns.tolist()
        return _safe(r[cols[0]].iloc[-1]), _safe(r[cols[1]].iloc[-1])
    return 50.0, 50.0


def supertrend(df: pd.DataFrame, period: int = 10, multiplier: float = 3.0) -> tuple[float, int]:
    """Returns (supertrend_value, direction) where direction 1=bullish, -1=bearish"""
    if len(df) < period + 1:
        return df["close"].iloc[-1], 1
    if _HAS_TA:
        r = ta.supertrend(df["high"], df["low"], df["close"], length=period, multiplier=multiplier)
        if r is None or r.empty:
            return df["close"].iloc[-1], 1
        trend_col = [c for c in r.columns if "SUPERTd" in c]
        val_col = [c for c in r.columns if c.startswith("SUPERT_") and "d" not in c and "l" not in c and "s" not in c]
        direction = int(r[trend_col[0]].iloc[-1]) if trend_col else 1
        value = _safe(r[val_col[0]].iloc[-1]) if val_col else df["close"].iloc[-1]
        return value, direction
    return df["close"].iloc[-1], 1


def vwap(df: pd.DataFrame) -> float:
    if "volume" not in df.columns or df["volume"].sum() == 0:
        return _safe(df["close"].iloc[-1])
    tp = (df["high"] + df["low"] + df["close"]) / 3
    val = (tp * df["volume"]).cumsum() / df["volume"].cumsum()
    return _safe(val.iloc[-1])


def bollinger_bands(df: pd.DataFrame, period: int = 20, std: float = 2.0) -> tuple[float, float, float]:
    """Returns (upper, middle, lower)"""
    if len(df) < period:
        c = _safe(df["close"].iloc[-1])
        return c, c, c
    if _HAS_TA:
        r = ta.bbands(df["close"], length=period, std=std)
        if r is None or r.empty:
            c = _safe(df["close"].iloc[-1])
            return c, c, c
        cols = sorted(r.columns.tolist())
        return _safe(r[cols[2]].iloc[-1]), _safe(r[cols[1]].iloc[-1]), _safe(r[cols[0]].iloc[-1])
    mid = _sma(df["close"], period)
    std_dev = df["close"].rolling(period).std()
    upper = mid + std * std_dev
    lower = mid - std * std_dev
    return _safe(upper.iloc[-1]), _safe(mid.iloc[-1]), _safe(lower.iloc[-1])


def pivot_points(df: pd.DataFrame) -> dict:
    """Classic pivot points based on previous day OHLC."""
    if len(df) < 2:
        return {}
    prev = df.iloc[-2]
    h, l, c = prev["high"], prev["low"], prev["close"]
    p = (h + l + c) / 3
    return {
        "pivot": round(p, 2),
        "r1": round(2 * p - l, 2),
        "r2": round(p + (h - l), 2),
        "r3": round(h + 2 * (p - l), 2),
        "s1": round(2 * p - h, 2),
        "s2": round(p - (h - l), 2),
        "s3": round(l - 2 * (h - p), 2),
    }


def week52(df: pd.DataFrame) -> tuple[float, float]:
    """Returns (52w_high, 52w_low)"""
    if df.empty:
        return 0.0, 0.0
    last_252 = df.tail(252)
    return _safe(last_252["high"].max()), _safe(last_252["low"].min())


def relative_strength(df: pd.DataFrame, benchmark_df: pd.DataFrame, period: int = 63) -> float:
    """RS ratio vs benchmark over `period` bars."""
    if len(df) < period or len(benchmark_df) < period:
        return 1.0
    stock_ret = df["close"].iloc[-1] / df["close"].iloc[-period]
    bench_ret = benchmark_df["close"].iloc[-1] / benchmark_df["close"].iloc[-period]
    return round(stock_ret / bench_ret, 4) if bench_ret else 1.0


def volume_ratio(df: pd.DataFrame, period: int = 20) -> float:
    """Current volume / average volume over period."""
    if len(df) < period or df["volume"].iloc[-1] == 0:
        return 1.0
    avg = df["volume"].tail(period + 1).iloc[:-1].mean()
    return round(df["volume"].iloc[-1] / avg, 2) if avg else 1.0


def compute_all(df: pd.DataFrame, benchmark_df: pd.DataFrame = None) -> dict:
    """Compute all indicators and return as a flat dict."""
    if df.empty or len(df) < 5:
        return {}

    rsi_val = rsi(df)
    macd_line, macd_sig, macd_hist = macd(df)
    ema20 = ema(df, 20)
    ema50 = ema(df, 50)
    ema100 = ema(df, 100)
    ema200 = ema(df, 200)
    sma50 = sma(df, 50)
    sma150 = sma(df, 150)
    sma200 = sma(df, 200)
    atr_val = atr(df)
    adx_val = adx(df)
    cci_val = cci(df)
    wr_val = williams_r(df)
    stoch_k, stoch_d = stoch_rsi(df)
    st_val, st_dir = supertrend(df)
    vwap_val = vwap(df)
    bb_upper, bb_mid, bb_lower = bollinger_bands(df)
    pivots = pivot_points(df)
    high52, low52 = week52(df)
    cmp = _safe(df["close"].iloc[-1])
    vol_ratio = volume_ratio(df)
    rs = relative_strength(df, benchmark_df) if benchmark_df is not None and not benchmark_df.empty else 1.0

    dist_52h = round((cmp - high52) / high52 * 100, 2) if high52 else 0
    dist_52l = round((cmp - low52) / low52 * 100, 2) if low52 else 0

    return {
        "rsi": round(rsi_val, 2),
        "macd": round(macd_line, 4),
        "macd_signal": round(macd_sig, 4),
        "macd_hist": round(macd_hist, 4),
        "ema20": round(ema20, 2),
        "ema50": round(ema50, 2),
        "ema100": round(ema100, 2),
        "ema200": round(ema200, 2),
        "sma50": round(sma50, 2),
        "sma150": round(sma150, 2),
        "sma200": round(sma200, 2),
        "atr": round(atr_val, 2),
        "adx": round(adx_val, 2),
        "cci": round(cci_val, 2),
        "williams_r": round(wr_val, 2),
        "stoch_k": round(stoch_k, 2),
        "stoch_d": round(stoch_d, 2),
        "supertrend": round(st_val, 2),
        "supertrend_dir": st_dir,
        "vwap": round(vwap_val, 2),
        "bb_upper": round(bb_upper, 2),
        "bb_mid": round(bb_mid, 2),
        "bb_lower": round(bb_lower, 2),
        "high_52w": round(high52, 2),
        "low_52w": round(low52, 2),
        "dist_52h_pct": dist_52h,
        "dist_52l_pct": dist_52l,
        "volume_ratio": vol_ratio,
        "relative_strength": round(rs, 4),
        **{f"pivot_{k}": v for k, v in pivots.items()},
    }
