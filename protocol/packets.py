"""QRing packet parsing — pure functions, bytes in, values out.

SCAFFOLD. Signatures and contracts only; Abhi writes the bodies (CLAUDE.md, division
of labor). Every function here must stay pure: no I/O, no globals, no hidden state.
That is what lets you replay `raw_payloads` from the database through a newer parser
later and get better answers out of bytes you already own.

Sources of truth for the byte layouts, in priority order (RESOURCES.md):
  1. colmi_r02_client source — **MIT licensed**, so code may be lifted directly with
     attribution, not merely read. Do not add it as a runtime dependency: it targets
     bleak 0.2x and the hub runs 3.0.2 (Bug_Backlog R-006).
  2. Gadgetbridge Yawell/Colmi device classes — the tiebreaker when 1 is ambiguous,
     and the ONLY reference for sleep and temperature, which colmi_r02_client omits.
  3. Your own bleak captures from R06_D29C — the final authority. Its firmware
     (`R06_1.00.06_240921`) is newer than the R02-era hardware most public tooling
     targets, so it has a second vendor service nothing upstream knows about.

Where a constant below is marked TODO(confirm), it is a plausible value from community
work that has NOT been verified against your ring. Verify before trusting it.
"""

from __future__ import annotations

from dataclasses import dataclass

# --- Framing ---------------------------------------------------------------
# QRing-family packets are fixed-length: one command byte, payload, one checksum byte.
PACKET_LEN = 16
CHECKSUM_INDEX = 15


@dataclass(frozen=True)
class Sample:
    """One scalar reading, ready for the `samples` table.

    `ts_utc` is TRUE UTC, already corrected for the ring's clock offset. Parsers that
    only see raw bytes cannot do that correction themselves — see `parse_*` contracts,
    which take an explicit epoch argument rather than guessing.
    """

    metric: str
    ts_utc: str
    value: float


@dataclass(frozen=True)
class SleepStage:
    stage: str      # 'light' | 'deep' | 'rem' | 'awake'
    start_utc: str
    end_utc: str


@dataclass(frozen=True)
class SleepSession:
    start_utc: str
    end_utc: str
    stages: tuple[SleepStage, ...]


def checksum(data: bytes) -> int:
    """Low 8 bits of the sum of the first 15 bytes.

    The & 0xFF does what a uint8_t accumulator gives you for free in C — Python
    ints are arbitrary-precision and never wrap.
    """
    return sum(data[:CHECKSUM_INDEX]) & 0xFF


def parse_command_id(packet: bytes) -> int:
    return packet[0]


def build_packet(command: int, payload: bytes = b"") -> bytes:
    """Assemble a 16-byte packet: command byte, payload, zero padding, checksum."""
    if len(payload) > CHECKSUM_INDEX - 1:
        raise ValueError(f"payload too long: {len(payload)} bytes")

    body = (bytes([command]) + payload).ljust(CHECKSUM_INDEX, b"\x00")
    return body + bytes([checksum(body)])


def is_valid(packet: bytes) -> bool:
    """True if the packet is PACKET_LEN bytes and its checksum byte matches."""
    if len(packet) != PACKET_LEN:
        return False
    return packet[CHECKSUM_INDEX] == checksum(packet)


# --- Parsers ---------------------------------------------------------------
# Each takes raw bytes plus whatever context it needs to produce true UTC, and
# returns typed values. None of them touch the database, the clock, or the radio.


def parse_battery(packet: bytes) -> tuple[int, bool]:
    percent = packet[1]
    # UNVERIFIED: byte[2] was 0 while worn. Charging test blocked by the ring being
    # unreachable in the case — don't depend on this until it's confirmed.
    is_charging = packet[2] != 0
    return percent, is_charging


def parse_heart_rate_log(
    packets: tuple[bytes, ...], day_start_utc: str
) -> tuple[Sample, ...]:
    """Reassemble a multi-packet heart-rate log into samples.

    Takes the whole burst rather than one frame at a time: reassembly with no hidden
    state is what keeps this pure and replayable against archived `raw_payloads`.
    (colmi_r02_client does this with a stateful parser instead; same result, but state
    is what makes a parser hard to re-run over history.)

    Wire format, from colmi_r02_client `hr.py` (MIT), unverified against this ring:

    - `byte[1]` is the **sub_type** — the frame's index within the burst.
    - In frame `sub_type == 0`, `byte[2]` is **how many frames follow**. The burst is
      complete when a frame with `sub_type == count - 1` arrives.
    - Frame `sub_type == 1` carries **9 HR values plus a 4-byte timestamp**.
    - Frames `sub_type >= 2` carry **13 HR values** each.
    - A full day is **288 samples at 5-minute intervals**. Short bursts are padded;
      slots in the future (when reading today) are zero.

    `day_start_utc` must be supplied by the caller, already corrected for the ring's
    clock offset — this function cannot know real time from bytes alone.

    The trap: a zero is **"no measurement taken"**, not a heart rate of zero. Drop
    those slots rather than storing them, or every rollup built on top will be dragged
    toward zero by gaps that were never real readings.
    """
    raise NotImplementedError


def parse_steps(packet: bytes, day_start_utc: str) -> tuple[Sample, ...]:
    """Parse a step-count packet into per-interval step samples.

    Reference: colmi_r02_client `steps.py` (MIT). Expect the same multi-packet
    sub_type framing as the HR log; widen the signature to a tuple if so.

    Confirm whether the value is cumulative-since-midnight or per-interval before
    writing any rollup — the two look identical inside a single packet and differ
    completely over a day.
    """
    raise NotImplementedError


def parse_spo2(packet: bytes, day_start_utc: str) -> tuple[Sample, ...]:
    """Parse a blood-oxygen packet. Deprioritized metric; scaffold kept for symmetry."""
    raise NotImplementedError


def parse_temperature(packet: bytes, day_start_utc: str) -> tuple[Sample, ...]:
    """Parse a skin-temperature packet.

    Values are likely fixed-point (scaled integers), not floats. Confirm the divisor;
    a factor-of-10 error here is invisible until the illness-detection baseline is
    quietly meaningless.
    """
    raise NotImplementedError


def parse_sleep(packets: tuple[bytes, ...], day_start_utc: str) -> tuple[SleepSession, ...]:
    """Parse a multi-packet sleep record into sessions with stage sequences.

    **No public Python reference exists for this.** colmi_r02_client has no sleep
    support at all, so Gadgetbridge's Colmi/Yawell classes are the only prior art —
    and sleep is this project's highest-priority metric, which makes it the biggest
    genuinely unsolved piece of the protocol.

    Worth testing before assuming the command channel: sleep may arrive on the second
    vendor service (`commands.BULK_*`), which nothing upstream knows about. A parser
    that never sees data may be listening on the wrong characteristic.

    Two things to get right once the bytes are in hand:
      - a session crossing midnight belongs to the night it STARTED
      - stage durations are typically in 5-minute units, not seconds
    """
    raise NotImplementedError
