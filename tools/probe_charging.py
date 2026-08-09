"""Resolve Bug_Backlog R-007: is the ring reachable over BLE while charging?

Session 2 found that `BleakClient` times out when the ring sits in its charging case.
Two very different causes look identical from a failed connect:

  * the ring stops advertising while charging (radio down), or
  * it still advertises but the metal case attenuates the link (or it refuses
    connections while charging).

This separates them by scanning first and reporting RSSI, then attempting the connect,
then — if it gets in — running a battery round trip.

That last step does double duty. `parse_battery`'s `is_charging` flag is a guess based
on `byte[2]` reading 0 while worn. If this connects on the charger and byte[2] reads
non-zero, the flag is confirmed and the parser is finished.

Run it TWICE and compare: once with the ring in the powered case, once on your finger.

    .venv/bin/python -m tools.probe_charging --label "in case, powered"
    .venv/bin/python -m tools.probe_charging --label "on finger"
"""

from __future__ import annotations

import argparse
import asyncio

from bleak import BleakClient, BleakScanner

from hub.config import R06
from protocol.packets import is_valid, parse_battery
from tools.battery import read_battery

SCAN_TIMEOUT_S = 15.0
CONNECT_TIMEOUT_S = 20.0


async def scan_for_ring() -> tuple[bool, int | None]:
    """Return (seen, rssi). RSSI is the whole point — it separates 'silent' from 'weak'."""
    found = await BleakScanner.discover(timeout=SCAN_TIMEOUT_S, return_adv=True)
    for address, (_device, adv) in found.items():
        if address.upper() == R06.address.upper():
            return True, adv.rssi
    return False, None


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--label", default="", help="note printed with the results")
    args = parser.parse_args()

    if args.label:
        print(f"--- {args.label} ---")
    print(f"target: {R06.name} @ {R06.address}\n")

    seen, rssi = await scan_for_ring()
    if seen:
        print(f"[scan]    FOUND, rssi={rssi} dBm")
    else:
        print("[scan]    NOT FOUND — no advertisements in "
              f"{SCAN_TIMEOUT_S:.0f}s")

    connected = False
    frame: bytes | None = None
    try:
        async with BleakClient(R06.address, timeout=CONNECT_TIMEOUT_S) as client:
            connected = client.is_connected
            print(f"[connect] OK, connected={connected}")
            frame = await read_battery(client)
    except Exception as exc:  # noqa: BLE001 - the failure mode IS the result here
        print(f"[connect] FAILED: {type(exc).__name__}: {exc}")

    if frame is not None:
        percent, is_charging = parse_battery(frame)
        print(f"[battery] {frame.hex(' ')}")
        print(f"          checksum_ok={is_valid(frame)}")
        print(f"          percent={percent}  byte[2]={frame[2]}  "
              f"is_charging={is_charging}")
    elif connected:
        print("[battery] connected but no reply within timeout")

    print("\n--- verdict ---")
    if seen and connected:
        print("Reachable in this state. R-007 does not apply here.")
        if frame is not None:
            state = "non-zero" if frame[2] else "zero"
            print(f"byte[2] is {state} in this state — compare against the other run")
            print("to confirm or reject the is_charging hypothesis.")
    elif seen and not connected:
        print("Advertises but will NOT accept a connection.")
        print("The radio is alive, so this is a firmware policy or an already-held")
        print("connection — not shielding. Sync policy must treat it as 'busy'.")
    elif not seen:
        print("Silent: no advertisements at all.")
        print("Either the radio is off in this state, or the case is shielding it.")
        print("Move the case a few cm from the adapter and re-run to separate those.")

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
