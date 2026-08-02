"""QRing packet parsing — pure functions, bytes in, values out.

SCAFFOLD. Signatures and contracts only; Abhi writes the bodies (CLAUDE.md, division
of labor). Every function here must stay pure: no I/O, no globals, no hidden state.
That is what lets you replay `raw_payloads` from the database through a newer parser
later and get better answers out of bytes you already own.

Sources of truth for the byte layouts, in priority order (RESOURCES.md):
  1. colmi_r02_client source  — read it, don't depend on it (Bug_Backlog R-006)
  2. Gadgetbridge Yawell/Colmi device classes — the tiebreaker when 1 is ambiguous
  3. Your own nRF Connect / bleak captures from R06_D29C — the final authority

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
    """Return the checksum byte for the first 15 bytes of a packet.

    TODO(Abhi): confirmed community behaviour is `sum(data[:15]) & 0xFF`. Verify
    against a real packet from R06_D29C before relying on it.
    """
    raise NotImplementedError


def build_packet(command: int, payload: bytes = b"") -> bytes:
    """Assemble a 16-byte command packet: command byte, payload, zero pad, checksum.

    Raises ValueError if payload is too long to fit. Must be the ONLY place packets
    are constructed — `commands.py` builds on top of this, nothing bypasses it.
    """
    raise NotImplementedError


def is_valid(packet: bytes) -> bool:
    """True if the packet is PACKET_LEN bytes and its checksum byte matches.

    Called on every received packet before parsing. A packet that fails this is
    logged and dropped, never parsed optimistically.
    """
    raise NotImplementedError


# --- Parsers ---------------------------------------------------------------
# Each takes raw bytes plus whatever context it needs to produce true UTC, and
# returns typed values. None of them touch the database, the clock, or the radio.


def parse_battery(packet: bytes) -> tuple[int, bool]:
    """Return (percent, is_charging) from a battery-status packet."""
    raise NotImplementedError


def parse_heart_rate_log(packet: bytes, day_start_utc: str) -> tuple[Sample, ...]:
    """Parse a heart-rate log packet into samples.

    The ring reports HR as a series of fixed-interval slots relative to the start of a
    day, not as absolute timestamps — so `day_start_utc` must be supplied by the
    caller, already corrected for clock offset. Slots with a zero/sentinel value mean
    "no measurement taken", NOT "heart rate was zero"; drop them rather than storing
    zeros, or every rollup you build later will be wrong.
    """
    raise NotImplementedError


def parse_steps(packet: bytes, day_start_utc: str) -> tuple[Sample, ...]:
    """Parse a step-count packet into per-interval step samples.

    Note: the ring reports steps accumulated per interval, so summing samples over a
    day gives the daily total. Confirm whether the value is cumulative-since-midnight
    or per-interval before writing the rollup — the two look identical in one packet
    and differ completely over a day.
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

    Sleep is the one record that spans several packets and must be reassembled before
    it means anything — hence the tuple input. Two things to get right:
      - a session crossing midnight belongs to the night it STARTED
      - stage durations are typically in 5-minute units, not seconds
    """
    raise NotImplementedError
