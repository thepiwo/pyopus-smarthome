# tests/test_client.py
from __future__ import annotations

import base64
import pytest
import aiohttp
from aioresponses import aioresponses

from pyopus_smarthome.client import OpusClient
from pyopus_smarthome.models import Device, Gateway
from pyopus_smarthome.exceptions import OpusConnectionError, OpusAuthError, OpusApiError

HOST = "192.168.1.1"
PORT = 8080
EURID = "abcdef12345678"  # last 8 chars → "12345678"
BASE_URL = f"http://{HOST}:{PORT}"


def expected_auth_header(eurid: str) -> str:
    password = eurid[-8:].upper()
    token = base64.b64encode(f"admin:{password}".encode()).decode()
    return f"Basic {token}"


@pytest.fixture
def client():
    return OpusClient(host=HOST, eurid=EURID, port=PORT)


SYSTEM_INFO_RESPONSE = {
    "version": "2.5.0",
    "eurid": EURID,
    "serialNumber": "SN123456",
    "productId": "OPUS-GW-1",
    "baseId": "FFAA0000",
    "frequency": 868,
    "homekitPin": "123-45-678",
    "processes": [
        {"featureId": "homekit", "state": "running", "isActivated": True, "version": "1.0"}
    ],
}

DEVICES_RESPONSE = {
    "devices": [
        {
            "deviceId": "AABB0001",
            "friendlyId": "Living Room Shutter",
            "eeps": [{"eep": "D2-05-02", "version": 0.9, "direction": "both"}],
            "states": [{"key": "position", "value": 50.0, "unit": "%"}],
            "location": "Living Room",
            "operable": True,
        },
        {
            "deviceId": "CCDD0002",
            "friendlyId": "Bedroom Temp",
            "eeps": [{"eep": "D2-14-54", "version": 1.0}],
            "states": [{"key": "temperature", "value": 22.5, "unit": "°C"}],
            "operable": True,
        },
    ]
}


@pytest.mark.asyncio
async def test_get_system_info_returns_gateway(client):
    with aioresponses() as m:
        m.get(f"{BASE_URL}/system/info", payload=SYSTEM_INFO_RESPONSE)
        result = await client.get_system_info()
        await client.close()

    assert isinstance(result, Gateway)
    assert result.version == "2.5.0"
    assert result.eurid == EURID
    assert result.serial == "SN123456"
    assert result.homekit_pin == "123-45-678"
    assert len(result.processes) == 1
    assert result.processes[0].feature_id == "homekit"


@pytest.mark.asyncio
async def test_get_devices_returns_device_list(client):
    with aioresponses() as m:
        m.get(f"{BASE_URL}/devices", payload=DEVICES_RESPONSE)
        result = await client.get_devices()
        await client.close()

    assert isinstance(result, list)
    assert len(result) == 2
    assert all(isinstance(d, Device) for d in result)
    assert result[0].device_id == "AABB0001"
    assert result[0].friendly_id == "Living Room Shutter"
    assert result[1].device_id == "CCDD0002"


@pytest.mark.asyncio
async def test_get_devices_empty_list(client):
    with aioresponses() as m:
        m.get(f"{BASE_URL}/devices", payload={"devices": []})
        result = await client.get_devices()
        await client.close()

    assert result == []


@pytest.mark.asyncio
async def test_set_state_sends_correct_put_body(client):
    device_id = "AABB0001"
    with aioresponses() as m:
        m.put(
            f"{BASE_URL}/devices/{device_id}/state",
            payload={},
            status=200,
        )
        await client.set_state(device_id, "position", 75.0)
        await client.close()

    # Verify the request was made with correct body
    request = m.requests[("PUT", aiohttp.client.URL(f"{BASE_URL}/devices/{device_id}/state"))][0]
    sent_json = request.kwargs.get("json")
    assert sent_json == {
        "state": {"functions": [{"key": "position", "value": 75.0}]}
    }


