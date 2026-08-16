"""
Elder Triple Screen Swing Scanner page.
"""
import asyncio
import traceback
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from services.elder_scanner import run_elder_scan

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
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


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


# -- Elder chart ---------------------------------------------------------------

def _build_elder_chart(symbol: str, row: pd.Series, cdf: pd.DataFrame) -> go.Figure:
    if cdf.empty:
        return go.Figure()

    dates = cdf["datetime"] if "datetime" in cdf.columns else pd.RangeIndex(len(cdf))
    entry = row.get("entry", 0)
    stop  = row.get("stop", 0)
    t1    = row.get("target1", 0)
    t2    = row.get("target2", 0)

    fig = make_subplots(
        rows=3, cols=1, shared_xaxes=True,
        row_heights=[0.55, 0.22, 0.23], vertical_spacing=0.02,
        subplot_titles=("", "Force Index 2-EMA", "MACD Histogram"),
    )

    fig.add_trace(go.Candlestick(
        x=dates, open=cdf["open"], high=cdf["high"],
        low=cdf["low"], close=cdf["close"],
        increasing_line_color=_GREEN, increasing_fillcolor="#0d2b1a",
        decreasing_line_color=_RED,   decreasing_fillcolor="#2b0d0d",
        line_width=1, name="Price",
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
        title=dict(text=f"{symbol} - Elder Triple Screen",
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
    if df is None or df.empty:
        st.info("No stocks currently pass the Triple Screen criteria. The system says NO TRADE.")
        return

    # Filter: only A+, A, B grades (remove WATCHLIST)
    df = df[df["grade"].isin(["A+", "A", "B"])]
    
    if df.empty:
        st.info("No stocks with A+, A, or B grades.")
        return

    a_plus  = df[df["grade"] == "A+"]
    a_grade = df[df["grade"] == "A"]
    b_grade = df[df["grade"] == "B"]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Setups", len(df))
    c2.metric("A+ Setups",    len(a_plus))
    c3.metric("A Setups",     len(a_grade))
    c4.metric("B Setups",     len(b_grade))

    t_ap, t_a, t_b, t_all = st.tabs([
        f"A+ ({len(a_plus)})",
        f"A ({len(a_grade)})",
        f"B ({len(b_grade)})",
        f"All ({len(df)})",
    ])

    def _tab(subset: pd.DataFrame, prefix: str):
        if subset.empty:
            st.info("No setups in this category.")
            return
        for _, row in subset.head(20).iterrows():
            _render_row(row, chart_store, key_prefix=prefix)

    with t_ap:  _tab(a_plus,   "ap_")
    with t_a:   _tab(a_grade,  "a_")
    with t_b:   _tab(b_grade,  "b_")
    with t_all: _tab(df,       "all_")


# -- Entry points --------------------------------------------------------------

def render_content():
    """Called from within a tab — no slot needed."""
    st.empty()  # Clear lingering components
    ph = st.empty()
    ph.markdown(
        '<style>#qx-loading-overlay{position:relative!important;height:300px!important;'
        'top:0!important;background:transparent!important;}</style>',
        unsafe_allow_html=True,
    )
    from components.ui import loading_html
    ph.markdown(loading_html("Running Elder Triple Screen scan..."), unsafe_allow_html=True)
    try:
        df, chart_store = _run(run_elder_scan())
    except Exception as e:
        ph.empty()
        st.error(f"Elder scan failed: {e}")
        st.code(traceback.format_exc())
        return
    ph.empty()
    _render_elder(df, chart_store)


def render(slot):
    """Called as a standalone page."""
    slot.empty()
    render_content()
