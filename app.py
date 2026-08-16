"""
Quantix – Nifty 200 Market Intelligence Platform
"""
import sys
import traceback
import time
import streamlit as st

st.set_page_config(
    page_title="Quantix – Market Intelligence",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

try:
    from database import init_db
    from utils.logger import setup_logger
    setup_logger()
    init_db()
except Exception as _boot_err:
    st.error(f"**Boot error:** {_boot_err}")
    st.code(traceback.format_exc())
    st.stop()

if "app_start_time" not in st.session_state:
    st.session_state.app_start_time = time.time()

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
if "_last_page" not in st.session_state:
    st.session_state._last_page = None

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');
*,*::before,*::after{box-sizing:border-box}
html,body,[class*="css"]{font-family:'Inter',system-ui,sans-serif;background:#0b0e17;color:#d1d4dc}
.stApp{background:#0b0e17}
[data-testid="stSidebar"],#MainMenu,footer,header,[data-testid="stDecoration"],[data-testid="stToolbar"],.stDeployButton{display:none!important}
.quantix-header{background:#131722;border-bottom:1px solid #1e2433;display:flex;align-items:center;justify-content:space-between;padding:0 12px;height:48px;width:100%}
.quantix-logo{font-size:1rem;font-weight:700;letter-spacing:.04em;color:#fff;text-transform:uppercase;display:flex;align-items:center;gap:5px}
.quantix-logo-dot{width:5px;height:5px;border-radius:50%;background:#00c853;display:inline-block}
.quantix-status{display:flex;align-items:center;gap:4px;font-size:.6rem;color:#4a5568}
.dot-on{display:inline-block;width:5px;height:5px;border-radius:50%;background:#00c853}
.dot-off{display:inline-block;width:5px;height:5px;border-radius:50%;background:#ef4444}
.block-container{padding:0 10px 12px!important;max-width:100%!important;background:#0b0e17!important}
.stTextInput input,.stSelectbox>div>div,.stTextArea textarea{background:#131722!important;border:1px solid #2d3748!important;border-radius:3px!important;color:#d1d4dc!important;font-size:.75rem!important;padding:8px 10px!important;height:36px!important}
.stTextInput input:focus,.stTextArea textarea:focus{border-color:#00c853!important;box-shadow:0 0 0 1px rgba(0,200,83,.2)!important}
.stButton>button{background:#00c853!important;color:#000!important;border:none!important;border-radius:3px!important;font-size:.7rem!important;font-weight:600!important;padding:7px 14px!important;min-height:36px!important}
.stButton>button:hover{background:#00e676!important}
.stButton>button[kind="secondary"]{background:#1e2433!important;color:#d1d4dc!important;border:1px solid #2d3748!important}
.stButton>button[kind="secondary"]:hover{background:#252d3d!important;border-color:#00c853!important}
.stTabs [data-baseweb="tab-list"]{background:transparent;border-bottom:1px solid #1e2433;gap:0;padding:0}
.stTabs [data-baseweb="tab"]{background:transparent!important;color:#6b7280!important;border-radius:0!important;font-size:.68rem!important;font-weight:500!important;padding:6px 12px!important;border-bottom:2px solid transparent!important}
.stTabs [aria-selected="true"]{color:#fff!important;border-bottom-color:#00c853!important}
[data-testid="stMetric"]{background:#131722;border:1px solid #1e2433;border-radius:4px;padding:10px 12px!important}
[data-testid="stMetricLabel"]{color:#6b7280!important;font-size:.58rem!important;font-weight:500!important}
[data-testid="stMetricValue"]{color:#fff!important;font-size:1rem!important;font-weight:700!important}
::-webkit-scrollbar{width:3px;height:3px}
::-webkit-scrollbar-track{background:#0b0e17}
::-webkit-scrollbar-thumb{background:#2d3748;border-radius:2px}
hr{border-color:#1e2433!important;margin:10px 0!important}
[data-testid="stAlert"]{border-radius:3px!important;font-size:.72rem!important;padding:8px 10px!important}
@media(max-width:768px){.quantix-header{padding:0 8px;height:44px}.quantix-logo{font-size:.9rem}.quantix-status{display:none}.block-container{padding:0 6px 8px!important}.stTabs [data-baseweb="tab"]{padding:4px 8px!important;font-size:.65rem!important}}
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

# Recreate page_slot each time to ensure clean state
page_slot = st.empty()

# Track page changes
if st.session_state._last_page != page_module:
    st.session_state._last_page = page_module

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
