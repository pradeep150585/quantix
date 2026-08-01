"""
Strategy scanners inspired by Qullamaggie, Minervini, and Zanger.
Each strategy returns a score 0-100 and a dict of signal details.
"""
import numpy as np
import pandas as pd
from indicators import compute_all, rsi, volume_ratio, ema, sma, week52, relative_strength


def _pct_above(price: float, level: float) -> bool:
    return price > level if level else False


# ── Minervini Trend Template ──────────────────────────────────────────────────

def minervini_score(df: pd.DataFrame, indicators: dict) -> tuple[float, dict]:
    if df.empty or len(df) < 200:
        return 0.0, {}

    cmp = df["close"].iloc[-1]
    ind = indicators

    checks = {
        "above_50sma": cmp > ind.get("sma50", 0),
        "above_150sma": cmp > ind.get("sma150", 0),
        "above_200sma": cmp > ind.get("sma200", 0),
        "sma150_above_200": ind.get("sma150", 0) > ind.get("sma200", 0),
        "sma50_above_150": ind.get("sma50", 0) > ind.get("sma150", 0),
        "sma200_rising": _sma200_rising(df),
        "within_25pct_52h": ind.get("dist_52h_pct", -100) >= -25,
        "rs_positive": ind.get("relative_strength", 1.0) >= 1.0,
        "volume_confirm": ind.get("volume_ratio", 1.0) >= 1.2,
        "rsi_above_50": ind.get("rsi", 50) >= 50,
    }

    score = sum(checks.values()) / len(checks) * 100
    trend_template = all([
        checks["above_50sma"], checks["above_150sma"], checks["above_200sma"],
        checks["sma150_above_200"], checks["sma50_above_150"], checks["sma200_rising"],
        checks["within_25pct_52h"],
    ])

    return round(score, 1), {**checks, "trend_template": trend_template}


def _sma200_rising(df: pd.DataFrame, lookback: int = 20) -> bool:
    if len(df) < 200 + lookback:
        return False
    sma200_now = df["close"].tail(200).mean()
    sma200_prev = df["close"].iloc[-(200 + lookback):-lookback].mean()
    return sma200_now > sma200_prev


# ── Qullamaggie (VCP / Momentum) ─────────────────────────────────────────────

def qullamaggie_score(df: pd.DataFrame, indicators: dict) -> tuple[float, dict]:
    if df.empty or len(df) < 50:
        return 0.0, {}

    cmp = df["close"].iloc[-1]
    ind = indicators

    vcp = _detect_vcp(df)
    checks = {
        "uptrend": cmp > ind.get("ema50", 0) > ind.get("ema200", 0),
        "near_52h": ind.get("dist_52h_pct", -100) >= -10,
        "high_rs": ind.get("relative_strength", 1.0) >= 1.1,
        "volume_contraction": vcp["volume_contracting"],
        "price_tightening": vcp["price_tightening"],
        "higher_highs": _higher_highs(df),
        "breakout_volume": ind.get("volume_ratio", 1.0) >= 1.5,
        "rsi_strong": ind.get("rsi", 50) >= 60,
        "above_ema20": cmp > ind.get("ema20", 0),
        "above_ema50": cmp > ind.get("ema50", 0),
    }

    score = sum(checks.values()) / len(checks) * 100
    return round(score, 1), {**checks, "vcp_details": vcp}


def _detect_vcp(df: pd.DataFrame, lookback: int = 20) -> dict:
    """Simplified VCP: shrinking price ranges and volume over last N bars."""
    if len(df) < lookback * 2:
        return {"volume_contracting": False, "price_tightening": False}

    recent = df.tail(lookback)
    prior = df.iloc[-lookback * 2:-lookback]

    recent_range = (recent["high"] - recent["low"]).mean()
    prior_range = (prior["high"] - prior["low"]).mean()
    recent_vol = recent["volume"].mean()
    prior_vol = prior["volume"].mean()

    return {
        "volume_contracting": recent_vol < prior_vol * 0.85,
        "price_tightening": recent_range < prior_range * 0.75,
    }


def _higher_highs(df: pd.DataFrame, lookback: int = 20) -> bool:
    if len(df) < lookback:
        return False
    highs = df["high"].tail(lookback).values
    mid = len(highs) // 2
    return highs[mid:].mean() > highs[:mid].mean()


# ── Dan Zanger ────────────────────────────────────────────────────────────────

