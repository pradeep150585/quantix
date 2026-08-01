"""
Page 4 – Legendary Traders Strategy Scanner
"""
import asyncio
import io
import time
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
from scanner import get_cached_scan
from strategies import score_color
from database import add_to_watchlist, remove_from_watchlist, is_in_watchlist
from components import render_candlestick_chart
from services.market_data import get_historical_df, get_quotes, parse_quote
from indicators import compute_all
from components.ui import page_heading, loading_html as _loading_html

_SCAN_KEY = "_strat_scan_df"
_LAST_REFRESH_KEY = "_strat_last_refresh"
_REFRESH_INTERVAL = 15


def _run(coro):
    try:
        loop = asyncio.new_event_loop()
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _run_scan_with_progress(ph) -> pd.DataFrame:
    from scanner import run_scan
    import scanner as _scanner
    from services.instruments import get_nifty200_symbols

    symbols_df = _run(get_nifty200_symbols())
    total = len(symbols_df) if not symbols_df.empty else 200
    completed = [0]
    current_symbol = [""]
    original_process = _scanner._process_stock

    async def _tracked(row, benchmark_df, semaphore):
        result = await original_process(row, benchmark_df, semaphore)
        completed[0] += 1
        current_symbol[0] = row.get("symbol", "")
        return result

    _scanner._process_stock = _tracked

    import threading
    scan_result = [None]
    scan_error = [None]

    def run_scan_thread():
        try:
            scan_result[0] = _run(run_scan(force=True))
        except Exception as e:
            scan_error[0] = e

    thread = threading.Thread(target=run_scan_thread, daemon=True)
    thread.start()

    while thread.is_alive():
        ph.markdown(
            _loading_html(f"Scanning {current_symbol[0] or 'initializing'} &nbsp;&middot;&nbsp; {completed[0]} / {total} stocks"),
            unsafe_allow_html=True,
        )
        time.sleep(0.3)

    thread.join()
    _scanner._process_stock = original_process

    if scan_error[0]:
        raise scan_error[0]
    return scan_result[0] if scan_result[0] is not None else pd.DataFrame()


@st.cache_data(ttl=15, show_spinner=False)
def _refresh_prices(keys_tuple: tuple) -> dict:
    return _run(get_quotes(list(keys_tuple)))


def _build_strategy_table_html(df: pd.DataFrame, ts: str) -> str:
    headers = ["#", "Symbol", "Company", "Strategy", "Score", "CMP", "Chg%",
               "RSI", "Vol Ratio", "52W Hi%", "Stop Loss", "Sector"]

    th = "".join(
        f'<th style="position:sticky;top:0;background:#131722;color:#9ca3af;'
        f'font-size:.62rem;font-weight:600;text-transform:uppercase;letter-spacing:.06em;'
        f'padding:10px 10px;white-space:nowrap;border-bottom:1px solid #1e2433;z-index:2;">{h}</th>'
        for h in headers
    )

    rows_html = ""
    for i, (_, row) in enumerate(df.iterrows()):
        pct = row.get("pct_change", 0)
        bg = "rgba(0,200,83,.05)" if pct > 0 else ("rgba(239,68,68,.05)" if pct < 0 else "transparent")
        rsi = row.get("rsi", 0)
        rsi_c = "#ef4444" if rsi >= 70 else ("#00c853" if rsi <= 30 else "#6b7280")
        vr = row.get("volume_ratio", 0)
        vr_c = "#f59e0b" if vr >= 2 else ("#00c853" if vr >= 1.2 else "#6b7280")
        d52 = row.get("dist_52h_pct", 0)
        d52_c = "#00c853" if d52 >= -5 else "#6b7280"
        score = row.get("best_score", 0)
        score_c = score_color(score)
        strat = row.get("best_strategy", "")
        sc = {"Minervini": "#60a5fa", "Qullamaggie": "#a78bfa", "Zanger": "#fbbf24"}.get(strat, "#6b7280")
        pct_c = "#00c853" if pct > 0 else ("#ef4444" if pct < 0 else "#6b7280")
        pct_arr = "▲" if pct > 0 else ("▼" if pct < 0 else "—")

        td = 'style="padding:9px 10px;border-bottom:1px solid #131722;white-space:nowrap;"'
        cells = [
            f'<td {td}><span style="color:#4a5568;font-size:.7rem;">{i + 1}</span></td>',
            f'<td {td}><span style="color:#ffffff;font-weight:600;font-size:.8rem;">{row.get("symbol","")}</span></td>',
            f'<td {td}><span style="color:#9ca3af;font-size:.74rem;">{row.get("company_name","")[:28]}</span></td>',
            f'<td {td}><span style="background:{sc}18;color:{sc};border:1px solid {sc}33;border-radius:3px;padding:2px 8px;font-size:.67rem;font-weight:600;">{strat}</span></td>',
            f'<td {td}><span style="color:{score_c};font-weight:700;">{score:.1f}%</span></td>',
            f'<td {td}><span style="color:#d1d4dc;font-weight:500;">&#8377;{row.get("cmp",0):,.2f}</span></td>',
            f'<td {td}><span style="color:{pct_c};font-weight:600;">{pct_arr} {abs(pct):.2f}%</span></td>',
            f'<td {td}><span style="color:{rsi_c};font-weight:600;">{rsi:.1f}</span></td>',
            f'<td {td}><span style="color:{vr_c};font-weight:600;">{vr:.2f}x</span></td>',
            f'<td {td}><span style="color:{d52_c};font-weight:600;">{d52:.1f}%</span></td>',
            f'<td {td}><span style="color:#6b7280;">&#8377;{row.get("stop_loss",0):,.2f}</span></td>',
            f'<td {td}><span style="color:#4a5568;font-size:.7rem;">{row.get("sector","")}</span></td>',
        ]
        rows_html += f'<tr style="background:{bg};">{"".join(cells)}</tr>\n'

    return f"""<!DOCTYPE html><html><head>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#0b0e17;color:#d1d4dc;font-family:'Inter',system-ui,sans-serif}}
.wrap{{width:100%;overflow-x:auto;overflow-y:auto;height:calc(100vh - 22px);border:1px solid #1e2433;border-radius:5px;background:#0b0e17}}
table{{border-collapse:collapse;width:max-content;min-width:100%}}
::-webkit-scrollbar{{width:4px;height:4px}}::-webkit-scrollbar-track{{background:#0b0e17}}
::-webkit-scrollbar-thumb{{background:#2d3748;border-radius:4px}}
.ts{{font-size:.6rem;color:#4a5568;text-align:right;padding:4px 0}}
</style></head><body>
<div class="wrap"><table>
<thead><tr>{th}</tr></thead>
<tbody>{rows_html}</tbody>
</table></div>
<div class="ts">Updated {ts} &middot; auto-refresh {_REFRESH_INTERVAL}s</div>
</body></html>"""


