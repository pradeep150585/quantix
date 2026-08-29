"""
AI Scanner page - Elder Triple Screen, SEPA Screener & Master Swing Trader
"""
import asyncio
import traceback
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from services.elder_scanner import run_elder_scan
from services.sepa_scanner import run_sepa_scan
from services.swing_scanner import run_swing_scan

_BG     = "#0b0e17"
_CARD   = "#131722"
_BORDER = "#1e2433"
_TEXT   = "#d1d4dc"
_MUTED  = "#6b7280"
_WHITE  = "#ffffff"
_GREEN  = "#00c853"
_RED    = "#ef4444"
_YELLOW = "#fbbf24"
_BLUE   = "#60a5fa"
_PURPLE = "#a78bfa"
_ORANGE = "#fb923c"


def _run(coro):
    try:
        import nest_asyncio
        nest_asyncio.apply()
    except ImportError:
        pass
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop.run_until_complete(coro)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(coro)


def _grade_color(g: str) -> str:
    return {"A+": _GREEN, "A": "#4ade80", "B": _YELLOW, "WATCHLIST": _ORANGE}.get(g, _MUTED)


def _signal_color(s: str) -> str:
    return {"BUY ON BREAKOUT": _GREEN, "BUY NOW": "#4ade80",
            "WATCH": _YELLOW, "NO TRADE": _RED}.get(s, _MUTED)


# -- Explanation panel ---------------------------------------------------------

def _explanation_html(row: pd.Series) -> str:
    w  = row.get("_weekly", {})
    d  = row.get("_daily",  {})
    pa = row.get("_pa",     {})
    v  = row.get("_vol",    {})

    def chk(ok: bool, label: str, val: str = "") -> str:
        c = _GREEN if ok else _RED
        i = "&#10003;" if ok else "&#10007;"
        return (
            f'<div style="display:flex;justify-content:space-between;padding:3px 0;'
            f'border-bottom:1px solid #1e2433;">'
            f'<span style="color:{c};font-weight:600;">{i} {label}</span>'
            f'<span style="color:#9ca3af;font-size:.68rem;">{val}</span></div>'
        )

    def sec(title: str, color: str) -> str:
        return (
            f'<div style="font-size:.62rem;font-weight:700;color:{color};'
            f'text-transform:uppercase;letter-spacing:.08em;margin:10px 0 4px;">'
            f'{title}</div>'
        )

    score    = row.get("score", 0)
    grade    = row.get("grade", "")
    signal   = row.get("signal", "")
    grade_c  = _grade_color(grade)
    signal_c = _signal_color(signal)
    false_bo = pa.get("false_bo_risk", "LOW")
    fbo_c    = _RED if false_bo == "HIGH" else (_YELLOW if false_bo == "MEDIUM" else _GREEN)
    entry    = row.get("entry", 0)
    stop     = row.get("stop", 0)
    t1       = row.get("target1", 0)
    t2       = row.get("target2", 0)
    rr       = row.get("rr", 0)

    return f"""<!DOCTYPE html><html><head>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>*{{box-sizing:border-box;margin:0;padding:0;font-family:'Inter',sans-serif;font-size:.75rem;}}
body{{background:#0b0e17;color:#d1d4dc;padding:12px;}}</style></head><body>

<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
  <div>
    <span style="font-size:1.1rem;font-weight:800;color:#fff;">{row.get('symbol','')}</span>
    <span style="color:#6b7280;margin-left:6px;font-size:.72rem;">{row.get('company_name','')} - {row.get('sector','')}</span>
  </div>
  <div style="text-align:right;">
    <span style="font-size:1.4rem;font-weight:800;color:{grade_c};">{score}/100</span>
    <span style="background:{grade_c}22;color:{grade_c};border:1px solid {grade_c}44;
      border-radius:3px;padding:2px 8px;font-size:.65rem;font-weight:700;margin-left:6px;">{grade}</span>
  </div>
</div>

<div style="background:{signal_c}18;border:1px solid {signal_c}44;border-radius:4px;
  padding:8px 12px;margin-bottom:10px;font-weight:700;color:{signal_c};font-size:.8rem;">
  {signal}
</div>

{sec("Weekly Trend - Screen 1", _BLUE)}
{chk(w.get('macd_hist_rising',False),    "MACD Histogram rising",         f"{w.get('macd_hist_now',0):.4f}")}
{chk(w.get('ema13_rising',False),         "Weekly EMA13 rising",           f"Rs{w.get('ema13',0):,.2f}")}
{chk(w.get('price_above_ema13',False),    "Price above EMA13",             "")}
{chk(w.get('di_bull',False),              "+DI > -DI",                     f"+{w.get('di_plus',0):.1f} / -{w.get('di_minus',0):.1f}")}
{chk(w.get('adx_rising',False),           "ADX rising",                    f"{w.get('adx',0):.1f}")}
{chk(w.get('weekly_fi13_pos',False),      "Weekly Force Index positive",   "")}

{sec("Daily Pullback - Screen 2", _PURPLE)}
{chk(d.get('fi2_neg_turning_up',False),   "Force Index 2-EMA &lt; 0, turning up", f"{d.get('fi2_now',0):.2f}")}
{chk(d.get('bear_power_rising',False) and d.get('bear_power',0)<0,
                                           "Bear Power &lt; 0 and rising",  f"{d.get('bear_power',0):.2f}")}
{chk(d.get('stoch_oversold_turning',False),"Stochastic oversold, turning up", f"%K {d.get('stoch_k',0):.1f}")}
{chk(d.get('wr_oversold_turning',False),  "Williams %R oversold, turning up", f"{d.get('williams_r',0):.1f}")}
{chk(40 <= d.get('rsi',0) <= 70,          "RSI in healthy zone",           f"{d.get('rsi',0):.1f}")}
{chk(d.get('daily_hist_turning',False),   "Daily MACD Hist turning up",    "")}

{sec("Price Action - Screen 3", _YELLOW)}
{chk(pa.get('higher_low',False),          "Higher low formed",             "")}
{chk(pa.get('breakout_20d',False),        "20-day high breakout",          f"Rs{pa.get('recent_sh',0):,.2f}")}
{chk(false_bo != 'HIGH',                  "False breakout risk",           f'<span style="color:{fbo_c};">{false_bo}</span>')}

{sec("Volume", _GREEN)}
{chk(v.get('rvol',0) >= 1.5,              "Breakout volume &ge; 1.5x",     f"{v.get('rvol',0):.2f}x")}
{chk(v.get('pullback_vol_ok',False),      "Pullback volume declining",     "")}

{sec("Trade Plan", _ORANGE)}
<div style="background:#131722;border:1px solid #1e2433;border-radius:4px;padding:10px 12px;margin-top:4px;">
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;">
    <div><span style="color:#6b7280;">Entry</span><br>
      <b style="color:#fff;font-size:.85rem;">Rs{entry:,.2f}</b></div>
    <div><span style="color:#6b7280;">Stop</span><br>
      <b style="color:{_RED};font-size:.85rem;">Rs{stop:,.2f}</b></div>
    <div><span style="color:#6b7280;">Target 1</span><br>
      <b style="color:{_GREEN};font-size:.85rem;">Rs{t1:,.2f}</b></div>
    <div><span style="color:#6b7280;">Target 2</span><br>
      <b style="color:{_GREEN};font-size:.85rem;">Rs{t2:,.2f}</b></div>
    <div><span style="color:#6b7280;">Risk</span><br>
      <b style="color:{_YELLOW};font-size:.85rem;">{row.get('risk_pct',0):.2f}%</b></div>
    <div><span style="color:#6b7280;">R:R</span><br>
      <b style="color:{'#4ade80' if rr>=2 else _YELLOW};font-size:.85rem;">{rr:.2f}</b></div>
  </div>
</div>

<div style="margin-top:8px;font-size:.65rem;color:#6b7280;">
  ATR: {row.get('atr',0):.2f} &nbsp;|&nbsp;
  52W Hi: {row.get('dist_52h_pct',0):.1f}% &nbsp;|&nbsp;
  Weekly: {row.get('weekly_score',0)}/30 &nbsp;|&nbsp;
  Daily: {row.get('daily_score',0)}/25
</div>
</body></html>"""


