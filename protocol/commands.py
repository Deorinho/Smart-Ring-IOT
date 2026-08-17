"""QRing command construction and the GATT interface contract.

SCAFFOLD. Signatures only; Abhi writes the bodies.

This module is the ring's *control* surface — what the hub asks the ring to do.
`packets.py` is the *data* surface — what the ring says back. Keeping them apart
means Architecture B's satellite can reuse command construction without ever
touching a parser, which is what "dumb radio, smart hub" actually requires.
"""

from __future__ import annotations

from datetime import datetime, timezone

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

# CONFIRMED 2026-08-08 against R06_D29C. Every request echoes 0x15 back; a day with no
# stored data replies with sub_type 0xFF and a zero payload (packets.NO_DATA_SUB_TYPE).
CMD_READ_HEART_RATE = 0x15   # 21

# HR logging settings (colmi_r02_client `hr_settings.py`, MIT). Sub-command in byte 1.
CMD_HR_LOG_SETTINGS = 0x16   # 22
HR_SETTINGS_READ = 0x01
HR_SETTINGS_WRITE = 0x02
HR_LOGGING_ENABLED = 0x01
HR_LOGGING_DISABLED = 0x02   # note: disabled is 2, not 0

# OBSERVED 2026-08-08, not in any public reference: the ring pushes `73 0c 63 01 ...`
# unprompted — 0x63 = 99% battery, 0x01 = charging — seen when it reached full charge.
# Two consequences: a notification handler must tolerate frames nobody requested, and
# there is a push path that can feed the low-battery alerting in Bug_Backlog R-009.
# Payload beyond battery and charging is unconfirmed.
CMD_STATUS_PUSH = 0x73

# OBSERVED 2026-08-09, undocumented: `2f f1 00 ... 20` arrived unprompted immediately
# before the ring acknowledged its first-ever clock write. Meaning unknown — possibly a
# "configuration changed" or state-transition notice. Recorded so a future handler
# recognises it rather than treating it as a corrupt frame.
CMD_UNKNOWN_2F = 0x2F

# From colmi_r02_client (MIT) `set_time.py`, 2026-08-08. See the DANGER note on
# set_time() before sending this one to R06_D29C.
CMD_SET_TIME = 0x01

LANGUAGE_ENGLISH = 0x01
LANGUAGE_CHINESE = 0x00


def _bcd(value: int) -> int:
    """Encode a two-digit decimal as binary-coded decimal: 26 -> 0x26.

    BCD stores each decimal digit in its own nibble, so the byte reads as the decimal
    number in hex. Cheap for an MCU with no division, and common in RTC hardware.
    """
    if not 0 <= value <= 99:
        raise ValueError(f"BCD encodes 0-99, got {value}")
    return ((value // 10) << 4) | (value % 10)


def set_time(now_utc: datetime, language: int = LANGUAGE_ENGLISH) -> bytes:
    """Build the packet that sets the ring's RTC.

    DANGER — this is a one-way door on R06_D29C. The ring is factory-virgin and its
    clock has never been set, which is a state that exists exactly once and cannot be
    recreated. The raw log MUST be captured first: some firmware wipes the onboard
    buffer on a clock write. `tools/set_ring_clock.py` enforces that ordering
    mechanically by refusing to run without a capture on disk — use it rather than
    calling this directly.

    Payload is 7 bytes (colmi_r02_client `set_time.py`, MIT): year, month, day, hour,
    minute, second — each BCD-encoded — then a language byte. Year is `year % 2000`,
    so 2026 becomes 0x26 and the encoding dies in 2100.

    **The ring wants UTC.** That is worth stating plainly because it is the opposite
    of what a vendor app setting the clock from a phone would suggest, and it means
    this project has no local-time conversion anywhere below the display layer.
    """
    ts = now_utc.astimezone(timezone.utc)
    payload = bytes(
        [
            _bcd(ts.year % 2000),
            _bcd(ts.month),
            _bcd(ts.day),
            _bcd(ts.hour),
            _bcd(ts.minute),
            _bcd(ts.second),
            language,
        ]
    )
    return build_packet(CMD_SET_TIME, payload)


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

    CONFIRMED 2026-08-09 against R06_D29C: requesting UTC midnight for the current day
    returned a 24-frame burst. A day with nothing stored replies with a single frame
    carrying `packets.NO_DATA_SUB_TYPE`.
    """
    ts = int(day_start.astimezone(timezone.utc).timestamp())
    if not 0 <= ts <= 0xFFFFFFFF:
        raise ValueError(f"timestamp does not fit in 4 bytes: {ts}")
    return build_packet(CMD_READ_HEART_RATE, ts.to_bytes(4, "little"))


def request_hr_log_settings() -> bytes:
    """Ask whether automatic heart-rate logging is on, and at what interval.

    Read-only and cheap. This is the question that decides why the log is empty: a
    ring with logging disabled has faithfully recorded nothing, which looks exactly
    like a ring whose buffer was lost or whose clock was never set.
    """
    return build_packet(CMD_HR_LOG_SETTINGS, bytes([HR_SETTINGS_READ]))


def set_hr_log_settings(enabled: bool, interval_minutes: int) -> bytes:
    """Turn automatic heart-rate logging on or off and set its interval.

    **This is the battery contract expressed in bytes** — the single biggest lever on
    the ring's power draw, since PPG optical duty cycle dominates everything else.
    `hub.config.DEFAULT_SENSING.hr_interval_minutes` is the project's chosen value.

    Note the enabled encoding is 1 for on and **2 for off**, not 0.
    """
    if not 1 <= interval_minutes <= 255:
        raise ValueError(f"interval must be 1-255 minutes, got {interval_minutes}")

    flag = HR_LOGGING_ENABLED if enabled else HR_LOGGING_DISABLED
    return build_packet(
        CMD_HR_LOG_SETTINGS,
        bytes([HR_SETTINGS_WRITE, flag, interval_minutes]),
    )


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
