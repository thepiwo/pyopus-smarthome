# src/pyopus_smarthome/client.py
from __future__ import annotations

import aiohttp

from .auth import derive_admin_password
from .models import Device, Gateway
from .exceptions import OpusConnectionError, OpusAuthError, OpusApiError


class OpusClient:
    def __init__(
        self,
        host: str,
        eurid: str,
        port: int = 8080,
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        self._base_url = f"http://{host}:{port}"
        self._auth = aiohttp.BasicAuth("admin", derive_admin_password(eurid))
        self._session = session
        self._owns_session = session is None

    async def _ensure_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
            self._owns_session = True
        return self._session

    async def close(self) -> None:
        if self._owns_session and self._session and not self._session.closed:
            await self._session.close()

    async def _request(self, method: str, path: str, **kwargs) -> dict:
        session = await self._ensure_session()
        url = f"{self._base_url}{path}"
        try:
            async with session.request(method, url, auth=self._auth, **kwargs) as resp:
                if resp.status == 401:
                    raise OpusAuthError("Invalid credentials")
                if resp.status >= 400:
                    text = await resp.text()
                    raise OpusApiError(resp.status, text)
                return await resp.json()
        except aiohttp.ClientError as e:
            raise OpusConnectionError(str(e)) from e

    async def get_system_info(self) -> Gateway:
        data = await self._request("GET", "/system/info")
        return Gateway.from_dict(data)

    async def get_devices(self) -> list[Device]:
        data = await self._request("GET", "/devices")
        return [Device.from_dict(d) for d in data.get("devices", [])]

    async def set_state(self, device_id: str, key: str, value: object) -> None:
        await self._request(
            "PUT",
            f"/devices/{device_id}/state",
            json={"state": {"functions": [{"key": key, "value": value}]}},
        )

    async def update_device(
        self,
        device_id: str,
        friendly_id: str,
        room_name: str | None = None,
    ) -> None:
        body: dict = {"deviceId": device_id, "friendlyId": friendly_id}
        if room_name:
            body["roomName"] = room_name
        await self._request("POST", f"/devices/{device_id}", json=body)

    async def get_device_configuration(self, device_id: str) -> dict:
        data = await self._request("GET", f"/devices/{device_id}/configuration")
        return data.get("configuration", {})
