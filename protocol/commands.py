"""QRing command construction and the GATT interface contract.

SCAFFOLD. Signatures only; Abhi writes the bodies.

This module is the ring's *control* surface — what the hub asks the ring to do.
`packets.py` is the *data* surface — what the ring says back. Keeping them apart
means Architecture B's satellite can reuse command construction without ever
touching a parser, which is what "dumb radio, smart hub" actually requires.
"""

from __future__ import annotations

from datetime import datetime
from protocol.packets import build_packet

# --- GATT interface --------------------------------------------------------
# CONFIRMED by enumeration of R06_D29C on 2026-08-02. Lowercase deliberately: bleak
# normalizes characteristic UUIDs to lowercase, so a naive `==` against an uppercase
# literal silently never matches. Casefold both sides if you ever compare by hand.
#
# Command channel — short fixed-length packets (see packets.PACKET_LEN).
UART_SERVICE_UUID = "6e40fff0-b5a3-f393-e0a9-e50e24dcca9e"
UART_RX_CHAR_UUID = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"   # hub writes here
UART_TX_CHAR_UUID = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"   # ring notifies here

# Second vendor service, same notify/write shape, found during the same enumeration.
# TODO(Abhi): identify what rides on this channel. Working hypothesis — two
# identically-shaped channels usually means short commands on one and bulk transfer on
# the other, so this is the likely home of large history dumps (sleep records, and any
# raw-waveform access later). Confirm against Gadgetbridge's Colmi/Yawell classes
# before assuming sleep data arrives on UART_TX_CHAR_UUID and concluding the parser is
# broken when it never shows up.
BULK_SERVICE_UUID = "de5bf728-d711-4e47-af26-65e3012a5dc7"
BULK_RX_CHAR_UUID = "de5bf72a-d711-4e47-af26-65e3012a5dc7"   # hub writes here
BULK_TX_CHAR_UUID = "de5bf729-d711-4e47-af26-65e3012a5dc7"   # ring notifies here

# CONFIRMED 2026-08-02 by round trip against R06_D29C: sending 0x03 returned
# `03 50 00 ... 00 53` — the ring echoes the command byte in position 0, so every
# reply is self-identifying and a single notify handler can dispatch on byte[0].
CMD_BATTERY = 0x03

# TODO(confirm): still unverified. Read it out of colmi_r02_client — and see the
# DANGER note on set_time() before sending this one to R06_D29C.
CMD_SET_TIME = 0x01


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
    return build_packet(CMD_BATTERY)


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
