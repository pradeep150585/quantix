"""
Page 6 – Settings
"""
import streamlit as st
import yaml
from pathlib import Path
from config import load_config
from api.upstox_client import get_client
from components.ui import page_heading

# Get password from config or use default
from config import get
_PASSWORD = get("app.settings_password", "Pragu1020$")

_SETTINGS_CSS = """
<style>
button[aria-label="Show password"],
[data-testid="textInputRootElement"] button,
.stTextInput button { display: none !important; }

input:-webkit-autofill,
input:-webkit-autofill:hover,
input:-webkit-autofill:focus,
input:-webkit-autofill:active {
    -webkit-box-shadow: 0 0 0 1000px #131722 inset !important;
    -webkit-text-fill-color: #d1d4dc !important;
}
</style>
"""


def _save(cfg, config_path):
    with open(config_path, "w") as f:
        yaml.dump(cfg, f, default_flow_style=False)


def render(slot):
    slot.empty()
    st.empty()  # Clear lingering components
    st.markdown(_SETTINGS_CSS, unsafe_allow_html=True)

    if not st.session_state.get("_settings_auth"):
        st.markdown('<div style="height:80px"></div>', unsafe_allow_html=True)
        pwd = st.text_input("Password", type="password",
                            label_visibility="collapsed",
                            placeholder="Enter password",
                            autocomplete="off",
                            key="pwd_gate")
        unlock = st.button("Unlock", use_container_width=True)
        if unlock:
            if pwd == _PASSWORD:
                st.session_state["_settings_auth"] = True
                st.rerun()
            else:
                st.error("Incorrect password.")
                # Debug info (remove in production)
                import streamlit as st
                if st.secrets.get("debug_mode", False):
                    st.caption(f"Expected: {_PASSWORD}, Got: {pwd}")
        return

    cfg = load_config()
    config_path = Path(__file__).parent.parent / "config" / "config.yaml"

    tabs = st.tabs(["API Keys", "Alerts", "Scanner", "Display", "Export"])

    with tabs[0]:
        st.markdown('<div style="font-size:.78rem;font-weight:600;color:#d1d4dc;margin-bottom:12px;">Upstox API Credentials</div>', unsafe_allow_html=True)
        api_key      = st.text_input("API Key",      value=cfg.get("upstox", {}).get("api_key", ""),      type="password", key="api_key_input")
        api_secret   = st.text_input("API Secret",   value=cfg.get("upstox", {}).get("api_secret", ""),   type="password", key="api_secret_input")
        access_token = st.text_input("Access Token", value=cfg.get("upstox", {}).get("access_token", ""), type="password", key="access_token_input",
                                     help="Paste your Upstox access token here. Tokens expire daily.")

        st.markdown('<div style="font-size:.78rem;font-weight:600;color:#d1d4dc;margin:16px 0 8px;">AI Configuration</div>', unsafe_allow_html=True)
        openai_key = st.text_input("OpenAI API Key", value=cfg.get("ai", {}).get("openai_api_key", ""), type="password", key="openai_input")
        ai_enabled = st.checkbox("Enable AI Analysis", value=cfg.get("ai", {}).get("enabled", False))

        if st.button("Save API Credentials"):
            cfg["upstox"]["api_key"]      = api_key
            cfg["upstox"]["api_secret"]   = api_secret
            cfg["upstox"]["access_token"] = access_token
            cfg["ai"]["openai_api_key"]   = openai_key
            cfg["ai"]["enabled"]          = ai_enabled
            _save(cfg, config_path)
            c = get_client()
            c.api_key      = api_key
            c.api_secret   = api_secret
            c.access_token = access_token
            st.cache_data.clear()
            st.success("API credentials saved!")

    with tabs[1]:
        st.markdown('<div style="font-size:.78rem;font-weight:600;color:#d1d4dc;margin-bottom:12px;">Telegram Alerts</div>', unsafe_allow_html=True)
        tg_enabled = st.checkbox("Enable Telegram", value=cfg.get("alerts", {}).get("telegram_enabled", False))
        tg_token   = st.text_input("Bot Token", value=cfg.get("alerts", {}).get("telegram_bot_token", ""), type="password", key="tg_token_input")
        tg_chat    = st.text_input("Chat ID",   value=cfg.get("alerts", {}).get("telegram_chat_id", ""),   key="tg_chat_input")
        min_score  = st.slider("Min Score for Alert", 0, 100, cfg.get("alerts", {}).get("min_score_alert", 75))

        if st.button("Save Alert Settings"):
            cfg["alerts"]["telegram_enabled"]   = tg_enabled
            cfg["alerts"]["telegram_bot_token"] = tg_token
            cfg["alerts"]["telegram_chat_id"]   = tg_chat
            cfg["alerts"]["min_score_alert"]    = min_score
            _save(cfg, config_path)
            st.success("Alert settings saved!")

    with tabs[2]:
        st.markdown('<div style="font-size:.78rem;font-weight:600;color:#d1d4dc;margin-bottom:12px;">Scanner Parameters</div>', unsafe_allow_html=True)
        sc = cfg.get("scanner", {})
        vcp_lb     = st.slider("VCP Lookback (bars)",        5,   50,  sc.get("vcp_lookback", 20))
        rs_lb      = st.slider("RS Lookback (bars)",        20,  252,  sc.get("rs_lookback", 63))
        vol_period = st.slider("Volume Avg Period",          5,   50,  sc.get("volume_avg_period", 20))
        vol_mult   = st.slider("Breakout Volume Multiplier", 1.0, 3.0, sc.get("breakout_volume_multiplier", 1.5), 0.1)
        rsi_period = st.slider("RSI Period",                 5,   30,  sc.get("rsi_period", 14))

        if st.button("Save Scanner Settings"):
            cfg["scanner"].update({
                "vcp_lookback": vcp_lb, "rs_lookback": rs_lb,
                "volume_avg_period": vol_period,
                "breakout_volume_multiplier": vol_mult,
                "rsi_period": rsi_period,
            })
            _save(cfg, config_path)
            st.success("Scanner settings saved!")

    with tabs[3]:
        st.markdown('<div style="font-size:.78rem;font-weight:600;color:#d1d4dc;margin-bottom:12px;">Display Settings</div>', unsafe_allow_html=True)
        refresh         = st.slider("Dashboard Refresh (seconds)",  5,  60, cfg.get("app", {}).get("refresh_interval", 10))
        scanner_refresh = st.slider("Scanner Refresh (seconds)",   30, 300, cfg.get("app", {}).get("scanner_refresh", 30))
        news_refresh    = st.slider("News Refresh (seconds)",      30, 300, cfg.get("app", {}).get("news_refresh", 60))

        if st.button("Save Display Settings"):
            cfg["app"]["refresh_interval"] = refresh
            cfg["app"]["scanner_refresh"]  = scanner_refresh
            cfg["app"]["news_refresh"]     = news_refresh
            _save(cfg, config_path)
            st.success("Display settings saved!")

    with tabs[4]:
        st.markdown('<div style="font-size:.78rem;font-weight:600;color:#d1d4dc;margin-bottom:12px;">Database</div>', unsafe_allow_html=True)
        st.info(f"SQLite path: `{cfg.get('database', {}).get('sqlite_path', 'database/nifty_scanner.db')}`")
        if st.button("Clear Scan Cache"):
            st.cache_data.clear()
            st.success("Cache cleared!")

    st.markdown("<hr>", unsafe_allow_html=True)
    if st.button("Lock Settings"):
        st.session_state["_settings_auth"] = False
        st.rerun()
