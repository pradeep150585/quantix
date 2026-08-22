"""
Page 1 – Live Market Dashboard
"""
import asyncio
import json
import streamlit as st
import streamlit.components.v1 as components
from services.index_service import get_all_index_quotes, INDEX_KEYS
from indicators import rsi as calc_rsi, macd as calc_macd
from services.market_data import get_historical_df
from config import get
from components.ui import page_heading, loading_html

_EXCLUDE = {"INDIA VIX"}


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


@st.cache_data(ttl=10, show_spinner=False)
def _fetch_live_quotes():
    """Fetch live quotes server-side with short cache"""
    return _run(get_all_index_quotes())


@st.cache_data(ttl=600, show_spinner=False)
def _fetch_indicators(key: str):
    df = _run(get_historical_df(key, interval="day", days=100))
    if df.empty:
        return 50.0, 0.0
    try:
        r = round(calc_rsi(df), 1)
        vals = calc_macd(df)
        return r, round(vals[2], 2)
    except Exception:
        return 50.0, 0.0


def _rsi_color(v):
    if v >= 70: return "#ef4444"
    if v >= 60: return "#f59e0b"
    if v <= 30: return "#00c853"
    return "#6b7280"


def _build_dashboard_html(quotes, indicators_map) -> str:
    index_names = [n for n in INDEX_KEYS if n not in _EXCLUDE]

    # Calculate advance/decline and sentiment from current quotes
    adv_count = 0
    dec_count = 0
    
    tiles_config = []
    for name in index_names:
        q = quotes.get(name, {})
        ltp = q.get("ltp", 0)
        prev = q.get("prev_close", 0)
        rsi_val, macd_hist = indicators_map.get(name, (50, 0))
        
        pct_change = ((ltp - prev) / prev * 100) if prev > 0 else 0
        if pct_change > 0:
            adv_count += 1
        elif pct_change < 0:
            dec_count += 1
            
        tiles_config.append({
            "name":      name,
            "key":       INDEX_KEYS[name],
            "ltp":       ltp,
            "prev":      prev,
            "pct":       pct_change,
            "rsi":       rsi_val,
            "rsi_c":     _rsi_color(rsi_val),
            "macd_hist": macd_hist,
        })

    # Get NIFTY 50 and VIX data
    nifty_q = quotes.get("NIFTY 50", {})
    nifty_ltp = nifty_q.get("ltp", 0)
    nifty_prev = nifty_q.get("prev_close", 0)
    nifty_pct = ((nifty_ltp - nifty_prev) / nifty_prev * 100) if nifty_prev > 0 else 0
    
    vix_q = quotes.get("INDIA VIX", {})
    vix_ltp = vix_q.get("ltp", 0)
    
    # Calculate market sentiment
    total_indices = adv_count + dec_count
    ratio = adv_count / total_indices if total_indices > 0 else 0.5
    sentiment = 'Bullish' if ratio > 0.6 else 'Bearish' if ratio < 0.4 else 'Neutral'
    sentiment_color = '#00c853' if sentiment == 'Bullish' else '#ef4444' if sentiment == 'Bearish' else '#6b7280'

    return f"""<!DOCTYPE html><html><head>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#0b0e17;color:#d1d4dc;font-family:'Inter',system-ui,sans-serif;padding:8px}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:14px}}
.mcard{{background:#131722;border:1px solid #1e2433;border-radius:6px;padding:14px 16px}}
.mlabel{{color:#6b7280;font-size:.62rem;text-transform:uppercase;letter-spacing:.08em;font-weight:500}}
.mval{{color:#ffffff;font-size:1.2rem;font-weight:700;margin-top:4px;font-family:'Inter',sans-serif}}
.mdelta{{font-size:.7rem;margin-top:3px;color:#6b7280}}
.htitle{{font-size:.65rem;font-weight:600;color:#9ca3af;text-transform:uppercase;letter-spacing:.08em;
  margin:12px 0 8px;padding-bottom:5px;border-bottom:1px solid #1e2433;display:flex;align-items:center;gap:6px}}
.live-dot{{width:6px;height:6px;border-radius:50%;background:#00c853;box-shadow:0 0 6px #00c85366;display:inline-block}}
.hgrid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(128px,1fr));gap:6px}}
.tile{{background:#131722;border:1px solid #1e2433;border-radius:5px;padding:11px 13px;transition:border-color .2s,transform .15s;cursor:default}}
.tile:hover{{border-color:#2d3748;transform:translateY(-1px)}}
.tname{{font-size:.58rem;font-weight:600;text-transform:uppercase;letter-spacing:.04em;margin-bottom:3px;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;color:#9ca3af}}
.tltp{{font-size:.95rem;font-weight:700;color:#ffffff;font-family:'Inter',sans-serif}}
.tchg{{font-size:.67rem;margin-top:2px}}
.tind{{display:flex;gap:6px;margin-top:5px;font-size:.58rem}}
.ts{{font-size:.6rem;color:#4a5568;text-align:right;margin-top:8px}}
@media(max-width:600px){{.grid{{grid-template-columns:repeat(2,1fr)}}.hgrid{{grid-template-columns:repeat(auto-fill,minmax(110px,1fr))}}.mval{{font-size:1rem}}}}
</style>
</head><body>
<div class="grid">
  <div class="mcard"><div class="mlabel">NIFTY 50</div>
    <div class="mval">{nifty_ltp:,.2f}</div>
    <div class="mdelta" style="color:{'#00c853' if nifty_pct >= 0 else '#ef4444'}">{'▲' if nifty_pct >= 0 else '▼'} {abs(nifty_pct):.2f}%</div></div>
  <div class="mcard"><div class="mlabel">India VIX</div>
    <div class="mval">{vix_ltp:.2f}</div>
    <div class="mdelta" style="color:#6b7280">Volatility Index</div></div>
  <div class="mcard"><div class="mlabel">Market Sentiment</div>
    <div class="mval" style="color:{sentiment_color}">{sentiment}</div>
    <div class="mdelta" style="color:#6b7280">Based on indices</div></div>
  <div class="mcard"><div class="mlabel">Advance / Decline</div>
    <div class="mval"><span style="color:#00c853">{adv_count}</span> / <span style="color:#ef4444">{dec_count}</span></div>
    <div class="mdelta" style="color:#6b7280">Indices breadth</div></div>
</div>
<div class="htitle"><span class="live-dot"></span> Indices Heatmap</div>
<div class="hgrid">"""

    # Build tiles
    for t in tiles_config:
        pct = t["pct"]
        arr = "▲" if pct > 0 else "▼" if pct < 0 else "—"
        fg_color = "#00c853" if pct >= 0 else "#ef4444"
        border_color = "#1a3a2a" if pct >= 0 else "#3a1a1a"
        mc = "#00c853" if t["macd_hist"] > 0 else "#ef4444"
        ma = "▲" if t["macd_hist"] > 0 else "▼"
        
        html += f"""
  <div class="tile" style="border-color:{border_color}">
    <div class="tname">{t['name']}</div>
    <div class="tltp">{t['ltp']:,.2f}</div>
    <div class="tchg" style="color:{fg_color}">{arr} {abs(pct):.2f}%</div>
    <div class="tind"><span style="color:{t['rsi_c']}">RSI {t['rsi']}</span><span style="color:{mc}">MACD {ma}</span></div>
  </div>"""
    
    html += f"""
</div>
<div class="ts">Updated just now · Server-side data</div>
</body></html>"""
    
    return html


def render(slot):
    slot.empty()
    with slot.container():
        # Add refresh button
        col1, col2 = st.columns([6, 1])
        with col2:
            if st.button("🔄 Refresh", use_container_width=True):
                st.cache_data.clear()
                st.rerun()
        
        ph = st.empty()
        ph.markdown(loading_html("Loading market data…"), unsafe_allow_html=True)
        
        quotes = _fetch_live_quotes()
        
        indicators_map = {}
        for name in [n for n in INDEX_KEYS if n not in _EXCLUDE]:
            key = INDEX_KEYS.get(name, "")
            if key:
                try:
                    indicators_map[name] = _fetch_indicators(key)
                except Exception:
                    indicators_map[name] = (50, 0)
        
        ph.empty()
        components.html(_build_dashboard_html(quotes, indicators_map), height=500, scrolling=True)
