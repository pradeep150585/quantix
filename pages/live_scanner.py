"""
Page 2 – Live Nifty 200 Scanner (Lightweight)
"""
import asyncio
import time
import json
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
from services.instruments import get_nifty200_symbols
from services.market_data import get_quotes, parse_quote
from config import get as cfg_get
from components.ui import page_heading, loading_html

_SYMBOLS_KEY = "_live_symbols_df"

def _run(coro):
    try:
        loop = asyncio.new_event_loop()
        return loop.run_until_complete(coro)
    finally:
        loop.close()

def _ai_signal(tbq_tsq: float, pct_change: float, volume_ratio: float) -> str:
    if tbq_tsq >= 1.5 and pct_change >= 0 and volume_ratio >= 1.0:
        return "BUY"
    if tbq_tsq >= 1.2 and pct_change >= -0.5:
        return "WATCH+"
    if tbq_tsq <= 0.6 and pct_change <= 0:
        return "SELL"
    if tbq_tsq <= 0.8 and pct_change <= 0.5:
        return "WATCH-"
    return "NEUTRAL"

def _signal_style(signal: str) -> tuple[str, str]:
    styles = {
        "BUY":     ("rgba(0,200,83,0.10)",   '#00c853', '▲ BUY'),
        "WATCH+":  ("rgba(0,200,83,0.05)",   '#4ade80', '◆ WATCH+'),
        "SELL":    ("rgba(239,68,68,0.10)",   '#ef4444', '▼ SELL'),
        "WATCH-":  ("rgba(239,68,68,0.05)",   '#f87171', '◆ WATCH-'),
        "NEUTRAL": ("transparent",            '#6b7280', '— NEUTRAL'),
    }
    bg, color, label = styles.get(signal, styles["NEUTRAL"])
    badge = f'<span style="background:{color}18;color:{color};border:1px solid {color}33;border-radius:2px;padding:1px 4px;font-size:.58rem;font-weight:600;">{label}</span>'
    return bg, badge

