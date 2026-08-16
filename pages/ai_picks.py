"""
Page 5 - AI Top Picks: VCP Scanner + Elder Triple Screen
"""
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
from services.scan_runner import run_combined_scan_cached
from components.ui import loading_html
import pages.elder_scanner_page as elder_page

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



def _score_color(s: float) -> str:
    return _GREEN if s >= 75 else (_YELLOW if s >= 50 else _RED)


# -- VCP chart builder ---------------------------------------------------------

def _build_vcp_chart(symbol: str, row: pd.Series, cdf: pd.DataFrame):
    import plotly.graph_objects as go
    
    if cdf.empty:
        return go.Figure()

    dates = cdf["datetime"] if "datetime" in cdf.columns else pd.RangeIndex(len(cdf))
    entry = row.get("entry_price", 0)
    stop  = row.get("stop_loss", 0)
    pivot = row.get("pivot", 0)

    fig = go.Figure()

    # Candlestick
    fig.add_trace(go.Candlestick(
        x=dates, open=cdf["open"], high=cdf["high"],
        low=cdf["low"], close=cdf["close"],
        increasing_line_color=_GREEN, increasing_fillcolor="#0d2b1a",
        decreasing_line_color=_RED,   decreasing_fillcolor="#2b0d0d",
        line_width=1, name="Price",
    ))

    # Moving averages
    if "wma10" in cdf.columns:
        fig.add_trace(go.Scatter(x=dates, y=cdf["wma10"],
            line=dict(color=_BLUE, width=1.2), name="WMA 10"))
    if "wma30" in cdf.columns:
        fig.add_trace(go.Scatter(x=dates, y=cdf["wma30"],
            line=dict(color=_PURPLE, width=1, dash="dot"), name="WMA 30"))

    # Entry, Stop, Pivot lines
    for price, color, label in [
        (pivot, _YELLOW, f"Pivot Rs{pivot:,.2f}"),
        (entry, _GREEN,  f"Entry Rs{entry:,.2f}"),
        (stop,  _RED,    f"Stop Rs{stop:,.2f}"),
    ]:
        if price > 0:
            fig.add_hline(y=price, line=dict(color=color, width=1.2, dash="dash"),
                annotation_text=f"  {label}",
                annotation_position="right",
                annotation_font=dict(color=color, size=9))

    fig.update_layout(
        paper_bgcolor=_BG, plot_bgcolor=_BG,
        font=dict(color=_TEXT, size=9, family="Inter"),
        margin=dict(l=0, r=50, t=20, b=0), height=350,
        showlegend=False,
        xaxis_rangeslider_visible=False,
        title=dict(text=f"{symbol} - VCP Pattern",
                   font=dict(size=11, color=_WHITE), x=0),
    )
    ax = dict(gridcolor=_BORDER, zerolinecolor=_BORDER,
              tickfont=dict(color=_MUTED, size=9), showgrid=True)
    fig.update_xaxes(**ax)
    fig.update_yaxes(**ax)
    return fig


# -- VCP card renderer ---------------------------------------------------------

