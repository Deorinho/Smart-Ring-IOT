"""Reconnaissance for the sleep record - the last big unmapped piece of the protocol.

Bug_Backlog R-008. `colmi_r02_client` has no `sleep.py` at all, Gadgetbridge's
Colmi/Yawell classes are the only prior art, and nothing upstream documents which
channel the data arrives on. So this tool does not parse anything. It asks carefully
chosen questions and archives every byte that comes back, on both vendor channels, with
enough context to work out afterwards what answered.

**Both channels are subscribed at once, always.** Session 2 found two identically-shaped
services, and the working hypothesis has been that `de5bf728` carries bulk transfers
while `6e40fff0` carries short commands. Listening to only one is how you conclude a
parser is broken when the data was arriving somewhere else entirely.

**Nothing here is a blind opcode sweep.** Known opcodes include writes - `0x01` sets the
clock and `0x16` rewrites the sensing policy - so walking 0x00..0xFF against a ring that
holds irreplaceable state is a way to lose the buffer or the clock. Candidates are
curated, each with a note on why it is plausible, and anything not on the list needs
`--extra` and a deliberate decision.

    .venv/bin/python -m tools.probe_sleep                    # the curated sweep
    .venv/bin/python -m tools.probe_sleep --days 2           # look further back
    .venv/bin/python -m tools.probe_sleep --extra 0x2a,0x2b  # add candidates by hand

Writes `protocol/fixtures/sleep_probe_<stamp>.json`. At this stage a human eye on the
hex is the point, so the file is indented and the summary prints what answered.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

from bleak import BleakClient, BleakScanner

from hub.config import CONNECT_TIMEOUT_S, R06, REPLY_CAP_S, REPLY_QUIET_S, SCAN_TIMEOUT_S
from protocol.commands import (
    BULK_RX_CHAR_UUID,
    BULK_TX_CHAR_UUID,
    UART_RX_CHAR_UUID,
    UART_TX_CHAR_UUID,
)
from protocol.packets import build_packet, is_valid

log = logging.getLogger("probe_sleep")

# Candidate opcodes, each with the reason it earns a write. Cheap and safe things first,
# so a ring that drops the link early still leaves useful evidence behind.
CANDIDATES: tuple[tuple[int, str], ...] = (
    (0x27, "commonly cited for the Colmi family's sleep/big-data request"),
    (0xBC, "the big-data opcode reported for R0x rings; expected on BULK if anywhere"),
    (0x15, "the HR log opcode. If sleep shares the log's day addressing it may answer"
           " here with an unfamiliar sub_type rather than the 0xFF sentinel"),
    (0x2F, "seen unsolicited immediately before the clock ack in session 3 and never"
           " explained. Worth asking directly rather than waiting for it"),
    (0x73, "the status push, known to arrive unbidden carrying battery state. A direct"
           " request may return a fuller status block"),
)

# Opcodes known or suspected to MUTATE ring state. Never probed.
FORBIDDEN = {
    0x01: "sets the RTC",
    0x02: "adjacent to set-time; unknown write semantics",
    0x16: "rewrites the HR logging policy",
}


def day_start_utc(days_ago: int) -> datetime:
    """UTC midnight, N days back. The ring keeps UTC - local midnight is a wrong day."""
    now = datetime.now(timezone.utc)
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return midnight - timedelta(days=days_ago)


def request(opcode: int, when: datetime) -> bytes:
    """A day-addressed request, built the way every confirmed command on this ring is.

    The 4-byte little-endian day start mirrors `request_heart_rate_log`. If sleep is not
    addressed per day this simply will not answer - which is itself a result, because it
    rules the shape out rather than leaving it untested.
    """
    return build_packet(opcode, int(when.timestamp()).to_bytes(4, "little"))


class Collector:
    """Records frames from both channels, tagged with where they arrived.

    The tag is the whole point. A reply on BULK_TX to a command written on UART_RX would
    confirm the two-channel hypothesis in a single observation, and that is invisible if
    the frames are pooled together.
    """

    def __init__(self) -> None:
        self.frames: list[dict] = []
        self._event = asyncio.Event()

    def handler(self, channel: str):
        def _cb(_sender, data: bytearray) -> None:
            raw = bytes(data)
            self.frames.append(
                {
                    "channel": channel,
                    "received_utc": datetime.now(timezone.utc).isoformat(),
                    "hex": raw.hex(" "),
                    "len": len(raw),
                    # Recorded, not enforced. A frame failing the checksum is still data:
                    # it may mean this channel uses different framing entirely.
                    "checksum_ok": is_valid(raw) if len(raw) == 16 else None,
                    "byte0": raw[0] if raw else None,
                }
            )
            self._event.set()

        return _cb

    async def drain(self, quiet_s: float, cap_s: float) -> list[dict]:
        """Collect until the stream goes quiet or the cap expires. Returns new frames."""
        start = len(self.frames)
        loop = asyncio.get_event_loop()
        deadline = loop.time() + cap_s
        while loop.time() < deadline:
            self._event.clear()
            try:
                await asyncio.wait_for(self._event.wait(), timeout=quiet_s)
            except asyncio.TimeoutError:
                break
        return self.frames[start:]


async def probe(days: int, extra: tuple[int, ...]) -> dict:
    device = await BleakScanner.find_device_by_address(
        R06.address, timeout=SCAN_TIMEOUT_S
    )
    if device is None:
        raise RuntimeError(f"{R06.name} not found - is it on your finger and awake?")

    candidates = list(CANDIDATES) + [(op, "supplied with --extra") for op in extra]
    probes: list[dict] = []

    async with BleakClient(device, timeout=CONNECT_TIMEOUT_S) as client:
        log.info("connected to %s", R06.name)
        collector = Collector()

        # Subscribe to BOTH before writing anything, or a fast reply on the channel you
        # were not yet listening to is simply lost.
        await client.start_notify(UART_TX_CHAR_UUID, collector.handler("uart"))
        await client.start_notify(BULK_TX_CHAR_UUID, collector.handler("bulk"))
        log.info("listening on both vendor channels")

        # Anything arriving before a single write is unsolicited and worth recording
        # separately - session 3 saw a 0x2f appear on its own.
        idle = await collector.drain(1.0, 3.0)
        if idle:
            log.info("%d unsolicited frame(s) before any request", len(idle))

        for opcode, why in candidates:
            if opcode in FORBIDDEN:
                log.warning("refusing %#04x - %s", opcode, FORBIDDEN[opcode])
                continue

            for day in range(days):
                when = day_start_utc(day)
                packet = request(opcode, when)

                for write_char, channel in (
                    (UART_RX_CHAR_UUID, "uart"),
                    (BULK_RX_CHAR_UUID, "bulk"),
                ):
                    label = f"{opcode:#04x} day-{day} via {channel}"
                    entry = {
                        "opcode": opcode,
                        "why": why,
                        "day_offset": day,
                        "requested_utc": when.isoformat(),
                        "written_on": channel,
                        "sent_hex": packet.hex(" "),
                        "frames": [],
                    }
                    try:
                        await client.write_gatt_char(write_char, packet, response=False)
                    except Exception as exc:  # noqa: BLE001 - a refused write is a result
                        log.info("%s: write rejected (%s)", label, type(exc).__name__)
                        entry["write_error"] = repr(exc)
                        probes.append(entry)
                        continue

                    entry["frames"] = await collector.drain(REPLY_QUIET_S, REPLY_CAP_S)
                    log.info("%s -> %d frame(s)", label, len(entry["frames"]))
                    probes.append(entry)

        await client.stop_notify(UART_TX_CHAR_UUID)
        await client.stop_notify(BULK_TX_CHAR_UUID)

    return {
        "ring": {"name": R06.name, "address": R06.address},
        "captured_utc": datetime.now(timezone.utc).isoformat(),
        "note": "Reconnaissance for R-008. Nothing here is parsed.",
        "probes": probes,
    }


def summarise(capture: dict) -> None:
    """Print what answered - the interesting result is usually that one thing did."""
    print("\nopcode  written-on  day  frames  answered-on")
    print("-" * 56)
    for p in capture["probes"]:
        chans = sorted({f["channel"] for f in p["frames"]}) or ["-"]
        n = len(p["frames"])
        flag = "  <-- ANSWERED" if n else ""
        print(
            f"{p['opcode']:#04x}    {p['written_on']:<10}  {p['day_offset']:<3}  "
            f"{n:<6}  {','.join(chans)}{flag}"
        )

    answered = [p for p in capture["probes"] if p["frames"]]
    print(f"\n{len(answered)} of {len(capture['probes'])} probes drew a reply")
    if not answered:
        print("Nothing answered. That rules out this entire family of shapes, which is")
        print("worth knowing: the next candidates are a different addressing scheme, or")
        print("a handshake the ring expects before it will discuss sleep at all.")
    else:
        cross = [p for p in answered if any(f["channel"] != p["written_on"] for f in p["frames"])]
        if cross:
            print("\nA reply arrived on a DIFFERENT channel than the write went out on.")
            print("That confirms the two-service hypothesis from session 2 - note which.")


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=2, help="how many days back to ask")
    parser.add_argument("--extra", default="", help="extra opcodes, e.g. 0x2a,0x2b")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    extra = tuple(int(x, 0) for x in (p.strip() for p in args.extra.split(",")) if x)
    for op in extra:
        if op in FORBIDDEN:
            print(f"refusing {op:#04x} - {FORBIDDEN[op]}")
            return 1

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = args.out or Path("protocol/fixtures") / f"sleep_probe_{stamp}.json"

    capture: dict = {"probes": []}
    try:
        capture = await probe(args.days, extra)
    finally:
        # Persistence in a finally, deliberately. Session 3 lost two captures to an
        # exception escaping before the write - the exact failure the tool existed to
        # prevent, twice, because the fix was applied to one file and not its sibling.
        if capture.get("probes"):
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(capture, indent=2), encoding="utf-8")
            total = sum(len(p["frames"]) for p in capture["probes"])
            print(f"\nwrote {out}  ({total} frames)")
            summarise(capture)

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
