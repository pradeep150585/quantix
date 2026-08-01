import httpx
import asyncio
import time
import hashlib
import hmac
import base64
from loguru import logger
from config import get
from typing import Optional

class UpstoxClient:
    BASE_URL = "https://api.upstox.com/v2"
    AUTH_URL = "https://api.upstox.com/v2/login/authorization/dialog"
    TOKEN_URL = "https://api.upstox.com/v2/login/authorization/token"

    def __init__(self):
        self.access_token = get("upstox.access_token", "")
        self.api_key = get("upstox.api_key", "")
        self.api_secret = get("upstox.api_secret", "")
        self._latency_ms: float = 0.0
        self._connected: bool = False

    @property
    def headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    @property
    def latency_ms(self) -> float:
        return self._latency_ms

    @property
    def is_connected(self) -> bool:
        return self._connected

    async def get_token_from_credentials(self, auth_code: str) -> bool:
        """
        Exchange authorization code for access token.
        This is called after user completes OAuth flow.
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                data = {
                    "code": auth_code,
                    "client_id": self.api_key,
                    "client_secret": self.api_secret,
                    "redirect_uri": "http://localhost:8501",
                    "grant_type": "authorization_code",
                }
                resp = await client.post(self.TOKEN_URL, data=data)
                resp.raise_for_status()
                result = resp.json()
                
                if result.get("status") == "success":
                    self.access_token = result.get("data", {}).get("access_token", "")
                    logger.info("Successfully obtained access token from OAuth")
                    return True
                else:
                    logger.error(f"Token exchange failed: {result}")
                    return False
        except Exception as e:
            logger.error(f"Token exchange error: {e}")
            return False

    async def get(self, endpoint: str, params: dict = None) -> Optional[dict]:
        url = f"{self.BASE_URL}{endpoint}"
        t0 = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(url, headers=self.headers, params=params or {})
            self._latency_ms = (time.monotonic() - t0) * 1000
            resp.raise_for_status()
            self._connected = True
            return resp.json()
        except httpx.HTTPStatusError as e:
            self._connected = False
            logger.error(f"HTTP {e.response.status_code} for {endpoint}: {e.response.text[:200]}")
            return None
        except Exception as e:
            self._connected = False
            logger.error(f"Request failed for {endpoint}: {type(e).__name__}: {e}")
            return None

    async def verify_token(self) -> bool:
        result = await self.get("/user/profile")
        self._connected = result is not None
        return self._connected

    async def get_market_quotes(self, instrument_keys: list[str]) -> Optional[dict]:
        if not instrument_keys:
            return {}
        chunks = [instrument_keys[i:i+500] for i in range(0, len(instrument_keys), 500)]
        combined = {}
        for chunk in chunks:
            params = {"instrument_key": ",".join(chunk)}
            result = await self.get("/market-quote/quotes", params=params)
            if result and result.get("status") == "success":
                combined.update(result.get("data", {}))
        return combined

    async def get_ltp(self, instrument_keys: list[str]) -> Optional[dict]:
        if not instrument_keys:
            return {}
        chunks = [instrument_keys[i:i+500] for i in range(0, len(instrument_keys), 500)]
        combined = {}
        for chunk in chunks:
            params = {"instrument_key": ",".join(chunk)}
            result = await self.get("/market-quote/ltp", params=params)
            if result and result.get("status") == "success":
                combined.update(result.get("data", {}))
        return combined

    async def get_ohlc(self, instrument_keys: list[str], interval: str = "1day") -> Optional[dict]:
        if not instrument_keys:
            return {}
        chunks = [instrument_keys[i:i+500] for i in range(0, len(instrument_keys), 500)]
        combined = {}
        for chunk in chunks:
            params = {"instrument_key": ",".join(chunk), "interval": interval}
            result = await self.get("/market-quote/ohlc", params=params)
            if result and result.get("status") == "success":
                combined.update(result.get("data", {}))
        return combined

    async def get_historical_candles(self, instrument_key: str, interval: str, from_date: str, to_date: str) -> Optional[dict]:
        endpoint = f"/historical-candle/{instrument_key}/{interval}/{to_date}/{from_date}"
        return await self.get(endpoint)

    async def get_intraday_candles(self, instrument_key: str, interval: str) -> Optional[dict]:
        endpoint = f"/historical-candle/intraday/{instrument_key}/{interval}"
        return await self.get(endpoint)

    async def get_instruments(self, exchange: str = "NSE") -> Optional[list]:
        result = await self.get(f"/instruments/{exchange}")
        if result:
            return result
        return None

    async def close(self):
        pass

_client_instance: Optional[UpstoxClient] = None

def get_client() -> UpstoxClient:
    global _client_instance
    if _client_instance is None:
        _client_instance = UpstoxClient()
    return _client_instance
