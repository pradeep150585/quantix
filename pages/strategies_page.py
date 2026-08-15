"""
Page 4 – Legendary Traders Strategy Scanner (Lightweight)
"""
import asyncio
import io
import time
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
from scanner import get_cached_scan
from strategies import score_color
from services.market_data import get_quotes, parse_quote
from components.ui import loading_html as _loading_html

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
    headers = ["#", "Symbol", "Score", "CMP", "Entry", "Chg%", "RSI", "52W%"]
    th = "".join(
        f'<th style="background:#131722;color:#9ca3af;font-size:.58rem;font-weight:600;text-transform:uppercase;letter-spacing:.04em;padding:6px 4px;border-bottom:1px solid #1e2433;">{h}</th>'
        for h in headers
    )
    rows_html = ""
    for i, (_, row) in enumerate(df.iterrows()):
        score = row.get("best_score", 0)
        score_c = score_color(score)
        rsi = row.get("rsi", 0)
        rsi_c = "#ef4444" if rsi >= 70 else ("#00c853" if rsi <= 30 else "#6b7280")
        d52 = row.get("dist_52h_pct", 0)
        pct = row.get("pct_change", 0)
        pct_c = "#00c853" if pct > 0 else ("#ef4444" if pct < 0 else "#6b7280")
        pct_arr = "▲" if pct > 0 else ("▼" if pct < 0 else "—")
        td = 'style="padding:6px 4px;border-bottom:1px solid #131722;font-size:.7rem;"'
        cells = [
            f'<td {td}><span style="color:#4a5568;">{i+1}</span></td>',
            f'<td {td}><span style="color:#fff;font-weight:600;">{row.get("symbol","")}</span></td>',
            f'<td {td}><span style="color:{score_c};font-weight:700;">{score:.0f}</span></td>',
            f'<td {td}><span style="color:#d1d4dc;">₹{row.get("cmp",0):,.0f}</span></td>',
            f'<td {td}><span style="color:#00c853;font-weight:600;">₹{row.get("entry_price", row.get("cmp",0)):,.0f}</span></td>',
            f'<td {td}><span style="color:{pct_c};font-weight:600;">{pct_arr} {abs(pct):.1f}%</span></td>',
            f'<td {td}><span style="color:{rsi_c};font-weight:600;">{rsi:.0f}</span></td>',
            f'<td {td}><span style="color:#d1d4dc;">{d52:.0f}%</span></td>',
        ]
        rows_html += f'<tr style="background:transparent;">{"".join(cells)}</tr>\n'

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
<div style="font-size:.55rem;color:#4a5568;padding:4px 4px;">Updated {ts} · auto-refresh {_REFRESH_INTERVAL}s</div>
</body></html>"""

def render(slot):
    slot.empty()
    st.empty()
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

    components.html(_build_strategy_table_html(df, time.strftime("%H:%M:%S")), height=450, scrolling=False)

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
