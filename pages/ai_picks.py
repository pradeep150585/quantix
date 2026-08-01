"""
Page 5 – AI Top Picks
"""
import streamlit as st
import pandas as pd
import plotly.express as px
from scanner import get_cached_scan
from services.ai_picks import compute_ai_scores
from strategies import score_color
from components.ui import loading_html

_BG      = "#0b0e17"
_CARD    = "#131722"
_BORDER  = "#1e2433"
_TEXT    = "#d1d4dc"
_MUTED   = "#6b7280"
_WHITE   = "#ffffff"
_GREEN   = "#00c853"
_RED     = "#ef4444"
_BLUE    = "#60a5fa"


def _strategy_badge(strat: str) -> str:
    colors = {
        "Minervini":   (_BLUE,    "rgba(96,165,250,.12)"),
        "Qullamaggie": ("#a78bfa", "rgba(167,139,250,.12)"),
        "Zanger":      ("#fbbf24", "rgba(251,191,36,.12)"),
    }
    fg, bg = colors.get(strat, (_MUTED, "rgba(107,114,128,.12)"))
    return (
        f'<span style="background:{bg};color:{fg};border:1px solid {fg}33;'
        f'border-radius:3px;padding:2px 8px;font-size:.65rem;font-weight:600;">{strat}</span>'
    )


