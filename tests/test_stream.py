# tests/test_stream.py
from __future__ import annotations

import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from pyopus_smarthome.stream import OpusStream
from pyopus_smarthome.models import Device, Telegram

HOST = "192.168.1.1"
EURID = "abcdef12345678"

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def make_stream(**kwargs) -> OpusStream:
    return OpusStream(host=HOST, eurid=EURID, **kwargs)


def devices_msg(devices: list[dict]) -> dict:
    return {"header": {"content": "devices"}, "devices": devices}


def telegram_msg(telegram: dict) -> dict:
    return {"header": {"content": "telegram"}, "telegram": telegram}


DEVICE_DATA = {
    "deviceId": "AABB0001",
    "friendlyId": "Test Shutter",
    "eeps": [{"eep": "D2-05-02"}],
    "states": [{"key": "position", "value": 50.0, "unit": "%"}],
    "operable": True,
}

TELEGRAM_DATA = {
    "deviceId": "DDEE0001",
    "friendlyId": "Test Doorbell",
    "timestamp": "2025-01-01T12:00:00.000+0100",
    "direction": "from",
    "functions": [{"key": "buttonBI", "value": "pressed", "meaning": "Button pressed"}],
    "telegramInfo": {"dbm": -68},
}


# ---------------------------------------------------------------------------
# _dispatch tests (unit tests — no network involved)
# ---------------------------------------------------------------------------

def test_dispatch_devices_calls_on_devices_callback():
    received = []
    stream = make_stream(on_devices=lambda devs: received.extend(devs))

    stream._dispatch(devices_msg([DEVICE_DATA]))

    assert len(received) == 1
    assert isinstance(received[0], Device)
    assert received[0].device_id == "AABB0001"


def test_dispatch_devices_parses_all_devices():
    received = []
    stream = make_stream(on_devices=lambda devs: received.extend(devs))

    device2 = {**DEVICE_DATA, "deviceId": "AABB0002", "friendlyId": "Device 2"}
    stream._dispatch(devices_msg([DEVICE_DATA, device2]))

    assert len(received) == 2
    assert received[1].device_id == "AABB0002"


def test_dispatch_telegram_calls_on_telegram_callback():
    received = []
    stream = make_stream(on_telegram=lambda tg: received.append(tg))

    stream._dispatch(telegram_msg(TELEGRAM_DATA))

    assert len(received) == 1
    assert isinstance(received[0], Telegram)
    assert received[0].device_id == "DDEE0001"


def test_dispatch_telegram_parses_functions():
    received = []
    stream = make_stream(on_telegram=lambda tg: received.append(tg))

    stream._dispatch(telegram_msg(TELEGRAM_DATA))

    tg = received[0]
    assert len(tg.functions) == 1
    assert tg.functions[0].key == "buttonBI"
    assert tg.functions[0].value == "pressed"


def test_dispatch_no_on_devices_callback_does_not_crash():
    """When no on_devices callback is set, devices message is silently ignored."""
    stream = make_stream()  # no callbacks
    stream._dispatch(devices_msg([DEVICE_DATA]))  # must not raise


def test_dispatch_no_on_telegram_callback_does_not_crash():
    """When no on_telegram callback is set, telegram message is silently ignored."""
    stream = make_stream()  # no callbacks
    stream._dispatch(telegram_msg(TELEGRAM_DATA))  # must not raise


def test_dispatch_unknown_content_ignored():
    """Messages with unknown content type are silently ignored."""
    received_devices = []
    received_telegrams = []
    stream = make_stream(
        on_devices=lambda d: received_devices.extend(d),
        on_telegram=lambda t: received_telegrams.append(t),
    )
    stream._dispatch({"header": {"content": "unknown"}, "data": "foo"})
    assert received_devices == []
    assert received_telegrams == []


# ---------------------------------------------------------------------------
# Stream parsing tests — mock aiohttp session
# ---------------------------------------------------------------------------

class AsyncLineIterator:
    """Async iterator that yields bytes lines then stops."""

    def __init__(self, lines: list[bytes]) -> None:
        self._lines = iter(lines)

    def __aiter__(self):
        return self

    async def __anext__(self) -> bytes:
        try:
            return next(self._lines)
        except StopIteration:
            raise StopAsyncIteration


class MockContent:
    """Mock for aiohttp response.content that supports `async for`."""

    def __init__(self, lines: list[bytes]) -> None:
        self._lines = lines

    def __aiter__(self):
        return AsyncLineIterator(self._lines)


def make_mock_response(lines: list[bytes]):
    """Build a mock aiohttp response whose content async-iterates over lines."""
    mock_resp = MagicMock()
    mock_resp.content = MockContent(lines)
    return mock_resp


