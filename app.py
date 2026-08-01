"""
Quantix – Nifty 200 Market Intelligence Platform
"""
import streamlit as st
from database import init_db
from utils.logger import setup_logger
import time

st.set_page_config(
    page_title="Quantix – Market Intelligence",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

setup_logger()
init_db()

if "app_start_time" not in st.session_state:
    st.session_state.app_start_time = time.time()
    st.cache_data.clear()
    st.cache_resource.clear()

PAGES = [
    ("Dashboard",        "dashboard"),
    ("Live Scanner",     "live_scanner"),
    ("News & Sentiment", "news_sentiment"),
    ("Strategies",       "strategies_page"),
    ("AI Picks",         "ai_picks"),
    ("Settings",         "settings"),
]

if "page" not in st.session_state:
    st.session_state.page = "dashboard"

cache_buster = int(time.time() / 10)

st.markdown(f"""
<style>
/* Cache buster: {cache_buster} */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

*, *::before, *::after {{ box-sizing: border-box; }}
html, body, [class*="css"] {{
    font-family: 'Inter', system-ui, -apple-system, sans-serif;
    background: #0b0e17;
    color: #d1d4dc;
}}
.stApp {{ background: #0b0e17; }}
[data-testid="stSidebar"]  {{ display: none !important; }}
#MainMenu, footer, header  {{ visibility: hidden; }}
[data-testid="stDecoration"], [data-testid="stToolbar"] {{ display: none !important; }}
.stDeployButton {{ display: none !important; }}

/* ── Combined header + nav bar ── */
.quantix-header {{
    background: #131722;
    border-bottom: 1px solid #1e2433;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 20px;
    height: 52px;
    width: 100%;
}}
.quantix-logo {{
    font-family: 'Inter', sans-serif;
    font-size: 1.15rem;
    font-weight: 800;
    letter-spacing: .06em;
    color: #ffffff;
    text-transform: uppercase;
    display: flex;
    align-items: center;
    gap: 7px;
}}
.quantix-logo-dot {{
    width: 7px; height: 7px;
    border-radius: 50%;
    background: #00c853;
    box-shadow: 0 0 8px #00c85388;
    display: inline-block;
}}
.quantix-status {{
    display: flex;
    align-items: center;
    gap: 5px;
    font-size: .65rem;
    color: #4a5568;
    margin-left: auto;
}}
.dot-on  {{ display:inline-block;width:6px;height:6px;border-radius:50%;background:#00c853;box-shadow:0 0 6px #00c85366; }}
.dot-off {{ display:inline-block;width:6px;height:6px;border-radius:50%;background:#ef4444; }}

/* ── Streamlit nav buttons — always on top of loading overlay ── */
div[data-testid="stHorizontalBlock"]:first-of-type {{
    position: relative;
    z-index: 9999 !important;
    background: #0b0e17;
}}

/* ── Page content ── */
.block-container {{
    padding: 0 16px 20px !important;
    max-width: 100% !important;
    background: #0b0e17 !important;
}}

/* ── Page heading ── */
.page-heading {{
    font-family: 'Inter', sans-serif;
    font-size: 1rem;
    font-weight: 700;
    color: #ffffff;
    letter-spacing: .02em;
    padding: 18px 0 4px;
    margin-bottom: 4px;
}}
.page-heading-line {{
    width: 32px; height: 2px;
    background: #00c853;
    margin: 0 0 16px;
    border-radius: 2px;
}}

/* ── Section header ── */
.section-header {{
    font-family: 'Inter', sans-serif;
    font-size: .72rem; font-weight: 600; color: #9ca3af;
    padding-bottom: 8px; margin-bottom: 12px;
    border-bottom: 1px solid #1e2433;
    letter-spacing: .06em;
    text-transform: uppercase;
}}

/* ── Metric cards ── */
[data-testid="stMetric"] {{
    background: #131722;
    border: 1px solid #1e2433;
    border-radius: 6px;
    padding: 14px 16px !important;
    box-shadow: none;
}}
[data-testid="stMetricLabel"] {{
    color: #6b7280 !important;
    font-size: .62rem !important;
    text-transform: uppercase;
    letter-spacing: .08em;
    font-weight: 500 !important;
}}
[data-testid="stMetricValue"] {{
    color: #ffffff !important;
    font-size: 1.1rem !important;
    font-weight: 700 !important;
    font-family: 'Inter', sans-serif !important;
}}
[data-testid="stMetricDelta"] {{ font-size: .68rem !important; }}

/* ── Inputs — uniform height ── */
.stTextInput input,
.stSelectbox > div > div,
.stTextArea textarea {{
    background: #131722 !important;
    border: 1px solid #2d3748 !important;
    border-radius: 4px !important;
    color: #d1d4dc !important;
    font-size: .78rem !important;
    font-family: 'Inter', sans-serif !important;
    box-shadow: none !important;
    padding: 9px 12px !important;
    height: 40px !important;
    min-height: 40px !important;
}}
.stTextInput input:focus, .stTextArea textarea:focus {{
    border-color: #00c853 !important;
    box-shadow: 0 0 0 2px rgba(0,200,83,.12) !important;
    outline: none !important;
}}
.stTextInput input[type="password"] {{
    background: #131722 !important;
    border: 1px solid #2d3748 !important;
    color: #d1d4dc !important;
    height: 40px !important;
}}
.stTextInput input[type="password"]:focus {{
    border-color: #00c853 !important;
    box-shadow: 0 0 0 2px rgba(0,200,83,.12) !important;
}}
input:-webkit-autofill,
input:-webkit-autofill:hover,
input:-webkit-autofill:focus {{
    -webkit-box-shadow: 0 0 0 1000px #131722 inset !important;
    -webkit-text-fill-color: #d1d4dc !important;
}}
[data-baseweb="popover"] *, [data-baseweb="menu"] *,
[role="listbox"] *, [role="option"] * {{
    background: #1a2035 !important;
    color: #d1d4dc !important;
}}
[role="option"]:hover, [data-highlighted="true"] {{
    background: #1e2d3d !important;
    color: #ffffff !important;
}}
.stSelectbox label, .stTextInput label, .stCheckbox label, .stTextArea label {{
    color: #6b7280 !important;
    font-size: .62rem !important;
    text-transform: uppercase;
    letter-spacing: .06em;
    font-weight: 500 !important;
}}

/* ── Buttons ── */
.stButton > button {{
    background: #00c853 !important;
    color: #000000 !important;
    border: none !important;
    border-radius: 4px !important;
    font-size: .72rem !important;
    font-weight: 600 !important;
    padding: 9px 18px !important;
    letter-spacing: .02em !important;
    box-shadow: none !important;
    transition: background .15s !important;
    min-height: 38px !important;
    font-family: 'Inter', sans-serif !important;
}}
.stButton > button:hover {{ background: #00e676 !important; }}
.stButton > button[kind="secondary"] {{
    background: #1e2433 !important;
    color: #d1d4dc !important;
    border: 1px solid #2d3748 !important;
}}
.stButton > button[kind="secondary"]:hover {{
    background: #252d3d !important;
    border-color: #00c853 !important;
    color: #ffffff !important;
}}
.stDownloadButton > button {{
    background: #1e2433 !important;
    color: #d1d4dc !important;
    border: 1px solid #2d3748 !important;
    border-radius: 4px !important;
    font-size: .7rem !important;
    font-weight: 500 !important;
    min-height: 38px !important;
    font-family: 'Inter', sans-serif !important;
}}
.stDownloadButton > button:hover {{
    background: #252d3d !important;
    border-color: #00c853 !important;
    color: #ffffff !important;
}}

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] {{
    background: transparent;
    border-bottom: 1px solid #1e2433;
    gap: 0; padding: 0;
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
}}
.stTabs [data-baseweb="tab"] {{
    background: transparent !important;
    color: #6b7280 !important;
    border-radius: 0 !important;
    font-size: .72rem !important;
    font-weight: 500 !important;
    padding: 8px 16px !important;
    border-bottom: 2px solid transparent !important;
    font-family: 'Inter', sans-serif !important;
    white-space: nowrap;
    flex-shrink: 0;
}}
.stTabs [aria-selected="true"] {{
    color: #ffffff !important;
    border-bottom-color: #00c853 !important;
    font-weight: 600 !important;
}}

/* ── Badges ── */
.badge {{ display:inline-block;padding:2px 7px;border-radius:3px;font-size:.62rem;font-weight:600;margin:2px 2px 2px 0;line-height:1.4; }}
.badge-green  {{ background:rgba(0,200,83,.12);color:#00c853;border:1px solid rgba(0,200,83,.25); }}
.badge-blue   {{ background:rgba(59,130,246,.12);color:#60a5fa;border:1px solid rgba(59,130,246,.25); }}
.badge-yellow {{ background:rgba(245,158,11,.12);color:#fbbf24;border:1px solid rgba(245,158,11,.25); }}
.badge-red    {{ background:rgba(239,68,68,.12);color:#f87171;border:1px solid rgba(239,68,68,.25); }}
.badge-purple {{ background:rgba(139,92,246,.12);color:#a78bfa;border:1px solid rgba(139,92,246,.25); }}

/* ── Vertical block ── */
[data-testid="stVerticalBlock"] {{
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
}}

/* ── Misc ── */
hr {{ border-color: #1e2433 !important; margin: 14px 0 !important; }}
.positive {{ color: #00c853 !important; }}
.negative {{ color: #ef4444 !important; }}
.neutral  {{ color: #6b7280 !important; }}
::-webkit-scrollbar {{ width: 4px; height: 4px; }}
::-webkit-scrollbar-track {{ background: #0b0e17; }}
::-webkit-scrollbar-thumb {{ background: #2d3748; border-radius: 4px; }}
::-webkit-scrollbar-thumb:hover {{ background: #4a5568; }}
[data-testid="stAlert"] {{ border-radius: 4px !important; font-size: .76rem !important; padding: 10px 14px !important; }}
.stSpinner > div {{ border-top-color: #00c853 !important; }}

/* ── Slider ── */
[data-testid="stSlider"] label p {{
    color: #9ca3af !important;
    font-size: .72rem !important;
    font-weight: 500 !important;
    text-transform: none !important;
    letter-spacing: 0 !important;
}}

/* ── Checkbox ── */
[data-testid="stCheckbox"] label {{
    color: #d1d4dc !important;
    font-size: .78rem !important;
    text-transform: none !important;
    letter-spacing: 0 !important;
    font-weight: 400 !important;
}}

/* ── Mobile ── */
@media (max-width: 900px) {{
    .quantix-logo {{ min-width: 90px; font-size: 1rem; }}
    .quantix-status {{ min-width: 80px; font-size: .6rem; }}
}}
@media (max-width: 600px) {{
    .quantix-header {{ padding: 0 10px; }}
    .quantix-logo {{ font-size: .85rem; min-width: 70px; }}
    .quantix-status {{ display: none; }}
    .block-container {{ padding: 0 6px 10px !important; }}
}}
</style>
""", unsafe_allow_html=True)

from api.upstox_client import get_client
from datetime import datetime

client  = get_client()
is_live = bool(client.access_token)
dot_cls = "dot-on" if is_live else "dot-off"
now_str = datetime.now().strftime("%H:%M")
active  = st.session_state.page

st.markdown(f"""
<div class="quantix-header">
  <div class="quantix-logo">
    <span class="quantix-logo-dot"></span>Quantix
  </div>
  <div class="quantix-status">
    <span class="{dot_cls}"></span>
    <span style="color:#9ca3af;">{"Live" if is_live else "Offline"}</span>
    <span style="color:#2d3748;margin:0 3px;">|</span>
    <span style="color:#6b7280;">{now_str}</span>
  </div>
</div>
<div style="height:10px;background:#0b0e17;"></div>
""", unsafe_allow_html=True)

# nav buttons — visible green buttons for routing
nav_cols = st.columns(len(PAGES))
for i, (label, key) in enumerate(PAGES):
    with nav_cols[i]:
        if st.button(label, key=f"nav_{key}", use_container_width=True,
                     type="primary" if active == key else "secondary"):
            st.session_state.page = key
            st.rerun()

page_module = st.session_state.page

# Single slot that holds ALL page content — replacing it clears old iframes too
if "page_slot" not in st.session_state:
    st.session_state.page_slot = None

page_slot = st.empty()

if page_module == "dashboard":
    from pages.dashboard import render
elif page_module == "live_scanner":
    from pages.live_scanner import render
elif page_module == "news_sentiment":
    from pages.news_sentiment import render
elif page_module == "strategies_page":
    from pages.strategies_page import render
elif page_module == "ai_picks":
    from pages.ai_picks import render
elif page_module == "settings":
    from pages.settings import render
else:
    render = None

if render:
    render(page_slot)
