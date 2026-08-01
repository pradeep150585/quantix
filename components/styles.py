# Legacy CSS reference — main styles are injected in app.py
# Kept for backward compatibility with any direct imports

LIGHT_THEME_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

html, body, [class*="css"] {
    font-family: 'Inter', system-ui, -apple-system, sans-serif;
    background-color: #0b0e17;
    color: #d1d4dc;
}
.stApp { background-color: #0b0e17; }
.block-container { padding: 0 !important; max-width: 100% !important; }

[data-testid="stSidebar"] { display: none !important; }
#MainMenu, footer, header { visibility: hidden; }
[data-testid="stDecoration"] { display: none; }
[data-testid="stToolbar"] { display: none !important; }
.stDeployButton { display: none !important; }

.page-content { padding: 20px 24px; min-height: calc(100vh - 52px); }

.section-header {
    font-size: .72rem; font-weight: 600; color: #9ca3af;
    padding-bottom: 8px; margin-bottom: 12px;
    border-bottom: 1px solid #1e2433;
    letter-spacing: .06em; text-transform: uppercase;
}

[data-testid="stMetric"] {
    background: #131722; border: 1px solid #1e2433;
    border-radius: 6px; padding: 14px 16px !important;
}
[data-testid="stMetricLabel"] { color: #6b7280 !important; font-size: .62rem !important; text-transform: uppercase; letter-spacing: .08em; font-weight: 500 !important; }
[data-testid="stMetricValue"] { color: #ffffff !important; font-size: 1.1rem !important; font-weight: 700 !important; }
[data-testid="stMetricDelta"] { font-size: .68rem !important; }

.badge { display:inline-block;padding:2px 7px;border-radius:3px;font-size:.62rem;font-weight:600;margin:2px 2px 2px 0;line-height:1.4; }
.badge-green  { background:rgba(0,200,83,.12);color:#00c853;border:1px solid rgba(0,200,83,.25); }
.badge-blue   { background:rgba(96,165,250,.12);color:#60a5fa;border:1px solid rgba(96,165,250,.25); }
.badge-yellow { background:rgba(245,158,11,.12);color:#fbbf24;border:1px solid rgba(245,158,11,.25); }
.badge-red    { background:rgba(239,68,68,.12);color:#f87171;border:1px solid rgba(239,68,68,.25); }
.badge-purple { background:rgba(139,92,246,.12);color:#a78bfa;border:1px solid rgba(139,92,246,.25); }

.stTextInput input, .stSelectbox > div > div {
    background: #131722 !important; border: 1px solid #2d3748 !important;
    border-radius: 4px !important; color: #d1d4dc !important;
    font-size: .78rem !important;
}
.stTextInput input:focus { border-color: #00c853 !important; box-shadow: 0 0 0 2px rgba(0,200,83,.12) !important; }

.stButton > button {
    background: #00c853 !important; color: #000000 !important;
    border: none !important; border-radius: 4px !important;
    font-size: .72rem !important; font-weight: 600 !important;
    padding: 9px 18px !important;
}
.stButton > button:hover { background: #00e676 !important; }

.stTabs [data-baseweb="tab-list"] { background: transparent; border-bottom: 1px solid #1e2433; gap: 0; padding: 0; }
.stTabs [data-baseweb="tab"] { background: transparent !important; color: #6b7280 !important; border-radius: 0 !important; font-size: .72rem !important; font-weight: 500 !important; padding: 8px 16px !important; border-bottom: 2px solid transparent !important; }
.stTabs [aria-selected="true"] { color: #ffffff !important; border-bottom-color: #00c853 !important; font-weight: 600 !important; }

hr { border-color: #1e2433 !important; margin: 14px 0 !important; }
.positive { color: #00c853 !important; }
.negative { color: #ef4444 !important; }
.neutral  { color: #6b7280 !important; }
::-webkit-scrollbar { width: 4px; height: 4px; }
::-webkit-scrollbar-track { background: #0b0e17; }
::-webkit-scrollbar-thumb { background: #2d3748; border-radius: 4px; }
.stSpinner > div { border-top-color: #00c853 !important; }
[data-testid="stAlert"] { border-radius: 4px !important; font-size: .76rem !important; }
</style>
"""
