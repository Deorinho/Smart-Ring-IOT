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

# From colmi_r02_client (MIT) `hr.py`, 2026-08-08. Not yet exercised against this ring.
CMD_READ_HEART_RATE = 0x15   # 21

# TODO(confirm): still unverified. Cross-check colmi_r02_client `set_time.py` — and see
# the DANGER note on set_time() before sending this one to R06_D29C.
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


def request_heart_rate_log(day_start: datetime) -> bytes:
    """Request the stored HR log for one day, addressed by absolute timestamp.

    Payload is a **4-byte little-endian Unix timestamp** for midnight of the target
    day (colmi_r02_client `hr.py`, MIT). There is NO day-offset form — the ring is
    asked for a point on its own timeline, not "N days ago".

    That matters more here than it would on any other ring. **R06_D29C's RTC has never
    been set**, so its timeline does not start where real-world time starts. Asking for
    midnight on a 2026 date may address a region of the ring's log that does not exist,
    and the ring will simply return nothing — which looks identical to a wrong opcode.

    Probing strategy until the ring's epoch is known: try real midnight first, then
    Unix 0, then 946684800 (2000-01-01), walking forward a few days from each. The
    first response that arrives carries a 4-byte timestamp in its sub_type-1 packet —
    that field reveals the ring's frame of reference, and everything else follows.

    If nothing lands at any epoch, that is itself the finding: a virgin ring may not
    log at all until its clock is set. Record it and set the clock deliberately.
    """
    raise NotImplementedError


def request_sleep_log(day_start: datetime) -> bytes:
    """Request the stored sleep record for one day.

    **colmi_r02_client does not implement sleep at all** — there is no `sleep.py` in
    that package. Gadgetbridge's Colmi/Yawell classes are the only reference, and the
    opcode is unknown.

    Two hypotheses worth testing before assuming this command exists in this form:
    sleep may ride the second vendor service (`BULK_*` below) rather than the command
    channel, and the addressing may not be per-day at all. Signature mirrors
    `request_heart_rate_log` for now; change it once the real shape is known.
    """
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

    Reference: colmi_r02_client `hr_settings.py` (MIT) covers the HR logging interval,
    which is the single biggest battery lever. It has no SpO2/stress/HRV equivalents —
    those come from Gadgetbridge or from observing the QRing app against the R09.
    See also their `real_time.py`: that is the continuous-streaming mode, by far the
    most expensive thing the hardware can do. Read it to know what never to enable.
    """
    raise NotImplementedError
