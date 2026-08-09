"""Probe R06_D29C's heart-rate log across candidate epochs and capture everything.

Session 3's instrument. The ring's RTC has never been set, and the log is addressed by
absolute Unix timestamp (colmi_r02_client `hr.py`, MIT) — so "which timestamps hold
data?" is an open question, and "no reply" is indistinguishable from "wrong opcode"
until something answers.

This script fires the same request at a spread of candidate timestamps, records every
frame that comes back, and writes the lot to JSON. It is deliberately dumb: it does not
parse heart-rate values, because the byte layout is unconfirmed and a wrong parse would
hide the raw evidence. Bytes first, meaning later.

Three properties that matter, all learned the hard way on 2026-08-08:

  * **The capture is always written.** The first version lost an entire run when the
    ring dropped the link mid-probe and the exception escaped before the file was
    saved. Persistence now lives in a `finally`; a crashed run still leaves evidence.
  * **Disconnects are survivable.** A ring on a nearly-flat battery drops the link.
    Each probe gets one reconnect attempt before being recorded as failed, and the run
    continues instead of dying.
  * **Both vendor notify characteristics are subscribed**, and every frame is tagged
    with its channel and a run-global sequence number — so a straggler misattributed
    to the following probe is visible rather than silently believed.

SAFETY: this script never sets the ring's clock. It does not import `set_time`, and it
must not be edited to. Dump first; the clock is a one-way door.

Run from the repo root:
    .venv/bin/python -m tools.probe_hr_log
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from bleak import BleakClient

from hub.config import R06
from protocol.commands import (
    BULK_TX_CHAR_UUID,
    CMD_READ_HEART_RATE,
    UART_RX_CHAR_UUID,
    UART_TX_CHAR_UUID,
)
from protocol.packets import build_packet, is_valid, parse_command_id

# A probe is done when no new frame has arrived for QUIET_S, or CAP_S total elapses.
# Quiet-detection rather than the documented frame count, because the frame count is
# exactly the thing being verified.
QUIET_S = 1.5
CAP_S = 8.0
POLL_S = 0.1
CONNECT_TIMEOUT_S = 20.0

CHANNELS = {
    UART_TX_CHAR_UUID: "command",
    BULK_TX_CHAR_UUID: "bulk",
}


class Collector:
    """Accumulates notification frames for one probe.

    `seq` is global across the whole run and never resets. A frame that belongs to the
    previous probe but arrives after this one started will carry a low `offset_ms` and
    an out-of-place `seq`, which is what makes straggler bleed detectable instead of
    quietly wrong.
    """

    def __init__(self) -> None:
        self.frames: list[dict] = []
        self.last_at: float = 0.0
        self._t0: float = time.monotonic()
        self._seq: int = 0

    def reset(self) -> None:
        self.frames = []
        self.last_at = 0.0
        self._t0 = time.monotonic()

    def handler(self, channel: str):
        def on_notify(_sender, data: bytearray) -> None:
            raw = bytes(data)
            self.last_at = time.monotonic()
            self._seq += 1
            self.frames.append(
                {
                    "seq": self._seq,
                    "channel": channel,
                    "offset_ms": round((self.last_at - self._t0) * 1000),
                    "hex": raw.hex(" "),
                    "len": len(raw),
                    "command_id": parse_command_id(raw) if raw else None,
                    "sub_type": raw[1] if len(raw) > 1 else None,
                    "checksum_ok": is_valid(raw),
                }
            )

        return on_notify


def build_probes(days_back: int) -> list[dict]:
    """Candidate timestamps to address the log with.

    **UTC midnight, not local.** The ring's RTC is written in UTC
    (`commands.set_time`), so its day boundaries are UTC ones. Probing local midnight
    asks for a point four hours into the ring's day here, which is the wrong day for
    anything recorded in that window. Earlier captures in `protocol/fixtures/` used
    local midnight and are labelled as such.

    The factory epochs remain in the set: they cover the case of an RTC that was never
    set, and they cost two seconds each.
    """
    midnight = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    probes: list[dict] = []
    for d in range(days_back + 1):
        day = midnight - timedelta(days=d)
        probes.append(
            {
                "label": f"UTC midnight -{d}d ({day.date()})",
                "ts": int(day.timestamp()),
            }
        )

    for name, base in (("1970-01-01", 0), ("2000-01-01", 946684800)):
        for d in (0, 1, 2):
            probes.append(
                {
                    "label": f"factory epoch {name} +{d}d",
                    "ts": base + d * 86400,
                }
            )

    return probes


async def run_probe(client: BleakClient, probe: dict, collector: Collector) -> dict:
    """Send one log request and collect whatever comes back."""
    collector.reset()
    request = build_packet(CMD_READ_HEART_RATE, probe["ts"].to_bytes(4, "little"))

    await client.write_gatt_char(UART_RX_CHAR_UUID, request, response=False)

    deadline = time.monotonic() + CAP_S
    while time.monotonic() < deadline:
        await asyncio.sleep(POLL_S)
        if collector.frames and (time.monotonic() - collector.last_at) > QUIET_S:
            break

    return {
        "label": probe["label"],
        "requested_ts": probe["ts"],
        # UTC, matching how the probe was built — rendering this in local time made a
        # correct UTC-midnight request look like it landed on the previous evening.
        "requested_iso": datetime.fromtimestamp(
            probe["ts"], timezone.utc
        ).isoformat(),
        "request_hex": request.hex(" "),
        "frame_count": len(collector.frames),
        "frames": collector.frames,
    }


async def connect_and_subscribe(collector: Collector) -> BleakClient:
    """Fresh connection with both vendor notify channels subscribed."""
    client = BleakClient(R06.address, timeout=CONNECT_TIMEOUT_S)
    await client.connect()
    for uuid, name in CHANNELS.items():
        try:
            await client.start_notify(uuid, collector.handler(name))
        except Exception as exc:  # noqa: BLE001 - channel may not be notifiable
            print(f"  subscribe FAILED on {name}: {exc!r}")
    return client


def summarize(result: dict) -> str:
    if "error" in result:
        return f"  {result['label']:<40} ERROR {result['error']}"

    n = result["frame_count"]
    if n == 0:
        return f"  {result['label']:<40} no reply"

    first = result["frames"][0]
    channels = {f["channel"] for f in result["frames"]}
    bad = sum(1 for f in result["frames"] if not f["checksum_ok"])

    return (
        f"  {result['label']:<40} {n:>2}f {'+'.join(sorted(channels)):<7} "
        f"sub={first['sub_type']} @{first['offset_ms']}ms bad={bad}\n"
        f"      {first['hex']}"
    )


def write_capture(path: Path, results: list[dict]) -> None:
    """Always called, including on failure. The capture is the whole point."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "captured_utc": datetime.now(timezone.utc).isoformat(),
                "ring": {"name": R06.name, "address": R06.address},
                "note": (
                    "Factory-virgin R06: RTC never set at capture time. "
                    "Clock NOT written."
                ),
                "command": {
                    "name": "CMD_READ_HEART_RATE",
                    "value": CMD_READ_HEART_RATE,
                },
                "probes": results,
            },
            indent=2,
        ),
        encoding="utf-8",
    )