def _render_stock_card(row: pd.Series, rank: int):
    ai_score  = row.get("ai_score", 0)
    pct       = row.get("pct_change", 0)
    pct_color = _GREEN if pct > 0 else (_RED if pct < 0 else _MUTED)
    pct_arr   = "▲" if pct > 0 else ("▼" if pct < 0 else "—")
    score_c   = score_color(ai_score)
    strat     = row.get("best_strategy", "")
    badges    = row.get("badges", [])
    badges_html = " ".join(
        f'<span style="background:rgba(96,165,250,.1);color:{_BLUE};border:1px solid rgba(96,165,250,.2);'
        f'border-radius:3px;padding:1px 7px;font-size:.62rem;font-weight:500;">{b}</span>'
        for b in badges[:4]
    )
    rsi = row.get("rsi", 0)
    vr  = row.get("volume_ratio", 0)
    d52 = row.get("dist_52h_pct", 0)

    st.markdown(f"""
    <div style="background:{_CARD};border:1px solid {_BORDER};border-radius:5px;
        padding:14px 16px;margin-bottom:6px;border-left:3px solid {_GREEN};">
      <div style="display:flex;align-items:center;gap:12px;">
        <div style="font-size:1.1rem;font-weight:800;color:{_MUTED};min-width:32px;
            text-align:center;background:#1e2433;border-radius:4px;padding:6px 0;">
          #{rank}
        </div>
        <div style="flex:1;min-width:0;">
          <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:6px;">
            <div style="display:flex;align-items:center;gap:8px;">
              <span style="font-size:.95rem;font-weight:700;color:{_WHITE};">{row.get('symbol','')}</span>
              {_strategy_badge(strat)}
            </div>
            <span style="font-size:1rem;font-weight:700;color:{_TEXT};">₹{row.get('cmp',0):,.2f}</span>
          </div>
          <div style="font-size:.72rem;color:{_MUTED};margin-top:2px;">{row.get('company_name','')}</div>
          <div style="display:flex;gap:14px;margin-top:6px;font-size:.72rem;flex-wrap:wrap;">
            <span style="color:{pct_color};font-weight:600;">{pct_arr} {abs(pct):.2f}%</span>
            <span style="color:{_MUTED};">RSI <b style="color:{_TEXT};">{rsi:.1f}</b></span>
            <span style="color:{_MUTED};">Vol <b style="color:{_TEXT};">{vr:.2f}x</b></span>
            <span style="color:{_MUTED};">52W Hi <b style="color:{_TEXT};">{d52:.1f}%</b></span>
            <span style="color:{_MUTED};">Score <b style="color:{score_c};">{row.get('best_score',0):.1f}%</b></span>
          </div>
          <div style="margin-top:6px;">{badges_html}</div>
        </div>
        <div style="text-align:center;min-width:64px;background:#1e2433;border-radius:5px;padding:10px 8px;">
          <div style="font-size:1.4rem;font-weight:800;color:{_GREEN};">{ai_score:.0f}</div>
          <div style="font-size:.58rem;color:{_MUTED};letter-spacing:.05em;text-transform:uppercase;">AI Score</div>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)


def render(slot):
    slot.empty()
    slot.markdown(loading_html("Computing AI scores…"), unsafe_allow_html=True)
    scan_df = get_cached_scan()
    slot.empty()

    if scan_df is None or scan_df.empty:
        st.markdown(f"""
        <div style="background:{_CARD};border:1px solid {_BORDER};border-radius:6px;padding:40px 32px;text-align:center;margin-top:20px;">
          <div style="font-size:1.8rem;margin-bottom:12px;">🔒</div>
          <div style="font-size:.9rem;font-weight:700;color:{_WHITE};margin-bottom:8px;">Strategy Scanner Required</div>
          <div style="font-size:.78rem;color:{_MUTED};line-height:1.6;">
            AI Top Picks is powered by the Strategy Scanner results.<br>
            Please run the <b style="color:{_GREEN};">Strategies</b> scan first, then return here.
          </div>
        </div>
        """, unsafe_allow_html=True)
        return

    ai_df = compute_ai_scores(scan_df, live_df=None)

    if ai_df is None or ai_df.empty:
        st.warning("Could not compute AI scores. Check scanner data.")
        return

    total = len(ai_df)
    top = ai_df.iloc[0]
    avg_score = ai_df["ai_score"].mean()
    buy_count = len(ai_df[ai_df.get("best_score", pd.Series(0)) >= 70]) if "best_score" in ai_df.columns else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Stocks Analysed", total)
    c2.metric("Avg AI Score", f"{avg_score:.1f}")
    c3.metric("High Conviction", buy_count)
    c4.metric("Top Pick", top.get("symbol", "—"))

    st.markdown("<div style='margin-bottom:14px;'></div>", unsafe_allow_html=True)

    if "sector" in ai_df.columns:
        st.markdown(
            f'<div style="font-size:.62rem;font-weight:600;color:{_MUTED};text-transform:uppercase;'
            f'letter-spacing:.07em;margin-bottom:10px;">Sector Strength</div>',
            unsafe_allow_html=True,
        )
        sector_df = (
            ai_df.groupby("sector")["ai_score"]
            .mean()
            .reset_index()
            .sort_values("ai_score", ascending=False)
        )
        fig2 = px.bar(
            sector_df, x="sector", y="ai_score",
            color="ai_score",
            color_continuous_scale=[[0, "#ef4444"], [0.5, "#f59e0b"], [1, "#00c853"]],
            height=260,
        )
        fig2.update_layout(
            paper_bgcolor=_BG, plot_bgcolor=_BG,
            font=dict(color=_MUTED, size=11, family="Inter"),
            showlegend=False, coloraxis_showscale=False,
            margin=dict(l=0, r=0, t=8, b=0),
            xaxis=dict(gridcolor=_BORDER, tickangle=-30, tickfont=dict(color=_MUTED, size=10)),
            yaxis=dict(gridcolor=_BORDER, tickfont=dict(color=_MUTED)),
        )
        st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar": False}, key="sector_strength_chart")
        st.markdown("<hr>", unsafe_allow_html=True)

    st.markdown(
        f'<div style="font-size:.62rem;font-weight:600;color:{_MUTED};text-transform:uppercase;'
        f'letter-spacing:.07em;margin-bottom:10px;">Top 30 Stocks by AI Score</div>',
        unsafe_allow_html=True,
    )
    fig = px.bar(
        ai_df.head(30), x="symbol", y="ai_score",
        color="ai_score",
        color_continuous_scale=[[0, "#ef4444"], [0.5, "#f59e0b"], [1, "#00c853"]],
        labels={"ai_score": "AI Score", "symbol": ""},
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
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False}, key="top_30_chart")

    st.markdown(
        f'<div style="font-size:.62rem;font-weight:600;color:{_MUTED};text-transform:uppercase;'
        f'letter-spacing:.07em;margin-bottom:10px;">Top 5 Stocks by AI Score</div>',
        unsafe_allow_html=True,
    )
    for rank, (_, row) in enumerate(ai_df.head(5).iterrows(), 1):
        _render_stock_card(row, rank)
