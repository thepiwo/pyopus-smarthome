# tests/test_ezr.py
from __future__ import annotations

import pytest
from aioresponses import aioresponses

from pyopus_smarthome import EzrClient, EzrStatus
from pyopus_smarthome.exceptions import OpusApiError, OpusConnectionError

HOST = "192.168.1.50"
BASE_URL = f"http://{HOST}:80"

# Trimmed, anonymised shape of /data/static.xml. Zone 2 has two actuators and
# a room unit that has lost contact; actuator 9 is unused.
STATIC_XML = """<?xml version="1.0" encoding="UTF-8"?>
<Devices>
  <Device>
    <ID>EZR0TEST1</ID>
    <NAME>Test Controller</NAME>
    <ERRORCOUNT>0</ERRORCOUNT>
    <PUMP_OUTPUT><PUMP_ISACTIVE>1</PUMP_ISACTIVE></PUMP_OUTPUT>
    <RELAIS><RELAIS_ISACTIVE>0</RELAIS_ISACTIVE></RELAIS>
    <EMERGENCYMODE>
      <EMERGENCYMODE_TIME>180</EMERGENCYMODE_TIME>
      <PWMCYCLE>15</PWMCYCLE>
      <PWMHEAT>25</PWMHEAT>
      <PWMCOOL>0</PWMCOOL>
    </EMERGENCYMODE>
    <HEATAREA nr="1">
      <HEATAREA_NAME>RBG1</HEATAREA_NAME>
      <T_ACTUAL>20.5</T_ACTUAL>
      <T_TARGET>21.0</T_TARGET>
      <HEATAREA_STATE>1</HEATAREA_STATE>
    </HEATAREA>
    <HEATAREA nr="2">
      <HEATAREA_NAME>RBG2</HEATAREA_NAME>
      <T_ACTUAL>19.0</T_ACTUAL>
      <T_TARGET>6.0</T_TARGET>
      <HEATAREA_STATE>0</HEATAREA_STATE>
    </HEATAREA>
    <HEATCTRL nr="1">
      <INUSE>1</INUSE><HEATAREA_NR>1</HEATAREA_NR>
      <ACTOR_PERCENT>0</ACTOR_PERCENT><HEATCTRL_STATE>0</HEATCTRL_STATE>
    </HEATCTRL>
    <HEATCTRL nr="2">
      <INUSE>1</INUSE><HEATAREA_NR>2</HEATAREA_NR>
      <ACTOR_PERCENT>25</ACTOR_PERCENT><HEATCTRL_STATE>1</HEATCTRL_STATE>
    </HEATCTRL>
    <HEATCTRL nr="3">
      <INUSE>1</INUSE><HEATAREA_NR>2</HEATAREA_NR>
      <ACTOR_PERCENT>10</ACTOR_PERCENT><HEATCTRL_STATE>1</HEATCTRL_STATE>
    </HEATCTRL>
    <HEATCTRL nr="9">
      <INUSE>0</INUSE><HEATAREA_NR>0</HEATAREA_NR>
      <ACTOR_PERCENT>0</ACTOR_PERCENT><HEATCTRL_STATE>0</HEATCTRL_STATE>
    </HEATCTRL>
    <IODEVICE nr="1">
      <HEATAREA_NR>1</HEATAREA_NR><SIGNALSTRENGTH>2</SIGNALSTRENGTH>
      <BATTERY>2</BATTERY><IODEVICE_COMERROR>0</IODEVICE_COMERROR>
    </IODEVICE>
    <IODEVICE nr="2">
      <HEATAREA_NR>2</HEATAREA_NR><SIGNALSTRENGTH>0</SIGNALSTRENGTH>
      <BATTERY>2</BATTERY><IODEVICE_COMERROR>1</IODEVICE_COMERROR>
    </IODEVICE>
  </Device>
</Devices>
"""

OK_RESPONSE = """<?xml version="1.0" encoding="UTF-8"?>
<COMMANDRESPONSE><STATE>OK</STATE><ERRORNUMBER>0</ERRORNUMBER></COMMANDRESPONSE>"""

ERROR_RESPONSE = """<?xml version="1.0" encoding="UTF-8"?>
<COMMANDRESPONSE><STATE>ERROR</STATE><ERRORNUMBER>7</ERRORNUMBER></COMMANDRESPONSE>"""


def test_status_parses_controller_values():
    status = EzrStatus.from_xml(STATIC_XML)

    assert status.device_id == "EZR0TEST1"
    assert status.name == "Test Controller"
    assert status.pump_active is True
    assert status.relay_active is False
    assert status.error_count == 0
    assert status.emergency_delay_minutes == 180
    assert status.emergency_heat_percent == 25


