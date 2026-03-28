"""Example: connect to OPUS gateway and list devices.

Copy .env.example to .env and fill in your gateway details before running.
"""
import asyncio
import os

from dotenv import load_dotenv

from pyopus_smarthome import OpusClient

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

GATEWAY_IP = os.environ["OPUS_GATEWAY_IP"]
GATEWAY_PORT = int(os.environ.get("OPUS_GATEWAY_PORT", "8080"))
EURID = os.environ["OPUS_EURID"]


async def main():
    client = OpusClient(GATEWAY_IP, eurid=EURID, port=GATEWAY_PORT)
    try:
        info = await client.get_system_info()
        print(f"Gateway: {info.version} (EURID: {info.eurid})")

        devices = await client.get_devices()
        for d in devices:
            print(f"  [{d.device_id}] {d.friendly_id} @ {d.location}")
            for s in d.states:
                print(f"    {s.key} = {s.value} {s.unit or ''}")
    finally:
        await client.close()


asyncio.run(main())
