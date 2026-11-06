# src/pyopus_smarthome/ezr.py
"""Client for the Möhlenhoff Alpha EZR floor-heating controller.

The OPUS gateway drives a Möhlenhoff EZR as a set of virtual heat areas, but it
does not pass on what the controller actually does: actuator duty cycle, pump,
boiler relay, or whether a zone has lost its room unit. The controller serves
all of that over its own unauthenticated XML API (port 80).

When a zone loses its room unit for longer than the configured emergency delay,
the controller drives that zone's actuators at a fixed duty cycle
(``emergency_heat_percent``), regardless of the zone's setpoint.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from xml.sax.saxutils import escape

import aiohttp

from .exceptions import OpusApiError, OpusConnectionError

STATUS_PATH = "/data/static.xml"
CHANGES_PATH = "/data/changes.xml"


def _text(el: ET.Element, tag: str) -> str | None:
    value = el.findtext(tag)
    return value.strip() if value is not None else None


def _int(el: ET.Element, tag: str) -> int | None:
    value = _text(el, tag)
    try:
        return int(value) if value else None
    except ValueError:
        return None


def _float(el: ET.Element, tag: str) -> float | None:
    value = _text(el, tag)
    try:
        return float(value) if value else None
    except ValueError:
        return None


def _flag(el: ET.Element, tag: str) -> bool:
    return _int(el, tag) == 1


@dataclass
class EzrActuator:
    """A valve actuator output (``HEATCTRL``)."""

    number: int
    zone: int
    percent: int
    active: bool


@dataclass
class EzrRoomUnit:
    """A room unit (``IODEVICE``) that reports a zone's temperature."""

    number: int
    zone: int
    signal_strength: int | None
    battery: int | None
    comm_error: bool


@dataclass
class EzrZone:
    """A heat area (``HEATAREA``) with its actuators and room units."""

    number: int
    name: str
    temperature: float | None
    target_temperature: float | None
    heating: bool
    actuators: list[EzrActuator] = field(default_factory=list)
    room_units: list[EzrRoomUnit] = field(default_factory=list)

    @property
    def valve_percent(self) -> int | None:
        """Highest actuator duty cycle in this zone, or None without actuators."""
        if not self.actuators:
            return None
        return max(a.percent for a in self.actuators)

    @property
    def room_unit_lost(self) -> bool:
        """True if the controller has lost contact with a room unit of this zone."""
        return any(u.comm_error for u in self.room_units)


