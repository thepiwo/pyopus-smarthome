"""Example: listen to the OPUS gateway NDJSON event stream.

Copy .env.example to .env and fill in your gateway details before running.
"""
import asyncio
import os

from dotenv import load_dotenv

from pyopus_smarthome import OpusStream, Telegram

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

GATEWAY_IP = os.environ["OPUS_GATEWAY_IP"]
GATEWAY_PORT = int(os.environ.get("OPUS_GATEWAY_PORT", "8080"))
EURID = os.environ["OPUS_EURID"]


def on_telegram(telegram: Telegram) -> None:
    print(f"[{telegram.timestamp}] {telegram.friendly_id} ({telegram.device_id})")
    for fn in telegram.functions:
        print(f"  {fn.key} = {fn.value} {fn.meaning or ''}")
    if telegram.dbm is not None:
        print(f"  signal: {telegram.dbm} dBm")
    print()


async def main():
    stream = OpusStream(
        GATEWAY_IP,
        eurid=EURID,
        port=GATEWAY_PORT,
        on_telegram=on_telegram,
        reconnect_delay=30.0,
    )
    print(f"Connecting to {GATEWAY_IP}...")
    await stream.start()

    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        await stream.stop()


asyncio.run(main())