def _render_vcp_card(rank: int, row: pd.Series, chart_store: dict, key_prefix: str = ""):
    symbol  = row.get("symbol", "")
    
    # Skip if symbol not in chart store (data mismatch)
    if symbol not in chart_store:
        return
    
    score   = row.get("vcp_score", 0)
    cmp     = row.get("cmp", 0)
    entry   = row.get("entry_price", 0)
    stop    = row.get("stop_loss", 0)
    is_bo   = row.get("is_breakout", False)
    vr      = row.get("volume_ratio", 0)
    squeeze = row.get("squeeze", False)
    dryup   = row.get("vol_dryup", False)
    contractions = row.get("contractions", 0)
    pct     = row.get("pct_change", 0)
    pct_c   = _GREEN if pct > 0 else (_RED if pct < 0 else _MUTED)
    pct_s   = f"+{pct:.2f}%" if pct > 0 else f"{pct:.2f}%"
    score_c = _score_color(score)

    badges = []
    if is_bo: badges.append("Breakout")
    if squeeze: badges.append("Squeeze")
    if dryup: badges.append("Vol Dry-up")
    if contractions >= 3: badges.append(f"{contractions}-Stage")
    
    # Add quality indicator for low-score breakouts
    if is_bo and score <= 30:
        badges.append("⚠️ Low Pattern Score")

    label = f"{symbol}  |  Rs{cmp:,.0f}  {pct_s}  |  Entry: Rs{entry:,.0f}  |  Score {score:.0f}"

    with st.expander(label, expanded=False):
        # Header metrics
        components.html(f"""<!DOCTYPE html><html><head>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>*{{box-sizing:border-box;margin:0;padding:0;font-family:'Inter',sans-serif;}}</style>
</head><body style="background:#0b0e17;padding:0;">
<div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:8px;">
  <div style="background:#131722;border:1px solid #1e2433;border-radius:4px;padding:8px 12px;flex:1;min-width:100px;">
    <div style="font-size:.58rem;color:#6b7280;text-transform:uppercase;">CMP</div>
    <div style="font-size:.9rem;font-weight:700;color:#fff;">Rs{cmp:,.0f}
      <span style="font-size:.65rem;color:{pct_c};margin-left:4px;">{pct_s}</span></div>
  </div>
  <div style="background:#131722;border:1px solid #1e2433;border-radius:4px;padding:8px 12px;flex:1;min-width:100px;">
    <div style="font-size:.58rem;color:#6b7280;text-transform:uppercase;">Entry</div>
    <div style="font-size:.9rem;font-weight:700;color:#00c853;">Rs{entry:,.0f}</div>
  </div>
  <div style="background:#131722;border:1px solid #1e2433;border-radius:4px;padding:8px 12px;flex:1;min-width:100px;">
    <div style="font-size:.58rem;color:#6b7280;text-transform:uppercase;">Stop</div>
    <div style="font-size:.9rem;font-weight:700;color:#ef4444;">Rs{stop:,.0f}</div>
  </div>
  <div style="background:#131722;border:1px solid #1e2433;border-radius:4px;padding:8px 12px;flex:1;min-width:100px;">
    <div style="font-size:.58rem;color:#6b7280;text-transform:uppercase;">Vol Ratio</div>
    <div style="font-size:.9rem;font-weight:700;color:#d1d4dc;">{vr:.2f}x</div>
  </div>
  <div style="background:{score_c}18;border:1px solid {score_c}44;border-radius:4px;padding:8px 12px;min-width:80px;text-align:center;">
    <div style="font-size:.58rem;color:#6b7280;text-transform:uppercase;">Score</div>
    <div style="font-size:1.1rem;font-weight:800;color:{score_c};">{score:.0f}</div>
  </div>
</div>
<div style="display:flex;gap:4px;flex-wrap:wrap;margin-bottom:8px;">
  {"".join(f'<span style="background:#a78bfa18;color:#a78bfa;border:1px solid #a78bfa44;border-radius:3px;padding:3px 8px;font-size:.65rem;font-weight:600;">{b}</span>' for b in badges)}
</div>
<div style="font-size:.67rem;color:#6b7280;">
  {row.get("company_name","")} - {row.get("sector","")}
</div>
</body></html>""", height=130, scrolling=False)

        # Chart
        chart_data = chart_store.get(symbol)
        if chart_data is not None:
            cdf = chart_data.get("df") if isinstance(chart_data, dict) else chart_data
            if cdf is not None and not cdf.empty:
                fig = _build_vcp_chart(symbol, row, cdf)
                st.plotly_chart(fig, use_container_width=True,
                                config={"displayModeBar": False},
                                key=f"vcp_chart_{key_prefix}{symbol}_{rank}")
            else:
                st.info("Chart data unavailable.")
        else:
            st.info("Chart data unavailable.")


# -- VCP tab content -----------------------------------------------------------

