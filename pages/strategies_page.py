"""
Page 4 – Legendary Traders Strategy Scanner (Lightweight)
"""
import asyncio
import time
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
from scanner import get_cached_scan
from strategies import score_color
from services.market_data import get_quotes, parse_quote, get_historical_df
from components.ui import loading_html as _loading_html
from indicators import compute_all

_SCAN_KEY = "_strat_scan_df"
_LAST_REFRESH_KEY = "_strat_last_refresh"
_REFRESH_INTERVAL = 15

_BG     = "#0b0e17"
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

@st.cache_data(ttl=300, show_spinner=False)
def _refresh_prices(keys_tuple: tuple) -> dict:
    return _run(get_quotes(list(keys_tuple)))

def _build_strategy_chart(symbol: str, row: pd.Series):
    """Build daily chart with technical indicators as subplots."""
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    try:
        ikey = row.get("instrument_key", "")
        df = _run(get_historical_df(ikey, interval="day", days=260))
        if df.empty or len(df) < 50:
            return go.Figure()

        # Use daily timeframe directly - no weekly resampling
        dates = df["datetime"]
        close = df["close"]
        
        # Compute indicators
        indicators = compute_all(df)
        sma50 = close.rolling(50).mean()
        sma150 = close.rolling(150).mean()
        sma200 = close.rolling(200).mean()
        
        # Extract indicator values
        rsi_series = pd.Series(index=close.index, dtype=float)
        for i in range(len(close)):
            temp_df = df.iloc[:i+1].copy()
            if len(temp_df) >= 14:
                delta = temp_df["close"].diff()
                gain = delta.clip(lower=0).ewm(span=14, adjust=False).mean()
                loss = (-delta.clip(upper=0)).ewm(span=14, adjust=False).mean()
                rsi_val = 100 - 100 / (1 + gain / (loss + 1e-9))
                rsi_series.iloc[i] = rsi_val.iloc[-1]
        
        # MACD
        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        macd_line = ema12 - ema26
        macd_signal = macd_line.ewm(span=9, adjust=False).mean()
        macd_hist = macd_line - macd_signal

        # Create subplots: Price + MA, RSI, MACD, Volume
        fig = make_subplots(
            rows=4, cols=1, shared_xaxes=True,
            row_heights=[0.5, 0.15, 0.15, 0.2],
            vertical_spacing=0.05,
            subplot_titles=("Price & Moving Averages", "RSI (14)", "MACD", "Volume")
        )

        # Row 1: Candlestick + Moving Averages
        fig.add_trace(go.Candlestick(
            x=dates, open=df["open"], high=df["high"],
            low=df["low"], close=df["close"],
            increasing_line_color=_GREEN, increasing_fillcolor="#0d2b1a",
            decreasing_line_color=_RED, decreasing_fillcolor="#2b0d0d",
            line_width=1, name="Price",
        ), row=1, col=1)

        fig.add_trace(go.Scatter(x=dates, y=sma50,
            line=dict(color=_BLUE, width=1.2), name="SMA 50"), row=1, col=1)
        fig.add_trace(go.Scatter(x=dates, y=sma150,
            line=dict(color=_PURPLE, width=1, dash="dot"), name="SMA 150"), row=1, col=1)
        fig.add_trace(go.Scatter(x=dates, y=sma200,
            line=dict(color=_YELLOW, width=1, dash="dash"), name="SMA 200"), row=1, col=1)

        # Row 2: RSI
        fig.add_trace(go.Scatter(x=dates, y=rsi_series,
            line=dict(color=_BLUE, width=1.5), name="RSI", fill="tozeroy",
            fillcolor="rgba(96, 165, 250, 0.1)"), row=2, col=1)
        fig.add_hline(y=70, line=dict(color=_RED, width=1, dash="dash"), row=2, col=1)
        fig.add_hline(y=30, line=dict(color=_GREEN, width=1, dash="dash"), row=2, col=1)

        # Row 3: MACD
        fig.add_trace(go.Scatter(x=dates, y=macd_line,
            line=dict(color=_BLUE, width=1.2), name="MACD"), row=3, col=1)
        fig.add_trace(go.Scatter(x=dates, y=macd_signal,
            line=dict(color=_RED, width=1), name="Signal"), row=3, col=1)
        
        colors = [_GREEN if val >= 0 else _RED for val in macd_hist]
        fig.add_trace(go.Bar(x=dates, y=macd_hist, marker_color=colors,
            marker_opacity=0.6, name="MACD Hist", showlegend=False), row=3, col=1)
        fig.add_hline(y=0, line=dict(color=_MUTED, width=0.8), row=3, col=1)

        # Row 4: Volume
        vol_colors = [_GREEN if df["close"].iloc[i] >= df["close"].iloc[i-1] else _RED 
                      for i in range(len(df))]
        fig.add_trace(go.Bar(x=dates, y=df["volume"], marker_color=vol_colors,
            marker_opacity=0.6, name="Volume", showlegend=False), row=4, col=1)

        fig.update_layout(
            paper_bgcolor=_BG, plot_bgcolor=_BG,
            font=dict(color=_TEXT, size=9, family="Inter"),
            margin=dict(l=0, r=50, t=40, b=0), height=700,
            showlegend=True,
            xaxis_rangeslider_visible=False,
            title=dict(text=f"{symbol} - Daily Technical Analysis",
                       font=dict(size=12, color=_WHITE), x=0),
            hovermode="x unified",
        )
        
        # Update all axes
        for i in range(1, 5):
            fig.update_xaxes(gridcolor=_BORDER, zerolinecolor=_BORDER,
                            tickfont=dict(color=_MUTED, size=8), showgrid=True, row=i, col=1)
            fig.update_yaxes(gridcolor=_BORDER, zerolinecolor=_BORDER,
                            tickfont=dict(color=_MUTED, size=8), showgrid=True, row=i, col=1)

        return fig
    except Exception as e:
        st.error(f"Chart error: {e}")
        return go.Figure()