@dataclass
class EzrStatus:
    """Snapshot of the controller state."""

    device_id: str
    name: str | None
    pump_active: bool
    relay_active: bool
    error_count: int | None
    emergency_delay_minutes: int | None
    emergency_heat_percent: int | None
    zones: dict[int, EzrZone] = field(default_factory=dict)

    @classmethod
    def from_xml(cls, text: str) -> EzrStatus:
        try:
            root = ET.fromstring(text)
        except ET.ParseError as e:
            raise OpusApiError(200, f"Invalid controller XML: {e}") from e

        device = root.find("Device")
        if device is None:
            raise OpusApiError(200, "Controller XML has no Device element")

        zones: dict[int, EzrZone] = {}
        for area in device.findall("HEATAREA"):
            nr = area.get("nr")
            if nr is None or not nr.isdigit():
                continue
            zones[int(nr)] = EzrZone(
                number=int(nr),
                name=_text(area, "HEATAREA_NAME") or f"Zone {nr}",
                temperature=_float(area, "T_ACTUAL"),
                target_temperature=_float(area, "T_TARGET"),
                heating=_flag(area, "HEATAREA_STATE"),
            )

        for ctrl in device.findall("HEATCTRL"):
            nr, zone = ctrl.get("nr"), _int(ctrl, "HEATAREA_NR")
            if nr is None or not nr.isdigit() or not _flag(ctrl, "INUSE"):
                continue
            if zone in zones:
                zones[zone].actuators.append(
                    EzrActuator(
                        number=int(nr),
                        zone=zone,
                        percent=_int(ctrl, "ACTOR_PERCENT") or 0,
                        active=_flag(ctrl, "HEATCTRL_STATE"),
                    )
                )

        for unit in device.findall("IODEVICE"):
            nr, zone = unit.get("nr"), _int(unit, "HEATAREA_NR")
            if nr is None or not nr.isdigit():
                continue
            if zone in zones:
                zones[zone].room_units.append(
                    EzrRoomUnit(
                        number=int(nr),
                        zone=zone,
                        signal_strength=_int(unit, "SIGNALSTRENGTH"),
                        battery=_int(unit, "BATTERY"),
                        comm_error=_flag(unit, "IODEVICE_COMERROR"),
                    )
                )

        emergency = device.find("EMERGENCYMODE")
        pump = device.find("PUMP_OUTPUT")
        relay = device.find("RELAIS")
        return cls(
            device_id=_text(device, "ID") or "",
            name=_text(device, "NAME"),
            pump_active=pump is not None and _flag(pump, "PUMP_ISACTIVE"),
            relay_active=relay is not None and _flag(relay, "RELAIS_ISACTIVE"),
            error_count=_int(device, "ERRORCOUNT"),
            emergency_delay_minutes=(
                _int(emergency, "EMERGENCYMODE_TIME") if emergency is not None else None
            ),
            emergency_heat_percent=(
                _int(emergency, "PWMHEAT") if emergency is not None else None
            ),
            zones=zones,
        )


class EzrClient:
    """Async client for the Möhlenhoff Alpha EZR XML API."""

    def __init__(
        self,
        host: str,
        port: int = 80,
        session: aiohttp.ClientSession | None = None,
        timeout: float = 10.0,
    ) -> None:
        self._base_url = f"http://{host}:{port}"
        self._session = session
        self._owns_session = session is None
        self._timeout = aiohttp.ClientTimeout(total=timeout)

    async def _ensure_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
            self._owns_session = True
        return self._session

    async def close(self) -> None:
        if self._owns_session and self._session and not self._session.closed:
            await self._session.close()

    async def _request(self, method: str, path: str, **kwargs) -> str:
        session = await self._ensure_session()
        url = f"{self._base_url}{path}"
        try:
            async with session.request(
                method, url, timeout=self._timeout, **kwargs
            ) as resp:
                text = await resp.text()
                if resp.status >= 400:
                    raise OpusApiError(resp.status, text)
                return text
        except aiohttp.ClientError as e:
            raise OpusConnectionError(str(e)) from e
        except TimeoutError as e:
            raise OpusConnectionError("Timeout talking to controller") from e

    async def get_status(self) -> EzrStatus:
        """Read the full controller state."""
        return EzrStatus.from_xml(await self._request("GET", STATUS_PATH))

    async def _send_changes(self, device_id: str, body: str) -> None:
        payload = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            f"<Devices><Device><ID>{escape(device_id)}</ID>{body}</Device></Devices>"
        )
        text = await self._request("POST", CHANGES_PATH, data=payload)
        try:
            response = ET.fromstring(text)
        except ET.ParseError as e:
            raise OpusApiError(200, f"Invalid controller response: {e}") from e
        state = response.findtext("STATE")
        if state is None or state.strip() != "OK":
            error = response.findtext("ERRORNUMBER")
            raise OpusApiError(200, f"Controller rejected change (error {error})")

    async def set_emergency_heat_percent(
        self, percent: int, device_id: str | None = None
    ) -> None:
        """Set the duty cycle used for zones in emergency mode (0 disables heating)."""
        if not 0 <= percent <= 100:
            raise ValueError("percent must be between 0 and 100")
        if device_id is None:
            device_id = (await self.get_status()).device_id
        await self._send_changes(
            device_id,
            f"<EMERGENCYMODE><PWMHEAT>{int(percent)}</PWMHEAT></EMERGENCYMODE>",
        )