def _build_table_html(df: pd.DataFrame, ts: str, token: str) -> str:
    headers = ["#", "Signal", "Symbol", "CMP", "Chg%", "TBQ/TSQ"]
    th = "".join(
        f'<th style="background:#131722;color:#9ca3af;font-size:.58rem;font-weight:600;text-transform:uppercase;letter-spacing:.04em;padding:6px 4px;border-bottom:1px solid #1e2433;">{h}</th>'
        for h in headers
    )
    tbody = ""
    rows_config = []
    for idx, (_, row) in enumerate(df.iterrows()):
        signal = row.get("signal", "NEUTRAL")
        row_bg, _ = _signal_style(signal)
        ikey = row.get("instrument_key", "")
        symbol = row.get("symbol", "")
        rows_config.append({"idx": idx, "key": ikey, "symbol": symbol, "prev": row.get("prev_close", 0), "signal": signal})
        pct = row.get("pct_change", 0)
        tbq_tsq_v = row.get("tbq_tsq", 0)
        _, badge = _signal_style(signal)
        pct_c = "#00c853" if pct > 0 else ("#ef4444" if pct < 0 else "#6b7280")
        pct_arr = "▲" if pct > 0 else ("▼" if pct < 0 else "—")
        tbq_tsq_c = "#00c853" if tbq_tsq_v >= 2 else ("#4ade80" if tbq_tsq_v >= 1.2 else ("#ef4444" if tbq_tsq_v <= 0.5 else ("#f87171" if tbq_tsq_v <= 0.8 else "#6b7280")))
        cells = [
            f'<td style="padding:6px 4px;border-bottom:1px solid #131722;font-size:.65rem;color:#4a5568;">{idx+1}</td>',
            f'<td id="r{idx}-signal" style="padding:6px 4px;border-bottom:1px solid #131722;font-size:.65rem;">{badge}</td>',
            f'<td style="padding:6px 4px;border-bottom:1px solid #131722;font-size:.7rem;color:#fff;font-weight:600;">{symbol}</td>',
            f'<td id="r{idx}-cmp" style="padding:6px 4px;border-bottom:1px solid #131722;font-size:.7rem;color:#d1d4dc;">₹{row.get("cmp",0):,.0f}</td>',
            f'<td id="r{idx}-pct_change" style="padding:6px 4px;border-bottom:1px solid #131722;font-size:.7rem;color:{pct_c};font-weight:600;">{pct_arr} {abs(pct):.1f}%</td>',
            f'<td id="r{idx}-tbq_tsq" style="padding:6px 4px;border-bottom:1px solid #131722;font-size:.7rem;color:{tbq_tsq_c};font-weight:700;">{tbq_tsq_v:.2f}</td>',
        ]
        tbody += f'<tr id="row{idx}" style="background:{row_bg};">{"".join(cells)}</tr>\n'
    all_keys = df["instrument_key"].tolist()
    return f"""<!DOCTYPE html><html><head>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#0b0e17;color:#d1d4dc;font-family:'Inter',system-ui,sans-serif;font-size:.7rem}}
table{{border-collapse:collapse;width:100%;table-layout:fixed}}
::-webkit-scrollbar{{width:2px;height:2px}}
::-webkit-scrollbar-track{{background:#0b0e17}}
::-webkit-scrollbar-thumb{{background:#2d3748;border-radius:1px}}
</style></head><body>
<table><thead><tr>{th}</tr></thead><tbody id="tbody">{tbody}</tbody></table>
<div style="font-size:.55rem;color:#4a5568;padding:4px 4px;">Updated {ts} · {len(df)} stocks · live</div>
<script>
const TOKEN='{token}';const ALL_KEYS={json.dumps(all_keys)};const ROWS={json.dumps(rows_config)};
const state={{}};ROWS.forEach(r=>{{state[r.idx]={{key:r.key,symbol:r.symbol,prev:r.prev,ratio:0,signal:r.signal}};}});
function pctColor(v){{return v>0?'#00c853':v<0?'#ef4444':'#6b7280';}}
function ratioColor(v){{if(v>=2)return'#00c853';if(v>=1.2)return'#4ade80';if(v<=0.5)return'#ef4444';if(v<=0.8)return'#f87171';return'#6b7280';}}
function rowBg(sig){{if(sig==='BUY')return'rgba(0,200,83,0.10)';if(sig==='WATCH+')return'rgba(0,200,83,0.05)';if(sig==='SELL')return'rgba(239,68,68,0.10)';if(sig==='WATCH-')return'rgba(239,68,68,0.05)';return'transparent';}}
function signalBadge(sig){{const map={{'BUY':['#00c853','▲ BUY'],'WATCH+':['#4ade80','◆ WATCH+'],'SELL':['#ef4444','▼ SELL'],'WATCH-':['#f87171','◆ WATCH-'],'NEUTRAL':['#6b7280','— NEUTRAL']}};const[c,label]=map[sig]||map['NEUTRAL'];return`<span style="background:${{c}}18;color:${{c}};border:1px solid ${{c}}33;border-radius:2px;padding:1px 4px;font-size:.58rem;font-weight:600;">${{label}}</span>`;}};
function aiSignal(ratio,pct,vol){{if(ratio>=1.5&&pct>=0&&vol>=1.0)return'BUY';if(ratio>=1.2&&pct>=-0.5)return'WATCH+';if(ratio<=0.6&&pct<=0)return'SELL';if(ratio<=0.8&&pct<=0.5)return'WATCH-';return'NEUTRAL';}}
async function refresh(){{const m={{}};for(let i=0;i<ALL_KEYS.length;i+=500){{const chunk=ALL_KEYS.slice(i,i+500);try{{const r=await fetch('https://api.upstox.com/v2/market-quote/quotes?instrument_key='+encodeURIComponent(chunk.join(',')),{{headers:{{Authorization:'Bearer '+TOKEN,Accept:'application/json'}}}});const j=await r.json();if(j.status!=='success')return;for(const[k,v]of Object.entries(j.data)){{const ltp=v.last_price||0;const prev=v.net_change?(ltp-v.net_change):(v.ohlc?.close||0);const obj={{ltp,prev,tbq:v.total_buy_quantity||0,tsq:v.total_sell_quantity||0}};[k,k.replace(/:/g,'|'),k.replace(/\\|/g,':')].forEach(x=>m[x]=obj);if(v.instrument_token)[v.instrument_token,v.instrument_token.replace(/:/g,'|')].forEach(x=>m[x]=obj);}}}}catch(e){{}}}}ROWS.forEach(row=>{{const d=m[row.key]||m['NSE_EQ:'+row.symbol]||m['NSE_EQ|'+row.symbol];if(!d||!d.ltp)return;const i=row.idx;const pct=row.prev?(d.ltp-row.prev)/row.prev*100:0;const ratio=d.tsq?d.tbq/d.tsq:0;const sig=aiSignal(ratio,pct,1);state[i].ratio=ratio;state[i].pct=pct;state[i].signal=sig;state[i].ltp=d.ltp;const tr=document.getElementById('row'+i);if(tr)tr.style.background=rowBg(sig);const cmpEl=document.getElementById('r'+i+'-cmp');if(cmpEl)cmpEl.innerHTML='₹'+d.ltp.toLocaleString('en-IN',{{minimumFractionDigits:0,maximumFractionDigits:0}});const pctEl=document.getElementById('r'+i+'-pct_change');if(pctEl)pctEl.innerHTML='<span style="color:'+pctColor(pct)+';font-weight:600;">'+(pct>0?'▲':pct<0?'▼':'—')+' '+Math.abs(pct).toFixed(1)+'%</span>';const ratEl=document.getElementById('r'+i+'-tbq_tsq');if(ratEl)ratEl.innerHTML='<span style="color:'+ratioColor(ratio)+';font-weight:700;">'+ratio.toFixed(2)+'</span>';const sigEl=document.getElementById('r'+i+'-signal');if(sigEl)sigEl.innerHTML=signalBadge(sig);}});}}
refresh();setInterval(refresh,3000);
</script>
</body></html>"""

