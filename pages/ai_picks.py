"""
Page 5 - AI Top Picks: VCP Scanner + Elder Triple Screen
"""
import asyncio
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
from services.vcp_scanner import run_vcp_scan
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


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _score_color(s: float) -> str:
    return _GREEN if s >= 75 else (_YELLOW if s >= 50 else _RED)


# -- VCP table ----------------------------------------------------------------

def _build_vcp_table_html(df: pd.DataFrame) -> str:
    headers = ["#", "Symbol", "Score", "CMP", "Entry", "Stop", "Vol", "52W%"]
    th = "".join(
        f'<th style="background:#131722;color:#9ca3af;font-size:.6rem;font-weight:600;text-transform:uppercase;letter-spacing:.05em;padding:8px 6px;border-bottom:1px solid #1e2433;">{h}</th>'
        for h in headers
    )
    rows_html = ""
    for i, (_, row) in enumerate(df.iterrows()):
        score   = row.get("vcp_score", 0)
        score_c = _score_color(score)
        is_bo   = row.get("is_breakout", False)
        pivot   = row.get("pivot", 0)
        entry   = row.get("entry_price", pivot if pivot > 0 else row.get("cmp", 0))
        stop    = row.get("stop_loss", 0)
        vr      = row.get("volume_ratio", 0)
        d52     = row.get("dist_52h_pct", 0)
        bg = "rgba(0,200,83,.06)" if is_bo else "transparent"
        bo_badge = '<span style="color:#00c853;font-weight:700;font-size:.55rem;">BO</span>' if is_bo else ""
        td = 'style="padding:7px 6px;border-bottom:1px solid #131722;font-size:.7rem;"'
        cells = [
            f'<td {td}><span style="color:#4a5568;">{i+1}</span></td>',
            f'<td {td}><span style="color:#fff;font-weight:600;">{row.get("symbol","")}</span> {bo_badge}</td>',
            f'<td {td}><span style="color:{score_c};font-weight:700;">{score:.0f}</span></td>',
            f'<td {td}><span style="color:#d1d4dc;">&#8377;{row.get("cmp",0):,.0f}</span></td>',
            f'<td {td}><span style="color:#00c853;font-weight:600;">&#8377;{entry:,.0f}</span></td>',
            f'<td {td}><span style="color:#ef4444;">&#8377;{stop:,.0f}</span></td>',
            f'<td {td}><span style="color:#d1d4dc;">{vr:.1f}x</span></td>',
            f'<td {td}><span style="color:#d1d4dc;">{d52:.0f}%</span></td>',
        ]
        rows_html += f'<tr style="background:{bg};">{"".join(cells)}</tr>\n'

    return f"""<!DOCTYPE html><html><head>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#0b0e17;color:#d1d4dc;font-family:'Inter',system-ui,sans-serif}}
table{{border-collapse:collapse;width:100%;table-layout:fixed}}
::-webkit-scrollbar{{width:2px;height:2px}}
::-webkit-scrollbar-track{{background:#0b0e17}}
::-webkit-scrollbar-thumb{{background:#2d3748;border-radius:1px}}
</style></head><body>
<table>
<thead><tr>{th}</tr></thead>
<tbody>{rows_html}</tbody>
</table>
</body></html>"""


# -- VCP tab content -----------------------------------------------------------

def _render_vcp():
    st.empty()  # Clear any lingering components
    ph = st.empty()
    ph.markdown(loading_html("Scanning for VCP setups..."), unsafe_allow_html=True)
    try:
        df, chart_store = _run(run_vcp_scan())
    except Exception as e:
        ph.empty()
        st.error(f"VCP scan failed: {e}")
        import traceback
        st.code(traceback.format_exc())
        return
    ph.empty()

    if df is None or df.empty:
        st.info("No stocks currently meet the VCP criteria.")
        return

    breakouts  = df[df["is_breakout"] == True]
    near_pivot = df[(df["is_breakout"] == False) & (df["dist_52h_pct"] >= -8)]
    avg_score  = df["vcp_score"].mean()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("VCP Setups",       len(df))
    c2.metric("Active Breakouts", len(breakouts))
    c3.metric("Near Pivot",       len(near_pivot))
    c4.metric("Avg VCP Score",    f"{avg_score:.1f}")

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
        components.html(_build_vcp_table_html(df.head(50)), height=500, scrolling=False)
    with t2:
        if breakouts.empty:
            st.info("No active breakouts right now.")
        else:
            components.html(_build_vcp_table_html(breakouts.head(50)), height=500, scrolling=False)
    with t3:
        if near_pivot.empty:
            st.info("No stocks near pivot right now.")
        else:
            components.html(_build_vcp_table_html(near_pivot.head(50)), height=500, scrolling=False)


# -- Page entry point ----------------------------------------------------------

def render(slot):
    slot.empty()
    st.empty()  # Clear lingering components
    slot.markdown(loading_html("Loading AI scanner..."), unsafe_allow_html=True)
    slot.empty()
    st.empty()  # Clear again before tabs
    tab_vcp, tab_elder = st.tabs(["VCP Scanner", "Elder Triple Screen"])
    with tab_vcp:
        _render_vcp()
    with tab_elder:
        elder_page.render_content()