def _render_strategy_row(rank: int, row: pd.Series):
    """Render expandable strategy row with chart."""
    symbol = row.get("symbol", "")
    score = row.get("best_score", 0)
    strategy = row.get("best_strategy", "")
    cmp = row.get("cmp", 0)
    entry = row.get("entry_price", row.get("cmp", 0))
    pct = row.get("pct_change", 0)
    rsi = row.get("rsi", 0)
    d52 = row.get("dist_52h_pct", 0)
    score_c = score_color(score)
    pct_c = "#00c853" if pct > 0 else ("#ef4444" if pct < 0 else "#6b7280")
    pct_arr = "▲" if pct > 0 else ("▼" if pct < 0 else "—")
    rsi_c = "#ef4444" if rsi >= 70 else ("#00c853" if rsi <= 30 else "#6b7280")

    label = f"{rank}. {symbol} | {strategy} | Score {score:.0f} | ₹{cmp:,.0f} {pct_arr}{abs(pct):.1f}%"

    with st.expander(label, expanded=False):
        # Metrics row
        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            st.metric("CMP", f"₹{cmp:,.0f}", f"{pct_arr}{abs(pct):.1f}%")
        with col2:
            st.metric("Entry", f"₹{entry:,.0f}")
        with col3:
            st.metric("RSI", f"{rsi:.0f}", delta_color="inverse")
        with col4:
            st.metric("52W%", f"{d52:.0f}%")
        with col5:
            st.metric("Score", f"{score:.0f}")

        # Chart with all technicals
        st.markdown("---")
        fig = _build_strategy_chart(symbol, row)
        if fig.data:
            st.plotly_chart(fig, use_container_width=True,
                            config={"displayModeBar": False},
                            key=f"strat_chart_{symbol}_{rank}")
        else:
            st.info("Chart data unavailable.")

def render(slot):
    slot.empty()
    with slot.container():
        ph = st.empty()
        ph.markdown(_loading_html("Initialising scan &nbsp;&middot;&nbsp; 0 / 200 stocks"), unsafe_allow_html=True)

        if _SCAN_KEY not in st.session_state:
            cached = get_cached_scan()
            if cached is not None and not cached.empty:
                st.session_state[_SCAN_KEY] = cached
            else:
                ph.empty()
                ph2 = st.empty()
                st.session_state[_SCAN_KEY] = _run_scan_with_progress(ph2)
                ph2.empty()
            st.session_state[_LAST_REFRESH_KEY] = time.time()

        df = st.session_state.get(_SCAN_KEY, pd.DataFrame())
        ph.empty()

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

        df_filtered = df[df['best_score'] > 70]
        if df_filtered.empty:
            st.info(f"No stocks with score > 70. Max score in data: {df['best_score'].max():.1f}")
            df_filtered = df.head(10)

        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Total Setups", len(df_filtered))
        c2.metric("Avg Score", f"{df_filtered['best_score'].mean():.1f}")
        c3.metric("High Volume", len(df_filtered[df_filtered['volume_ratio'] >= 1.5]))
        c4.metric("Near 52W High", len(df_filtered[df_filtered['dist_52h_pct'] >= -5]))
        
        # Add force rescan button
        with c5:
            if st.button("🔄 Force Rescan", help="Clear cache and run fresh scan", use_container_width=True):
                # Clear database cache
                from database import get_conn
                with get_conn() as conn:
                    conn.execute("DELETE FROM scan_results_cache")
                    conn.commit()
                # Clear session state
                if _SCAN_KEY in st.session_state:
                    del st.session_state[_SCAN_KEY]
                st.cache_data.clear()
                st.rerun()

        st.markdown("---")
        st.markdown('<div style="font-size:.75rem;font-weight:600;color:#6b7280;text-transform:uppercase;letter-spacing:.05em;margin-bottom:8px;">Strategy Setups - Click to Expand for Chart</div>', unsafe_allow_html=True)

        for rank, (_, row) in enumerate(df_filtered.head(30).iterrows(), 1):
            _render_strategy_row(rank, row)
