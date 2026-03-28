# tests/conftest.py
import pytest

@pytest.fixture
def roller_shutter_data():
    return {
        "deviceId": "AABB0001",
        "friendlyId": "Test Shutter",
        "eeps": [{"eep": "D2-05-02", "version": 0.9, "direction": "both"}],
        "manufacturer": "Jaeger Direkt",
        "location": "Bedroom",
        "productId": "004000000004",
        "states": [
            {"key": "position", "value": 0.0, "unit": "%"},
            {"key": "angle", "value": 0.0, "unit": "%"},
            {"key": "lockingMode", "value": "unblock"},
        ],
        "operable": True,
        "supported": True,
    }

@pytest.fixture
def heating_zone_data():
    return {
        "deviceId": "FFCC0001",
        "friendlyId": "Test Room",
        "eeps": [{"eep": "D1-4B-04", "version": 0.9}],
        "deviceType": "Heatarea",
        "states": [
            {"key": "temperature", "value": 21.5, "unit": "°C"},
            {"key": "temperatureSetpoint", "value": 21.0, "unit": "°C"},
            {"key": "valvePosition", "value": 0.0, "unit": "%"},
            {"key": "heaterMode", "value": "heating"},
        ],
    }

@pytest.fixture
def telegram_data():
    return {
        "deviceId": "DDEE0001",
        "friendlyId": "Test Doorbell",
        "timestamp": "2025-01-01T12:00:00.000+0100",
        "direction": "from",
        "functions": [{"key": "buttonBI", "value": "pressed", "meaning": "Button pressed"}],
        "telegramInfo": {"rorg": "F6", "data": "50", "status": "30", "dbm": -68},
    }