def _calculate_heikin_ashi(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate Heikin-Ashi candles"""
    ha_df = df.copy()
    
    # HA Close = (Open + High + Low + Close) / 4
    ha_df['ha_close'] = (df['open'] + df['high'] + df['low'] + df['close']) / 4
    
    # HA Open = (Previous HA Open + Previous HA Close) / 2
    ha_df['ha_open'] = 0.0
    ha_df.loc[ha_df.index[0], 'ha_open'] = (df.loc[df.index[0], 'open'] + df.loc[df.index[0], 'close']) / 2
    
    for i in range(1, len(df)):
        ha_df.loc[ha_df.index[i], 'ha_open'] = (ha_df.loc[ha_df.index[i-1], 'ha_open'] + ha_df.loc[ha_df.index[i-1], 'ha_close']) / 2
    
    # HA High = Max(High, HA Open, HA Close)
    ha_df['ha_high'] = ha_df[['high', 'ha_open', 'ha_close']].max(axis=1)
    
    # HA Low = Min(Low, HA Open, HA Close)
    ha_df['ha_low'] = ha_df[['low', 'ha_open', 'ha_close']].min(axis=1)
    
    return ha_df


# -- Elder chart ---------------------------------------------------------------

def _build_elder_chart(symbol: str, row: pd.Series, cdf: pd.DataFrame) -> go.Figure:
    """Elder Triple Screen with Heikin-Ashi (Weekly)"""
    if cdf.empty:
        return go.Figure()
    
    # Calculate Heikin-Ashi
    ha_df = _calculate_heikin_ashi(cdf)

    dates = ha_df["datetime"] if "datetime" in ha_df.columns else pd.RangeIndex(len(ha_df))
    entry = row.get("entry", 0)
    stop  = row.get("stop", 0)
    t1    = row.get("target1", 0)
    t2    = row.get("target2", 0)

    fig = make_subplots(
        rows=3, cols=1, shared_xaxes=True,
        row_heights=[0.55, 0.22, 0.23], vertical_spacing=0.02,
        subplot_titles=("", "Force Index 2-EMA", "MACD Histogram"),
    )

    # Use Heikin-Ashi candles
    fig.add_trace(go.Candlestick(
        x=dates, open=ha_df["ha_open"], high=ha_df["ha_high"],
        low=ha_df["ha_low"], close=ha_df["ha_close"],
        increasing_line_color=_GREEN, increasing_fillcolor="#0d2b1a",
        decreasing_line_color=_RED,   decreasing_fillcolor="#2b0d0d",
        line_width=1, name="Heikin-Ashi",
    ), row=1, col=1)

    if "ema13" in cdf.columns:
        fig.add_trace(go.Scatter(x=dates, y=cdf["ema13"],
            line=dict(color=_BLUE, width=1.2), name="EMA 13"), row=1, col=1)
    if "ema26" in cdf.columns:
        fig.add_trace(go.Scatter(x=dates, y=cdf["ema26"],
            line=dict(color=_PURPLE, width=1, dash="dot"), name="EMA 26"), row=1, col=1)

    for price, color, label in [
        (entry, _YELLOW, f"Entry Rs{entry:,.2f}"),
        (stop,  _RED,    f"Stop Rs{stop:,.2f}"),
        (t1,    _GREEN,  f"T1 Rs{t1:,.2f}"),
        (t2,    "#4ade80", f"T2 Rs{t2:,.2f}"),
    ]:
        if price > 0:
            fig.add_hline(y=price, line=dict(color=color, width=1.2, dash="dash"),
                annotation_text=f"  {label}",
                annotation_position="right",
                annotation_font=dict(color=color, size=9),
                row=1, col=1)

    if "fi2" in cdf.columns:
        fi2 = cdf["fi2"]
        fi_colors = [_GREEN if v >= 0 else _RED for v in fi2]
        fig.add_trace(go.Bar(x=dates, y=fi2, marker_color=fi_colors,
            marker_opacity=0.7, name="FI 2-EMA", showlegend=False), row=2, col=1)
        fig.add_hline(y=0, line=dict(color=_MUTED, width=0.8), row=2, col=1)

    if "macd_h" in cdf.columns:
        mh = cdf["macd_h"]
        mh_colors = [_GREEN if v >= 0 else _RED for v in mh]
        fig.add_trace(go.Bar(x=dates, y=mh, marker_color=mh_colors,
            marker_opacity=0.7, name="MACD Hist", showlegend=False), row=3, col=1)
        fig.add_hline(y=0, line=dict(color=_MUTED, width=0.8), row=3, col=1)

    fig.update_layout(
        paper_bgcolor=_BG, plot_bgcolor=_BG,
        font=dict(color=_TEXT, size=9, family="Inter"),
        margin=dict(l=0, r=50, t=20, b=0), height=400,
        showlegend=False,
        xaxis_rangeslider_visible=False,
        title=dict(text=f"{symbol} - Elder HA Weekly",
                   font=dict(size=11, color=_WHITE), x=0),
    )
    ax = dict(gridcolor=_BORDER, zerolinecolor=_BORDER,
              tickfont=dict(color=_MUTED, size=9), showgrid=True)
    fig.update_xaxes(**ax)
    fig.update_yaxes(**ax)
    return fig


# -- SEPA Chart ----------------------------------------------------------------

def _build_sepa_chart(symbol: str, row: pd.Series, cdf: pd.DataFrame) -> go.Figure:
    """Build SEPA (Minervini) Heikin-Ashi chart with SMAs (Weekly)"""
    if cdf.empty:
        return go.Figure()
    
    # Calculate Heikin-Ashi
    ha_df = _calculate_heikin_ashi(cdf)

    dates = ha_df["datetime"] if "datetime" in ha_df.columns else pd.RangeIndex(len(ha_df))
    entry = row.get("entry", 0)
    stop  = row.get("stop", 0)
    t1    = row.get("target1", 0)

    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True,
        row_heights=[0.70, 0.30], vertical_spacing=0.02,
        subplot_titles=("", "Volume"),
    )

    # Use Heikin-Ashi candles
    fig.add_trace(go.Candlestick(
        x=dates, open=ha_df["ha_open"], high=ha_df["ha_high"],
        low=ha_df["ha_low"], close=ha_df["ha_close"],
        increasing_line_color=_GREEN, increasing_fillcolor="#0d2b1a",
        decreasing_line_color=_RED,   decreasing_fillcolor="#2b0d0d",
        line_width=1, name="Heikin-Ashi",
    ), row=1, col=1)

    # Add SMAs for Minervini's Trend Template (calculated on original close)
    if "close" in cdf.columns:
        sma50 = cdf["close"].rolling(50).mean()
        sma150 = cdf["close"].rolling(150).mean()
        sma200 = cdf["close"].rolling(200).mean()
        
        fig.add_trace(go.Scatter(x=dates, y=sma50,
            line=dict(color=_BLUE, width=1.2), name="SMA 50"), row=1, col=1)
        fig.add_trace(go.Scatter(x=dates, y=sma150,
            line=dict(color=_PURPLE, width=1, dash="dot"), name="SMA 150"), row=1, col=1)
        fig.add_trace(go.Scatter(x=dates, y=sma200,
            line=dict(color=_ORANGE, width=1, dash="dash"), name="SMA 200"), row=1, col=1)

    # Trade levels
    for price, color, label in [
        (entry, _YELLOW, f"Entry Rs{entry:,.2f}"),
        (stop,  _RED,    f"Stop Rs{stop:,.2f}"),
        (t1,    _GREEN,  f"T1 Rs{t1:,.2f}"),
    ]:
        if price > 0:
            fig.add_hline(y=price, line=dict(color=color, width=1.2, dash="dash"),
                annotation_text=f"  {label}",
                annotation_position="right",
                annotation_font=dict(color=color, size=9),
                row=1, col=1)

    # Volume
    if "volume" in cdf.columns:
        vol_colors = [_GREEN if cdf["close"].iloc[i] >= cdf["open"].iloc[i] else _RED 
                      for i in range(len(cdf))]
        fig.add_trace(go.Bar(x=dates, y=cdf["volume"], marker_color=vol_colors,
            marker_opacity=0.7, name="Volume", showlegend=False), row=2, col=1)

    fig.update_layout(
        paper_bgcolor=_BG, plot_bgcolor=_BG,
        font=dict(color=_TEXT, size=9, family="Inter"),
        margin=dict(l=0, r=50, t=20, b=0), height=400,
        showlegend=False,
        xaxis_rangeslider_visible=False,
        title=dict(text=f"{symbol} - SEPA HA Weekly",
                   font=dict(size=11, color=_WHITE), x=0),
    )
    ax = dict(gridcolor=_BORDER, zerolinecolor=_BORDER,
              tickfont=dict(color=_MUTED, size=9), showgrid=True)
    fig.update_xaxes(**ax)
    fig.update_yaxes(**ax)
    return fig


# -- Swing Chart ---------------------------------------------------------------

def _build_swing_chart(symbol: str, row: pd.Series, cdf: pd.DataFrame) -> go.Figure:
    """Build Master Swing Trader Heikin-Ashi chart with EMAs, RSI (Weekly)"""
    if cdf.empty:
        return go.Figure()
    
    # Calculate Heikin-Ashi
    ha_df = _calculate_heikin_ashi(cdf)

    dates = ha_df["datetime"] if "datetime" in ha_df.columns else pd.RangeIndex(len(ha_df))
    entry = row.get("entry", 0)
    stop  = row.get("stop", 0)
    t1    = row.get("target1", 0)

    fig = make_subplots(
        rows=3, cols=1, shared_xaxes=True,
        row_heights=[0.55, 0.22, 0.23], vertical_spacing=0.02,
        subplot_titles=("", "RSI", "Volume"),
    )

    # Use Heikin-Ashi candles
    fig.add_trace(go.Candlestick(
        x=dates, open=ha_df["ha_open"], high=ha_df["ha_high"],
        low=ha_df["ha_low"], close=ha_df["ha_close"],
        increasing_line_color=_GREEN, increasing_fillcolor="#0d2b1a",
        decreasing_line_color=_RED,   decreasing_fillcolor="#2b0d0d",
        line_width=1, name="Heikin-Ashi",
    ), row=1, col=1)

    # Add EMAs for trend alignment (calculated on original close)
    if "close" in cdf.columns:
        ema10 = cdf["close"].ewm(span=10, adjust=False).mean()
        ema20 = cdf["close"].ewm(span=20, adjust=False).mean()
        ema50 = cdf["close"].ewm(span=50, adjust=False).mean()
        
        fig.add_trace(go.Scatter(x=dates, y=ema10,
            line=dict(color=_BLUE, width=1.2), name="EMA 10"), row=1, col=1)
        fig.add_trace(go.Scatter(x=dates, y=ema20,
            line=dict(color=_PURPLE, width=1, dash="dot"), name="EMA 20"), row=1, col=1)
        fig.add_trace(go.Scatter(x=dates, y=ema50,
            line=dict(color=_ORANGE, width=1, dash="dash"), name="EMA 50"), row=1, col=1)

    # Trade levels
    for price, color, label in [
        (entry, _YELLOW, f"Entry Rs{entry:,.2f}"),
        (stop,  _RED,    f"Stop Rs{stop:,.2f}"),
        (t1,    _GREEN,  f"T1 Rs{t1:,.2f}"),
    ]:
        if price > 0:
            fig.add_hline(y=price, line=dict(color=color, width=1.2, dash="dash"),
                annotation_text=f"  {label}",
                annotation_position="right",
                annotation_font=dict(color=color, size=9),
                row=1, col=1)

    # RSI (on original close)
    if "close" in cdf.columns and len(cdf) >= 14:
        delta = cdf["close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        fig.add_trace(go.Scatter(x=dates, y=rsi,
            line=dict(color=_BLUE, width=1.2), name="RSI", showlegend=False), row=2, col=1)
        fig.add_hline(y=70, line=dict(color=_RED, width=0.8, dash="dot"), row=2, col=1)
        fig.add_hline(y=30, line=dict(color=_GREEN, width=0.8, dash="dot"), row=2, col=1)
        fig.add_hline(y=50, line=dict(color=_MUTED, width=0.6), row=2, col=1)

    # Volume
    if "volume" in cdf.columns:
        vol_colors = [_GREEN if cdf["close"].iloc[i] >= cdf["open"].iloc[i] else _RED 
                      for i in range(len(cdf))]
        fig.add_trace(go.Bar(x=dates, y=cdf["volume"], marker_color=vol_colors,
            marker_opacity=0.7, name="Volume", showlegend=False), row=3, col=1)

    fig.update_layout(
        paper_bgcolor=_BG, plot_bgcolor=_BG,
        font=dict(color=_TEXT, size=9, family="Inter"),
        margin=dict(l=0, r=50, t=20, b=0), height=400,
        showlegend=False,
        xaxis_rangeslider_visible=False,
        title=dict(text=f"{symbol} - Swing HA Weekly",
                   font=dict(size=11, color=_WHITE), x=0),
    )
    ax = dict(gridcolor=_BORDER, zerolinecolor=_BORDER,
              tickfont=dict(color=_MUTED, size=9), showgrid=True)
    fig.update_xaxes(**ax)
    fig.update_yaxes(**ax)
    return fig


# -- Stock row -----------------------------------------------------------------

def _render_row(row: pd.Series, chart_store: dict, key_prefix: str = ""):
    symbol  = row.get("symbol", "")
    score   = row.get("score", 0)
    grade   = row.get("grade", "")
    signal  = row.get("signal", "")
    cmp     = row.get("cmp", 0)
    pct     = row.get("pct_change", 0)
    entry   = row.get("entry", 0)
    stop    = row.get("stop", 0)
    t1      = row.get("target1", 0)
    rr      = row.get("rr", 0)
    trend   = row.get("_weekly", {}).get("weekly_trend", "")
    pct_c   = _GREEN if pct > 0 else (_RED if pct < 0 else _MUTED)
    pct_s   = f"+{pct:.2f}%" if pct > 0 else f"{pct:.2f}%"
    grade_c = _grade_color(grade)

    label = f"{symbol}  |  Rs{cmp:,.2f}  {pct_s}  |  Entry: Rs{entry:,.2f}  |  {signal}  |  Score {score}"

    with st.expander(label, expanded=False):
        components.html(f"""<!DOCTYPE html><html><head>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>*{{box-sizing:border-box;margin:0;padding:0;font-family:'Inter',sans-serif;}}</style>
</head><body style="background:#0b0e17;padding:0;">
<div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:8px;">
  <div style="background:#131722;border:1px solid #1e2433;border-radius:4px;padding:8px 12px;flex:1;min-width:110px;">
    <div style="font-size:.58rem;color:#6b7280;text-transform:uppercase;">CMP</div>
    <div style="font-size:.9rem;font-weight:700;color:#fff;">Rs{cmp:,.2f}
      <span style="font-size:.65rem;color:{pct_c};margin-left:4px;">{pct_s}</span></div>
  </div>
  <div style="background:#131722;border:1px solid #1e2433;border-radius:4px;padding:8px 12px;flex:1;min-width:110px;">
    <div style="font-size:.58rem;color:#6b7280;text-transform:uppercase;">Entry</div>
    <div style="font-size:.9rem;font-weight:700;color:{_YELLOW};">Rs{entry:,.2f}</div>
  </div>
  <div style="background:#131722;border:1px solid #1e2433;border-radius:4px;padding:8px 12px;flex:1;min-width:110px;">
    <div style="font-size:.58rem;color:#6b7280;text-transform:uppercase;">Stop</div>
    <div style="font-size:.9rem;font-weight:700;color:{_RED};">Rs{stop:,.2f}</div>
  </div>
  <div style="background:#131722;border:1px solid #1e2433;border-radius:4px;padding:8px 12px;flex:1;min-width:110px;">
    <div style="font-size:.58rem;color:#6b7280;text-transform:uppercase;">Target 1</div>
    <div style="font-size:.9rem;font-weight:700;color:{_GREEN};">Rs{t1:,.2f}</div>
  </div>
  <div style="background:#131722;border:1px solid #1e2433;border-radius:4px;padding:8px 12px;flex:1;min-width:80px;">
    <div style="font-size:.58rem;color:#6b7280;text-transform:uppercase;">R:R</div>
    <div style="font-size:.9rem;font-weight:700;color:{'#4ade80' if rr>=2 else _YELLOW};">{rr:.2f}</div>
  </div>
  <div style="background:{grade_c}18;border:1px solid {grade_c}44;border-radius:4px;padding:8px 12px;min-width:70px;text-align:center;">
    <div style="font-size:.58rem;color:#6b7280;text-transform:uppercase;">Grade</div>
    <div style="font-size:1.1rem;font-weight:800;color:{grade_c};">{grade}</div>
  </div>
</div>
<div style="font-size:.67rem;color:#6b7280;">
  {row.get('company_name','')} - {row.get('sector','')} - Weekly:
  <span style="color:{'#4ade80' if 'BULL' in trend else _YELLOW};">{trend}</span>
</div>
</body></html>""", height=110, scrolling=False)

        col_exp, col_chart = st.columns([1, 2])
        with col_exp:
            components.html(_explanation_html(row), height=520, scrolling=True)
        with col_chart:
            cdf = chart_store.get(symbol)
            if cdf is not None and not cdf.empty:
                fig = _build_elder_chart(symbol, row, cdf)
                st.plotly_chart(fig, use_container_width=True,
                                config={"displayModeBar": False},
                                key=f"elder_chart_{key_prefix}{symbol}")
            else:
                st.info("Chart data unavailable.")


# -- Main render body ----------------------------------------------------------

def _render_elder(df: pd.DataFrame, chart_store: dict):
    """Render Elder Triple Screen results - Top 10 with Buy Now/Watch tabs"""
    if df is None or df.empty:
        st.info("No stocks currently pass the Triple Screen criteria. The system says NO TRADE.")
        return

    # Summary metrics
    a_plus  = df[df["grade"] == "A+"]
    a_grade = df[df["grade"] == "A"]
    b_grade = df[df["grade"] == "B"]
    buy_now = df[df["signal"] == "BUY NOW"]
    breakout = df[df["signal"] == "BUY ON BREAKOUT"]

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Top Stocks", len(df))
    c2.metric("A+ Setups", len(a_plus))
    c3.metric("A Setups", len(a_grade))
    c4.metric("B Setups", len(b_grade))
    c5.metric("Buy Now", len(buy_now))
    c6.metric("Breakout", len(breakout))

    st.markdown("---")
    
    # Tabs for Buy Now vs Watchlist
    buy_ready = df[df["signal"].isin(["BUY NOW", "BUY ON BREAKOUT"])]
    watch_list = df[df["signal"] == "WATCH"]
    
    tab_all, tab_buy, tab_watch = st.tabs([
        f"All Setups ({len(df)})",
        f"Buy Ready ({len(buy_ready)})",
        f"Watch List ({len(watch_list)})"
    ])
    
    with tab_all:
        st.markdown('<div style="font-size:.65rem;font-weight:600;color:#6b7280;text-transform:uppercase;letter-spacing:.05em;margin-bottom:8px;">Top 10 Triple Screen Setups (Sorted by Score)</div>', unsafe_allow_html=True)
        for idx, row in df.iterrows():
            _render_row(row, chart_store, key_prefix=f"all_{idx}")
    
    with tab_buy:
        st.markdown('<div style="font-size:.65rem;font-weight:600;color:#6b7280;text-transform:uppercase;letter-spacing:.05em;margin-bottom:8px;">Buy Ready Stocks</div>', unsafe_allow_html=True)
        if buy_ready.empty:
            st.info("No stocks in BUY status")
        else:
            for idx, row in buy_ready.iterrows():
                _render_row(row, chart_store, key_prefix=f"buy_{idx}")
    
    with tab_watch:
        st.markdown('<div style="font-size:.65rem;font-weight:600;color:#6b7280;text-transform:uppercase;letter-spacing:.05em;margin-bottom:8px;">Watch List</div>', unsafe_allow_html=True)
        if watch_list.empty:
            st.info("No stocks in watch list")
        else:
            for idx, row in watch_list.iterrows():
                _render_row(row, chart_store, key_prefix=f"watch_{idx}")


# -- Entry points --------------------------------------------------------------

def _render_sepa(df: pd.DataFrame, chart_store: dict):
    """Render SEPA scanner results (matches Elder UI exactly)"""
    if df.empty:
        st.warning("No stocks meet the Minervini SEPA criteria.")
        return
    
    # Summary metrics
    elite = df[df["grade"] == "Superperformer"]
    strong_buy = df[df["grade"] == "Strong Buy"]
    buy_stocks = df[df["grade"] == "Buy"]
    buy_now = df[df["signal"] == "BUY NOW"]
    breakout = df[df["signal"] == "BUY ON BREAKOUT"]
    vcp_stocks = df[df["vcp_score"] >= 15]
    
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Top Stocks", len(df))
    c2.metric("Superperformer", len(elite))
    c3.metric("Strong Buy", len(strong_buy))
    c4.metric("VCP Quality", len(vcp_stocks))
    c5.metric("Buy Now", len(buy_now))
    c6.metric("Near Breakout", len(breakout))
    
    st.markdown("---")
    
    # Tabs for Buy Now vs Watchlist
    buy_ready = df[df["signal"].isin(["BUY NOW", "BUY ON BREAKOUT"])]
    watch_list = df[df["signal"] == "WATCH"]
    
    tab_all, tab_buy, tab_watch = st.tabs([
        f"All Setups ({len(df)})",
        f"Buy Ready ({len(buy_ready)})",
        f"Watch List ({len(watch_list)})"
    ])
    
    with tab_all:
        st.markdown('<div style="font-size:.65rem;font-weight:600;color:#6b7280;text-transform:uppercase;letter-spacing:.05em;margin-bottom:8px;">Top 10 SEPA Setups (Sorted by Score)</div>', unsafe_allow_html=True)
        for idx, row in df.iterrows():
            _render_sepa_row(row, chart_store, key_prefix=f"all_{idx}")
    
    with tab_buy:
        st.markdown('<div style="font-size:.65rem;font-weight:600;color:#6b7280;text-transform:uppercase;letter-spacing:.05em;margin-bottom:8px;">Buy Ready Stocks</div>', unsafe_allow_html=True)
        if buy_ready.empty:
            st.info("No stocks in BUY status")
        else:
            for idx, row in buy_ready.iterrows():
                _render_sepa_row(row, chart_store, key_prefix=f"buy_{idx}")
    
    with tab_watch:
        st.markdown('<div style="font-size:.65rem;font-weight:600;color:#6b7280;text-transform:uppercase;letter-spacing:.05em;margin-bottom:8px;">Watch List</div>', unsafe_allow_html=True)
        if watch_list.empty:
            st.info("No stocks in watch list")
        else:
            for idx, row in watch_list.iterrows():
                _render_sepa_row(row, chart_store, key_prefix=f"watch_{idx}")


def _render_sepa_row(row: pd.Series, chart_store: dict, key_prefix: str = ""):
    """Render a single SEPA stock row (matches Elder UI exactly)"""
    symbol  = row.get("symbol", "")
    score   = row.get("score", 0)
    grade   = row.get("grade", "")
    signal  = row.get("signal", "")
    cmp     = row.get("price", 0)  # SEPA uses "price" not "cmp"
    pct     = row.get("change_pct", 0)  # SEPA uses "change_pct" not "pct_change"
    entry   = row.get("entry", 0)
    stop    = row.get("stop", 0)
    t1      = row.get("target1", 0)
    rr      = row.get("risk_reward", 0)  # SEPA uses "risk_reward" not "rr"
    
    # Get SEPA details
    trend_d = row.get("trend_detail", {})
    vcp_d = row.get("vcp_detail", {})
    vcp = vcp_d.get("quality", "None")
    trend_passed = trend_d.get("passed", 0)
    
    pct_c   = _GREEN if pct > 0 else (_RED if pct < 0 else _MUTED)
    pct_s   = f"+{pct:.2f}%" if pct > 0 else f"{pct:.2f}%"
    
    # Map SEPA grades to colors
    if grade == "Superperformer":
        grade_c = _GREEN
    elif grade == "Strong Buy":
        grade_c = "#4ade80"
    elif grade == "Buy":
        grade_c = _YELLOW
    else:
        grade_c = _MUTED
    
    label = f"{symbol}  |  Rs{cmp:,.2f}  {pct_s}  |  Entry: Rs{entry:,.2f}  |  {signal}  |  SEPA Score {score}"
    
    with st.expander(label, expanded=False):
        components.html(f"""<!DOCTYPE html><html><head>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>*{{box-sizing:border-box;margin:0;padding:0;font-family:'Inter',sans-serif;}}</style>
</head><body style="background:#0b0e17;padding:0;">
<div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:8px;">
  <div style="background:#131722;border:1px solid #1e2433;border-radius:4px;padding:8px 12px;flex:1;min-width:110px;">
    <div style="font-size:.58rem;color:#6b7280;text-transform:uppercase;">CMP</div>
    <div style="font-size:.9rem;font-weight:700;color:#fff;">Rs{cmp:,.2f}
      <span style="font-size:.65rem;color:{pct_c};margin-left:4px;">{pct_s}</span></div>
  </div>
  <div style="background:#131722;border:1px solid #1e2433;border-radius:4px;padding:8px 12px;flex:1;min-width:110px;">
    <div style="font-size:.58rem;color:#6b7280;text-transform:uppercase;">Entry</div>
    <div style="font-size:.9rem;font-weight:700;color:{_YELLOW};">Rs{entry:,.2f}</div>
  </div>
  <div style="background:#131722;border:1px solid #1e2433;border-radius:4px;padding:8px 12px;flex:1;min-width:110px;">
    <div style="font-size:.58rem;color:#6b7280;text-transform:uppercase;">Stop</div>
    <div style="font-size:.9rem;font-weight:700;color:{_RED};">Rs{stop:,.2f}</div>
  </div>
  <div style="background:#131722;border:1px solid #1e2433;border-radius:4px;padding:8px 12px;flex:1;min-width:110px;">
    <div style="font-size:.58rem;color:#6b7280;text-transform:uppercase;">Target 1</div>
    <div style="font-size:.9rem;font-weight:700;color:{_GREEN};">Rs{t1:,.2f}</div>
  </div>
  <div style="background:#131722;border:1px solid #1e2433;border-radius:4px;padding:8px 12px;flex:1;min-width:80px;">
    <div style="font-size:.58rem;color:#6b7280;text-transform:uppercase;">R:R</div>
    <div style="font-size:.9rem;font-weight:700;color:{'#4ade80' if rr>=2 else _YELLOW};">{rr:.2f}</div>
  </div>
  <div style="background:{grade_c}18;border:1px solid {grade_c}44;border-radius:4px;padding:8px 12px;min-width:70px;text-align:center;">
    <div style="font-size:.58rem;color:#6b7280;text-transform:uppercase;">Grade</div>
    <div style="font-size:1.1rem;font-weight:800;color:{grade_c};">{grade}</div>
  </div>
</div>
<div style="font-size:.67rem;color:#6b7280;">
  {row.get('company_name','')} - {row.get('sector','')} - Trend: {trend_passed}/8 passed | VCP: {vcp}
</div>
</body></html>""", height=110, scrolling=False)
        
        col_exp, col_chart = st.columns([1, 2])
        with col_exp:
            components.html(_render_sepa_explanation_html(row), height=520, scrolling=True)
        with col_chart:
            cdf = chart_store.get(symbol)
            if cdf is not None and not cdf.empty:
                fig = _build_sepa_chart(symbol, row, cdf)
                st.plotly_chart(fig, use_container_width=True,
                                config={"displayModeBar": False},
                                key=f"{key_prefix}_chart_{symbol}")
            else:
                st.info("Chart data unavailable.")("ðŸ“Š SEPA Chart coming soon")


def _render_sepa_explanation_html(row: pd.Series) -> str:
    """Render SEPA score breakdown as HTML string"""
    trend_d = row.get("trend_detail", {})
    rs_d = row.get("rs_detail", {})
    vcp_d = row.get("vcp_detail", {})
    vol_d = row.get("volume_detail", {})
    pivot_d = row.get("pivot_detail", {})
    
    def chk(ok: bool, label: str, val: str = "") -> str:
        c = _GREEN if ok else _RED
        i = "&#10003;" if ok else "&#10007;"
        return (
            f'<div style="display:flex;justify-content:space-between;padding:3px 0;'
            f'border-bottom:1px solid #1e2433;">'
            f'<span style="color:{c};font-weight:600;">{i} {label}</span>'
            f'<span style="color:#9ca3af;font-size:.68rem;">{val}</span></div>'
        )
    
    def sec(title: str, color: str) -> str:
        return (
            f'<div style="font-size:.62rem;font-weight:700;color:{color};'
            f'text-transform:uppercase;letter-spacing:.08em;margin:10px 0 4px;">'
            f'{title}</div>'
        )
    
    score = row.get("score", 0)
    grade = row.get("grade", "")
    
    # Map SEPA grades to colors
    if grade == "Superperformer":
        grade_c = _GREEN
    elif grade == "Strong Buy":
        grade_c = "#4ade80"
    elif grade == "Buy":
        grade_c = _YELLOW
    else:
        grade_c = _MUTED
    
    conditions = trend_d.get("conditions", {})
    
    html = f"""<!DOCTYPE html><html><head>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>*{{box-sizing:border-box;margin:0;padding:0;font-family:'Inter',sans-serif;font-size:.75rem;}}
body{{background:#0b0e17;color:#d1d4dc;padding:12px;}}</style></head><body>

<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
  <div>
    <span style="font-size:1.1rem;font-weight:800;color:#fff;">{row.get('symbol','')}</span>
    <span style="color:#6b7280;margin-left:6px;font-size:.72rem;">SEPA Analysis</span>
  </div>
  <div style="background:{grade_c}18;border:2px solid {grade_c};border-radius:4px;padding:6px 14px;">
    <span style="font-size:1.2rem;font-weight:800;color:{grade_c};">{score}</span>
    <span style="font-size:.65rem;color:#6b7280;margin-left:4px;">{grade}</span>
  </div>
</div>

{sec("TREND TEMPLATE (25 pts)", _BLUE)}
{chk(conditions.get('c1_price_above_150_200', False), "Price > 150 & 200 SMA", "")}
{chk(conditions.get('c2_150_above_200', False), "150 SMA > 200 SMA", "")}
{chk(conditions.get('c3_200_trending_up', False), "200 SMA Trending Up", "")}
{chk(conditions.get('c4_50_above_150_200', False), "50 SMA > 150 & 200", "")}
{chk(conditions.get('c5_price_above_50', False), "Price > 50 SMA", "")}
{chk(conditions.get('c6_30pct_above_52w_low', False), "30% Above 52W Low", "")}
{chk(conditions.get('c7_within_25pct_of_52w_high', False), "Within 25% of 52W High", "")}
{chk(conditions.get('c8_rs_rank_70plus', False), "RS Rank >= 70", "")}
<div style="font-size:.68rem;color:#9ca3af;margin-top:4px;">
  Passed: {trend_d.get('passed', 0)}/8 | Stage: {trend_d.get('stage', '')} | Score: {row.get('trend_score', 0)}/25
</div>

{sec("RELATIVE STRENGTH (20 pts)", _PURPLE)}
<div style="display:flex;justify-content:space-between;">
  <span>RS Rank: <b style="color:#fff;">{rs_d.get('rs_rank', 0)}</b></span>
  <span style="color:#9ca3af;">{rs_d.get('classification', '')}</span>
</div>
<div style="display:flex;justify-content:space-between;font-size:.68rem;color:#9ca3af;margin-top:2px;">
  <span>3M: {rs_d.get('ret_3m', 0):.1f}%</span>
  <span>6M: {rs_d.get('ret_6m', 0):.1f}%</span>
  <span>9M: {rs_d.get('ret_9m', 0):.1f}%</span>
  <span>12M: {rs_d.get('ret_12m', 0):.1f}%</span>
</div>
<div style="font-size:.68rem;color:#9ca3af;margin-top:2px;">Score: {row.get('rs_score', 0)}/20</div>

{sec("VCP PATTERN (25 pts)", _ORANGE)}
{chk(vcp_d.get('vcp_detected', False), "VCP Detected", vcp_d.get('quality', ''))}
<div style="font-size:.68rem;color:#9ca3af;">
  Contractions: {" â†’ ".join(str(c) + "%" for c in vcp_d.get('contractions', []))}
</div>
<div style="font-size:.68rem;color:#9ca3af;margin-top:2px;">Score: {row.get('vcp_score', 0)}/25</div>

{sec("PIVOT & BREAKOUT (15 pts)", _YELLOW)}
<div style="display:flex;justify-content:space-between;">
  <span>Pivot: Rs{pivot_d.get('pivot', 0):,.2f}</span>
  <span style="color:#9ca3af;">{pivot_d.get('dist_to_pivot_pct', 0):.1f}% away</span>
</div>
<div style="font-size:.68rem;color:#9ca3af;">
  Status: {pivot_d.get('status', '')} | Vol Ratio: {pivot_d.get('vol_ratio', 0):.2f}x
</div>
<div style="font-size:.68rem;color:#9ca3af;margin-top:2px;">Score: {row.get('pivot_score', 0)}/15</div>

{sec("VOLUME ANALYSIS (15 pts)", _GREEN)}
<div style="display:flex;justify-content:space-between;">
  <span>{vol_d.get('classification', '')}</span>
  <span style="color:#9ca3af;">Dry-up: {'Yes' if vol_d.get('dryup', False) else 'No'}</span>
</div>
<div style="font-size:.68rem;color:#9ca3af;margin-top:2px;">Score: {row.get('volume_score', 0)}/15</div>

</body></html>"""
    
    return html


def _build_sepa_chart(symbol: str, row: pd.Series, cdf: pd.DataFrame) -> go.Figure:
    """Build SEPA chart (matches Elder pattern)"""
    if cdf.empty:
        return go.Figure()
    
    dates = cdf["datetime"] if "datetime" in cdf.columns else pd.RangeIndex(len(cdf))
    entry = row.get("entry", 0)
    stop  = row.get("stop", 0)
    t1    = row.get("target1", 0)
    t2    = row.get("target2", 0)
    
    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True,
        row_heights=[0.7, 0.3], vertical_spacing=0.02,
        subplot_titles=("", "Volume"),
    )
    
    fig.add_trace(go.Candlestick(
        x=dates, open=cdf["open"], high=cdf["high"],
        low=cdf["low"], close=cdf["close"],
        increasing_line_color=_GREEN, increasing_fillcolor="#0d2b1a",
        decreasing_line_color=_RED,   decreasing_fillcolor="#2b0d0d",
        line_width=1, name="Price",
    ), row=1, col=1)
    
    if "sma50" in cdf.columns:
        fig.add_trace(go.Scatter(x=dates, y=cdf["sma50"],
            line=dict(color=_BLUE, width=1.2), name="SMA 50"), row=1, col=1)
    if "sma150" in cdf.columns:
        fig.add_trace(go.Scatter(x=dates, y=cdf["sma150"],
            line=dict(color=_PURPLE, width=1, dash="dot"), name="SMA 150"), row=1, col=1)
    if "sma200" in cdf.columns:
        fig.add_trace(go.Scatter(x=dates, y=cdf["sma200"],
            line=dict(color=_YELLOW, width=1, dash="dash"), name="SMA 200"), row=1, col=1)
    
    for price, color, label in [
        (entry, _YELLOW, f"Pivot Rs{entry:,.2f}"),
        (stop,  _RED,    f"Stop Rs{stop:,.2f}"),
        (t1,    _GREEN,  f"T1 Rs{t1:,.2f}"),
        (t2,    "#4ade80", f"T2 Rs{t2:,.2f}"),
    ]:
        if price > 0:
            fig.add_hline(y=price, line=dict(color=color, width=1.2, dash="dash"),
                annotation_text=f"  {label}",
                annotation_position="right",
                annotation_font=dict(color=color, size=9),
                row=1, col=1)
    
    if "volume" in cdf.columns:
        vol_colors = [_GREEN if cdf["close"].iloc[i] >= cdf["close"].iloc[i-1] else _RED 
                      for i in range(len(cdf))]
        fig.add_trace(go.Bar(x=dates, y=cdf["volume"], marker_color=vol_colors,
            marker_opacity=0.7, name="Volume", showlegend=False), row=2, col=1)
    
    fig.update_layout(
        paper_bgcolor=_BG, plot_bgcolor=_BG,
        font=dict(color=_TEXT, size=9, family="Inter"),
        margin=dict(l=0, r=50, t=20, b=0), height=400,
        showlegend=False,
        xaxis_rangeslider_visible=False,
        title=dict(text=f"{symbol} - SEPA Analysis",
                   font=dict(size=11, color=_WHITE), x=0),
    )
    ax = dict(gridcolor=_BORDER, zerolinecolor=_BORDER,
              tickfont=dict(color=_MUTED, size=9), showgrid=True)
    fig.update_xaxes(**ax)
    fig.update_yaxes(**ax)
    return fig


# -- Entry points --------------------------------------------------------------

def render_content(df: pd.DataFrame = None, chart_store: dict = None):
    """Called from within a tab â€” accepts pre-fetched data or runs its own scan."""
    if df is None or chart_store is None:
        # Standalone fallback: run own scan with session state cache
        cache_key = "_elder_scan_data"
        if cache_key not in st.session_state:
            from components.ui import loading_html
            ph = st.empty()
            ph.markdown(loading_html("Running Elder Triple Screen scan..."), unsafe_allow_html=True)
            try:
                df, chart_store = _run(run_elder_scan())
                st.session_state[cache_key] = (df, chart_store)
            except Exception as e:
                ph.empty()
                st.error(f"Elder scan failed: {e}")
                st.code(traceback.format_exc())
                return
            ph.empty()
        else:
            df, chart_store = st.session_state[cache_key]

    _render_elder(df, chart_store)


def render(slot):
    """Called as a standalone page."""
    slot.empty()
    with slot.container():
        # Create tabs for all 4 scanners + backtest
        tab_elder, tab_sepa, tab_swing, tab_backtest = st.tabs([
            "Elder Triple Screen", 
            "SEPA Screener",
            "Master Swing Trader",
            "📊 Backtest"
        ])
        
        with tab_elder:
            render_elder_tab()
        
        with tab_sepa:
            render_sepa_tab()
        
        with tab_swing:
            render_swing_tab()
        
        with tab_backtest:
            render_backtest_tab()


def render_elder_tab():
    """Render Elder Triple Screen tab"""
    cache_key = "_elder_scan_data"
    if cache_key not in st.session_state:
        from components.ui import loading_html
        ph = st.empty()
        ph.markdown(loading_html("Running Elder Triple Screen scan..."), unsafe_allow_html=True)
        try:
            df, chart_store = _run(run_elder_scan())
            st.session_state[cache_key] = (df, chart_store)
        except Exception as e:
            ph.empty()
            st.error(f"Elder scan failed: {e}")
            st.code(traceback.format_exc())
            return
        ph.empty()
    else:
        df, chart_store = st.session_state[cache_key]
    
    _render_elder(df, chart_store)


def render_sepa_tab():
    """Render SEPA Screener tab"""
    cache_key = "_sepa_scan_data"
    if cache_key not in st.session_state:
        from components.ui import loading_html
        ph = st.empty()
        ph.markdown(loading_html("Running SEPA scan..."), unsafe_allow_html=True)
        try:
            df, chart_store = _run(run_sepa_scan())
            st.session_state[cache_key] = (df, chart_store)
        except Exception as e:
            ph.empty()
            st.error(f"SEPA scan failed: {e}")
            st.code(traceback.format_exc())
            return
        ph.empty()
    else:
        df, chart_store = st.session_state[cache_key]
    
    _render_sepa(df, chart_store)


def render_swing_tab():
    """Render Master Swing Trader tab"""
    cache_key = "_swing_scan_data"
    if cache_key not in st.session_state:
        from components.ui import loading_html
        ph = st.empty()
        ph.markdown(loading_html("Running Master Swing Trader scan..."), unsafe_allow_html=True)
        try:
            df, chart_store = _run(run_swing_scan())
            st.session_state[cache_key] = (df, chart_store)
        except Exception as e:
            ph.empty()
            st.error(f"Swing scan failed: {e}")
            st.code(traceback.format_exc())
            return
        ph.empty()
    else:
        df, chart_store = st.session_state[cache_key]
    
    _render_swing(df, chart_store)


def _render_swing(df: pd.DataFrame, chart_store: dict):
    """Render Master Swing Trader results (matches Elder/SEPA UI exactly)"""
    if df.empty:
        st.warning("No stocks meet the Master Swing Trader criteria.")
        return
    
    # Summary metrics
    master = df[df["grade"] == "Master Setup"]
    strong = df[df["grade"] == "Strong Setup"]
    good = df[df["grade"] == "Good Setup"]
    buy_now = df[df["signal"] == "STRONG BUY"]
    buy = df[df["signal"] == "BUY"]
    
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Top Stocks", len(df))
    c2.metric("Master Setup", len(master))
    c3.metric("Strong Setup", len(strong))
    c4.metric("Good Setup", len(good))
    c5.metric("Strong Buy", len(buy_now))
    c6.metric("Buy", len(buy))
    
    st.markdown("---")
    
    # Tabs for Buy Now vs Watchlist
    buy_ready = df[df["signal"].isin(["STRONG BUY", "BUY"])]
    watch_list = df[df["signal"] == "WATCH"]
    
    tab_all, tab_buy, tab_watch = st.tabs([
        f"All Setups ({len(df)})",
        f"Buy Ready ({len(buy_ready)})",
        f"Watch List ({len(watch_list)})"
    ])
    
    with tab_all:
        st.markdown('<div style="font-size:.65rem;font-weight:600;color:#6b7280;text-transform:uppercase;letter-spacing:.05em;margin-bottom:8px;">Top 10 Swing Setups (Sorted by Score)</div>', unsafe_allow_html=True)
        for idx, row in df.iterrows():
            _render_swing_row(row, chart_store, key_prefix=f"all_{idx}")
    
    with tab_buy:
        st.markdown('<div style="font-size:.65rem;font-weight:600;color:#6b7280;text-transform:uppercase;letter-spacing:.05em;margin-bottom:8px;">Buy Ready Stocks</div>', unsafe_allow_html=True)
        if buy_ready.empty:
            st.info("No stocks in BUY status")
        else:
            for idx, row in buy_ready.iterrows():
                _render_swing_row(row, chart_store, key_prefix=f"buy_{idx}")
    
    with tab_watch:
        st.markdown('<div style="font-size:.65rem;font-weight:600;color:#6b7280;text-transform:uppercase;letter-spacing:.05em;margin-bottom:8px;">Watch List</div>', unsafe_allow_html=True)
        if watch_list.empty:
            st.info("No stocks in watch list")
        else:
            for idx, row in watch_list.iterrows():
                _render_swing_row(row, chart_store, key_prefix=f"watch_{idx}")


def _render_swing_row(row: pd.Series, chart_store: dict, key_prefix: str = ""):
    """Render a single Swing stock row (matches Elder UI exactly)"""
    symbol  = row.get("symbol", "")
    score   = row.get("score", 0)
    grade   = row.get("grade", "")
    signal  = row.get("signal", "NO TRADE")
    price   = row.get("price", 0)
    pct     = row.get("change_pct", 0)
    entry   = row.get("entry", price)
    stop    = row.get("stop", 0)
    t1      = row.get("target1", 0)
    rr      = row.get("risk_reward", 0)
    
    # Grade color
    if "Master" in grade:
        grade_c = _GREEN
    elif "Strong" in grade:
        grade_c = "#4ade80"
    elif "Good" in grade:
        grade_c = _YELLOW
    else:
        grade_c = _MUTED
    
    pct_c   = _GREEN if pct > 0 else (_RED if pct < 0 else _MUTED)
    pct_s   = f"+{pct:.2f}%" if pct > 0 else f"{pct:.2f}%"
    
    label = f"{symbol}  |  Rs{price:,.2f}  {pct_s}  |  Entry: Rs{entry:,.2f}  |  {signal}  |  Swing Score {score}"
    
    with st.expander(label, expanded=False):
        components.html(f"""<!DOCTYPE html><html><head>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>*{{box-sizing:border-box;margin:0;padding:0;font-family:'Inter',sans-serif;}}</style>
</head><body style="background:#0b0e17;padding:0;">
<div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:8px;">
  <div style="background:#131722;border:1px solid #1e2433;border-radius:4px;padding:8px 12px;flex:1;min-width:110px;">
    <div style="font-size:.58rem;color:#6b7280;text-transform:uppercase;">CMP</div>
    <div style="font-size:.9rem;font-weight:700;color:#fff;">Rs{price:,.2f}
      <span style="font-size:.65rem;color:{pct_c};margin-left:4px;">{pct_s}</span></div>
  </div>
  <div style="background:#131722;border:1px solid #1e2433;border-radius:4px;padding:8px 12px;flex:1;min-width:110px;">
    <div style="font-size:.58rem;color:#6b7280;text-transform:uppercase;">Entry</div>
    <div style="font-size:.9rem;font-weight:700;color:{_YELLOW};">Rs{entry:,.2f}</div>
  </div>
  <div style="background:#131722;border:1px solid #1e2433;border-radius:4px;padding:8px 12px;flex:1;min-width:110px;">
    <div style="font-size:.58rem;color:#6b7280;text-transform:uppercase;">Stop</div>
    <div style="font-size:.9rem;font-weight:700;color:{_RED};">Rs{stop:,.2f}</div>
  </div>
  <div style="background:#131722;border:1px solid #1e2433;border-radius:4px;padding:8px 12px;flex:1;min-width:110px;">
    <div style="font-size:.58rem;color:#6b7280;text-transform:uppercase;">Target 1</div>
    <div style="font-size:.9rem;font-weight:700;color:{_GREEN};">Rs{t1:,.2f}</div>
  </div>
  <div style="background:#131722;border:1px solid #1e2433;border-radius:4px;padding:8px 12px;flex:1;min-width:80px;">
    <div style="font-size:.58rem;color:#6b7280;text-transform:uppercase;">R:R</div>
    <div style="font-size:.9rem;font-weight:700;color:{'#4ade80' if rr>=2 else _YELLOW};">{rr:.2f}</div>
  </div>
  <div style="background:{grade_c}18;border:1px solid {grade_c}44;border-radius:4px;padding:8px 12px;min-width:70px;text-align:center;">
    <div style="font-size:.58rem;color:#6b7280;text-transform:uppercase;">Grade</div>
    <div style="font-size:1.1rem;font-weight:800;color:{grade_c};">{grade}</div>
  </div>
</div>
<div style="font-size:.67rem;color:#6b7280;">
  {row.get('company_name','')} - {row.get('sector','')}
</div>
</body></html>""", height=110, scrolling=False)
        
        col_exp, col_chart = st.columns([1, 2])
        with col_exp:
            components.html(_render_swing_explanation_html(row), height=520, scrolling=True)
        with col_chart:
            cdf = chart_store.get(symbol)
            if cdf is not None and not cdf.empty:
                fig = _build_swing_chart(symbol, row, cdf)
                st.plotly_chart(fig, use_container_width=True,
                                config={"displayModeBar": False},
                                key=f"{key_prefix}_chart_{symbol}")
            else:
                st.info("Chart data unavailable.")("ðŸ“Š Swing Chart coming soon")


def _render_swing_explanation_html(row: pd.Series) -> str:
    """Render Swing score breakdown as HTML string"""
    trend_d = row.get("trend_detail", {})
    pattern_d = row.get("pattern_detail", {})
    sr_d = row.get("sr_detail", {})
    momentum_d = row.get("momentum_detail", {})
    rr_d = row.get("rr_detail", {})
    
    score = row.get("score", 0)
    grade = row.get("grade", "")
    
    # Grade color
    if "Master" in grade:
        grade_c = _GREEN
    elif "Strong" in grade:
        grade_c = "#4ade80"
    elif "Good" in grade:
        grade_c = _YELLOW
    else:
        grade_c = _MUTED
    
    def sec(title: str, color: str) -> str:
        return (
            f'<div style="font-size:.62rem;font-weight:700;color:{color};'
            f'text-transform:uppercase;letter-spacing:.08em;margin:10px 0 4px;">'
            f'{title}</div>'
        )
    
    html = f"""<!DOCTYPE html><html><head>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>*{{box-sizing:border-box;margin:0;padding:0;font-family:'Inter',sans-serif;font-size:.75rem;}}
body{{background:#0b0e17;color:#d1d4dc;padding:12px;}}</style></head><body>

<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
  <div>
    <span style="font-size:1.1rem;font-weight:800;color:#fff;">{row.get('symbol','')}</span>
    <span style="color:#6b7280;margin-left:6px;font-size:.72rem;">Swing Analysis</span>
  </div>
  <div style="background:{grade_c}18;border:2px solid {grade_c};border-radius:4px;padding:6px 14px;">
    <span style="font-size:1.2rem;font-weight:800;color:{grade_c};">{score}</span>
    <span style="font-size:.65rem;color:#6b7280;margin-left:4px;">{grade}</span>
  </div>
</div>

{sec("TREND ALIGNMENT (25 pts)", _BLUE)}
<div style="font-size:.68rem;color:#9ca3af;">
  Strength: {trend_d.get('trend_strength', 'N/A')}<br/>
  Price vs EMAs: {trend_d.get('price_above_emas', 'N/A')}<br/>
  ADX: {trend_d.get('adx', 0):.1f}<br/>
  Score: {row.get('trend_score', 0)}/25
</div>

{sec("PATTERN RECOGNITION (25 pts)", _PURPLE)}
<div style="font-size:.68rem;color:#9ca3af;">
  Pattern: {pattern_d.get('pattern_name', 'None')}<br/>
  Quality: {pattern_d.get('quality', 'N/A')}<br/>
  Score: {row.get('pattern_score', 0)}/25
</div>

{sec("SUPPORT/RESISTANCE (20 pts)", _ORANGE)}
<div style="font-size:.68rem;color:#9ca3af;">
  Support: Rs{sr_d.get('support', 0):,.2f}<br/>
  Resistance: Rs{sr_d.get('resistance', 0):,.2f}<br/>
  Quality: {sr_d.get('quality', 'N/A')}<br/>
  Score: {row.get('sr_score', 0)}/20
</div>

{sec("MOMENTUM/VOLUME (15 pts)", _YELLOW)}
<div style="font-size:.68rem;color:#9ca3af;">
  RSI: {momentum_d.get('rsi', 0):.1f}<br/>
  Volume: {momentum_d.get('volume_strength', 'N/A')}<br/>
  Score: {row.get('momentum_score', 0)}/15
</div>

{sec("RISK/REWARD (15 pts)", _GREEN)}
<div style="font-size:.68rem;color:#9ca3af;">
  Entry: Rs{rr_d.get('entry', 0):,.2f}<br/>
  Stop: Rs{rr_d.get('stop', 0):,.2f}<br/>
  Target: Rs{rr_d.get('target1', 0):,.2f}<br/>
  R:R Ratio: {rr_d.get('risk_reward', 0):.2f}:1<br/>
  Risk: {rr_d.get('risk_pct', 0):.1f}%<br/>
  Score: {row.get('rr_score', 0)}/15
</div>

</body></html>"""
    
    return html


def render_backtest_tab():
    """Render Backtest Results tab - Buy Ready signals only"""
    
    # Fetch backtest data (last 30 days, all scanners)
    cache_key = "_backtest_data_30_All"
    
    if cache_key not in st.session_state:
        from components.ui import loading_html
        from services.backtest import get_backtest_results
        
        ph = st.empty()
        ph.markdown(loading_html("Analyzing historical signals..."), unsafe_allow_html=True)
        
        try:
            results_df = _run(get_backtest_results(days=30, scanner_type=None))
            st.session_state[cache_key] = results_df
            ph.empty()
        except Exception as e:
            ph.empty()
            st.error(f"Failed to fetch backtest data: {e}")
            st.code(traceback.format_exc())
            return
    else:
        results_df = st.session_state[cache_key]
    
    if results_df.empty:
        st.info("No historical signals found. Signals will appear here after running scans.")
        return
    
    # Filter for Buy Ready signals only (BUY NOW, BUY ON BREAKOUT, STRONG BUY, BUY)
    buy_signals = ["BUY NOW", "BUY ON BREAKOUT", "STRONG BUY", "BUY"]
    buy_ready_df = results_df[results_df["signal"].isin(buy_signals)]
    
    if buy_ready_df.empty:
        st.info("No Buy Ready signals in the last 30 days.")
        return
    
    # Prepare display dataframe with Strategy column
    display_df = buy_ready_df[[
        "signal_date", "scanner_type", "symbol", "entry_price", 
        "current_price", "target1_price", 
        "target1_achieved", "achieved_date", "status"
    ]].copy()
    
    display_df.columns = [
        "Date", "Strategy", "Symbol", "Entry", "CMP", "Target", 
        "Achieved", "Achieved Date", "Status"
    ]
    
    # Format columns
    display_df["Entry"] = display_df["Entry"].apply(lambda x: f"₹{x:,.2f}" if x > 0 else "-")
    display_df["CMP"] = display_df["CMP"].apply(lambda x: f"₹{x:,.2f}" if x > 0 else "-")
    display_df["Target"] = display_df["Target"].apply(lambda x: f"₹{x:,.2f}" if x > 0 else "-")
    display_df["Achieved"] = display_df["Achieved"].apply(lambda x: "✅ Yes" if x else "❌ No")
    display_df["Achieved Date"] = display_df["Achieved Date"].fillna("-")
    
    # Apply styling
    def style_status(val):
        if "T2 Achieved" in val or "T1 Achieved" in val:
            return "background-color: #00c85320; color: #00c853; font-weight: 600;"
        elif "Stop Hit" in val:
            return "background-color: #ef444420; color: #ef4444; font-weight: 600;"
        elif "Active" in val:
            return "background-color: #60a5fa20; color: #60a5fa; font-weight: 600;"
        return ""
    
    def style_achieved(val):
        if "✅" in val:
            return "color: #00c853;"
        elif "❌" in val:
            return "color: #ef4444;"
        return ""
    
    # Display as styled dataframe
    st.dataframe(
        display_df.style.map(style_status, subset=["Status"])
                        .map(style_achieved, subset=["Achieved"]),
        use_container_width=True,
        height=600
    )
