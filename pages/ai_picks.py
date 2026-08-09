"""
Page 5 – AI Top Picks (VCP Scanner)
"""
import asyncio
import streamlit as st
import pandas as pd
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


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _badge(text: str, color: str, bg: str) -> str:
    return (
        f'<span style="background:{bg};color:{color};border:1px solid {color}33;'
        f'border-radius:3px;padding:2px 8px;font-size:.63rem;font-weight:600;">{text}</span>'
    )


def _score_color(score: float) -> str:
    if score >= 75: return _GREEN
    if score >= 50: return _YELLOW
    return _RED


def _render_card(row: pd.Series, rank: int):
    score     = row.get("vcp_score", 0)
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

    badges_html = " ".join(
        _badge(b,
               _GREEN  if b == "Breakout"   else
               _BLUE   if b == "Squeeze"    else
               _YELLOW if b == "Vol Dry-up" else _MUTED,
               "rgba(0,200,83,.08)"  if b == "Breakout"   else
               "rgba(96,165,250,.08)" if b == "Squeeze"   else
               "rgba(251,191,36,.08)" if b == "Vol Dry-up" else "rgba(107,114,128,.08)")
        for b in row.get("badges", [])[:4]
    )

    border_color = _GREEN if is_bo else _BORDER

    st.markdown(f"""
    <div style="background:{_CARD};border:1px solid {border_color};border-radius:5px;
        padding:14px 16px;margin-bottom:6px;border-left:3px solid {score_c};">
      <div style="display:flex;align-items:center;gap:12px;">
        <div style="font-size:1.1rem;font-weight:800;color:{_MUTED};min-width:32px;
            text-align:center;background:#1e2433;border-radius:4px;padding:6px 0;">
          #{rank}
        </div>
        <div style="flex:1;min-width:0;">
          <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:6px;">
            <div style="display:flex;align-items:center;gap:8px;">
              <span style="font-size:.95rem;font-weight:700;color:{_WHITE};">{row.get('symbol','')}</span>
              {'<span style="background:rgba(0,200,83,.12);color:#00c853;border:1px solid rgba(0,200,83,.3);border-radius:3px;padding:2px 8px;font-size:.63rem;font-weight:700;">BREAKOUT</span>' if is_bo else ''}
            </div>
            <span style="font-size:1rem;font-weight:700;color:{_TEXT};">₹{row.get('cmp',0):,.2f}</span>
          </div>
          <div style="font-size:.72rem;color:{_MUTED};margin-top:2px;">{row.get('company_name','')} · {row.get('sector','')}</div>
          <div style="display:flex;gap:14px;margin-top:6px;font-size:.72rem;flex-wrap:wrap;">
            <span style="color:{pct_color};font-weight:600;">{pct_arr} {abs(pct):.2f}%</span>
            <span style="color:{_MUTED};">Contractions <b style="color:{_TEXT};">{n_cont}</b></span>
            <span style="color:{_MUTED};">Pivot <b style="color:{_TEXT};">₹{pivot:,.2f}</b></span>
            <span style="color:{_MUTED};">Vol <b style="color:{_TEXT};">{vr:.2f}x</b></span>
            <span style="color:{_MUTED};">52W Hi <b style="color:{_TEXT};">{row.get('dist_52h_pct',0):.1f}%</b></span>
          </div>
          <div style="font-size:.68rem;color:{_MUTED};margin-top:4px;">
            Contractions: <span style="color:{_TEXT};">{cont_str}</span>
          </div>
          <div style="margin-top:6px;">{badges_html}</div>
        </div>
        <div style="text-align:center;min-width:64px;background:#1e2433;border-radius:5px;padding:10px 8px;">
          <div style="font-size:1.4rem;font-weight:800;color:{score_c};">{score:.0f}</div>
          <div style="font-size:.58rem;color:{_MUTED};letter-spacing:.05em;text-transform:uppercase;">VCP Score</div>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)


def render(slot):
    slot.empty()
    slot.markdown(loading_html("Scanning for VCP setups…"), unsafe_allow_html=True)

    try:
        df = _run(run_vcp_scan())
    except Exception as e:
        slot.empty()
        st.error(f"VCP scan failed: {e}")
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
    c1.metric("VCP Setups Found", len(df))
    c2.metric("Active Breakouts",  len(breakouts))
    c3.metric("Near Pivot",        len(near_pivot))
    c4.metric("Avg VCP Score",     f"{avg_score:.1f}")

    st.markdown("<div style='margin-bottom:14px;'></div>", unsafe_allow_html=True)

    # Sector distribution
    if "sector" in df.columns and df["sector"].notna().any():
        st.markdown(
            f'<div style="font-size:.62rem;font-weight:600;color:{_MUTED};text-transform:uppercase;'
            f'letter-spacing:.07em;margin-bottom:10px;">Sector Distribution</div>',
            unsafe_allow_html=True,
        )
        sector_df = (
            df.groupby("sector")["vcp_score"]
            .mean().reset_index()
            .sort_values("vcp_score", ascending=False)
        )
        fig_s = px.bar(
            sector_df, x="sector", y="vcp_score",
            color="vcp_score",
            color_continuous_scale=[[0, "#ef4444"], [0.5, "#f59e0b"], [1, "#00c853"]],
            height=240,
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

    # Top 30 bar chart
    st.markdown(
        f'<div style="font-size:.62rem;font-weight:600;color:{_MUTED};text-transform:uppercase;'
        f'letter-spacing:.07em;margin-bottom:10px;">Top 30 by VCP Score</div>',
        unsafe_allow_html=True,
    )
    fig = px.bar(
        df.head(30), x="symbol", y="vcp_score",
        color="vcp_score",
        color_continuous_scale=[[0, "#ef4444"], [0.5, "#f59e0b"], [1, "#00c853"]],
        labels={"vcp_score": "VCP Score", "symbol": ""},
        height=210,
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

    # Tabs: All / Breakouts / Near Pivot
    tab1, tab2, tab3 = st.tabs([
        f"All Setups ({len(df)})",
        f"Active Breakouts ({len(breakouts)})",
        f"Near Pivot ({len(near_pivot)})",
    ])

    with tab1:
        for rank, (_, row) in enumerate(df.head(20).iterrows(), 1):
            _render_card(row, rank)

    with tab2:
        if breakouts.empty:
            st.info("No active breakouts right now.")
        else:
            for rank, (_, row) in enumerate(breakouts.head(20).iterrows(), 1):
                _render_card(row, rank)

    with tab3:
        if near_pivot.empty:
            st.info("No stocks near pivot right now.")
        else:
            for rank, (_, row) in enumerate(near_pivot.head(20).iterrows(), 1):
                _render_card(row, rank)