def render(slot):
    slot.empty()
    st.empty()
    slot.markdown(loading_html("Loading live data…"), unsafe_allow_html=True)

    if _SYMBOLS_KEY not in st.session_state:
        st.session_state[_SYMBOLS_KEY] = _run(get_nifty200_symbols())
    symbols_df = st.session_state[_SYMBOLS_KEY]

    if symbols_df.empty:
        slot.empty()
        st.warning("Could not load Nifty 200 constituents.")
        return

    keys = tuple(symbols_df["instrument_key"].tolist())
    raw_quotes = _run(get_quotes(list(keys)))
    slot.empty()

    if not raw_quotes:
        st.warning("No live data. Check your Upstox access token in Settings.")
        return

    records = []
    for _, row in symbols_df.iterrows():
        key    = row["instrument_key"]
        symbol = row.get("symbol", "")
        raw = raw_quotes.get(key) or raw_quotes.get(f"NSE_EQ:{symbol}") or raw_quotes.get(f"NSE_EQ|{symbol}") or {}
        q = parse_quote(raw)
        if not q or q.get("ltp", 0) == 0:
            continue
        ltp        = q["ltp"]
        prev_close = q.get("prev_close", 0)
        pct_change = (ltp - prev_close) / prev_close * 100 if prev_close else 0
        tbq, tsq   = q.get("tbq", 0), q.get("tsq", 0)
        tbq_tsq    = round(tbq / tsq, 2) if tsq else 0
        records.append({
            "symbol":         symbol,
            "cmp":            round(ltp, 2),
            "pct_change":     round(pct_change, 2),
            "prev_close":     prev_close,
            "tbq_tsq":        tbq_tsq,
            "signal":         _ai_signal(tbq_tsq, pct_change, 1.0),
            "instrument_key": key,
        })

    df = pd.DataFrame(records)
    if df.empty:
        st.warning("No live data returned. Market may be closed or token expired.")
        return

    search = st.session_state.get("live_search", "")
    if search:
        mask = df["symbol"].str.contains(search.upper(), na=False)
        df = df[mask]
    
    sig_filter = st.selectbox("Signal", ["BUY & SELL", "BUY only", "SELL only", "All"], index=0, key="live_sig_filter_v1")
    if sig_filter == "BUY & SELL":
        df = df[df["signal"].isin(["BUY", "SELL"])]
    elif sig_filter == "BUY only":
        df = df[df["signal"] == "BUY"]
    elif sig_filter == "SELL only":
        df = df[df["signal"] == "SELL"]

    df = df.sort_values("tbq_tsq", ascending=False).reset_index(drop=True)

    token = cfg_get("upstox.access_token", "")
    components.html(_build_table_html(df, time.strftime("%H:%M:%S"), token), height=450, scrolling=False)
