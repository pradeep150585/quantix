"""
Page 2 – Live Nifty 200 Scanner
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


def _fmt_vol(v):
    try:
        v = float(v)
    except Exception:
        return "&mdash;"
    if v >= 1_00_00_000: return f"{v/1_00_00_000:.1f}Cr"
    if v >= 1_00_000:    return f"{v/1_00_000:.1f}L"
    if v >= 1_000:       return f"{v/1_000:.1f}K"
    return str(int(v))


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
    badge = f'<span style="background:{color}18;color:{color};border:1px solid {color}33;border-radius:3px;padding:1px 6px;font-size:.63rem;font-weight:600;">{label}</span>'
    return bg, badge


def _build_table_html(df: pd.DataFrame, ts: str, token: str) -> str:
    cols = [
        ("signal",       "AI Signal", 90),
        ("symbol",       "Symbol",    88),
        ("company_name", "Company",   155),
        ("sector",       "Sector",    115),
        ("cmp",          "CMP",       85),
        ("pct_change",   "Chg %",     70),
        ("volume",       "Volume",    78),
        ("tbq",          "TBQ",       78),
        ("tsq",          "TSQ",       78),
        ("tbq_tsq",      "TBQ/TSQ",   76),
    ]
    frozen_count = 4
    cum = 0
    left_px = []
    for _, _, w in cols:
        left_px.append(cum)
        cum += w

    th = ""
    for i, (key, label, width) in enumerate(cols):
        frozen = i < frozen_count
        z = "30" if frozen else "20"
        left = f"left:{left_px[i]}px;" if frozen else ""
        br = "border-right:1px solid #2d3748;" if i == frozen_count - 1 else ""
        th += (
            f'<th style="position:sticky;top:0;{left}z-index:{z};'
            f'width:{width}px;min-width:{width}px;max-width:{width}px;'
            f'background:#131722;color:#9ca3af;font-size:.62rem;font-weight:600;'
            f'text-transform:uppercase;letter-spacing:.06em;padding:10px 8px;'
            f'white-space:nowrap;border-bottom:1px solid #1e2433;{br}">{label}</th>'
        )

    tbody = ""
    rows_config = []

    for idx, (_, row) in enumerate(df.iterrows()):
        pct        = row.get("pct_change", 0)
        tbq_tsq_v  = row.get("tbq_tsq", 0)
        signal     = row.get("signal", "NEUTRAL")
        row_bg, _  = _signal_style(signal)
        solid      = row_bg if row_bg != "transparent" else "#0b0e17"
        ikey       = row.get("instrument_key", "")
        symbol     = row.get("symbol", "")

        rows_config.append({
            "idx":    idx,
            "key":    ikey,
            "symbol": symbol,
            "prev":   row.get("prev_close", 0),
            "signal": signal,
        })

        cells = ""
        for i, (key, label, width) in enumerate(cols):
            val    = row.get(key, "")
            frozen = i < frozen_count
            pos    = "position:sticky;" if frozen else ""
            left   = f"left:{left_px[i]}px;" if frozen else ""
            br     = "border-right:1px solid #1e2433;" if i == frozen_count - 1 else ""
            cbg    = f"background:{solid};" if frozen else f"background:{row_bg};"
            cell_id = f' id="r{idx}-{key}"' if key in ("cmp", "pct_change", "tbq", "tsq", "tbq_tsq", "volume", "signal") else ""

            if key == "signal":
                _, badge = _signal_style(signal)
                display = badge
            elif key == "pct_change":
                c   = "#00c853" if pct > 0 else ("#ef4444" if pct < 0 else "#6b7280")
                arr = "▲" if pct > 0 else ("▼" if pct < 0 else "—")
                display = f'<span style="color:{c};font-weight:600;">{arr} {abs(pct):.2f}%</span>'
            elif key == "tbq_tsq":
                c = "#00c853" if tbq_tsq_v >= 2 else ("#4ade80" if tbq_tsq_v >= 1.2 else ("#ef4444" if tbq_tsq_v <= 0.5 else ("#f87171" if tbq_tsq_v <= 0.8 else "#6b7280")))
                display = f'<span style="color:{c};font-weight:700;">{tbq_tsq_v:.2f}</span>'
            elif key in ("tbq", "tsq", "volume"):
                display = _fmt_vol(float(val)) if val else "&mdash;"
            elif key == "cmp":
                display = f"&#8377;{float(val):,.2f}" if val else "&mdash;"
            elif key == "symbol":
                display = f'<span style="color:#ffffff;font-weight:600;">{val}</span>'
            elif key == "company_name":
                display = f'<span style="color:#9ca3af;font-size:.74rem;">{val}</span>'
            else:
                display = str(val) if val else "&mdash;"

            cells += (
                f'<td{cell_id} style="{pos}{left}width:{width}px;min-width:{width}px;max-width:{width}px;'
                f'{cbg}padding:8px 8px;font-size:.78rem;color:#d1d4dc;'
                f'border-bottom:1px solid #131722;white-space:nowrap;'
                f'overflow:hidden;text-overflow:ellipsis;{br}">{display}</td>'
            )
        tbody += f'<tr id="row{idx}">{cells}</tr>\n'

    all_keys = df["instrument_key"].tolist()

    return f"""<!DOCTYPE html><html><head>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#0b0e17;color:#d1d4dc;font-family:'Inter',system-ui,sans-serif}}
