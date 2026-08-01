import yaml
import os
from pathlib import Path
from loguru import logger

_config = None

_DEFAULT_CONFIG = {
    "upstox": {"access_token": "", "api_key": "", "api_secret": "", "redirect_uri": ""},
    "ai": {"openai_api_key": "", "enabled": False},
    "alerts": {"telegram_enabled": False, "telegram_bot_token": "", "telegram_chat_id": "", "min_score_alert": 75},
    "scanner": {"vcp_lookback": 20, "rs_lookback": 63, "volume_avg_period": 20, "breakout_volume_multiplier": 1.5, "rsi_period": 14},
    "app": {"refresh_interval": 10, "scanner_refresh": 30, "news_refresh": 60},
    "database": {"sqlite_path": "database/nifty_scanner.db"},
}

def load_config() -> dict:
    global _config
    if _config is not None:
        return _config
    config_path = Path(__file__).parent / "config.yaml"
    if config_path.exists():
        with open(config_path, "r") as f:
            _config = yaml.safe_load(f) or {}
    else:
        import copy
        _config = copy.deepcopy(_DEFAULT_CONFIG)
    # Ensure all top-level keys exist
    for k, v in _DEFAULT_CONFIG.items():
        _config.setdefault(k, v)
    # Override with environment variables if present
    if os.getenv("UPSTOX_ACCESS_TOKEN"):
        _config["upstox"]["access_token"] = os.getenv("UPSTOX_ACCESS_TOKEN")
    if os.getenv("UPSTOX_API_KEY"):
        _config["upstox"]["api_key"] = os.getenv("UPSTOX_API_KEY")
    if os.getenv("UPSTOX_API_SECRET"):
        _config["upstox"]["api_secret"] = os.getenv("UPSTOX_API_SECRET")
    if os.getenv("OPENAI_API_KEY"):
        _config["ai"]["openai_api_key"] = os.getenv("OPENAI_API_KEY")
    if os.getenv("TELEGRAM_BOT_TOKEN"):
        _config["alerts"]["telegram_bot_token"] = os.getenv("TELEGRAM_BOT_TOKEN")
    return _config

def get(key_path: str, default=None):
    cfg = load_config()
    keys = key_path.split(".")
    val = cfg
    for k in keys:
        if isinstance(val, dict):
            val = val.get(k)
        else:
            return default
    return val if val is not None else default
