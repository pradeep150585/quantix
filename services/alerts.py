"""
Alert service – Telegram notifications.
"""
import asyncio
import httpx
from loguru import logger
from config import get


async def send_telegram(message: str):
    if not get("alerts.telegram_enabled", False):
        return
    token = get("alerts.telegram_bot_token", "")
    chat_id = get("alerts.telegram_chat_id", "")
    if not token or not chat_id:
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(url, json={"chat_id": chat_id, "text": message, "parse_mode": "HTML"})
    except Exception as e:
        logger.warning(f"Telegram send failed: {e}")


async def alert_strategy_match(symbol: str, strategy: str, score: float):
    min_score = get("alerts.min_score_alert", 75)
    if score < min_score:
        return
    msg = f"🚀 <b>{symbol}</b> matched <b>{strategy}</b> with score <b>{score:.0f}%</b>"
    await send_telegram(msg)
