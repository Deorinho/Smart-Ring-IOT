"""Read R06_D29C's battery level.

The quick one. Connect, ask, print, disconnect.

    .venv/bin/python -m tools.battery
    .venv/bin/python -m tools.battery --watch          # poll every 60s
    .venv/bin/python -m tools.battery --watch 300      # poll every 5 min

`--watch` holds one connection open and polls, rather than reconnecting each time —
cheaper for the ring and it plots a charge or discharge curve if you leave it running.
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime

from bleak import BleakClient

from hub.config import R06
from protocol.commands import UART_RX_CHAR_UUID, UART_TX_CHAR_UUID, request_battery
from protocol.packets import is_valid, parse_battery

REPLY_TIMEOUT_S = 10.0
CONNECT_TIMEOUT_S = 20.0
DEFAULT_WATCH_S = 60


async def read_battery(client: BleakClient) -> bytes | None:
    """Send a battery request and return the reply frame, or None on timeout.

    Shared with `tools.probe_charging`. Subscribes before writing — the ring answers
    in milliseconds, and subscribing afterwards loses the reply.
    """
    reply: list[bytes] = []
    got = asyncio.Event()

    def on_notify(_sender, data: bytearray) -> None:
        reply.append(bytes(data))
        got.set()

    await client.start_notify(UART_TX_CHAR_UUID, on_notify)
    try:
        await client.write_gatt_char(
            UART_RX_CHAR_UUID, request_battery(), response=False
        )
        await asyncio.wait_for(got.wait(), REPLY_TIMEOUT_S)
    except TimeoutError:
        return None
    finally:
        try:
            await client.stop_notify(UART_TX_CHAR_UUID)
        except Exception:  # noqa: BLE001 - best effort on teardown
            pass

    return reply[0] if reply else None


def format_reading(frame: bytes | None) -> str:
    stamp = datetime.now().strftime("%H:%M:%S")
    if frame is None:
        return f"{stamp}  no reply"
    if not is_valid(frame):
        return f"{stamp}  BAD CHECKSUM  {frame.hex(' ')}"

    percent, charging = parse_battery(frame)
    state = "charging" if charging else "on battery"
    return f"{stamp}  {percent:>3}%  {state}"


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--watch",
        nargs="?",
        type=int,
        const=DEFAULT_WATCH_S,
        default=None,
        metavar="SECONDS",
        help=f"poll repeatedly (default {DEFAULT_WATCH_S}s); Ctrl-C to stop",
    )
    args = parser.parse_args()

    async with BleakClient(R06.address, timeout=CONNECT_TIMEOUT_S) as client:
        if args.watch is None:
            print(format_reading(await read_battery(client)))
            return 0

        print(f"polling {R06.name} every {args.watch}s — Ctrl-C to stop")
        try:
            while True:
                print(format_reading(await read_battery(client)), flush=True)
                await asyncio.sleep(args.watch)
        except KeyboardInterrupt:
            print("\nstopped")

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
