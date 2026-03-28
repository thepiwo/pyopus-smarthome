# src/pyopus_smarthome/stream.py
from __future__ import annotations
import asyncio
import json
import logging
from collections.abc import Callable
import aiohttp
from .auth import derive_admin_password
from .models import Device, Telegram

_LOGGER = logging.getLogger(__name__)


class OpusStream:
    STREAM_PATH = "/devices/stream?direction=from&delimited=newLine&output=singleLine&levelOfDetail=high"

    def __init__(self, host: str, eurid: str, port: int = 8080,
                 on_devices: Callable[[list[Device]], None] | None = None,
                 on_telegram: Callable[[Telegram], None] | None = None,
                 reconnect_delay: float = 30.0) -> None:
        self._url = f"http://{host}:{port}{self.STREAM_PATH}"
        self._auth = aiohttp.BasicAuth("admin", derive_admin_password(eurid))
        self._on_devices = on_devices
        self._on_telegram = on_telegram
        self._reconnect_delay = reconnect_delay
        self._task: asyncio.Task | None = None
        self._session: aiohttp.ClientSession | None = None
        self._running = False

    async def start(self) -> None:
        self._running = True
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        if self._session and not self._session.closed:
            await self._session.close()

    async def _run(self) -> None:
        while self._running:
            try:
                if not self._session or self._session.closed:
                    self._session = aiohttp.ClientSession()
                timeout = aiohttp.ClientTimeout(total=None, sock_read=None)
                async with self._session.get(self._url, auth=self._auth, timeout=timeout) as resp:
                    async for raw_line in resp.content:
                        line = raw_line.strip()
                        if not line:
                            continue
                        try:
                            msg = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        self._dispatch(msg)
            except asyncio.CancelledError:
                raise
            except Exception:
                _LOGGER.warning("Stream disconnected, reconnecting in %ss", self._reconnect_delay)
                if self._session and not self._session.closed:
                    await self._session.close()
                await asyncio.sleep(self._reconnect_delay)

    def _dispatch(self, msg: dict) -> None:
        content = msg.get("header", {}).get("content")
        if content == "devices" and self._on_devices:
            devices = [Device.from_dict(d) for d in msg.get("devices", [])]
            self._on_devices(devices)
        elif content == "telegram" and self._on_telegram:
            telegram = Telegram.from_dict(msg["telegram"])
            self._on_telegram(telegram)
