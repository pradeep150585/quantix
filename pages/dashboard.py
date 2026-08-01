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
        loop = asyncio.new_event_loop()
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@st.cache_data(ttl=86400, show_spinner=False)
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
    access_token = get("upstox.access_token", "")
    index_names = [n for n in INDEX_KEYS if n not in _EXCLUDE]

    tiles_config = []
    for name in index_names:
        q = quotes.get(name, {})
        ltp = q.get("ltp", 0)
        prev = q.get("prev_close", 0)
        rsi_val, macd_hist = indicators_map.get(name, (50, 0))
        tiles_config.append({
            "name":      name,
            "key":       INDEX_KEYS[name],
            "ltp":       ltp,
            "prev":      prev,
            "rsi":       rsi_val,
            "rsi_c":     _rsi_color(rsi_val),
            "macd_hist": macd_hist,
        })

    vix_q = quotes.get("INDIA VIX", {})
    vix_ltp = vix_q.get("ltp", 0)
    vix_key = INDEX_KEYS.get("INDIA VIX", "")
    nifty_key = INDEX_KEYS.get("NIFTY 50", "")
    all_keys = list(INDEX_KEYS.values())

    return f"""<!DOCTYPE html><html><head>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
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
@keyframes pulse{{0%{{opacity:.5}}50%{{opacity:1}}100%{{opacity:1}}}}
.pulse{{animation:pulse .4s ease}}
@media(max-width:600px){{.grid{{grid-template-columns:repeat(2,1fr)}}.hgrid{{grid-template-columns:repeat(auto-fill,minmax(110px,1fr))}}.mval{{font-size:1rem}}}}
</style>
</head><body>
<div class="grid">
  <div class="mcard"><div class="mlabel">NIFTY 50</div>
    <div class="mval" id="s-nifty">—</div>
    <div class="mdelta" id="s-nifty-d" style="color:#6b7280">—</div></div>
  <div class="mcard"><div class="mlabel">India VIX</div>
    <div class="mval" id="s-vix">{vix_ltp:.2f}</div>
    <div class="mdelta" style="color:#6b7280">Volatility Index</div></div>
  <div class="mcard"><div class="mlabel">Market Sentiment</div>
    <div class="mval" id="s-sent" style="color:#6b7280">—</div>
    <div class="mdelta" style="color:#6b7280">Based on indices</div></div>
  <div class="mcard"><div class="mlabel">Advance / Decline</div>
    <div class="mval" id="s-adv">— / —</div>
    <div class="mdelta" style="color:#6b7280">Indices breadth</div></div>
</div>
<div class="htitle"><span class="live-dot"></span> Indices Heatmap</div>
<div class="hgrid" id="hgrid"></div>
<div class="ts" id="ts">Connecting...</div>
<script>
const TOKEN = {json.dumps(access_token)};
const ALL_KEYS = {json.dumps(all_keys)};
const VIX_KEY = {json.dumps(vix_key)};
const NIFTY_KEY = {json.dumps(nifty_key)};
const TILES = {json.dumps(tiles_config)};

function bg(p){{return p>=2?"#0d2b1a":p>=.5?"#0a1f14":p>=0?"#0c1a10":p>=-.5?"#1f0d0d":p>=-2?"#2b0d0d":"#3b0d0d"}}
function fg(p){{return p>=0?"#00c853":"#ef4444"}}
function fmt(n){{return n.toLocaleString('en-IN',{{minimumFractionDigits:2,maximumFractionDigits:2}})}}

(function buildTiles(){{
  const g = document.getElementById('hgrid');
  TILES.forEach(t => {{
    const pct = t.prev ? (t.ltp - t.prev) / t.prev * 100 : 0;
    const arr = pct>0?"▲":pct<0?"▼":"—";
    const mc = t.macd_hist>0?"#00c853":"#ef4444";
    const ma = t.macd_hist>0?"▲":"▼";
    const id = t.key.replace(/[|:]/g,'_');
    const div = document.createElement('div');
    div.innerHTML = `<div class="tile" id="tile-${{id}}" style="border-color:${{pct>=0?'#1a3a2a':'#3a1a1a'}}">
      <div class="tname">${{t.name}}</div>
      <div class="tltp" id="ltp-${{id}}">${{t.ltp ? fmt(t.ltp) : '—'}}</div>
      <div class="tchg" style="color:${{fg(pct)}}" id="chg-${{id}}">${{t.ltp ? arr+' '+Math.abs(pct).toFixed(2)+'%' : '—'}}</div>
      <div class="tind"><span style="color:${{t.rsi_c}}">RSI ${{t.rsi}}</span><span style="color:${{mc}}">MACD ${{ma}}</span></div>
    </div>`;
    g.appendChild(div);
  }});
}})();

async function refresh() {{
  try {{
    const url = 'https://api.upstox.com/v2/market-quote/quotes?instrument_key=' + encodeURIComponent(ALL_KEYS.join(','));
    const resp = await fetch(url, {{headers: {{Authorization: 'Bearer ' + TOKEN, Accept: 'application/json'}}}});
    const json = await resp.json();
    if (json.status !== 'success') {{
      document.getElementById('ts').textContent = 'API error: ' + (json.errors?.[0]?.message || JSON.stringify(json).slice(0,80));
      return;
    }}
    const m = {{}};
    for (const [k, v] of Object.entries(json.data)) {{
      const obj = {{ ltp: v.last_price || 0, prev: (v.last_price || 0) - (v.net_change || 0) }};
      [k, k.replace(/:/g,'|'), k.replace(/\\|/g,':')].forEach(x => m[x] = obj);
      if (v.instrument_token) [v.instrument_token, v.instrument_token.replace(/:/g,'|')].forEach(x => m[x] = obj);
    }}
    let adv = 0, dec = 0;
    TILES.forEach(t => {{
      const d = m[t.key]; if (!d || !d.ltp) return;
      const pct = d.prev ? (d.ltp - d.prev) / d.prev * 100 : 0;
      const arr = pct>0?"▲":pct<0?"▼":"—";
      const id = t.key.replace(/[|:]/g,'_');
      const tile = document.getElementById('tile-'+id);
      const ltpEl = document.getElementById('ltp-'+id);
      const chgEl = document.getElementById('chg-'+id);
      if (tile) {{ tile.style.borderColor = pct>=0?'#1a3a2a':'#3a1a1a'; }}
      if (ltpEl) {{ ltpEl.textContent = fmt(d.ltp); ltpEl.classList.remove('pulse'); void ltpEl.offsetWidth; ltpEl.classList.add('pulse'); }}
      if (chgEl) {{ chgEl.style.color = fg(pct); chgEl.innerHTML = arr+' '+Math.abs(pct).toFixed(2)+'% <span style="color:#4a5568;font-size:.58rem;">'+(d.ltp-d.prev>=0?'+':'')+(d.ltp-d.prev).toFixed(2)+'</span>'; }}
      if (pct > 0) adv++; else if (pct < 0) dec++;
    }});
    const nf = m[NIFTY_KEY];
    if (nf) {{
      const np = nf.prev ? (nf.ltp - nf.prev) / nf.prev * 100 : 0;
      document.getElementById('s-nifty').textContent = fmt(nf.ltp);
      const nd = document.getElementById('s-nifty-d');
      nd.style.color = fg(np);
      nd.innerHTML = (np>=0?'▲':'▼') + ' ' + Math.abs(np).toFixed(2) + '%';
    }}
    const vx = m[VIX_KEY];
    if (vx) document.getElementById('s-vix').textContent = vx.ltp.toFixed(2);
    const tot = adv + dec || 1, ratio = adv / tot;
    const sent = ratio > 0.6 ? 'Bullish' : ratio < 0.4 ? 'Bearish' : 'Neutral';
    const sc = sent === 'Bullish' ? '#00c853' : sent === 'Bearish' ? '#ef4444' : '#6b7280';
    const se = document.getElementById('s-sent'); se.textContent = sent; se.style.color = sc;
    document.getElementById('s-adv').innerHTML = `<span style="color:#00c853">${{adv}}</span> / <span style="color:#ef4444">${{dec}}</span>`;
    document.getElementById('ts').textContent = 'Updated ' + new Date().toLocaleTimeString('en-IN') + ' · live ●';
  }} catch(e) {{
    document.getElementById('ts').textContent = 'Error: ' + e.message;
  }}
}}

refresh();
setInterval(refresh, 3000);
</script></body></html>"""


def render(slot):
    slot.empty()
    slot.markdown(loading_html("Loading market data…"), unsafe_allow_html=True)

    quotes = _run(get_all_index_quotes())
    indicators_map = {}
    for name in [n for n in INDEX_KEYS if n not in _EXCLUDE]:
        key = INDEX_KEYS.get(name, "")
        if key:
            try:
                indicators_map[name] = _fetch_indicators(key)
            except Exception:
                indicators_map[name] = (50, 0)

    slot.empty()
    components.html(_build_dashboard_html(quotes, indicators_map), height=620, scrolling=True)
