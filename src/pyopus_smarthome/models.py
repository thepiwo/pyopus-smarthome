# src/pyopus_smarthome/models.py
from __future__ import annotations
from dataclasses import dataclass, field

# EEP constants for device type detection
EEP_COVER = "D2-05-02"
EEP_MULTISENSOR = "D2-14-54"
EEP_HEATAREA = "D1-4B-04"
EEP_HEATCONTROLLER = "D1-4B-02"
EEP_ROCKER_SWITCH = "F6-02-01"

@dataclass
class DeviceState:
    key: str
    value: object
    unit: str | None = None
    meaning: str | None = None

    @classmethod
    def from_dict(cls, data: dict) -> DeviceState:
        return cls(
            key=data["key"],
            value=data.get("value"),
            unit=data.get("unit"),
            meaning=data.get("meaning"),
        )

@dataclass
class TelegramFunction:
    key: str
    value: object
    unit: str | None = None
    meaning: str | None = None

    @classmethod
    def from_dict(cls, data: dict) -> TelegramFunction:
        return cls(key=data["key"], value=data.get("value"),
                   unit=data.get("unit"), meaning=data.get("meaning"))

@dataclass
class Telegram:
    device_id: str
    friendly_id: str
    timestamp: str
    direction: str
    functions: list[TelegramFunction]
    dbm: int | None = None

    @classmethod
    def from_dict(cls, data: dict) -> Telegram:
        info = data.get("telegramInfo", {})
        return cls(
            device_id=data["deviceId"],
            friendly_id=data.get("friendlyId", ""),
            timestamp=data.get("timestamp", ""),
            direction=data.get("direction", "from"),
            functions=[TelegramFunction.from_dict(f) for f in data.get("functions", [])],
            dbm=info.get("dbm"),
        )

@dataclass
class Device:
    device_id: str
    friendly_id: str
    eeps: list[str]
    states: list[DeviceState]
    location: str | None = None
    manufacturer: str | None = None
    product_id: str | None = None
    device_type: str | None = None
    operable: bool = True
    _raw: dict = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: dict) -> Device:
        return cls(
            device_id=data["deviceId"],
            friendly_id=data.get("friendlyId", ""),
            eeps=[e["eep"] for e in data.get("eeps", [])],
            states=[DeviceState.from_dict(s) for s in data.get("states", [])],
            location=data.get("location"),
            manufacturer=data.get("manufacturer"),
            product_id=data.get("productId"),
            device_type=data.get("deviceType"),
            operable=data.get("operable", True),
            _raw=data,
        )

    def get_state(self, key: str) -> object | None:
        for s in self.states:
            if s.key == key:
                return s.value
        return None

    def update_state(self, key: str, value: object) -> None:
        for s in self.states:
            if s.key == key:
                s.value = value
                return
        self.states.append(DeviceState(key=key, value=value))

    @property
    def is_cover(self) -> bool:
        return EEP_COVER in self.eeps

    @property
    def is_climate(self) -> bool:
        return EEP_HEATAREA in self.eeps

    @property
    def is_sensor(self) -> bool:
        return EEP_MULTISENSOR in self.eeps

    @property
    def is_doorbell(self) -> bool:
        return EEP_ROCKER_SWITCH in self.eeps and not self.is_cover

    @property
    def is_heat_controller(self) -> bool:
        return EEP_HEATCONTROLLER in self.eeps

@dataclass
class GatewayProcess:
    feature_id: str
    state: str
    is_activated: bool
    version: str | None = None

@dataclass
class Gateway:
    version: str
    eurid: str
    serial: str
    product_id: str
    base_id: str
    frequency: int
    homekit_pin: str | None = None
    processes: list[GatewayProcess] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> Gateway:
        si = data.get("systemInfo", data)
        return cls(
            version=si.get("version", ""),
            eurid=si.get("eurid", ""),
            serial=si.get("serialNumber", ""),
            product_id=si.get("productId", ""),
            base_id=si.get("baseId", ""),
            frequency=si.get("frequency", 868),
            homekit_pin=si.get("homekitPin"),
            processes=[
                GatewayProcess(
                    feature_id=p["featureId"],
                    state=p["state"],
                    is_activated=p["isActivated"],
                    version=p.get("version"),
                )
                for p in si.get("processes", [])
            ],
        )
