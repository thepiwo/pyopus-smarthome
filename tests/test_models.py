# tests/test_models.py
from pyopus_smarthome.models import Device, Telegram

def test_device_from_dict(roller_shutter_data):
    dev = Device.from_dict(roller_shutter_data)
    assert dev.device_id == "AABB0001"
    assert dev.friendly_id == "Test Shutter"
    assert dev.location == "Bedroom"
    assert dev.get_state("position") == 0.0
    assert dev.get_state("nonexistent") is None
    assert dev.eeps == ["D2-05-02"]

def test_device_is_cover(roller_shutter_data):
    dev = Device.from_dict(roller_shutter_data)
    assert dev.is_cover

def test_device_is_climate(heating_zone_data):
    dev = Device.from_dict(heating_zone_data)
    assert dev.is_climate

def test_telegram_from_dict(telegram_data):
    t = Telegram.from_dict(telegram_data)
    assert t.device_id == "DDEE0001"
    assert t.functions[0].key == "buttonBI"
    assert t.functions[0].value == "pressed"
    assert t.dbm == -68