def _render_vcp(df: pd.DataFrame, chart_store: dict):
    from loguru import logger

    if df is None or df.empty:
        st.info("No stocks currently meet the VCP criteria.")
        return

    # Log pre-filter stats
    total_before = len(df)
    breakouts_before = len(df[df["is_breakout"] == True])
    logger.info(f"VCP UI: Before filtering - {total_before} setups, {breakouts_before} breakouts")
    
    # Filter: high score OR active breakout (don't filter out breakouts)
    score_threshold = 30
    df = df[(df["vcp_score"] > score_threshold) | (df["is_breakout"] == True)]
    
    if df.empty:
        st.info(f"No stocks with VCP score above {score_threshold} or active breakouts.")
        logger.warning(f"VCP UI: All {total_before} setups filtered out")
        return

    breakouts  = df[df["is_breakout"] == True]
    near_pivot = df[(df["is_breakout"] == False) & (df["dist_52h_pct"] >= -20)]
    avg_score  = df["vcp_score"].mean()
    
    # Log post-filter stats
    logger.info(f"VCP UI: After filtering - {len(df)} setups, {len(breakouts)} breakouts, {len(near_pivot)} near pivot")
    logger.info(f"VCP UI: Filtered out {total_before - len(df)} low-score non-breakout setups")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("VCP Setups",       len(df))
    c2.metric("Active Breakouts", len(breakouts))
    c3.metric("Near Pivot",       len(near_pivot))
    c4.metric("Avg VCP Score",    f"{avg_score:.1f}")
    
    # Info message about filtering
    filtered_count = total_before - len(df)
    if filtered_count > 0:
        st.info(f"ℹ️ Showing {len(df)} setups (filtered out {filtered_count} low-score non-breakout patterns). All active breakouts are shown regardless of score.")

    st.markdown("<div style='margin-bottom:8px;'></div>", unsafe_allow_html=True)

    # Sector summary as table
    if "sector" in df.columns and df["sector"].notna().any():
        sector_df = (
            df.groupby("sector").agg(
                Setups=("vcp_score", "count"),
                Avg_Score=("vcp_score", "mean"),
                Breakouts=("is_breakout", "sum"),
            ).reset_index().sort_values("Avg_Score", ascending=False)
        )
        sector_df["Avg_Score"] = sector_df["Avg_Score"].round(1)
        st.markdown(
            '<div style="font-size:.62rem;font-weight:600;color:#6b7280;text-transform:uppercase;'
            'letter-spacing:.07em;margin-bottom:6px;">Sector Summary</div>',
            unsafe_allow_html=True,
        )
        st.dataframe(
            sector_df.rename(columns={"sector": "Sector"}),
            use_container_width=True, hide_index=True, height=180,
        )
        st.markdown("<hr>", unsafe_allow_html=True)

    t1, t2, t3 = st.tabs([
        f"All Setups ({len(df)})",
        f"Active Breakouts ({len(breakouts)})",
        f"Near Pivot ({len(near_pivot)})",
    ])

    with t1:
        if df.empty:
            st.info("No setups in this category.")
        else:
            for rank, (_, row) in enumerate(df.head(20).iterrows(), 1):
                _render_vcp_card(rank, row, chart_store, key_prefix="all_")

    with t2:
        if breakouts.empty:
            st.info("No active breakouts right now.")
        else:
            for rank, (_, row) in enumerate(breakouts.head(20).iterrows(), 1):
                _render_vcp_card(rank, row, chart_store, key_prefix="bo_")

    with t3:
        if near_pivot.empty:
            st.info("No stocks near pivot right now.")
        else:
            for rank, (_, row) in enumerate(near_pivot.head(20).iterrows(), 1):
                _render_vcp_card(rank, row, chart_store, key_prefix="np_")


# -- Page entry point ----------------------------------------------------------

def render(slot):
    slot.empty()
    with slot.container():
        ph = st.empty()
        ph.markdown(loading_html("Running AI scans..."), unsafe_allow_html=True)
        try:
            vcp_df, vcp_charts, elder_df, elder_charts = run_combined_scan_cached()
        except Exception as e:
            ph.empty()
            st.error(f"Scan failed: {e}")
            import traceback
            st.code(traceback.format_exc())
            return
        ph.empty()

        tab_vcp, tab_elder = st.tabs(["VCP Scanner", "Elder Triple Screen"])
        with tab_vcp:
            _render_vcp(vcp_df, vcp_charts)
        with tab_elder:
            elder_page.render_content(elder_df, elder_charts)