def test_status_parses_zones_actuators_and_room_units():
    status = EzrStatus.from_xml(STATIC_XML)

    assert set(status.zones) == {1, 2}
    zone1, zone2 = status.zones[1], status.zones[2]

    assert zone1.name == "RBG1"
    assert zone1.temperature == 20.5
    assert zone1.target_temperature == 21.0
    assert zone1.heating is True
    assert zone1.valve_percent == 0
    assert zone1.room_unit_lost is False

    assert [a.number for a in zone2.actuators] == [2, 3]
    assert zone2.valve_percent == 25
    assert zone2.heating is False
    assert zone2.room_unit_lost is True
    assert zone2.room_units[0].signal_strength == 0


def test_unused_actuators_are_ignored():
    status = EzrStatus.from_xml(STATIC_XML)
    numbers = [a.number for z in status.zones.values() for a in z.actuators]
    assert 9 not in numbers


def test_zone_without_actuators_has_no_valve_percent():
    xml = STATIC_XML.replace('<HEATAREA_NR>1</HEATAREA_NR>\n      <ACTOR', '<HEATAREA_NR>0</HEATAREA_NR>\n      <ACTOR')
    status = EzrStatus.from_xml(xml)
    assert status.zones[1].actuators == []
    assert status.zones[1].valve_percent is None


def test_invalid_xml_raises_api_error():
    with pytest.raises(OpusApiError):
        EzrStatus.from_xml("<Devices><Device>")


def test_missing_device_element_raises_api_error():
    with pytest.raises(OpusApiError):
        EzrStatus.from_xml("<Devices></Devices>")


@pytest.mark.asyncio
async def test_get_status_fetches_static_xml():
    client = EzrClient(HOST)
    with aioresponses() as m:
        m.get(f"{BASE_URL}/data/static.xml", body=STATIC_XML, content_type="text/xml")
        status = await client.get_status()
        await client.close()

    assert status.device_id == "EZR0TEST1"
    assert status.zones[2].room_unit_lost is True


@pytest.mark.asyncio
async def test_get_status_http_error_raises_api_error():
    client = EzrClient(HOST)
    with aioresponses() as m:
        m.get(f"{BASE_URL}/data/static.xml", status=500, body="boom")
        with pytest.raises(OpusApiError) as exc_info:
            await client.get_status()
        await client.close()

    assert exc_info.value.status == 500


@pytest.mark.asyncio
async def test_get_status_connection_error():
    import aiohttp

    client = EzrClient(HOST)
    with aioresponses() as m:
        m.get(f"{BASE_URL}/data/static.xml", exception=aiohttp.ClientConnectionError("refused"))
        with pytest.raises(OpusConnectionError):
            await client.get_status()
        await client.close()


@pytest.mark.asyncio
async def test_set_emergency_heat_percent_posts_change():
    client = EzrClient(HOST)
    with aioresponses() as m:
        m.post(f"{BASE_URL}/data/changes.xml", body=OK_RESPONSE)
        await client.set_emergency_heat_percent(0, device_id="EZR0TEST1")
        await client.close()

        request = list(m.requests.values())[0][0]
        body = request.kwargs["data"]

    assert "<ID>EZR0TEST1</ID>" in body
    assert "<EMERGENCYMODE><PWMHEAT>0</PWMHEAT></EMERGENCYMODE>" in body


@pytest.mark.asyncio
async def test_set_emergency_heat_percent_reads_device_id_when_missing():
    client = EzrClient(HOST)
    with aioresponses() as m:
        m.get(f"{BASE_URL}/data/static.xml", body=STATIC_XML)
        m.post(f"{BASE_URL}/data/changes.xml", body=OK_RESPONSE)
        await client.set_emergency_heat_percent(25)
        await client.close()

        posts = [reqs for (method, _), reqs in m.requests.items() if method == "POST"]
        body = posts[0][0].kwargs["data"]

    assert "<ID>EZR0TEST1</ID>" in body
    assert "<PWMHEAT>25</PWMHEAT>" in body


@pytest.mark.asyncio
async def test_set_emergency_heat_percent_rejected_raises():
    client = EzrClient(HOST)
    with aioresponses() as m:
        m.post(f"{BASE_URL}/data/changes.xml", body=ERROR_RESPONSE)
        with pytest.raises(OpusApiError):
            await client.set_emergency_heat_percent(10, device_id="EZR0TEST1")
        await client.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("percent", [-1, 101])
async def test_set_emergency_heat_percent_validates_range(percent):
    client = EzrClient(HOST)
    with pytest.raises(ValueError):
        await client.set_emergency_heat_percent(percent, device_id="EZR0TEST1")
    await client.close()
