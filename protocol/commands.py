"""QRing command construction and the GATT interface contract.

SCAFFOLD. Signatures only; Abhi writes the bodies.

This module is the ring's *control* surface — what the hub asks the ring to do.
`packets.py` is the *data* surface — what the ring says back. Keeping them apart
means Architecture B's satellite can reuse command construction without ever
touching a parser, which is what "dumb radio, smart hub" actually requires.
"""

from __future__ import annotations

from datetime import datetime

# --- GATT interface --------------------------------------------------------
# TODO(confirm by enumeration): these are the QRing-family UUIDs reported by
# community tooling. Enumerate R06_D29C with nRF Connect or bleak's
# `BleakClient.services` and confirm before writing a single byte to the ring.
# Writing commands to a guessed characteristic is how you find out the hard way.
UART_SERVICE_UUID = "6E40FFF0-B5A3-F393-E0A9-E50E24DCCA9E"
UART_RX_CHAR_UUID = "6E400002-B5A3-F393-E0A9-E50E24DCCA9E"   # hub writes here
UART_TX_CHAR_UUID = "6E400003-B5A3-F393-E0A9-E50E24DCCA9E"   # ring notifies here

# TODO(confirm): command opcodes. Read them out of colmi_r02_client rather than
# trusting this comment.
CMD_SET_TIME = 0x01
CMD_BATTERY = 0x03


def set_time(now_utc: datetime) -> bytes:
    """Build the packet that sets the ring's RTC.

    DANGER — read CLAUDE.md before calling this on R06_D29C. The ring is
    factory-virgin and its clock has never been set. The raw log MUST be dumped
    first: setting the time is a one-way door, and some firmware wipes the buffer on
    a clock write. This is the only chance to observe how a never-paired ring
    timestamps its own data.

    Note the ring likely expects LOCAL time, not UTC, because the vendor app sets it
    from the phone's wall clock. Confirm which, then convert exactly once here — the
    rest of the system stays UTC end to end.
    """
    raise NotImplementedError


def request_battery() -> bytes:
    """Build the battery-status request. The cheapest end-to-end round trip, so this
    is the right first command to prove the write/notify path works."""
    raise NotImplementedError


def request_heart_rate_log(day_offset: int) -> bytes:
    """Request the stored HR log for a day, where 0 is today and 1 is yesterday.

    How far back `day_offset` can usefully go IS the buffer-depth measurement that
    gates Architecture B. Walk it backwards until the ring returns nothing and record
    the answer — the ring went on 2026-08-02 00:30 local having never synced.
    """
    raise NotImplementedError


def request_sleep_log(day_offset: int) -> bytes:
    """Request the stored sleep record for a day. Same offset convention as above."""
    raise NotImplementedError


def set_sensing_policy(
    hr_interval_minutes: int,
    spo2_enabled: bool,
    stress_enabled: bool,
    hrv_enabled: bool,
) -> tuple[bytes, ...]:
    """Build the packets that configure the ring's automatic sensing schedule.

    This is the battery contract in CLAUDE.md, expressed as bytes. The hub writes it
    on every connect so the ring's power budget is a thing under version control
    rather than a thing you hope stayed put.

    Returns several packets because each knob is typically its own command. Order them
    so that a partial failure leaves the ring MORE conservative, not less — turn
    expensive sensing off first, set intervals after.
    """
    raise NotImplementedError
