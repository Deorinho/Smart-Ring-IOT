"""BLE sync service — connect to the ring, pull what it has, store it, disconnect.

Run once per invocation and exit. A systemd timer supplies the schedule, so this is a
script rather than a daemon: no long-lived connection to leak, no scheduler to debug,
and every run is a discrete journald event you can point at.

**Hub-only.** This is the one module that touches BlueZ, so it is expected to fail
immediately on Windows — that is the portable/hub-only boundary working, not a bug.

Design rules it exists to honour (CLAUDE.md):

* **The hub owns the ring's sensing schedule** and writes it on every connect, so the
  power budget is version-controlled rather than whatever was last set by hand.
* **Every await has a timeout.** An unbounded wait on a radio is a hang you cannot SSH
  into, and this runs unattended.
* **Every attempt is recorded**, successful or not. A store that only remembers
  successes cannot tell you the ring has been unreachable for two days.
* **Idempotent by construction** — re-pulling a day already stored costs nothing, so
  the service always asks for a few days back rather than tracking what it has.

    python -m hub.sync              # one attempt, then exit
    python -m hub.sync --force      # ignore the minimum-interval guard
    python -m hub.sync --days 7     # reach further back
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import time
from datetime import datetime, timedelta, timezone

from bleak import BleakClient, BleakScanner

from hub import db
from hub.config import (
    CONNECT_TIMEOUT_S,
    DEFAULT_SENSING,
    MIN_SECONDS_BETWEEN_SYNCS,
    R06,
    REPLY_CAP_S,
    REPLY_QUIET_S,
    SCAN_TIMEOUT_S,
    SYNC_DAYS_BACK,
    SYNC_TIMEOUT_S,
    Ring,
)
from protocol.commands import (
    BULK_TX_CHAR_UUID,
    UART_RX_CHAR_UUID,
    UART_TX_CHAR_UUID,
    request_battery,
    request_heart_rate_log,
    request_hr_log_settings,
    set_hr_log_settings,
)
from protocol.packets import (
    Sample,
    is_valid,
    parse_battery,
    parse_command_id,
    parse_heart_rate_log,
    parse_hr_log_settings,
)

log = logging.getLogger("ring-sync")

POLL_S = 0.1


class FrameCollector:
    """Gathers notification frames from both vendor channels.

    Keeps everything, including frames nobody asked for. The ring pushes unsolicited
    status (`0x73`) and at least one undocumented frame (`0x2f`), so a collector that
    only kept expected replies would quietly discard evidence — and `raw_payloads`
    exists precisely to keep it.
    """

    def __init__(self) -> None:
        self.all_frames: list[bytes] = []
        self._window: list[bytes] = []
        self._last_at = 0.0

    def handler(self, _sender, data: bytearray) -> None:
        frame = bytes(data)
        self._last_at = time.monotonic()
        self.all_frames.append(frame)
        self._window.append(frame)
        if not is_valid(frame):
            log.warning("bad checksum, kept anyway: %s", frame.hex(" "))

    def open_window(self) -> None:
        self._window = []
        self._last_at = 0.0

    @property
    def window(self) -> list[bytes]:
        return list(self._window)

    @property
    def quiet_for(self) -> float:
        return time.monotonic() - self._last_at if self._last_at else 0.0


async def exchange(
    client: BleakClient, collector: FrameCollector, request: bytes
) -> list[bytes]:
    """Send one command and return the frames that answered it.

    Filters the reply on the echoed command byte. The ring's replies are
    self-identifying, so an unsolicited push landing mid-exchange is separated out
    rather than mistaken for the answer — which has already happened once during
    manual probing.
    """
    collector.open_window()
    await client.write_gatt_char(UART_RX_CHAR_UUID, request, response=False)

    deadline = time.monotonic() + REPLY_CAP_S
    while time.monotonic() < deadline:
        await asyncio.sleep(POLL_S)
        if collector.window and collector.quiet_for > REPLY_QUIET_S:
            break
    else:
        log.warning("no quiet period within %.0fs for cmd 0x%02x", REPLY_CAP_S, request[0])

    want = request[0]
    return [f for f in collector.window if f and parse_command_id(f) == want]


async def apply_sensing_policy(client: BleakClient, collector: FrameCollector) -> None:
    """Write the hub's sensing schedule, but only when it differs.

    Reading first costs one round trip and avoids a pointless flash write on every
    sync. It also logs drift: if the ring's settings ever change without the hub doing
    it, that shows up here rather than as an unexplained battery cliff.
    """
    reply = await exchange(client, collector, request_hr_log_settings())
    if not reply:
        log.warning("no reply to HR settings read; skipping policy write")
        return

    current = parse_hr_log_settings(reply[0])
    wanted_interval = DEFAULT_SENSING.hr_interval_minutes
    if current.enabled and current.interval_minutes == wanted_interval:
        log.info("sensing policy already correct (HR every %d min)", wanted_interval)
        return

    log.info(
        "sensing policy drift: ring has enabled=%s interval=%d, writing enabled=True "
        "interval=%d",
        current.enabled,
        current.interval_minutes,
        wanted_interval,
    )
    await exchange(
        client,
        collector,
        set_hr_log_settings(enabled=True, interval_minutes=wanted_interval),
    )


async def pull_battery(
    client: BleakClient, collector: FrameCollector, now: datetime
) -> list[Sample]:
    """Read the battery and turn it into stored samples.

    Recording this is what eventually replaces the vendor app's low-battery warning
    (Bug_Backlog R-009): a percentage nobody writes down cannot be alerted on, and the
    ring has already run itself flat unnoticed once.

    Returns two samples sharing one timestamp: the percentage, and the charging flag as
    `battery_charging` (1 or 0). The shared `ts_utc` is load-bearing rather than
    incidental -- the dashboard only believes the charging state when its timestamp
    matches the percentage's, because nothing polls the ring and both readings are only
    ever as fresh as the sync that produced them. Writing them at different instants
    would let a charging flag from one sync be rendered beside a percentage from another.

    The flag rides the generic scalar table as a 0/1 rather than getting a column of its
    own: `samples` is keyed by (source, metric, ts_utc) precisely so a new scalar costs
    nothing, and a boolean is a scalar.
    """
    reply = await exchange(client, collector, request_battery())
    if not reply:
        log.warning("no battery reply")
        return []

    percent, charging = parse_battery(reply[0])
    log.info("battery %d%% (%s)", percent, "charging" if charging else "on battery")
    ts = db.to_iso_utc(now)
    return [
        Sample("battery", ts, float(percent)),
        Sample("battery_charging", ts, 1.0 if charging else 0.0),
    ]


async def pull_heart_rate(
    client: BleakClient, collector: FrameCollector, days_back: int, now: datetime
) -> list[Sample]:
    """Request the HR log for today and the previous `days_back` UTC days.

    UTC midnight, not local: the ring's RTC is written in UTC so its day boundaries are
    UTC ones. Asking at local midnight requests a point several hours into the ring's
    day and silently returns the wrong day's data.
    """
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    samples: list[Sample] = []

    for offset in range(days_back + 1):
        day = midnight - timedelta(days=offset)
        frames = await exchange(client, collector, request_heart_rate_log(day))
        if not frames:
            log.warning("no reply for %s", day.date())
            continue

        parsed = parse_heart_rate_log(tuple(frames), db.to_iso_utc(day))
        log.info("%s: %d frames -> %d samples", day.date(), len(frames), len(parsed))
        samples.extend(parsed)

    return samples


async def sync_once(ring: Ring, days_back: int, force: bool) -> int:
    """One full attempt. Returns a process exit code.

    Exits 0 when the ring simply isn't there. An unreachable ring is the normal case
    several times a day — it is on a hand that leaves the house — and a timer unit that
    reports failure every time you go to work trains you to ignore it.
    """
    conn = db.connect()
    source_id = db.ensure_source(conn, ring)

    last_ok = db.last_ok_sync_utc(conn, source_id)
    if last_ok and not force:
        age = (
            datetime.now(timezone.utc)
            - datetime.strptime(last_ok, db.ISO_UTC).replace(tzinfo=timezone.utc)
        ).total_seconds()
        if age < MIN_SECONDS_BETWEEN_SYNCS:
            log.info("last sync %.0fs ago, under the guard; skipping", age)
            conn.close()
            return 0

    log.info("scanning for %s", ring.name)
    try:
        device = await BleakScanner.find_device_by_address(
            ring.address, timeout=SCAN_TIMEOUT_S
        )
    except Exception as exc:  # noqa: BLE001 - no adapter is a recordable state
        # Bug_Backlog R-005: the Bluetooth stack initialises ~43 s into boot on this
        # hub, so a timer firing early meets no adapter at all. Scanning must not be
        # able to crash the process — this is the exact failure that looks like
        # "works by hand, never after a reboot".
        log.error("scan failed, adapter may not be ready: %r", exc)
        run_id = db.start_sync_run(conn, source_id)
        db.finish_sync_run(conn, run_id, "ble_error", note=f"scan failed: {exc!r}")
        conn.close()
        return 1

    if device is None:
        log.info("%s not found; nothing to do", ring.name)
        run_id = db.start_sync_run(conn, source_id)
        db.finish_sync_run(conn, run_id, "no_device", note="not seen in scan")
        conn.close()
        return 0

    run_id = db.start_sync_run(conn, source_id)
    collector = FrameCollector()
    now = datetime.now(timezone.utc)

    try:
        async with BleakClient(device, timeout=CONNECT_TIMEOUT_S) as client:
            log.info("connected")
            for uuid, name in ((UART_TX_CHAR_UUID, "command"), (BULK_TX_CHAR_UUID, "bulk")):
                try:
                    await client.start_notify(uuid, collector.handler)
                except Exception as exc:  # noqa: BLE001 - bulk may not be notifiable
                    log.warning("subscribe failed on %s: %r", name, exc)

            await apply_sensing_policy(client, collector)
            samples = await pull_battery(client, collector, now)
            samples += await pull_heart_rate(client, collector, days_back, now)

        stored = db.insert_samples(conn, source_id, samples)
        db.store_raw_payloads(conn, run_id, collector.all_frames)
        db.finish_sync_run(
            conn,
            run_id,
            "ok",
            rows_ingested=stored,
            note=f"{len(collector.all_frames)} frames, {len(samples)} parsed",
        )
        log.info("stored %d new of %d parsed samples", stored, len(samples))
        return 0

    except asyncio.TimeoutError:
        db.store_raw_payloads(conn, run_id, collector.all_frames)
        db.finish_sync_run(conn, run_id, "ble_error", note="timeout")
        log.error("sync timed out")
        return 1
    except Exception as exc:  # noqa: BLE001 - recorded, then re-raised for journald
        # Archive first: frames already received are evidence about the failure, and
        # discarding them because the run ended badly is exactly backwards.
        db.store_raw_payloads(conn, run_id, collector.all_frames)
        db.finish_sync_run(conn, run_id, "ble_error", note=repr(exc))
        log.exception("sync failed")
        return 1
    finally:
        conn.close()


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=SYNC_DAYS_BACK)
    parser.add_argument(
        "--force", action="store_true", help="ignore the minimum-interval guard"
    )
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )

    try:
        return await asyncio.wait_for(
            sync_once(R06, args.days, args.force), timeout=SYNC_TIMEOUT_S
        )
    except asyncio.TimeoutError:
        log.error("whole sync exceeded %.0fs", SYNC_TIMEOUT_S)
        return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
