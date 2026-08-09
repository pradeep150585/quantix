"""
Page 5 – AI Top Picks (VCP Scanner)
"""
import asyncio
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.express as px
from services.vcp_scanner import run_vcp_scan
from components.ui import loading_html

_BG     = "#0b0e17"
_CARD   = "#131722"
_BORDER = "#1e2433"
_TEXT   = "#d1d4dc"
_MUTED  = "#6b7280"
_WHITE  = "#ffffff"
_GREEN  = "#00c853"
_RED    = "#ef4444"
_BLUE   = "#60a5fa"
_YELLOW = "#fbbf24"
_PURPLE = "#a78bfa"


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _score_color(s: float) -> str:
    return _GREEN if s >= 75 else (_YELLOW if s >= 50 else _RED)


def _badge_html(text: str, color: str) -> str:
    return (
        f'<span style="background:{color}18;color:{color};border:1px solid {color}44;'
        f'border-radius:3px;padding:2px 8px;font-size:.63rem;font-weight:600;">{text}</span>'
    )


# ── VCP Chart ─────────────────────────────────────────────────────────────────

def _build_vcp_chart(symbol: str, row: pd.Series, chart_data: dict) -> go.Figure:
    cdf    = chart_data["df"]
    hi_idx = chart_data["hi"]
    lo_idx = chart_data["lo"]
    pivot  = row.get("pivot", 0)
    is_bo  = row.get("is_breakout", False)

    dates  = cdf["datetime"] if "datetime" in cdf.columns else pd.RangeIndex(len(cdf))

    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        row_heights=[0.72, 0.28],
        vertical_spacing=0.03,
    )

    # ── Candlesticks ──
    fig.add_trace(go.Candlestick(
        x=dates,
        open=cdf["open"], high=cdf["high"],
        low=cdf["low"],   close=cdf["close"],
        increasing_line_color=_GREEN,  increasing_fillcolor="#0d2b1a",
        decreasing_line_color=_RED,    decreasing_fillcolor="#2b0d0d",
        line_width=1, name="Price",
    ), row=1, col=1)

    # ── SMAs ──
    if "sma50" in cdf.columns:
        fig.add_trace(go.Scatter(
            x=dates, y=cdf["sma50"],
            line=dict(color=_BLUE, width=1.2, dash="solid"),
            name="SMA 50", hoverinfo="skip",
        ), row=1, col=1)

    if "sma150" in cdf.columns:
        fig.add_trace(go.Scatter(
            x=dates, y=cdf["sma150"],
            line=dict(color=_PURPLE, width=1.2, dash="dot"),
            name="SMA 150", hoverinfo="skip",
        ), row=1, col=1)

    # ── Swing highs ──
    if hi_idx:
        sh_dates = [dates.iloc[i] for i in hi_idx if i < len(cdf)]
        sh_vals  = [float(cdf["high"].iloc[i]) for i in hi_idx if i < len(cdf)]
        fig.add_trace(go.Scatter(
            x=sh_dates, y=[v * 1.005 for v in sh_vals],
            mode="markers+text",
            marker=dict(symbol="triangle-down", size=10, color=_RED),
            text=["H"] * len(sh_dates),
            textposition="top center",
            textfont=dict(size=8, color=_RED),
            name="Swing High", hovertemplate="%{y:.2f}",
        ), row=1, col=1)

    # ── Swing lows ──
    if lo_idx:
        sl_dates = [dates.iloc[i] for i in lo_idx if i < len(cdf)]
        sl_vals  = [float(cdf["low"].iloc[i]) for i in lo_idx if i < len(cdf)]
        fig.add_trace(go.Scatter(
            x=sl_dates, y=[v * 0.995 for v in sl_vals],
            mode="markers+text",
            marker=dict(symbol="triangle-up", size=10, color=_GREEN),
            text=["L"] * len(sl_dates),
            textposition="bottom center",
            textfont=dict(size=8, color=_GREEN),
            name="Swing Low", hovertemplate="%{y:.2f}",
        ), row=1, col=1)

    # ── Contraction zone shading (between consecutive swing high/low pairs) ──
    if hi_idx and lo_idx:
        paired_hi = [i for i in hi_idx if any(j > i for j in lo_idx)]
        for k, hi in enumerate(paired_hi):
            next_lo = next((j for j in lo_idx if j > hi), None)
            if next_lo is None or hi >= len(cdf) or next_lo >= len(cdf):
                continue
            x0 = dates.iloc[hi]
            x1 = dates.iloc[next_lo]
            shade = "rgba(251,191,36,0.06)" if k % 2 == 0 else "rgba(96,165,250,0.06)"
            fig.add_vrect(
                x0=x0, x1=x1,
                fillcolor=shade, opacity=1.0,
                layer="below", line_width=0,
            )

    # ── Pivot line ──
    if pivot > 0:
        fig.add_hline(
            y=pivot,
            line=dict(color=_YELLOW, width=1.5, dash="dash"),
            annotation_text=f"  Pivot ₹{pivot:,.2f}",
            annotation_position="right",
            annotation_font=dict(color=_YELLOW, size=10),
            row=1, col=1,
        )

    # ── Breakout marker ──
    if is_bo:
        last_date  = dates.iloc[-1]
        last_close = float(cdf["close"].iloc[-1])
        fig.add_trace(go.Scatter(
            x=[last_date], y=[last_close * 1.01],
            mode="markers+text",
            marker=dict(symbol="star", size=14, color=_GREEN,
                        line=dict(color=_WHITE, width=1)),
            text=["BREAKOUT"],
            textposition="top center",
            textfont=dict(size=9, color=_GREEN, family="Inter"),
            name="Breakout", hoverinfo="skip",
        ), row=1, col=1)

    # ── Volume bars ──
    vol_colors = [
        _GREEN if float(cdf["close"].iloc[i]) >= float(cdf["open"].iloc[i]) else _RED
        for i in range(len(cdf))
    ]
    vol_20avg = float(cdf["volume"].tail(21).iloc[:-1].mean()) if len(cdf) > 20 else 0
    fig.add_trace(go.Bar(
        x=dates, y=cdf["volume"],
        marker_color=vol_colors, marker_opacity=0.6,
        name="Volume", showlegend=False,
    ), row=2, col=1)

    if vol_20avg > 0:
        fig.add_hline(
            y=vol_20avg,
            line=dict(color=_MUTED, width=1, dash="dot"),
            annotation_text="  20d avg",
            annotation_font=dict(color=_MUTED, size=9),
            row=2, col=1,
        )

    # ── Layout ──
    fig.update_layout(
        paper_bgcolor=_BG, plot_bgcolor=_BG,
        font=dict(color=_TEXT, size=11, family="Inter"),
        margin=dict(l=0, r=60, t=32, b=0),
        height=520,
        showlegend=True,
        legend=dict(
            orientation="h", x=0, y=1.02,
            font=dict(size=10, color=_MUTED),
            bgcolor="rgba(0,0,0,0)",
        ),
        xaxis_rangeslider_visible=False,
        title=dict(
            text=f"{symbol} — VCP Chart",
            font=dict(size=13, color=_WHITE, family="Inter"),
            x=0,
        ),
    )
    axis_style = dict(
        gridcolor=_BORDER, gridwidth=1,
        zerolinecolor=_BORDER,
        tickfont=dict(color=_MUTED, size=10),
        showgrid=True,
    )
    fig.update_xaxes(**axis_style)
    fig.update_yaxes(**axis_style)
    fig.update_yaxes(tickprefix="₹", row=1, col=1)

    return fig


