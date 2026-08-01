import yaml
import os
from pathlib import Path
from loguru import logger

_config = None

def load_config() -> dict:
    global _config
    if _config is not None:
        return _config
    config_path = Path(__file__).parent / "config.yaml"
    with open(config_path, "r") as f:
        _config = yaml.safe_load(f)
    # Override with environment variables if present
    if os.getenv("UPSTOX_ACCESS_TOKEN"):
        _config["upstox"]["access_token"] = os.getenv("UPSTOX_ACCESS_TOKEN")
    if os.getenv("UPSTOX_API_KEY"):
        _config["upstox"]["api_key"] = os.getenv("UPSTOX_API_KEY")
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
