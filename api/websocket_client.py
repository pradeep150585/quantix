import asyncio
import json
import time
from typing import Callable, Optional
import websockets
from loguru import logger
from config import get


class UpstoxWebSocket:
    WS_URL = "wss://api.upstox.com/v2/feed/market-data-feed"

    def __init__(self):
        self.access_token = get("upstox.access_token", "")
        self._ws = None
        self._running = False
        self._callbacks: list[Callable] = []
        self._subscribed_keys: set[str] = set()
        self.status: str = "Disconnected"
        self._last_msg_time: float = 0.0

    def add_callback(self, fn: Callable):
        self._callbacks.append(fn)

    async def connect(self):
        headers = {"Authorization": f"Bearer {self.access_token}"}
        try:
            self._ws = await websockets.connect(self.WS_URL, extra_headers=headers, ping_interval=20)
            self._running = True
            self.status = "Connected"
            logger.info("WebSocket connected")
        except Exception as e:
            self.status = f"Error: {e}"
            logger.error(f"WebSocket connect failed: {e}")

    async def subscribe(self, instrument_keys: list[str], mode: str = "full"):
        if not self._ws:
            return
        self._subscribed_keys.update(instrument_keys)
        payload = {
            "guid": "nifty_scanner",
            "method": "sub",
            "data": {"mode": mode, "instrumentKeys": instrument_keys},
        }
        await self._ws.send(json.dumps(payload))

    async def listen(self):
        if not self._ws:
            return
        try:
            async for message in self._ws:
                self._last_msg_time = time.time()
                try:
                    data = json.loads(message) if isinstance(message, str) else message
                    for cb in self._callbacks:
                        try:
                            await cb(data) if asyncio.iscoroutinefunction(cb) else cb(data)
                        except Exception as e:
                            logger.warning(f"WS callback error: {e}")
                except Exception as e:
                    logger.warning(f"WS parse error: {e}")
        except websockets.ConnectionClosed:
            self.status = "Disconnected"
            logger.warning("WebSocket connection closed")
        except Exception as e:
            self.status = f"Error: {e}"
            logger.error(f"WebSocket listen error: {e}")

    async def disconnect(self):
        self._running = False
        if self._ws:
            await self._ws.close()
            self.status = "Disconnected"

    @property
    def is_alive(self) -> bool:
        return self._running and (time.time() - self._last_msg_time < 30)
