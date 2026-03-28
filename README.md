# pyopus-smarthome

Async Python client library for the **OPUS SmartHome** gateway (also marketed as OPUS greenNet).
It provides HTTP API access and a real-time NDJSON event stream over a local network connection.

---

## Credentials

The gateway uses HTTP Basic Auth on port 8080. The password is derived from the gateway's **EURID** — the last 8 hex characters, uppercased.

You can find the EURID on the QR code label on the gateway, or decode it with the included `opus-qr` CLI tool. The library handles password derivation automatically — just pass the EURID.

---

## Installation

```bash
pip install pyopus-smarthome
```

Or with [uv](https://github.com/astral-sh/uv):

```bash
uv add pyopus-smarthome
```

---

## Quick start

```python
import asyncio
from pyopus_smarthome import OpusClient

async def main():
    # Connect using gateway IP and EURID (from GET /system/info)
    client = OpusClient("192.168.1.100", eurid="YOUR_EURID")

    gateway = await client.get_system_info()
    print(f"Gateway: {gateway.version}")

    devices = await client.get_devices()
    for d in devices:
        print(f"  {d.friendly_id}: cover={d.is_cover} climate={d.is_climate}")

    # Control a roller shutter
    await client.set_state("DEVICE_ID", "position", 50)

    await client.close()

asyncio.run(main())
```

---

## Real-time event stream

`OpusStream` connects to the gateway's NDJSON server-sent event endpoint and dispatches
callbacks when device states change or telegrams arrive.

```python
import asyncio
from pyopus_smarthome import OpusStream, Device, Telegram

def on_devices(devices: list[Device]) -> None:
    for d in devices:
        print(f"Device update: {d.friendly_id}")

def on_telegram(telegram: Telegram) -> None:
    for fn in telegram.functions:
        print(f"Telegram: {fn.key} = {fn.value}")

async def main():
    stream = OpusStream(
        "192.168.1.100",
        eurid="YOUR_EURID",
        on_devices=on_devices,
        on_telegram=on_telegram,
        reconnect_delay=30.0,
    )
    await stream.start()

    # Run until interrupted
    try:
        await asyncio.sleep(3600)
    finally:
        await stream.stop()

asyncio.run(main())
```

See [`examples/`](examples/) for runnable scripts — copy `.env.example` to `.env` and fill in your gateway details.

---

## Supported device types

The library models the following device categories (detected from `deviceType` and function keys):

| Category | `is_*` property | Description |
|----------|----------------|-------------|
| Roller shutters | `device.is_cover` | Position control (0–100%) |
| Heating zones | `device.is_climate` | Set-point and current temperature |
| Temperature/humidity sensors | `device.is_sensor` | Read-only sensor values |
| Doorbell | `device.is_doorbell` | Binary press events |

---

## API reference

### `OpusClient`

```python
OpusClient(host: str, eurid: str, port: int = 8080, session: aiohttp.ClientSession | None = None)
```

| Method | Description |
|--------|-------------|
| `await client.get_system_info()` | Returns a `Gateway` with version and EURID |
| `await client.get_devices()` | Returns `list[Device]` |
| `await client.set_state(device_id, key, value)` | Send a state update to a device |
| `await client.update_device(device_id, friendly_id, room_name)` | Rename a device or room |
| `await client.get_device_configuration(device_id)` | Raw configuration dict |
| `await client.close()` | Close the underlying HTTP session |

### `OpusStream`

```python
OpusStream(host, eurid, port=8080, on_devices=None, on_telegram=None, reconnect_delay=30.0)
```

| Method | Description |
|--------|-------------|
| `await stream.start()` | Open the stream and begin dispatching callbacks |
| `await stream.stop()` | Stop the stream and close the connection |

### Models

- `Gateway` — gateway system info (`version`, `eurid`, `serial`)
- `Device` — device with `device_id`, `friendly_id`, `location`, `states: list[DeviceState]`
- `DeviceState` — a key/value/unit triplet
- `Telegram` — incoming radio telegram with `device_id` and `functions: list[TelegramFunction]`
- `TelegramFunction` — `key` + `value` pair from a telegram

### Auth helpers

```python
from pyopus_smarthome import derive_admin_password, derive_config_password, parse_qr_code

password = derive_admin_password("00AABBCCDD")   # -> "AABBCCDD"

# Or derive credentials from the gateway QR code label
creds = parse_qr_code("30S0000AABBCCDD+1P00400000002B+S12345678")
creds.admin_password   # -> "AABBCCDD"
creds.config_password  # -> "AABBCCDD-12345678"
```

### Exceptions

| Exception | Raised when |
|-----------|------------|
| `OpusError` | Base class |
| `OpusConnectionError` | Network-level failure |
| `OpusAuthError` | HTTP 401 from gateway |
| `OpusApiError` | HTTP 4xx/5xx other than 401 |

---

## License

MIT