# ── Stock card ────────────────────────────────────────────────────────────────

def _render_card(row: pd.Series, rank: int, chart_store: dict):
    symbol    = row.get("symbol", "")
    score     = row.get("vcp_score", 0)
    cmp       = row.get("cmp", 0)
    pct       = row.get("pct_change", 0)
    pct_color = _GREEN if pct > 0 else (_RED if pct < 0 else _MUTED)
    pct_arr   = "▲" if pct > 0 else ("▼" if pct < 0 else "—")
    score_c   = _score_color(score)
    is_bo     = row.get("is_breakout", False)
    pivot     = row.get("pivot", 0)
    vr        = row.get("volume_ratio", 0)
    n_cont    = row.get("contractions", 0)
    cont_pcts = row.get("contraction_pcts", [])
    cont_str  = " → ".join(f"{c:.1f}%" for c in cont_pcts) if cont_pcts else "—"

    badge_map = {
        "Breakout":  _GREEN,
        "Squeeze":   _BLUE,
        "Vol Dry-up": _YELLOW,
    }
    badges_html = " ".join(
        _badge_html(b, badge_map.get(b, _PURPLE))
        for b in row.get("badges", [])[:4]
    )
    bo_tag = (
        '<span style="background:rgba(0,200,83,.12);color:#00c853;border:1px solid '
        'rgba(0,200,83,.3);border-radius:3px;padding:2px 8px;font-size:.63rem;'
        'font-weight:700;">BREAKOUT</span>'
        if is_bo else ""
    )

    st.markdown(f"""
<div style="background:{_CARD};border:1px solid {'#00c853' if is_bo else _BORDER};
    border-radius:5px;padding:14px 16px;margin-bottom:2px;border-left:3px solid {score_c};">
  <div style="display:flex;align-items:center;gap:12px;">
    <div style="font-size:1rem;font-weight:800;color:{_MUTED};min-width:28px;
        text-align:center;background:#1e2433;border-radius:4px;padding:5px 0;">
      #{rank}
    </div>
    <div style="flex:1;min-width:0;">
      <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:6px;">
        <div style="display:flex;align-items:center;gap:8px;">
          <span style="font-size:.95rem;font-weight:700;color:{_WHITE};">{symbol}</span>
          {bo_tag}
        </div>
        <span style="font-size:1rem;font-weight:700;color:{_TEXT};">₹{cmp:,.2f}
          <span style="font-size:.72rem;color:{pct_color};font-weight:600;margin-left:4px;">
            {pct_arr} {abs(pct):.2f}%
          </span>
        </span>
      </div>
      <div style="font-size:.7rem;color:{_MUTED};margin-top:2px;">
        {row.get('company_name','')} · {row.get('sector','')}
      </div>
      <div style="display:flex;gap:14px;margin-top:5px;font-size:.7rem;flex-wrap:wrap;">
        <span style="color:{_MUTED};">Contractions <b style="color:{_TEXT};">{n_cont}</b></span>
        <span style="color:{_MUTED};">Pivot <b style="color:{_TEXT};">₹{pivot:,.2f}</b></span>
        <span style="color:{_MUTED};">Vol <b style="color:{_TEXT};">{vr:.2f}x</b></span>
        <span style="color:{_MUTED};">52W Hi <b style="color:{_TEXT};">{row.get('dist_52h_pct',0):.1f}%</b></span>
        <span style="color:{_MUTED};">ATR <b style="color:{_TEXT};">{row.get('atr',0):.2f}</b></span>
      </div>
      <div style="font-size:.67rem;color:{_MUTED};margin-top:3px;">
        Contractions: <span style="color:{_TEXT};">{cont_str}</span>
      </div>
      <div style="margin-top:5px;">{badges_html}</div>
    </div>
    <div style="text-align:center;min-width:58px;background:#1e2433;border-radius:5px;padding:9px 6px;">
      <div style="font-size:1.35rem;font-weight:800;color:{score_c};">{score:.0f}</div>
      <div style="font-size:.56rem;color:{_MUTED};letter-spacing:.05em;text-transform:uppercase;">VCP</div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

    # Expandable chart
    with st.expander(f"📈 {symbol} — View VCP Chart", expanded=False):
        chart_data = chart_store.get(symbol)
        if chart_data is None or chart_data["df"].empty:
            st.info("Chart data not available.")
        else:
            fig = _build_vcp_chart(symbol, row, chart_data)
            st.plotly_chart(fig, use_container_width=True,
                            config={"displayModeBar": False},
                            key=f"vcp_chart_{symbol}_{rank}")

            # Key stats row under chart
            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("CMP",       f"₹{cmp:,.2f}")
            c2.metric("Pivot",     f"₹{pivot:,.2f}")
            c3.metric("SMA 50",    f"₹{row.get('sma50',0):,.2f}")
            c4.metric("SMA 150",   f"₹{row.get('sma150',0):,.2f}")
            c5.metric("VCP Score", f"{score:.0f}")


# ── Page render ───────────────────────────────────────────────────────────────

def render(slot):
    slot.empty()
    slot.markdown(loading_html("Scanning for VCP setups…"), unsafe_allow_html=True)

    try:
        df, chart_store = _run(run_vcp_scan())
    except Exception as e:
        slot.empty()
        st.error(f"VCP scan failed: {e}")
        import traceback
        st.code(traceback.format_exc())
        return

    slot.empty()

    if df is None or df.empty:
        st.markdown(f"""
<div style="background:{_CARD};border:1px solid {_BORDER};border-radius:6px;
    padding:40px 32px;text-align:center;margin-top:20px;">
  <div style="font-size:1.8rem;margin-bottom:12px;">📉</div>
  <div style="font-size:.9rem;font-weight:700;color:{_WHITE};margin-bottom:8px;">No VCP Setups Found</div>
  <div style="font-size:.78rem;color:{_MUTED};line-height:1.6;">
    No stocks currently meet the VCP criteria.<br>
    Check back when market conditions improve or data is available.
  </div>
</div>
""", unsafe_allow_html=True)
        return

    breakouts  = df[df["is_breakout"] == True]
    near_pivot = df[(df["is_breakout"] == False) & (df["dist_52h_pct"] >= -8)]
    avg_score  = df["vcp_score"].mean()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("VCP Setups",      len(df))
    c2.metric("Active Breakouts", len(breakouts))
    c3.metric("Near Pivot",       len(near_pivot))
    c4.metric("Avg VCP Score",    f"{avg_score:.1f}")

    st.markdown("<div style='margin-bottom:12px;'></div>", unsafe_allow_html=True)

    # Sector chart
    if "sector" in df.columns and df["sector"].notna().any():
        sector_df = (
            df.groupby("sector")["vcp_score"].mean()
            .reset_index().sort_values("vcp_score", ascending=False)
        )
        fig_s = px.bar(
            sector_df, x="sector", y="vcp_score",
            color="vcp_score",
            color_continuous_scale=[[0, _RED], [0.5, _YELLOW], [1, _GREEN]],
            height=220,
        )
        fig_s.update_layout(
            paper_bgcolor=_BG, plot_bgcolor=_BG,
            font=dict(color=_MUTED, size=11, family="Inter"),
            showlegend=False, coloraxis_showscale=False,
            margin=dict(l=0, r=0, t=8, b=0),
            xaxis=dict(gridcolor=_BORDER, tickangle=-30, tickfont=dict(color=_MUTED, size=10)),
            yaxis=dict(gridcolor=_BORDER, tickfont=dict(color=_MUTED)),
        )
        st.plotly_chart(fig_s, use_container_width=True,
                        config={"displayModeBar": False}, key="vcp_sector_chart")
        st.markdown("<hr>", unsafe_allow_html=True)

    # Top 30 score bar
    fig = px.bar(
        df.head(30), x="symbol", y="vcp_score",
        color="vcp_score",
        color_continuous_scale=[[0, _RED], [0.5, _YELLOW], [1, _GREEN]],
        labels={"vcp_score": "VCP Score", "symbol": ""},
        height=200,
    )
    fig.update_layout(
        paper_bgcolor=_BG, plot_bgcolor=_BG,
        font=dict(color=_MUTED, size=11, family="Inter"),
        showlegend=False, coloraxis_showscale=False,
        margin=dict(l=0, r=0, t=8, b=0),
        xaxis=dict(gridcolor=_BORDER, tickfont=dict(color=_MUTED, size=10)),
        yaxis=dict(gridcolor=_BORDER, tickfont=dict(color=_MUTED)),
    )
    st.plotly_chart(fig, use_container_width=True,
                    config={"displayModeBar": False}, key="vcp_top30_chart")

    tab1, tab2, tab3 = st.tabs([
        f"All Setups ({len(df)})",
        f"Active Breakouts ({len(breakouts)})",
        f"Near Pivot ({len(near_pivot)})",
    ])

    with tab1:
        for rank, (_, row) in enumerate(df.head(20).iterrows(), 1):
            _render_card(row, rank, chart_store)

    with tab2:
        if breakouts.empty:
            st.info("No active breakouts right now.")
        else:
            for rank, (_, row) in enumerate(breakouts.head(20).iterrows(), 1):
                _render_card(row, rank, chart_store)

    with tab3:
        if near_pivot.empty:
            st.info("No stocks near pivot right now.")
        else:
            for rank, (_, row) in enumerate(near_pivot.head(20).iterrows(), 1):
                _render_card(row, rank, chart_store)