@pytest.mark.asyncio
async def test_update_device_sends_post_with_room(client):
    device_id = "AABB0001"
    with aioresponses() as m:
        m.post(
            f"{BASE_URL}/devices/{device_id}",
            payload={},
            status=200,
        )
        await client.update_device(device_id, "New Name", room_name="Kitchen")
        await client.close()

    request = m.requests[("POST", aiohttp.client.URL(f"{BASE_URL}/devices/{device_id}"))][0]
    sent_json = request.kwargs.get("json")
    assert sent_json == {
        "deviceId": device_id,
        "friendlyId": "New Name",
        "roomName": "Kitchen",
    }


@pytest.mark.asyncio
async def test_update_device_sends_post_without_room(client):
    device_id = "AABB0001"
    with aioresponses() as m:
        m.post(
            f"{BASE_URL}/devices/{device_id}",
            payload={},
            status=200,
        )
        await client.update_device(device_id, "New Name")
        await client.close()

    request = m.requests[("POST", aiohttp.client.URL(f"{BASE_URL}/devices/{device_id}"))][0]
    sent_json = request.kwargs.get("json")
    assert sent_json == {
        "deviceId": device_id,
        "friendlyId": "New Name",
    }
    assert "roomName" not in sent_json


@pytest.mark.asyncio
async def test_auth_header_is_basic_derived_from_eurid(client):
    with aioresponses() as m:
        m.get(f"{BASE_URL}/system/info", payload=SYSTEM_INFO_RESPONSE)
        await client.get_system_info()
        await client.close()

    request = m.requests[("GET", aiohttp.client.URL(f"{BASE_URL}/system/info"))][0]
    # aiohttp BasicAuth is passed as auth= kwarg, not as a header directly in kwargs
    # We verify the auth object used matches expected credentials
    auth = request.kwargs.get("auth")
    assert auth is not None
    assert auth.login == "admin"
    assert auth.password == EURID[-8:].upper()


@pytest.mark.asyncio
async def test_connection_error_raises_opus_connection_error(client):
    with aioresponses() as m:
        m.get(f"{BASE_URL}/system/info", exception=aiohttp.ClientConnectionError("refused"))
        with pytest.raises(OpusConnectionError):
            await client.get_system_info()
        await client.close()


@pytest.mark.asyncio
async def test_401_raises_opus_auth_error(client):
    with aioresponses() as m:
        m.get(f"{BASE_URL}/system/info", status=401, payload={"error": "Unauthorized"})
        with pytest.raises(OpusAuthError):
            await client.get_system_info()
        await client.close()


@pytest.mark.asyncio
async def test_500_raises_opus_api_error(client):
    with aioresponses() as m:
        m.get(f"{BASE_URL}/system/info", status=500, body="Internal Server Error")
        with pytest.raises(OpusApiError) as exc_info:
            await client.get_system_info()
        await client.close()

    assert exc_info.value.status == 500


@pytest.mark.asyncio
async def test_get_device_configuration_returns_dict(client):
    device_id = "AABB0001"
    config_response = {
        "configuration": {
            "channel": 1,
            "powerLevel": 100,
        }
    }
    with aioresponses() as m:
        m.get(
            f"{BASE_URL}/devices/{device_id}/configuration",
            payload=config_response,
        )
        result = await client.get_device_configuration(device_id)
        await client.close()

    assert result == {"channel": 1, "powerLevel": 100}


@pytest.mark.asyncio
async def test_client_accepts_external_session():
    """Client should use an externally provided session and not close it."""
    async with aiohttp.ClientSession() as session:
        client = OpusClient(host=HOST, eurid=EURID, port=PORT, session=session)
        assert client._owns_session is False

        with aioresponses() as m:
            m.get(f"{BASE_URL}/system/info", payload=SYSTEM_INFO_RESPONSE)
            result = await client.get_system_info()

        assert isinstance(result, Gateway)
        # Closing client should not close the external session
        await client.close()
        assert not session.closed
