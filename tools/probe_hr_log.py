"""Probe R06_D29C's heart-rate log across candidate epochs and capture everything.

Session 3's instrument. The ring's RTC has never been set, and the log is addressed by
absolute Unix timestamp (colmi_r02_client `hr.py`, MIT) — so "which timestamps hold
data?" is an open question, and "no reply" is indistinguishable from "wrong opcode"
until something answers.

This script fires the same request at a spread of candidate timestamps, records every
frame that comes back, and writes the lot to JSON. It is deliberately dumb: it does not
parse heart-rate values, because the byte layout is unconfirmed and a wrong parse would
hide the raw evidence. Bytes first, meaning later.

Two things it does that matter:

  * It subscribes to BOTH vendor notify characteristics and tags each frame with the
    channel it arrived on. Nothing upstream knows the second service exists; if the log
    arrives there, this run finds out.
  * It writes a capture file. R06_D29C is factory-virgin exactly once — whatever these
    bytes say about how a never-time-set ring stamps its data is unrepeatable.

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
from protocol.packets import is_valid, parse_command_id, build_packet

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

    Frames are tagged with arrival time and channel so the capture shows ordering and
    which service answered — both unknown going in.
    """

    def __init__(self) -> None:
        self.frames: list[dict] = []
        self.last_at: float = 0.0
        self._t0: float = time.monotonic()

    def reset(self) -> None:
        self.frames = []
        self.last_at = 0.0
        self._t0 = time.monotonic()

    def handler(self, channel: str):
        def on_notify(_sender, data: bytearray) -> None:
            raw = bytes(data)
            self.last_at = time.monotonic()
            self.frames.append(
                {
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

    Local midnight for the recent past is what the vendor app would use. The factory
    epochs cover the real possibility that an unset RTC never left its default, in
    which case the ring's data lives near 1970 or 2000 rather than near today.
    """
    now_local = datetime.now().astimezone()
    midnight = now_local.replace(hour=0, minute=0, second=0, microsecond=0)

    probes: list[dict] = []
    for d in range(days_back + 1):
        day = midnight - timedelta(days=d)
        probes.append(
            {
                "label": f"local midnight -{d}d ({day.date()})",
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
        "requested_iso": datetime.fromtimestamp(probe["ts"]).isoformat(),
        "request_hex": request.hex(" "),
        "frame_count": len(collector.frames),
        "frames": collector.frames,
    }


def summarize(result: dict) -> str:
    n = result["frame_count"]
    if n == 0:
        return f"  {result['label']:<40} no reply"

    channels = {f["channel"] for f in result["frames"]}
    bad = sum(1 for f in result["frames"] if not f["checksum_ok"])
    first = result["frames"][0]
    # In the documented layout, byte[2] of the sub_type-0 frame is how many follow.
    declared = "?"
    raw_first = bytes.fromhex(first["hex"].replace(" ", ""))
    if first["sub_type"] == 0 and len(raw_first) > 2:
        declared = raw_first[2]

    return (
        f"  {result['label']:<40} {n:>3} frames  "
        f"channel={'+'.join(sorted(channels))}  "
        f"declared_follow={declared}  bad_checksum={bad}"
    )


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
    out_path.parent.mkdir(parents=True, exist_ok=True)

    collector = Collector()
    results: list[dict] = []

    print(f"connecting to {R06.name} @ {R06.address}")
    async with BleakClient(R06.address, timeout=CONNECT_TIMEOUT_S) as client:
        print(f"connected: {client.is_connected}\n")

        # Listen on both vendor channels before sending anything.
        for uuid, name in CHANNELS.items():
            try:
                await client.start_notify(uuid, collector.handler(name))
                print(f"subscribed: {name} ({uuid})")
            except Exception as exc:  # noqa: BLE001 - channel may not be notifiable
                print(f"subscribe FAILED on {name}: {exc!r}")
        print()

        for probe in probes:
            result = await run_probe(client, probe, collector)
            results.append(result)
            print(summarize(result))

        for uuid in CHANNELS:
            try:
                await client.stop_notify(uuid)
            except Exception:  # noqa: BLE001 - best effort on teardown
                pass

    capture = {
        "captured_utc": datetime.now(timezone.utc).isoformat(),
        "ring": {"name": R06.name, "address": R06.address},
        "note": "Factory-virgin R06: RTC never set at capture time. Clock NOT written.",
        "command": {"name": "CMD_READ_HEART_RATE", "value": CMD_READ_HEART_RATE},
        "probes": results,
    }
    out_path.write_text(json.dumps(capture, indent=2), encoding="utf-8")

    answered = [r for r in results if r["frame_count"] > 0]
    print(f"\ncapture written: {out_path}")
    print(f"{len(answered)} of {len(results)} probes answered")
    if answered:
        print("\nProbes that returned data:")
        for r in answered:
            print(f"  {r['requested_iso']}  ({r['requested_ts']})  {r['frame_count']} frames")
    else:
        print("\nNo probe returned anything. Candidate conclusions, in order:")
        print("  1. A virgin ring does not log until its clock is set.")
        print("  2. CMD_READ_HEART_RATE (0x15) is wrong for this firmware.")
        print("  3. The payload encoding is not a 4-byte LE Unix timestamp.")

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