def make_mock_session_single_shot(mock_response):
    """Build a mock session that returns lines once then blocks forever on subsequent calls."""
    # After the first request, subsequent get() calls will block until cancelled
    call_count = 0

    async def blocking_aenter(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return mock_response
        else:
            # Block until cancelled
            await asyncio.sleep(3600)

    mock_cm = MagicMock()
    mock_cm.__aenter__ = blocking_aenter
    mock_cm.__aexit__ = AsyncMock(return_value=False)

    mock_session = MagicMock()
    mock_session.get = MagicMock(return_value=mock_cm)
    mock_session.closed = False
    mock_session.close = AsyncMock()
    return mock_session


async def run_stream_and_cancel(stream: OpusStream, delay: float = 0.1) -> None:
    """Run stream._run() then cancel after delay."""
    task = asyncio.create_task(stream._run())
    await asyncio.sleep(delay)
    stream._running = False
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


@pytest.mark.asyncio
async def test_stream_dispatches_devices_line():
    received = []
    stream = make_stream(on_devices=lambda devs: received.extend(devs))

    line = json.dumps(devices_msg([DEVICE_DATA])).encode() + b"\n"
    mock_resp = make_mock_response([line])
    stream._running = True
    stream._session = make_mock_session_single_shot(mock_resp)

    await run_stream_and_cancel(stream)

    assert len(received) == 1
    assert isinstance(received[0], Device)
    assert received[0].device_id == "AABB0001"


@pytest.mark.asyncio
async def test_stream_dispatches_telegram_line():
    received = []
    stream = make_stream(on_telegram=lambda tg: received.append(tg))

    line = json.dumps(telegram_msg(TELEGRAM_DATA)).encode() + b"\n"
    mock_resp = make_mock_response([line])
    stream._running = True
    stream._session = make_mock_session_single_shot(mock_resp)

    await run_stream_and_cancel(stream)

    assert len(received) == 1
    assert isinstance(received[0], Telegram)
    assert received[0].device_id == "DDEE0001"


@pytest.mark.asyncio
async def test_stream_skips_malformed_json_lines():
    """Malformed JSON lines must not crash the stream."""
    received = []
    stream = make_stream(on_telegram=lambda tg: received.append(tg))

    bad_line = b"not valid json\n"
    good_line = json.dumps(telegram_msg(TELEGRAM_DATA)).encode() + b"\n"
    mock_resp = make_mock_response([bad_line, good_line])
    stream._running = True
    stream._session = make_mock_session_single_shot(mock_resp)

    await run_stream_and_cancel(stream)

    # The good line should still be processed
    assert len(received) == 1
    assert received[0].device_id == "DDEE0001"


@pytest.mark.asyncio
async def test_stream_skips_empty_lines():
    """Empty lines must not crash the stream."""
    received = []
    stream = make_stream(on_devices=lambda devs: received.extend(devs))

    good_line = json.dumps(devices_msg([DEVICE_DATA])).encode() + b"\n"
    mock_resp = make_mock_response([b"\n", b"  \n", good_line])
    stream._running = True
    stream._session = make_mock_session_single_shot(mock_resp)

    await run_stream_and_cancel(stream)

    assert len(received) == 1
    assert received[0].device_id == "AABB0001"


# ---------------------------------------------------------------------------
# Reconnect test
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_stream_reconnects_after_exception():
    """Stream should reconnect (re-enter _run loop) after an exception, with delay."""
    received = []
    stream = make_stream(
        on_devices=lambda devs: received.extend(devs),
        reconnect_delay=0.01,  # very short for fast tests
    )

    good_line = json.dumps(devices_msg([DEVICE_DATA])).encode() + b"\n"
    call_count = 0

    async def blocking_aenter(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # First call: raise a connection error
            raise Exception("Connection refused")
        elif call_count == 2:
            # Second call: return devices then block
            return make_mock_response([good_line])
        else:
            # Subsequent calls: block until cancelled
            await asyncio.sleep(3600)

    mock_cm = MagicMock()
    mock_cm.__aenter__ = blocking_aenter
    mock_cm.__aexit__ = AsyncMock(return_value=False)

    mock_session = MagicMock()
    mock_session.get = MagicMock(return_value=mock_cm)
    mock_session.closed = False
    mock_session.close = AsyncMock()

    stream._running = True
    stream._session = mock_session

    # Run for long enough: reconnect_delay (0.01s) + processing time
    task = asyncio.create_task(stream._run())
    await asyncio.sleep(0.2)  # > 10x reconnect_delay
    stream._running = False
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    # Should have tried at least twice
    assert call_count >= 2
    # And processed the devices from the second successful connection
    assert len(received) >= 1
    assert received[0].device_id == "AABB0001"