def render(slot):
    slot.empty()
    slot.markdown(_loading_html("Initialising scan &nbsp;&middot;&nbsp; 0 / 200 stocks"), unsafe_allow_html=True)

    if _SCAN_KEY not in st.session_state:
        cached = get_cached_scan()
        if cached is not None and not cached.empty:
            st.session_state[_SCAN_KEY] = cached
        else:
            slot.empty()
            ph = st.empty()
            st.session_state[_SCAN_KEY] = _run_scan_with_progress(ph)
            ph.empty()
        st.session_state[_LAST_REFRESH_KEY] = time.time()

    df = st.session_state.get(_SCAN_KEY, pd.DataFrame())
    slot.empty()

    if df is None or df.empty:
        st.warning("No scan data. Ensure Upstox token is configured.")
        return

    now = time.time()
    last = st.session_state.get(_LAST_REFRESH_KEY, 0)
    if now - last >= _REFRESH_INTERVAL:
        raw = _refresh_prices(tuple(df["instrument_key"].tolist()))
        if raw:
            df = df.copy()
            for i, row in df.iterrows():
                q = parse_quote(raw.get(row["instrument_key"], {}))
                if q and q.get("ltp", 0) > 0:
                    ltp = q["ltp"]
                    prev = q.get("prev_close", 0)
                    df.at[i, "cmp"] = round(ltp, 2)
                    df.at[i, "pct_change"] = round((ltp - prev) / prev * 100, 2) if prev else 0
            st.session_state[_SCAN_KEY] = df
        st.session_state[_LAST_REFRESH_KEY] = now

    components.html(_build_strategy_table_html(df, time.strftime("%H:%M:%S")), height=620, scrolling=False)

    col_x, col_y = st.columns(2)
    with col_x:
        st.download_button("Export CSV",
                           df.drop(columns=["instrument_key", "badges"], errors="ignore")
                             .to_csv(index=False).encode(),
                           "strategy_scan.csv", "text/csv")
    with col_y:
        buf = io.BytesIO()
        df.drop(columns=["instrument_key", "badges"], errors="ignore").to_excel(buf, index=False, engine="openpyxl")
        st.download_button("Export Excel", buf.getvalue(), "strategy_scan.xlsx",
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    st.markdown("<hr>", unsafe_allow_html=True)
    st.markdown('<div style="font-size:.78rem;font-weight:500;color:#6b7280;margin-bottom:8px;">Stock Detail</div>',
                unsafe_allow_html=True)
    selected = st.selectbox("Select stock", df["symbol"].tolist(), key="strat_chart_sel",
                            label_visibility="collapsed")
    if selected:
        row = df[df["symbol"] == selected].iloc[0]
        key = row.get("instrument_key", "")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("CMP", f"Rs.{row['cmp']:,.2f}", f"{row['pct_change']:+.2f}%")
        c2.metric("Strategy", row["best_strategy"])
        c3.metric("Score", f"{row['best_score']:.1f}%")
        c4.metric("Stop Loss", f"Rs.{row['stop_loss']:,.2f}")

        badges = row.get("badges", [])
        if badges:
            st.markdown(" ".join(f'<span class="badge badge-green">{b}</span>' for b in badges),
                        unsafe_allow_html=True)

        in_wl = is_in_watchlist(selected)
        if in_wl:
            if st.button(f"Remove {selected} from Watchlist"):
                remove_from_watchlist(selected)
                st.success(f"{selected} removed")
        else:
            if st.button(f"Add {selected} to Watchlist"):
                add_to_watchlist(selected, row.get("company_name", ""), key)
                st.success(f"{selected} added!")

        if key:
            with st.spinner("Loading chart..."):
                hist_df = _run(get_historical_df(key, interval="day", days=260))
                indicators = compute_all(hist_df) if not hist_df.empty else {}
            render_candlestick_chart(hist_df, selected, indicators)
