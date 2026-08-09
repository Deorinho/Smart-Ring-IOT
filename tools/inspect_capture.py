"""Decode a saved capture: verify the frame structure, then parse it into samples.

Runs entirely offline against a JSON file from `tools.probe_hr_log`, so the parser can
be iterated on without the ring, the radio, or a battery. That is the whole point of
archiving raw frames — a byte you misread in August is still on disk in December.

    .venv/bin/python -m tools.inspect_capture protocol/fixtures/first_real_hr_*.json
    .venv/bin/python -m tools.inspect_capture <file> --samples   # every reading

It reports structure before values, because a plausible-looking heart rate built on a
misread header is worse than an obvious failure.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from protocol.packets import (
    HR_VALUES_IN_FIRST_FRAME,
    HR_VALUES_PER_FRAME,
    NO_DATA_SUB_TYPE,
    parse_heart_rate_log,
    parse_hr_log_ring_timestamp,
)


def frames_of(probe: dict) -> list[bytes]:
    return [bytes.fromhex(f["hex"].replace(" ", "")) for f in probe["frames"]]


def report_structure(frames: list[bytes]) -> None:
    """Check the wire format against what protocol/packets.py assumes."""
    by_sub = {f[1]: f for f in frames if len(f) == 16}

    header = by_sub.get(0)
    if header is None:
        print("    no sub_type 0 header in this burst")
    else:
        declared, interval = header[2], header[3]
        print(f"    header       : {declared} frames declared, {interval}-min slots")
        if declared != len(frames):
            print(
                f"    NOTE         : header says {declared}, received {len(frames)} — "
                f"'declared' counts total frames, not frames-after-this"
            )

    data_subs = sorted(s for s in by_sub if s >= 1 and s != NO_DATA_SUB_TYPE)
    if data_subs:
        expected = list(range(1, max(data_subs) + 1))
        missing = [s for s in expected if s not in by_sub]
        print(f"    data frames  : sub_type {data_subs[0]}..{data_subs[-1]}")
        print(f"    missing      : {missing if missing else 'none'}")

        slots = HR_VALUES_IN_FIRST_FRAME + (len(data_subs) - 1) * HR_VALUES_PER_FRAME
        print(f"    slot capacity: {slots}  (288 = a full 24 h at 5-min slots)")

    ring_ts = parse_hr_log_ring_timestamp(tuple(frames))
    if ring_ts is not None:
        as_utc = datetime.fromtimestamp(ring_ts, timezone.utc)
        print(f"    ring's own ts: {ring_ts}  = {as_utc.isoformat()}")


def report_values(samples: tuple, show_all: bool) -> None:
    if not samples:
        print("    no non-zero samples")
        return

    values = [s.value for s in samples]
    print(
        f"    samples      : {len(samples)} non-zero   "
        f"min={min(values):.0f}  max={max(values):.0f}  "
        f"mean={sum(values) / len(values):.1f} bpm"
    )
    print(f"    first        : {samples[0].ts_utc}  {samples[0].value:.0f} bpm")
    print(f"    last         : {samples[-1].ts_utc}  {samples[-1].value:.0f} bpm")

    # Hourly means in LOCAL time — this is the display layer, and the only useful
    # question here is "does this look like a day in your life?"
    buckets: dict[int, list[float]] = defaultdict(list)
    for s in samples:
        local = datetime.fromisoformat(s.ts_utc.replace("Z", "+00:00")).astimezone()
        buckets[local.hour].append(s.value)

    print("\n    hourly mean (local time):")
    for hour in sorted(buckets):
        vals = buckets[hour]
        mean = sum(vals) / len(vals)
        bar = "#" * max(1, round((mean - 40) / 2))
        print(f"      {hour:02d}:00  {mean:5.1f}  n={len(vals):<2} {bar}")

    if show_all:
        print("\n    all samples:")
        for s in samples:
            local = datetime.fromisoformat(s.ts_utc.replace("Z", "+00:00")).astimezone()
            print(f"      {s.ts_utc}  ({local:%H:%M} local)  {s.value:.0f} bpm")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path)
    parser.add_argument("--samples", action="store_true", help="print every reading")
    args = parser.parse_args()

    capture = json.loads(args.capture.read_text(encoding="utf-8"))
    print(f"{args.capture}")
    print(f"captured {capture['captured_utc']}  ring {capture['ring']['name']}\n")

    interesting = [p for p in capture["probes"] if p["frame_count"] > 1]
    if not interesting:
        print("No probe returned more than one frame — nothing but no-data sentinels.")
        return 0

    for probe in interesting:
        day_start = datetime.fromtimestamp(probe["requested_ts"], timezone.utc)
        day_start_utc = day_start.strftime("%Y-%m-%dT%H:%M:%SZ")
        print(f"  {day_start_utc}  ({probe['frame_count']} frames)")

        frames = frames_of(probe)
        report_structure(frames)
        report_values(parse_heart_rate_log(tuple(frames), day_start_utc), args.samples)
        print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
