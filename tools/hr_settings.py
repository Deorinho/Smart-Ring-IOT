"""Read — and optionally set — R06_D29C's automatic heart-rate logging.

This answers the question left open when every log probe came back with the
`sub_type 0xFF` "no data" sentinel: **was the ring ever recording?** A ring with
logging disabled has faithfully stored nothing, which is indistinguishable from a
ring whose buffer was lost or whose clock was never set.

It is also the battery contract's control surface. The HR interval is the single
biggest lever on the ring's power draw — factory defaults burned ~12%/day.

    .venv/bin/python -m tools.hr_settings                 # read only
    .venv/bin/python -m tools.hr_settings --interval 30   # enable at 30 min
    .venv/bin/python -m tools.hr_settings --disable       # turn logging off

Writing re-reads afterwards and shows before/after, because a command the ring
silently ignored is otherwise indistinguishable from one it applied.
"""

from __future__ import annotations

import argparse
import asyncio

from bleak import BleakClient

from hub.config import DEFAULT_SENSING, R06
from protocol.commands import (
    UART_RX_CHAR_UUID,
    UART_TX_CHAR_UUID,
    request_hr_log_settings,
    set_hr_log_settings,
)
from protocol.packets import is_valid, parse_command_id, parse_hr_log_settings

REPLY_TIMEOUT_S = 10.0
CONNECT_TIMEOUT_S = 20.0
SETTLE_S = 1.0


async def _round_trip(client: BleakClient, request: bytes) -> bytes | None:
    """Write one command and wait for the matching reply.

    Matches on the echoed command byte rather than taking the first frame that
    arrives — the ring pushes unsolicited status frames (CMD_STATUS_PUSH, 0x73), and
    one landing mid-exchange would otherwise be mistaken for the answer.
    """
    want = request[0]
    reply: list[bytes] = []
    got = asyncio.Event()

    def on_notify(_sender, data: bytearray) -> None:
        raw = bytes(data)
        if raw and parse_command_id(raw) == want:
            reply.append(raw)
            got.set()
        else:
            print(f"  (unsolicited frame ignored: {raw.hex(' ')})")

    await client.start_notify(UART_TX_CHAR_UUID, on_notify)
    try:
        await client.write_gatt_char(UART_RX_CHAR_UUID, request, response=False)
        await asyncio.wait_for(got.wait(), REPLY_TIMEOUT_S)
    except TimeoutError:
        return None
    finally:
        try:
            await client.stop_notify(UART_TX_CHAR_UUID)
        except Exception:  # noqa: BLE001 - best effort on teardown
            pass

    return reply[0] if reply else None


def describe(frame: bytes | None) -> str:
    if frame is None:
        return "no reply"
    if not is_valid(frame):
        return f"BAD CHECKSUM  {frame.hex(' ')}"

    settings = parse_hr_log_settings(frame)
    state = "ENABLED" if settings.enabled else "DISABLED"
    return (
        f"{state}, every {settings.interval_minutes} min   [{frame.hex(' ')}]"
    )


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--interval",
        type=int,
        metavar="MINUTES",
        help=f"enable logging at this interval (project default: "
        f"{DEFAULT_SENSING.hr_interval_minutes})",
    )
    group.add_argument(
        "--disable", action="store_true", help="turn automatic logging off"
    )
    args = parser.parse_args()

    async with BleakClient(R06.address, timeout=CONNECT_TIMEOUT_S) as client:
        print(f"connected to {R06.name}\n")

        before = await _round_trip(client, request_hr_log_settings())
        print(f"current : {describe(before)}")

        if args.interval is None and not args.disable:
            return 0

        if args.disable:
            write = set_hr_log_settings(enabled=False, interval_minutes=1)
            intent = "disable logging"
        else:
            write = set_hr_log_settings(enabled=True, interval_minutes=args.interval)
            intent = f"enable logging every {args.interval} min"

        print(f"\nwriting : {intent}")
        print(f"          {write.hex(' ')}")
        ack = await _round_trip(client, write)
        print(f"ack     : {'none' if ack is None else ack.hex(' ')}")

        await asyncio.sleep(SETTLE_S)
        after = await _round_trip(client, request_hr_log_settings())
        print(f"\nnow     : {describe(after)}")

        if before is not None and after is not None and before[2:4] == after[2:4]:
            print("\nWARNING: settings unchanged. The ring accepted the write without")
            print("applying it, or the payload encoding is wrong.")

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
