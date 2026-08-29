"""
Page 2 – Live Nifty 200 Scanner (Lightweight)
"""
import asyncio
import time
import json
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import plotly.graph_objects as go
from services.instruments import get_nifty200_symbols
from services.market_data import get_quotes, parse_quote, get_historical_df
from config import get as cfg_get
from components.ui import page_heading, loading_html

_SYMBOLS_KEY = "_live_symbols_df"
_BG     = "#0b0e17"
_BORDER = "#1e2433"
_TEXT   = "#d1d4dc"
_MUTED  = "#6b7280"
_GREEN  = "#00c853"
_RED    = "#ef4444"
_BLUE   = "#60a5fa"


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


def _calculate_heikin_ashi(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate Heikin-Ashi candles"""
    ha_df = df.copy()
    
    # HA Close = (Open + High + Low + Close) / 4
    ha_df['ha_close'] = (df['open'] + df['high'] + df['low'] + df['close']) / 4
    
    # HA Open = (Previous HA Open + Previous HA Close) / 2
    ha_df['ha_open'] = 0.0
    ha_df.loc[0, 'ha_open'] = (df.loc[0, 'open'] + df.loc[0, 'close']) / 2
    
    for i in range(1, len(df)):
        ha_df.loc[i, 'ha_open'] = (ha_df.loc[i-1, 'ha_open'] + ha_df.loc[i-1, 'ha_close']) / 2
    
    # HA High = Max(High, HA Open, HA Close)
    ha_df['ha_high'] = ha_df[['high', 'ha_open', 'ha_close']].max(axis=1)
    
    # HA Low = Min(Low, HA Open, HA Close)
    ha_df['ha_low'] = ha_df[['low', 'ha_open', 'ha_close']].min(axis=1)
    
    return ha_df


def _build_heikin_ashi_chart(symbol: str, instrument_key: str) -> go.Figure:
    """Build Heikin-Ashi chart with EMA 10 and Pivot Points (10-min timeframe)"""
    try:
        # Fetch 10-minute data
        df = _run(get_historical_df(instrument_key, interval="10minute", days=5))
        
        if df.empty or len(df) < 20:
            fig = go.Figure()
            fig.add_annotation(text="Insufficient data", showarrow=False,
                             font=dict(size=14, color=_MUTED))
            fig.update_layout(paper_bgcolor=_BG, plot_bgcolor=_BG, height=400)
            return fig
        
        # Calculate Heikin-Ashi
        ha_df = _calculate_heikin_ashi(df)
        
        # Calculate EMA 10
        ha_df['ema10'] = ha_df['ha_close'].ewm(span=10, adjust=False).mean()
        
        # Calculate Standard Pivot Points (using previous day's data)
        # Use last complete day for pivot calculation
        prev_day = df[df['datetime'] < pd.Timestamp.now().normalize()].tail(1)
        if not prev_day.empty:
            prev_high = prev_day['high'].iloc[0]
            prev_low = prev_day['low'].iloc[0]
            prev_close = prev_day['close'].iloc[0]
        else:
            # Fallback to overall high/low/close if no previous day
            prev_high = df['high'].max()
            prev_low = df['low'].min()
            prev_close = df['close'].iloc[-1]
        
        # Standard Pivot Points formula
        pivot = (prev_high + prev_low + prev_close) / 3
        r1 = (2 * pivot) - prev_low
        r2 = pivot + (prev_high - prev_low)
        r3 = prev_high + 2 * (pivot - prev_low)
        s1 = (2 * pivot) - prev_high
        s2 = pivot - (prev_high - prev_low)
        s3 = prev_low - 2 * (prev_high - pivot)
        
        dates = ha_df["datetime"] if "datetime" in ha_df.columns else pd.RangeIndex(len(ha_df))
        
        fig = go.Figure()
        
        # Add Heikin-Ashi candlesticks
        fig.add_trace(go.Candlestick(
            x=dates,
            open=ha_df['ha_open'],
            high=ha_df['ha_high'],
            low=ha_df['ha_low'],
            close=ha_df['ha_close'],
            increasing_line_color=_GREEN,
            increasing_fillcolor="#0d2b1a",
            decreasing_line_color=_RED,
            decreasing_fillcolor="#2b0d0d",
            line_width=1,
            name="Heikin-Ashi",
        ))
        
        # Add EMA 10
        fig.add_trace(go.Scatter(
            x=dates,
            y=ha_df['ema10'],
            line=dict(color=_BLUE, width=1.5),
            name="EMA 10"
        ))
        
        # Add Pivot Points
        pivot_levels = [
            (s3, "#ef4444", "S3", "dash"),
            (s2, "#f87171", "S2", "dot"),
            (s1, "#fca5a5", "S1", "dot"),
            (pivot, "#fbbf24", "Pivot", "solid"),
            (r1, "#86efac", "R1", "dot"),
            (r2, "#4ade80", "R2", "dot"),
            (r3, "#00c853", "R3", "dash"),
        ]
        
        for level, color, name, dash in pivot_levels:
            fig.add_hline(
                y=level,
                line=dict(color=color, width=1, dash=dash),
                annotation_text=f"{name} {level:.2f}",
                annotation_position="right",
                annotation_font=dict(color=color, size=8)
            )
        
        fig.update_layout(
            paper_bgcolor=_BG,
            plot_bgcolor=_BG,
            font=dict(color=_TEXT, size=10, family="Inter"),
            margin=dict(l=10, r=80, t=30, b=10),
            height=450,
            showlegend=True,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1,
                font=dict(size=9)
            ),
            xaxis_rangeslider_visible=False,
            title=dict(
                text=f"{symbol} - Heikin-Ashi 10-Min with Pivots",
                font=dict(size=12, color=_TEXT),
                x=0
            ),
        )
        
        ax = dict(
            gridcolor=_BORDER,
            zerolinecolor=_BORDER,
            tickfont=dict(color=_MUTED, size=9),
            showgrid=True
        )
        fig.update_xaxes(**ax)
        fig.update_yaxes(**ax)
        
        return fig
        
    except Exception as e:
        fig = go.Figure()
        fig.add_annotation(text=f"Error: {str(e)}", showarrow=False,
                         font=dict(size=12, color=_RED))
        fig.update_layout(paper_bgcolor=_BG, plot_bgcolor=_BG, height=400)
        return fig

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
            f'<td style="padding:6px 4px;border-bottom:1px solid #131722;font-size:.7rem;color:#60a5fa;font-weight:600;">{symbol}</td>',
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
    with slot.container():
        ph = st.empty()
        ph.markdown(loading_html("Loading live data…"), unsafe_allow_html=True)

        if _SYMBOLS_KEY not in st.session_state:
            st.session_state[_SYMBOLS_KEY] = _run(get_nifty200_symbols())
        symbols_df = st.session_state[_SYMBOLS_KEY]

        if symbols_df.empty:
            ph.empty()
            st.warning("Could not load Nifty 200 constituents.")
            return

        keys = tuple(symbols_df["instrument_key"].tolist())
        raw_quotes = _run(get_quotes(list(keys)))
        ph.empty()

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
        
        # Display table
        token = cfg_get("upstox.access_token", "")
        components.html(_build_table_html(df, time.strftime("%H:%M:%S"), token), height=450, scrolling=False)

