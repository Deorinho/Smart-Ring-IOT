"""Find every opcode this firmware actually implements, using the 0xEE oracle.

Discovered 2026-08-26 by `tools/probe_sleep.py`: an unsupported command is answered with
the request opcode **OR'd with 0x80**, followed by `0xEE`.

    sent 0x27  ->  a7 ee 00 ...      0x27 | 0x80 = 0xa7
    sent 0x2f  ->  af ee 00 ...      0x2f | 0x80 = 0xaf
    sent 0x15  ->  15 ...            supported: opcode echoed as-is, data follows

That turns "which opcode is sleep" from guesswork into a search with a decision
procedure. This tool walks a range and reports only what did NOT say 0xEE.

**Payload is deliberately all zeros, not a day timestamp.** We are testing whether an
opcode exists, not asking it for data, and a zero payload is the least likely to be
read as a meaningful argument by a command we do not understand. An opcode that exists
but wants parameters will answer with something other than 0xEE -- a bad-parameter error
is still proof of existence, which is all this pass needs.

**This writes unknown opcodes to a ring holding irreplaceable state.** Known mutating
commands are refused via probe_sleep's FORBIDDEN map, but an unknown opcode could still
be a write. Before running: take a backup, and know the clock can be re-set with
`tools/set_ring_clock.py` if something disturbs it. The sweep re-reads the battery
afterwards as a liveness check.

    .venv/bin/python -m tools.sweep_opcodes                  # 0x10..0xF0
    .venv/bin/python -m tools.sweep_opcodes --start 0x20 --end 0x40
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from bleak import BleakClient, BleakScanner

from hub.config import CONNECT_TIMEOUT_S, R06, SCAN_TIMEOUT_S
from protocol.commands import UART_RX_CHAR_UUID, UART_TX_CHAR_UUID, request_battery
from protocol.packets import build_packet, is_valid, parse_battery
from tools.probe_sleep import FORBIDDEN, Collector

log = logging.getLogger("sweep")

UNSUPPORTED_MARKER = 0xEE

# Short waits: classification needs one frame, not a whole burst. The full 1.5 s quiet
# window from a data pull would turn 225 probes into seven minutes of mostly waiting.
FIRST_FRAME_TIMEOUT_S = 0.9
SETTLE_S = 0.25


def classify(opcode: int, frames: list[dict]) -> str:
    """supported | unsupported | silent, from the reply's first two bytes."""
    if not frames:
        return "silent"
    raw = bytes.fromhex(frames[0]["hex"].replace(" ", ""))
    if len(raw) >= 2 and raw[0] == (opcode | 0x80) and raw[1] == UNSUPPORTED_MARKER:
        return "unsupported"
    return "supported"


