"""Ingest a saved capture into the SQLite store.

The offline half of the pipeline: capture JSON -> parser -> database, with no radio
involved. Iterating storage against a file is faster than against a ring, costs no
battery, and gives byte-identical input every run — which is what makes the idempotency
claim testable rather than aspirational.

    .venv/bin/python -m tools.ingest_capture protocol/fixtures/first_real_hr_20260809.json
    .venv/bin/python -m tools.ingest_capture <file> --db /tmp/scratch.db

Run it twice on the same capture. The second run should report 0 new samples.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from hub import db
from hub.config import R06
from protocol.packets import parse_heart_rate_log, parse_hr_log_ring_timestamp


def frames_of(probe: dict) -> tuple[bytes, ...]:
    return tuple(
        bytes.fromhex(f["hex"].replace(" ", "")) for f in probe["frames"]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path)
    parser.add_argument("--db", type=Path, default=None, help="override the store path")
    args = parser.parse_args()

    capture = json.loads(args.capture.read_text(encoding="utf-8"))
    probes = capture["probes"]

    conn = db.connect(args.db)
    source_id = db.ensure_source(conn, R06)
    run_id = db.start_sync_run(conn, source_id)

    total_new = 0
    total_parsed = 0
    total_frames = 0
    stored_frames = 0
    ring_clock_utc: str | None = None

    try:
        for probe in probes:
            frames = frames_of(probe)
            # Every frame is archived, including no-data sentinels and unsolicited
            # pushes — a frame you discard is a frame you cannot re-read. `seq` is
            # unique per run, so it advances across probes rather than restarting.
            stored_frames += db.store_raw_payloads(
                conn, run_id, frames, seq_start=total_frames
            )
            total_frames += len(frames)

            if len(frames) <= 1:
                continue

            day_start = datetime.fromtimestamp(probe["requested_ts"], timezone.utc)
            samples = parse_heart_rate_log(frames, db.to_iso_utc(day_start))
            total_parsed += len(samples)
            total_new += db.insert_samples(conn, source_id, samples)

            echoed = parse_hr_log_ring_timestamp(frames)
            if echoed is not None:
                ring_clock_utc = db.to_iso_utc(
                    datetime.fromtimestamp(echoed, timezone.utc)
                )
    except Exception as exc:  # noqa: BLE001 - the run must be recorded either way
        db.finish_sync_run(conn, run_id, "parse_error", total_new, note=repr(exc))
        raise

    db.finish_sync_run(
        conn,
        run_id,
        "ok",
        rows_ingested=total_new,
        ring_clock_utc=ring_clock_utc,
        note=f"offline ingest of {args.capture.name}",
    )

    print(f"capture      : {args.capture}")
    print(f"probes       : {len(probes)}  frames: {total_frames}")
    print(f"archived     : {stored_frames} raw frames")
    print(f"parsed       : {total_parsed} samples")
    print(f"newly stored : {total_new}")
    if stored_frames != total_frames:
        print(f"    WARNING  : {total_frames - stored_frames} frames not archived")
    if total_parsed and not total_new:
        print("               (all already present - idempotent re-ingest)")

    print("\nstore summary:")
    for row in db.metric_days(conn, "heart_rate"):
        print(
            f"  {row['day']}  n={row['n']:<4} "
            f"min={row['lo']:.0f} max={row['hi']:.0f} mean={row['avg']:.1f} bpm"
        )

    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
