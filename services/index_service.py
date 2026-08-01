"""
Index service – maps NSE index names to Upstox instrument keys and fetches quotes.
"""
import asyncio
from services.market_data import get_quotes, parse_quote
from loguru import logger

# Upstox instrument keys for major NSE indices
INDEX_KEYS = {
    "NIFTY 50":       "NSE_INDEX|Nifty 50",
    "NIFTY NEXT 50":  "NSE_INDEX|Nifty Next 50",
    "NIFTY 100":      "NSE_INDEX|Nifty 100",
    "NIFTY 200":      "NSE_INDEX|Nifty 200",
    "BANK NIFTY":     "NSE_INDEX|Nifty Bank",
    "NIFTY IT":       "NSE_INDEX|Nifty IT",
    "NIFTY AUTO":     "NSE_INDEX|Nifty Auto",
    "NIFTY FMCG":     "NSE_INDEX|Nifty FMCG",
    "NIFTY PHARMA":   "NSE_INDEX|Nifty Pharma",
    "NIFTY METAL":    "NSE_INDEX|Nifty Metal",
    "NIFTY ENERGY":   "NSE_INDEX|Nifty Energy",
    "NIFTY REALTY":   "NSE_INDEX|Nifty Realty",
    "NIFTY PSU BANK": "NSE_INDEX|Nifty PSU Bank",
    "INDIA VIX":      "NSE_INDEX|India VIX",
}


async def get_all_index_quotes() -> dict:
    """Returns dict of {index_name: parsed_quote}"""
    keys = list(INDEX_KEYS.values())
    raw = await get_quotes(keys)
    result = {}
    for name, key in INDEX_KEYS.items():
        q = raw.get(key, {})
        result[name] = parse_quote(q) if q else {}
    return result
