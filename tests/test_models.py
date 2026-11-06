# tests/test_models.py
from pyopus_smarthome.models import Device, DeviceConfiguration, Telegram

def test_device_from_dict(roller_shutter_data):
    dev = Device.from_dict(roller_shutter_data)
    assert dev.device_id == "AABB0001"
    assert dev.friendly_id == "Test Shutter"
    assert dev.location == "Bedroom"
    assert dev.get_state("position") == 0.0
    assert dev.get_state("nonexistent") is None
    assert dev.eeps == ["D2-05-02"]
    assert isinstance(dev.configuration, DeviceConfiguration)
    assert dev.configuration is not None
    assert dev.configuration.device_id == "AABB0001"
    assert dev.configuration.get_parameter_value("rotationTime") == 2

def test_device_is_cover(roller_shutter_data):
    dev = Device.from_dict(roller_shutter_data)
    assert dev.is_cover
    assert dev.supports_cover_tilt
    assert dev.get_configuration_parameter_value("verticalMovementTime") == 120


def test_cover_does_not_support_tilt_when_rotation_time_is_zero(roller_shutter_data):
    roller_shutter_data["configuration"]["parameters"][1]["value"] = 0
    dev = Device.from_dict(roller_shutter_data)
    assert not dev.supports_cover_tilt

def test_device_is_climate(heating_zone_data):
    dev = Device.from_dict(heating_zone_data)
    assert dev.is_climate
    assert not dev.supports_cover_tilt


def test_heatarea_number_from_physical_device(heating_zone_data):
    heating_zone_data["physicalDevice"] = "001122334455_3"
    dev = Device.from_dict(heating_zone_data)
    assert dev.physical_device == "001122334455_3"
    assert dev.heatarea_number == 3


def test_heatarea_number_none_without_physical_device(heating_zone_data):
    dev = Device.from_dict(heating_zone_data)
    assert dev.physical_device is None
    assert dev.heatarea_number is None


def test_heatarea_number_none_for_malformed_physical_device(heating_zone_data):
    heating_zone_data["physicalDevice"] = "001122334455_x"
    assert Device.from_dict(heating_zone_data).heatarea_number is None

def test_telegram_from_dict(telegram_data):
    t = Telegram.from_dict(telegram_data)
    assert t.device_id == "DDEE0001"
    assert t.functions[0].key == "buttonBI"
    assert t.functions[0].value == "pressed"
    assert t.dbm == -68