def zanger_score(df: pd.DataFrame, indicators: dict) -> tuple[float, dict]:
    if df.empty or len(df) < 50:
        return 0.0, {}

    cmp = df["close"].iloc[-1]
    ind = indicators

    cup_handle = _detect_cup_handle(df)
    bull_flag = _detect_bull_flag(df)
    flat_base = _detect_flat_base(df)

    checks = {
        "high_volume_breakout": ind.get("volume_ratio", 1.0) >= 1.5,
        "rsi_above_threshold": ind.get("rsi", 50) >= 55,
        "cup_handle": cup_handle,
        "bull_flag": bull_flag,
        "flat_base": flat_base,
        "above_ema50": cmp > ind.get("ema50", 0),
        "momentum": ind.get("macd_hist", 0) > 0,
        "clean_structure": _clean_structure(df),
        "multi_week_consolidation": _consolidation(df),
        "near_52h": ind.get("dist_52h_pct", -100) >= -15,
    }

    score = sum(checks.values()) / len(checks) * 100
    return round(score, 1), checks


def _detect_cup_handle(df: pd.DataFrame, lookback: int = 60) -> bool:
    if len(df) < lookback:
        return False
    window = df["close"].tail(lookback).values
    mid = len(window) // 2
    left_peak = window[:mid // 2].max()
    cup_bottom = window[mid // 4: 3 * mid // 4].min()
    right_peak = window[3 * mid // 4:].max()
    depth = (left_peak - cup_bottom) / left_peak if left_peak else 0
    return (0.12 <= depth <= 0.35) and (right_peak >= left_peak * 0.9)


def _detect_bull_flag(df: pd.DataFrame, pole_bars: int = 10, flag_bars: int = 10) -> bool:
    if len(df) < pole_bars + flag_bars:
        return False
    pole = df["close"].iloc[-(pole_bars + flag_bars):-flag_bars]
    flag = df["close"].tail(flag_bars)
    pole_gain = (pole.iloc[-1] - pole.iloc[0]) / pole.iloc[0] if pole.iloc[0] else 0
    flag_range = (flag.max() - flag.min()) / flag.max() if flag.max() else 0
    return pole_gain >= 0.08 and flag_range <= 0.06


def _detect_flat_base(df: pd.DataFrame, lookback: int = 30) -> bool:
    if len(df) < lookback:
        return False
    window = df["close"].tail(lookback)
    rng = (window.max() - window.min()) / window.max() if window.max() else 0
    return rng <= 0.05


def _clean_structure(df: pd.DataFrame, lookback: int = 20) -> bool:
    """Low number of large gap-down days."""
    if len(df) < lookback:
        return True
    pct_changes = df["close"].pct_change().tail(lookback)
    big_drops = (pct_changes < -0.04).sum()
    return big_drops <= 1


def _consolidation(df: pd.DataFrame, weeks: int = 4) -> bool:
    bars = weeks * 5
    if len(df) < bars:
        return False
    window = df["close"].tail(bars)
    rng = (window.max() - window.min()) / window.max() if window.max() else 0
    return rng <= 0.12


# ── Unified scanner entry point ───────────────────────────────────────────────

STRATEGIES = {
    "Minervini": minervini_score,
    "Qullamaggie": qullamaggie_score,
    "Zanger": zanger_score,
}


def score_all(df: pd.DataFrame, indicators: dict) -> dict:
    """Returns {strategy_name: (score, details)} for all strategies."""
    return {name: fn(df, indicators) for name, fn in STRATEGIES.items()}


def best_strategy(scores: dict) -> tuple[str, float]:
    """Returns (strategy_name, best_score)."""
    if not scores:
        return "None", 0.0
    best = max(scores.items(), key=lambda x: x[1][0])
    return best[0], best[1][0]


def score_color(score: float) -> str:
    if score >= 90:
        return "#00ff88"
    elif score >= 75:
        return "#88ff44"
    elif score >= 60:
        return "#ffdd00"
    elif score >= 40:
        return "#ff8800"
    return "#ff4444"


def score_label(score: float) -> str:
    if score >= 90:
        return "Excellent"
    elif score >= 75:
        return "Strong"
    elif score >= 60:
        return "Watchlist"
    elif score >= 40:
        return "Developing"
    return "No Setup"


def get_badges(indicators: dict, scores: dict) -> list[str]:
    badges = []
    ind = indicators
    if ind.get("volume_ratio", 0) >= 2.0:
        badges.append("🔥 High Volume")
    if ind.get("dist_52h_pct", -100) >= -3:
        badges.append("🚀 Near 52W High")
    if ind.get("relative_strength", 0) >= 1.2:
        badges.append("💪 RS Leader")
    if ind.get("rsi", 0) >= 70:
        badges.append("⚡ Momentum")
    if ind.get("supertrend_dir", -1) == 1:
        badges.append("📈 Supertrend Bull")
    minervini_details = scores.get("Minervini", (0, {}))[1]
    if minervini_details.get("trend_template"):
        badges.append("✅ Trend Template")
    qulla_details = scores.get("Qullamaggie", (0, {}))[1]
    if qulla_details.get("price_tightening") and qulla_details.get("volume_contraction"):
        badges.append("🎯 VCP Candidate")
    return badges