async def run_all(probes: list[dict], collector: Collector, results: list[dict]) -> None:
    """Probe every timestamp, reconnecting once per probe if the link drops."""
    client: BleakClient | None = None
    try:
        for probe in probes:
            result: dict | None = None
            for attempt in (1, 2):
                try:
                    if client is None or not client.is_connected:
                        if attempt == 2:
                            print("  (link dropped, reconnecting)")
                        client = await connect_and_subscribe(collector)
                    result = await run_probe(client, probe, collector)
                    break
                except Exception as exc:  # noqa: BLE001 - recorded, not raised
                    client = None
                    if attempt == 2:
                        result = {
                            "label": probe["label"],
                            "requested_ts": probe["ts"],
                            "frame_count": 0,
                            "frames": [],
                            "error": f"{type(exc).__name__}: {exc}",
                        }

            if result is not None:
                results.append(result)
                print(summarize(result))
    finally:
        if client is not None and client.is_connected:
            try:
                await client.disconnect()
            except Exception:  # noqa: BLE001 - best effort on teardown
                pass


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days-back", type=int, default=8, help="local days to probe")
    parser.add_argument("--out", type=Path, default=None, help="capture file path")
    parser.add_argument(
        "--dry-run", action="store_true", help="print the probe plan and exit"
    )
    args = parser.parse_args()

    probes = build_probes(args.days_back)

    if args.dry_run:
        print(f"{len(probes)} probes planned:")
        for p in probes:
            print(f"  {p['ts']:>12}  {p['label']}")
        return 0

    out_path = args.out or Path("protocol/fixtures") / (
        f"virgin_hr_probe_{datetime.now().strftime('%Y%m%dT%H%M%S')}.json"
    )

    collector = Collector()
    results: list[dict] = []

    print(f"probing {R06.name} @ {R06.address}\n")
    try:
        await run_all(probes, collector, results)
    finally:
        # Unconditional: a run that crashed still produced evidence worth keeping.
        write_capture(out_path, results)
        print(f"\ncapture written: {out_path}  ({len(results)} probes recorded)")

    answered = [r for r in results if r["frame_count"] > 0]
    errored = [r for r in results if "error" in r]

    print(f"{len(answered)} of {len(results)} probes answered, {len(errored)} errored")
    if answered:
        print("\nProbes that returned data:")
        for r in answered:
            print(
                f"  {r['requested_iso']}  ({r['requested_ts']})  "
                f"{r['frame_count']} frames"
            )
    else:
        print("\nNo probe returned anything. Candidate conclusions, in order:")
        print("  1. A virgin ring does not log until its clock is set.")
        print("  2. The buffer did not survive the battery reaching 1%.")
        print("  3. CMD_READ_HEART_RATE (0x15) is wrong for this firmware.")
        print("  4. The payload encoding is not a 4-byte LE Unix timestamp.")

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
