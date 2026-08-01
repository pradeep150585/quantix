"""
AI Top Picks – composite scoring engine.
Weights: Technical(30) + RS(20) + Volume(15) + TBQ/TSQ(10) + News(10) + Sector(10) + Momentum(5)
"""
import pandas as pd
import numpy as np


WEIGHTS = {
    "technical": 0.30,
    "relative_strength": 0.20,
    "volume": 0.15,
    "tbq_tsq": 0.10,
    "news": 0.10,
    "sector": 0.10,
    "momentum": 0.05,
}


def _norm(series: pd.Series) -> pd.Series:
    mn, mx = series.min(), series.max()
    if mx == mn:
        return pd.Series(50.0, index=series.index)
    return (series - mn) / (mx - mn) * 100


def compute_ai_scores(scan_df: pd.DataFrame, live_df: pd.DataFrame = None, news_sentiment: dict = None) -> pd.DataFrame:
    """
    scan_df: output from scanner.run_scan()
    live_df: output from scanner.live_scanner.get_live_scanner_data()
    news_sentiment: {symbol: score} from news engine
    Returns scan_df with ai_score column added.
    """
    if scan_df.empty:
        return scan_df

    df = scan_df.copy()

    # Technical score (from best strategy score)
    df["_tech"] = _norm(df["best_score"])

    # Relative strength
    df["_rs"] = _norm(df.get("relative_strength", pd.Series(1.0, index=df.index)))

    # Volume
    df["_vol"] = _norm(df.get("volume_ratio", pd.Series(1.0, index=df.index)))

    # TBQ/TSQ from live data
    if live_df is not None and not live_df.empty and "tbq_tsq" in live_df.columns:
        tbq_map = live_df.set_index("symbol")["tbq_tsq"].to_dict()
        df["_tbq"] = df["symbol"].map(tbq_map).fillna(1.0)
        df["_tbq"] = _norm(df["_tbq"])
    else:
        df["_tbq"] = 50.0

    # News sentiment
    if news_sentiment:
        df["_news"] = df["symbol"].map(news_sentiment).fillna(0.0)
        df["_news"] = _norm(df["_news"])
    else:
        df["_news"] = 50.0

    # Sector strength (average score within sector)
    sector_avg = df.groupby("sector")["best_score"].transform("mean")
    df["_sector"] = _norm(sector_avg)

    # Momentum (RSI + MACD hist)
    df["_momentum"] = _norm(df.get("rsi", pd.Series(50.0, index=df.index)))

    df["ai_score"] = (
        df["_tech"] * WEIGHTS["technical"] +
        df["_rs"] * WEIGHTS["relative_strength"] +
        df["_vol"] * WEIGHTS["volume"] +
        df["_tbq"] * WEIGHTS["tbq_tsq"] +
        df["_news"] * WEIGHTS["news"] +
        df["_sector"] * WEIGHTS["sector"] +
        df["_momentum"] * WEIGHTS["momentum"]
    ).round(1)

    # Drop temp columns
    df = df.drop(columns=[c for c in df.columns if c.startswith("_")])
    df = df.sort_values("ai_score", ascending=False).reset_index(drop=True)
    return df


def get_top_picks(df: pd.DataFrame, category: str = "top10") -> pd.DataFrame:
    limits = {
        "top10": 10, "top20": 20, "top50": 50,
        "swing": 20, "intraday": 20, "breakout": 20,
        "volume": 20, "rsi": 20, "momentum": 20,
    }
    n = limits.get(category, 10)

    if category == "swing":
        df = df[df.get("adx", pd.Series(0)) > 20] if "adx" in df.columns else df
    elif category == "intraday":
        df = df.sort_values("volume_ratio", ascending=False) if "volume_ratio" in df.columns else df
    elif category == "breakout":
        df = df[df.get("dist_52h_pct", pd.Series(-100)) >= -5] if "dist_52h_pct" in df.columns else df
    elif category == "volume":
        df = df.sort_values("volume_ratio", ascending=False) if "volume_ratio" in df.columns else df
    elif category == "rsi":
        df = df.sort_values("rsi", ascending=False) if "rsi" in df.columns else df
    elif category == "momentum":
        df = df.sort_values("relative_strength", ascending=False) if "relative_strength" in df.columns else df

    return df.head(n)