async def sweep(start: int, end: int, results: list[dict]) -> None:
    """Walk the range, appending each classification to the caller's list.

    `results` belongs to the caller so a dropped link mid-sweep cannot take 200 probes
    of evidence with it -- the failure probe_sleep had on its first run, and probe_hr_log
    had in session 3.
    """
    device = await BleakScanner.find_device_by_address(
        R06.address, timeout=SCAN_TIMEOUT_S
    )
    if device is None:
        raise RuntimeError(f"{R06.name} not found - is it on your finger and awake?")

    async with BleakClient(device, timeout=CONNECT_TIMEOUT_S) as client:
        log.info("connected to %s", R06.name)
        collector = Collector()
        await client.start_notify(UART_TX_CHAR_UUID, collector.handler("uart"))

        for opcode in range(start, end + 1):
            if opcode in FORBIDDEN:
                log.warning("skipping %#04x - %s", opcode, FORBIDDEN[opcode])
                results.append(
                    {"opcode": opcode, "verdict": "skipped", "why": FORBIDDEN[opcode]}
                )
                continue

            before = len(collector.frames)
            try:
                await client.write_gatt_char(
                    UART_RX_CHAR_UUID, build_packet(opcode), response=False
                )
            except Exception as exc:  # noqa: BLE001 - a refused write is a result
                results.append(
                    {"opcode": opcode, "verdict": "write_error", "error": repr(exc)}
                )
                if not client.is_connected:
                    log.warning("ring disconnected at %#04x - stopping", opcode)
                    return
                continue

            # Wait for the first frame, then settle briefly in case more follow.
            try:
                collector._event.clear()
                await asyncio.wait_for(
                    collector._event.wait(), timeout=FIRST_FRAME_TIMEOUT_S
                )
                await asyncio.sleep(SETTLE_S)
            except asyncio.TimeoutError:
                pass

            frames = collector.frames[before:]
            verdict = classify(opcode, frames)
            results.append(
                {
                    "opcode": opcode,
                    "verdict": verdict,
                    "n_frames": len(frames),
                    "frames": frames if verdict != "unsupported" else frames[:1],
                }
            )
            if verdict == "supported":
                log.info("%#04x SUPPORTED (%d frames) %s",
                         opcode, len(frames), frames[0]["hex"][:32])

        # Liveness check. If the ring still answers a known-good command with a sane
        # battery reading, the sweep did not leave it in a strange state.
        before = len(collector.frames)
        await client.write_gatt_char(UART_RX_CHAR_UUID, request_battery(), response=False)
        try:
            collector._event.clear()
            await asyncio.wait_for(collector._event.wait(), timeout=2.0)
        except asyncio.TimeoutError:
            pass
        tail = collector.frames[before:]
        if tail:
            raw = bytes.fromhex(tail[0]["hex"].replace(" ", ""))
            if is_valid(raw) and raw[0] == 0x03:
                pct, charging = parse_battery(raw)
                log.info("post-sweep liveness: battery %d%% (%s)",
                         pct, "charging" if charging else "on battery")

        try:
            await client.stop_notify(UART_TX_CHAR_UUID)
        except Exception as exc:  # noqa: BLE001 - teardown is best effort
            log.debug("stop_notify failed: %s", type(exc).__name__)


def summarise(results: list[dict]) -> None:
    supported = [r for r in results if r["verdict"] == "supported"]
    unsupported = [r for r in results if r["verdict"] == "unsupported"]
    silent = [r for r in results if r["verdict"] == "silent"]
    skipped = [r for r in results if r["verdict"] in ("skipped", "write_error")]

    print("\n=== OPCODES THIS FIRMWARE IMPLEMENTS ===")
    if not supported:
        print("  none in this range")
    for r in supported:
        first = r["frames"][0]["hex"] if r["frames"] else ""
        print(f"  {r['opcode']:#04x}  {r['n_frames']:>2} frame(s)  {first}")

    print(f"\nunsupported (answered {UNSUPPORTED_MARKER:#04x}): {len(unsupported)}")
    print(f"silent (no reply at all):                {len(silent)}")
    print(f"skipped / write error:                   {len(skipped)}")

    if silent:
        ops = ", ".join(f"{r['opcode']:#04x}" for r in silent[:16])
        print(f"\nSilent opcodes are ambiguous and worth a second look: {ops}")
        print("Silence is not the documented refusal, so these may be commands that")
        print("accept the request and answer on a channel or timescale this pass missed.")


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", type=lambda x: int(x, 0), default=0x10)
    parser.add_argument("--end", type=lambda x: int(x, 0), default=0xF0)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = args.out or Path("protocol/fixtures") / f"opcode_sweep_{stamp}.json"

    results: list[dict] = []
    capture = {
        "ring": {"name": R06.name, "address": R06.address},
        "captured_utc": datetime.now(timezone.utc).isoformat(),
        "range": [args.start, args.end],
        "note": "Opcode existence sweep. Unsupported = reply byte0 == op|0x80, byte1 == 0xEE.",
        "results": results,
    }
    try:
        await sweep(args.start, args.end, results)
    except Exception as exc:  # noqa: BLE001 - record it, then save what we have
        log.error("sweep aborted: %r", exc)
        capture["aborted"] = repr(exc)
    finally:
        if results:
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(capture, indent=2), encoding="utf-8")
            print(f"\nwrote {out}  ({len(results)} opcodes probed)")
            summarise(results)

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
