"""Set R06_D29C's RTC — a one-way door — and measure exactly what it changes.

The ring has never had its clock set. That state exists once and cannot be recreated,
so this script refuses to run until a virgin capture is on disk. The interlock is
mechanical on purpose: "remember to dump first" is a rule you break at 1 a.m.

What it does, in order:

  1. Refuses unless `protocol/fixtures/virgin_hr_probe_*.json` exists.
  2. Refuses unless `--confirm` is passed. Prints the exact bytes first.
  3. Writes the clock in UTC (colmi_r02_client `set_time.py`, MIT).
  4. Re-probes the SAME timestamps the virgin capture used, plus recent UTC midnights.
  5. Writes a post-set capture and diffs it against the virgin one.

Step 5 is the experiment. Comparing identical requests before and after a clock write
answers two questions nobody has documented for this hardware: does a virgin ring log
at all before its clock is set, and does setting the clock wipe the onboard buffer?

Run from the repo root:
    .venv/bin/python -m tools.set_ring_clock            # dry run, shows the bytes
    .venv/bin/python -m tools.set_ring_clock --confirm  # actually writes the clock
"""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from bleak import BleakClient

from hub.config import R06
from protocol.commands import UART_RX_CHAR_UUID, set_time
from tools.probe_hr_log import (
    CHANNELS,
    CONNECT_TIMEOUT_S,
    Collector,
    run_probe,
    summarize,
)

FIXTURES = Path("protocol/fixtures")
VIRGIN_GLOB = "virgin_hr_probe_*.json"
SETTLE_S = 2.0


def find_virgin_capture() -> Path | None:
    """Newest virgin capture on disk, or None. This is the safety interlock."""
    matches = sorted(FIXTURES.glob(VIRGIN_GLOB))
    return matches[-1] if matches else None


def answered_map(capture: dict) -> dict[int, int]:
    """{requested_ts: frame_count} for every probe in a capture."""
    return {p["requested_ts"]: p["frame_count"] for p in capture["probes"]}


def build_reprobes(virgin: dict) -> list[dict]:
    """Replay the virgin capture's timestamps, plus recent UTC midnights.

    Replaying identical inputs is what makes the before/after diff meaningful. The UTC
    midnights are added because the ring is now known to keep UTC, so those are where
    data should appear if the clock write took effect.
    """
    probes = [
        {"label": f"replay {p['label']}", "ts": p["requested_ts"]}
        for p in virgin["probes"]
    ]

    seen = {p["ts"] for p in probes}
    midnight_utc = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    for d in range(8):
        day = midnight_utc - timedelta(days=d)
        ts = int(day.timestamp())
        if ts not in seen:
            probes.append({"label": f"UTC midnight -{d}d ({day.date()})", "ts": ts})
            seen.add(ts)

    return probes


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--confirm", action="store_true", help="actually write the clock"
    )
    parser.add_argument("--out", type=Path, default=None, help="capture file path")
    args = parser.parse_args()

    virgin_path = find_virgin_capture()
    if virgin_path is None:
        print("REFUSING: no virgin capture found in protocol/fixtures/")
        print()
        print("R06_D29C's RTC has never been set. That state exists exactly once, and")
        print("setting the clock may wipe the onboard buffer. Capture the log first:")
        print()
        print("    .venv/bin/python -m tools.probe_hr_log")
        print()
        print("Then copy the capture here and re-run. This check is deliberate.")
        return 1

    virgin = json.loads(virgin_path.read_text(encoding="utf-8"))
    before = answered_map(virgin)
    answered_before = sum(1 for n in before.values() if n > 0)

    now = datetime.now(timezone.utc)
    packet = set_time(now)

    print(f"virgin capture : {virgin_path}")
    print(f"                 {len(before)} probes, {answered_before} answered")
    print(f"will write     : {now.isoformat()}  (UTC)")
    print(f"packet         : {packet.hex(' ')}")
    print()

    if not args.confirm:
        print("Dry run. Nothing was sent. Re-run with --confirm to write the clock.")
        print("This is irreversible: the ring can never be un-set.")
        return 0

    collector = Collector()
    results: list[dict] = []

    print(f"connecting to {R06.name} @ {R06.address}")
    async with BleakClient(R06.address, timeout=CONNECT_TIMEOUT_S) as client:
        print(f"connected: {client.is_connected}")

        for uuid, name in CHANNELS.items():
            try:
                await client.start_notify(uuid, collector.handler(name))
            except Exception as exc:  # noqa: BLE001 - channel may not be notifiable
                print(f"subscribe FAILED on {name}: {exc!r}")

        collector.reset()
        await client.write_gatt_char(UART_RX_CHAR_UUID, packet, response=False)
        await asyncio.sleep(SETTLE_S)

        print(f"clock written. {len(collector.frames)} frame(s) in reply:")
        for frame in collector.frames:
            print(f"  {frame['channel']:<8} {frame['hex']}")
        print()

        for probe in build_reprobes(virgin):
            result = await run_probe(client, probe, collector)
            results.append(result)
            print(summarize(result))

        for uuid in CHANNELS:
            try:
                await client.stop_notify(uuid)
            except Exception:  # noqa: BLE001 - best effort on teardown
                pass

    out_path = args.out or FIXTURES / (
        f"post_clockset_hr_probe_{now.strftime('%Y%m%dT%H%M%S')}.json"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(
            {
                "captured_utc": now.isoformat(),
                "ring": {"name": R06.name, "address": R06.address},
                "note": "Captured immediately AFTER the first-ever clock write.",
                "clock_written_utc": now.isoformat(),
                "clock_packet_hex": packet.hex(" "),
                "compared_against": str(virgin_path),
                "probes": results,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    after = answered_map({"probes": results})
    appeared = [ts for ts, n in after.items() if n > 0 and before.get(ts, 0) == 0]
    vanished = [ts for ts, n in before.items() if n > 0 and after.get(ts, 1) == 0]

    print(f"\ncapture written: {out_path}")
    print(f"answered before: {answered_before} / {len(before)}")
    print(f"answered after : {sum(1 for n in after.values() if n > 0)} / {len(after)}")

    if appeared:
        print(f"\nData APPEARED at {len(appeared)} timestamp(s) that were empty before.")
        print("Reading: the ring was logging all along; the clock write made it")
        print("addressable. The buffer survived.")
    if vanished:
        print(f"\nData VANISHED at {len(vanished)} timestamp(s) that had data before.")
        print("Reading: the clock write wiped or re-based the buffer. Record this —")
        print("it is undocumented for this hardware and it changes sync design.")
    if not appeared and not vanished:
        print("\nNo change either way. Either the clock write did not take, or the")
        print("log is not addressed the way colmi_r02_client's hr.py describes.")

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