.wrap{{width:100%;overflow-x:auto;overflow-y:auto;height:calc(100vh - 24px);border:1px solid #1e2433;border-radius:5px;background:#0b0e17}}
table{{border-collapse:collapse;table-layout:fixed;width:max-content;min-width:100%}}
::-webkit-scrollbar{{width:4px;height:4px}}
::-webkit-scrollbar-track{{background:#0b0e17}}
::-webkit-scrollbar-thumb{{background:#2d3748;border-radius:4px}}
.ts{{font-size:.6rem;color:#4a5568;text-align:right;padding:3px 8px}}
@keyframes flash{{0%{{opacity:.4}}50%{{opacity:1}}100%{{opacity:1}}}}
.flash{{animation:flash .4s ease}}
</style>
</head><body>
<div class="wrap"><table>
<thead><tr>{th}</tr></thead>
<tbody id="tbody">{tbody}</tbody>
</table></div>
<div class="ts" id="ts-label">Updated {ts} &middot; {len(df)} stocks &middot; live &#9679;</div>
<script>
const TOKEN    = {json.dumps(token)};
const ALL_KEYS = {json.dumps(all_keys)};
const ROWS     = {json.dumps(rows_config)};

const state = {{}};
ROWS.forEach(r => {{ state[r.idx] = {{ key: r.key, symbol: r.symbol, prev: r.prev, ratio: 0, signal: r.signal }}; }});

function fmtVol(v) {{
  if (v >= 1e7) return (v/1e7).toFixed(1)+'Cr';
  if (v >= 1e5) return (v/1e5).toFixed(1)+'L';
  if (v >= 1e3) return (v/1e3).toFixed(1)+'K';
  return String(Math.round(v));
}}
function pctColor(v)  {{ return v>0?'#00c853':v<0?'#ef4444':'#6b7280'; }}
function ratioColor(v){{
  if(v>=2) return '#00c853'; if(v>=1.2) return '#4ade80';
  if(v<=0.5) return '#ef4444'; if(v<=0.8) return '#f87171';
  return '#6b7280';
}}
function rowBg(sig) {{
  if(sig==='BUY')    return 'rgba(0,200,83,0.10)';
  if(sig==='WATCH+') return 'rgba(0,200,83,0.05)';
  if(sig==='SELL')   return 'rgba(239,68,68,0.10)';
  if(sig==='WATCH-') return 'rgba(239,68,68,0.05)';
  return 'transparent';
}}
function signalBadge(sig) {{
  const map = {{
    'BUY':     ['#00c853','▲ BUY'],
    'WATCH+':  ['#4ade80','◆ WATCH+'],
    'SELL':    ['#ef4444','▼ SELL'],
    'WATCH-':  ['#f87171','◆ WATCH-'],
    'NEUTRAL': ['#6b7280','— NEUTRAL'],
  }};
  const [c, label] = map[sig] || map['NEUTRAL'];
  return `<span style="background:${{c}}18;color:${{c}};border:1px solid ${{c}}33;border-radius:3px;padding:1px 6px;font-size:.63rem;font-weight:600;">${{label}}</span>`;
}}
function aiSignal(ratio, pct, vol) {{
  if (ratio >= 1.5 && pct >= 0 && vol >= 1.0) return 'BUY';
  if (ratio >= 1.2 && pct >= -0.5)            return 'WATCH+';
  if (ratio <= 0.6 && pct <= 0)               return 'SELL';
  if (ratio <= 0.8 && pct <= 0.5)             return 'WATCH-';
  return 'NEUTRAL';
}}

async function refresh() {{
  const m = {{}};
  for (let i = 0; i < ALL_KEYS.length; i += 500) {{
    const chunk = ALL_KEYS.slice(i, i+500);
    try {{
      const r = await fetch(
        'https://api.upstox.com/v2/market-quote/quotes?instrument_key=' + encodeURIComponent(chunk.join(',')),
        {{headers: {{Authorization: 'Bearer '+TOKEN, Accept: 'application/json'}}}}
      );
      const j = await r.json();
      if (j.status !== 'success') {{
        document.getElementById('ts-label').textContent = 'API error: ' + (j.errors?.[0]?.message || '');
        return;
      }}
      for (const [k, v] of Object.entries(j.data)) {{
        const ltp = v.last_price || 0;
        const prev = v.net_change ? (ltp - v.net_change) : (v.ohlc?.close || 0);
        const obj = {{ ltp, prev, tbq: v.total_buy_quantity || 0, tsq: v.total_sell_quantity || 0, vol: v.volume || 0 }};
        [k, k.replace(/:/g,'|'), k.replace(/\\|/g,':')].forEach(x => m[x] = obj);
        if (v.instrument_token) [v.instrument_token, v.instrument_token.replace(/:/g,'|')].forEach(x => m[x] = obj);
      }}
    }} catch(e) {{
      document.getElementById('ts-label').textContent = 'Fetch error: ' + e.message;
      return;
    }}
  }}

  ROWS.forEach(row => {{
    const d = m[row.key] || m['NSE_EQ:'+row.symbol] || m['NSE_EQ|'+row.symbol];
    if (!d || !d.ltp) return;
    const i   = row.idx;
    const pct = row.prev ? (d.ltp - row.prev) / row.prev * 100 : 0;
    const ratio = d.tsq ? d.tbq / d.tsq : 0;
    const sig = aiSignal(ratio, pct, 1);
    state[i].ratio = ratio; state[i].pct = pct; state[i].signal = sig; state[i].ltp = d.ltp; state[i].tbq = d.tbq; state[i].tsq = d.tsq; state[i].vol = d.vol;
    const tr = document.getElementById('row'+i);
    if (tr) tr.style.background = rowBg(sig);
    const cmpEl = document.getElementById('r'+i+'-cmp');
    if (cmpEl) {{ cmpEl.innerHTML = '\\u20b9' + d.ltp.toLocaleString('en-IN',{{minimumFractionDigits:2,maximumFractionDigits:2}}); cmpEl.classList.remove('flash'); void cmpEl.offsetWidth; cmpEl.classList.add('flash'); }}
    const pctEl = document.getElementById('r'+i+'-pct_change');
    if (pctEl) pctEl.innerHTML = '<span style="color:'+pctColor(pct)+';font-weight:600;">'+(pct>0?'▲':pct<0?'▼':'—')+' '+Math.abs(pct).toFixed(2)+'%</span>';
    const tbqEl = document.getElementById('r'+i+'-tbq'); if (tbqEl) tbqEl.textContent = fmtVol(d.tbq);
    const tsqEl = document.getElementById('r'+i+'-tsq'); if (tsqEl) tsqEl.textContent = fmtVol(d.tsq);
    const ratEl = document.getElementById('r'+i+'-tbq_tsq'); if (ratEl) ratEl.innerHTML = '<span style="color:'+ratioColor(ratio)+';font-weight:700;">'+ratio.toFixed(2)+'</span>';
    const volEl = document.getElementById('r'+i+'-volume'); if (volEl) volEl.textContent = fmtVol(d.vol);
    const sigEl = document.getElementById('r'+i+'-signal'); if (sigEl) sigEl.innerHTML = signalBadge(sig);
  }});

  const tbody = document.getElementById('tbody');
  const rows  = Array.from(tbody.querySelectorAll('tr'));
  rows.sort((a, b) => {{
    const ia = parseInt(a.id.replace('row','')), ib = parseInt(b.id.replace('row',''));
    return (state[ib]?.ratio || 0) - (state[ia]?.ratio || 0);
  }});
  rows.forEach(r => tbody.appendChild(r));
  document.getElementById('ts-label').textContent = 'Updated ' + new Date().toLocaleTimeString('en-IN') + ' \\u00b7 {len(df)} stocks \\u00b7 live \\u25cf';
}}

refresh();
setInterval(refresh, 3000);
</script>
</body></html>"""


def render(slot):
    slot.empty()
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
        raw = (
            raw_quotes.get(key) or
            raw_quotes.get(f"NSE_EQ:{symbol}") or
            raw_quotes.get(f"NSE_EQ|{symbol}") or
            {}
        )
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
            "company_name":   row.get("company_name", ""),
            "sector":         row.get("sector", ""),
            "cmp":            round(ltp, 2),
            "pct_change":     round(pct_change, 2),
            "prev_close":     prev_close,
            "volume":         q.get("volume", 0),
            "tbq":            tbq,
            "tsq":            tsq,
            "tbq_tsq":        tbq_tsq,
            "signal":         _ai_signal(tbq_tsq, pct_change, 1.0),
            "instrument_key": key,
        })

    df = pd.DataFrame(records)
    if df.empty:
        st.warning("No live data returned. Market may be closed or token expired.")
        return

    search        = st.session_state.get("live_search", "")
    sector_filter = st.session_state.get("live_sector", "All")
    if search:
        mask = (df["symbol"].str.contains(search.upper(), na=False) |
                df["company_name"].str.contains(search, case=False, na=False))
        df = df[mask]
    if sector_filter != "All" and "sector" in df.columns:
        df = df[df["sector"] == sector_filter]
    df = df.sort_values("tbq_tsq", ascending=False).reset_index(drop=True)

    col1, col2 = st.columns([1, 1])
    with col1:
        st.text_input("Search symbol / company", placeholder="e.g. RELIANCE", key="live_search")
    with col2:
        sector_vals = symbols_df["sector"].dropna().unique().tolist() if "sector" in symbols_df.columns else []
        sectors = ["All"] + sorted([s for s in sector_vals if s])
        st.selectbox("Sector", sectors, key="live_sector")

    token = cfg_get("upstox.access_token", "")
    components.html(_build_table_html(df, time.strftime("%H:%M:%S"), token), height=640, scrolling=False)

    export_df = df.drop(columns=["instrument_key", "prev_close"], errors="ignore")
    st.download_button("Export CSV", export_df.to_csv(index=False).encode(),
                       "live_scanner.csv", "text/csv", key="live_csv")
