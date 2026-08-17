# Notebook

Session log — date, what worked, what broke, how long it took. This file is the script skeleton for Phase 4.

---

## 2026-07-11

- Added `PLAN.md` to the repo (see file for full plan).
- Scaffolded the monorepo per Phase 0 / Week 0: `protocol/`, `hub/`, `dashboard/`, `firmware/`, `notebook.md`.
- Status per plan: models selected (1x Ruofine R10 sz 10, 2x Ruofine R09 sz 9), order pending final size confirmation.
- Next: jeweler sizing confirmation for the R10, then place the parts order (blocking all Phase 0 hardware work).

## 2026-07-18 — Fleet finalized, priorities re-sequenced (planning-room session)

**Hardware (the big one):**

- Near-miss caught: the originally ordered "Ruofine R09" was confirmed **JRing-protocol** via its listing's manual PDF — different app, different BLE protocol, zero compatibility with QRing/Colmi tooling. Cancelled before shipping. Lesson codified as a standing pre-purchase rule in RESOURCES.md: model numbers are reused across incompatible hardware families; always confirm the companion app is QRing before buying, and re-verify via nRF Connect on arrival.
- Final fleet, both from the official Colmi store, both QRing-confirmed, ETA end of July: **Colmi R09 sz 12 = DAILY**, **Colmi R06 sz 10 = DEV**.
- **HERO is now a gated purchase:** a second R09, bought only after DAILY survives the on-wrist testing phase. If DAILY shows issues, hold; if it breaks or bricks, the replacement purchase doubles as the HERO decision point.
- Ruofine R10 dropped from the active plan entirely — project fully functions on the R09/R06 pair.

**Priorities:**

- **Travel Protocol shelved.** Design retained in PLAN.md §2.1 for future revival; not on the critical path.
- **Top priority: hub foundation plug-and-play before the rings arrive** — HUB_SETUP.md checklist completion so arrival day is bring-up, not setup.

**Video production model revised:**

- Dev pass is now *documentary-filmed*, not camera-free: challenges, design issues, and growing understanding captured raw as they happen. This footage is the substance of the video.
- HERO filmed pass (Phase 4) shifts to pure production polish — eye-catching, entertaining delivery — with dev-pass documentary material cut in as the real story.
- Evidence rule (notebook entries, screenshots, asciinema) still applies alongside the camera.

**Design work: sync trigger strategy — DECIDED (B now, C later):**

- Evaluated (A) opportunistic continuous-scan, (B) scheduled timer windows, (C) adaptive hybrid. All three share an identical execution path (connect → pull → parse → dedupe → store); only the trigger differs → sync service architected with a pluggable SyncPolicy so the choice is config, not structure.
- **Decision: B for v1** — systemd timer, 60 min cadence, 15 min during the 05:00–10:00 sleep-data window. Deterministic, trivially testable, discrete journald events.
- **C is the designed v2 drop-in:** passive advert listening + pure `decide(now, last_sync, rssi, state)` gate (fixture-testable like the parsers). State machine per ring: Listening → Present → Eligible → Syncing → Cooldown/Backoff → Listening. RSSI hysteresis (−85 present / −80 connect), per-ring state by MAC, overnight quiet hours 23:00–05:00, one deliberate UTC→local conversion for windows, scanner watchdog.
- Executor rules written once, policy-independent: per-ring connection lock (single-central), capped exponential backoff, min-interval guard. Full design recorded in PLAN.md §2.2 — this is the design input for the sync service task.

**Tooling:**

- Added `.claude/skills/python-engineering/` and `.claude/skills/cpp-embedded/` — language guidelines tuned to how Abhi works (test-engineer mindset: determinism, verifiability, efficiency, dependency minimalism).
- CLAUDE.md updated: new status, design-before-code rule (from 07-17 workflow decision), pointer to skills.

## 2026-07-19 — Phase 0a task breakdown + Task 1 design (docs only, no code)

- Wrote `TASKS.md`: Phase 0a broken into 8 ordered, independently-reviewable tasks (hub
  env verification → protocol parsers/fixtures → pytest harness → SQLite schema →
  synthetic-data generator → analytics rollups → FastAPI skeleton → PWA). Noted that
  Tasks 2–6 aren't hard-blocked by Task 1 despite being listed after it; the real
  dependency is Tasks 7–8 needing Task 1's Tailscale/systemd verification proven true.
- Caught and corrected a scope error while writing Task 5: "synthetic data for metrics
  1-15" as a literal numeric range is wrong against PLAN.md §3 — it would wrongly include
  Phase-3-only 5b/6/7 (need raw PPG + custom firmware) and wrongly exclude the
  Phase 1–2 temperature metrics 20/21. Resolved scope is every metric tagged "Phase 1–2"
  in §3, i.e. {1,2,3,4,5,8,9,10,11,12,13,14,15,20,21} — same count, different set.
- Wrote `DESIGN_01_hub_environment_verification.md` per the design-before-code rule:
  flow diagram (automated pytest path vs. manual runbook path for the 6 HUB_SETUP.md §8
  items), state diagram (per-item verification lifecycle — reasoned that a single
  pytest run itself doesn't need one, pytest's own pass/fail model covers that), class
  diagram (thin `ChecklistItem`/`ChecklistRegistry` + plain-function `Probes`, with a
  rejected richer `CheckResult` alternative documented), and 8 open questions (file
  location, invocation ergonomics, how manual items surface in tooling, report
  destination, BLE-scan tolerance with no ring yet, checklist source of truth, dummy vs.
  real systemd unit, run-history persistence).
- Side note, not acted on: notebook's 07-18 entry says `.claude/skills/` was added, but
  no `.claude/` directory exists in the repo yet — flagging for Abhi, not fixing this
  session (out of scope, docs-only).
- No implementation code written this session, per explicit instruction. Next: Abhi
  reviews DESIGN_01's open questions; Task 1 implementation waits on that review.

## 2026-07-19 — WAR_ROOM ingest: two-room sync workflow documented (WR-2026-07-19-01, -02)

- Applied a WAR_ROOM block via the `ingest` skill, encoding the two-room sync
  workflow itself into `CLAUDE.md` so it outlives chat memory: `run-project-routine`
  (Planning Room) stages settled decisions as a block; `ingest` (Execution Room)
  applies it idempotently by entry ID, authors this notebook entry, and archives
  the block in `WAR_ROOM.md`, which it alone owns.
- Added `WAR_ROOM.md` as a listed source-of-truth doc in `CLAUDE.md` so the ledger
  is discoverable alongside `PLAN.md`, `RESOURCES.md`, `HUB_SETUP.md`, and
  `notebook.md`.

## 2026-08-02 — Project reset: hardware in hand, roles locked, architecture chosen

**Hardware reality (supersedes everything dated July):** both rings arrived. Roles
**reversed** from the July plan and this is final — **R06 sz 10 = DAILY + DEV**
(better fit, worn every day, the ring the hub is built against); **R09 sz 12 =
SHOWCASE**, used for the YouTube video. The gated third-ring purchase is cancelled;
end state is both rings running the same software, then one chosen for teardown.

- R09 has been running on the stock QRing app for initial evaluation. It stays there
  for now as the **validation oracle** — hub-computed numbers get diffed against
  vendor-computed ones on the same wrist-days, then it migrates to the hub at the end.
- **R06 has never been connected to anything.** Factory-virgin: its RTC has never
  been set. First hub connect must **dump the raw log before writing the clock** —
  a one-shot observation (does a virgin ring log at all? what epoch? does time-set
  wipe the buffer?). The R09 cannot substitute; QRing already time-set it.
- Empirical confirmation of the battery hypothesis: enabling all QRing metric-gathering
  functions on the R09 drained it fast. Consistent with PPG optical duty cycle, not
  MCU compute, being the dominant draw. Offloading computation to the hub saves
  almost nothing; sensing cadence is the lever.

**Buffer-depth experiment — STARTED.** R06 put on at **2026-08-02 00:30 local
(04:30 UTC)**, fully charged, synced to nothing. Unknown at start: how many days the
onboard log retains. This number sets sync cadence, the battery ceiling, and whether
the remote relay is a necessity or a convenience. Measured on first successful hub sync.

**Decisions locked this session:**

- **Architecture A now, B next.** A = single hub, no relay, accept data gaps on long
  trips. B = ESP32-C3 satellite at the second location. Peer-node option (C, a Pi-class
  box running the same Python) was costed as cheaper and faster but **declined
  deliberately** — the embedded firmware work is wanted for its own sake.
- **Schema is generic, not ring-shaped.** Scalar time series in one table keyed by
  `(source, metric, ts_utc)`; structured events (sleep sessions, workouts) get their
  own tables rather than being forced into scalar rows. Rationale: the hub is a
  personal telemetry store whose first source happens to be a ring — future hub
  projects must not start from zero.
- **Metric priority:** sleep, activity, and heart rate first. SpO2 and VO2max
  deprioritized (revisit if running becomes a hobby). Composite scores stay deferred.
- **Sync cadence 3×/day**, down from the shelved plan's ~20×/day — that cadence was
  tuned for dashboard freshness, which is the opposite of the stated priority.
- **Working split:** Abhi writes `protocol/` parsers, the BLE sync service, and the
  storage layer. Claude scaffolds signatures/TODOs, owns dashboard + FastAPI plumbing
  and all boilerplate, and on bugs narrows to a function/line range without solving.

**Removed:** `TASKS.md`, `DESIGN_01_hub_environment_verification.md`, `WAR_ROOM.md`,
and the `ingest` / `run-project-routine` skills. The two-room sync ceremony is retired
— process machinery had outgrown a repo containing zero lines of code. Git history
retained deliberately (dated evidence for the video).

**Doc drift found during the audit:** the July 18 fleet decision was applied to
PLAN.md's status line but never swept through §2, §5, §6, or the BOM — seven live
contradictions, including three places still calling the R10 the daily driver. README
still described a fleet that was never purchased. Root cause: docs with no code to
anchor them drift silently. PLAN.md and CLAUDE.md are being rewritten against reality.

### Hub build-out — session 1 (~4 h, ended 01:30)

Goal was HUB_SETUP.md §1–4 on the 2014 MacBook Air. **Achieved, plus the real prize:
the hub can see the ring.**

**The win:** `BleakScanner.discover()` on the hub returned
`('81:5F:4A:87:D2:9C', 'R06_D29C')`. Kernel → BlueZ → Python all agree the ring exists,
with no vendor app anywhere in the path. Screenshotted — this is the opening shot of the
video. Noted: the advertised name encodes the last two bytes of the MAC (`D2:9C`),
which indicates a **fixed** device address rather than a rotating private one, so it's
safe as a permanent database key. Re-verify in a week.

**What broke, in order — most of the session was here, not in the setup itself:**

1. `ssh-copy-id` failed with `Permission denied` at *connect*, not at auth. That
   distinction was the diagnosis: the TCP socket was blocked, not the credentials
   rejected. Cause was **Mullvad blocking LAN traffic** (local network sharing is off
   by default). Then it changed to a timeout, which meant the desktop side was fixed
   and the hub side still wasn't.
2. Decision: **Mullvad stays on the hub.** Flagged that Mullvad and Tailscale both
   manage routing and will conflict when Tailscale goes in next session → Bug_Backlog
   R-001. Not a surprise to be discovered mid-session later.
3. `python3 -m venv` failed — Debian/Ubuntu split `ensurepip` out. `python3.12-venv`
   needed. Wasted a step because the SSH detour skipped past HUB_SETUP.md §4's apt line.
4. First scan raised `BleakBluetoothNotAvailableError: POWERED_OFF`. `dmesg` had already
   proven the controller was healthy (`BCM: chip id 73 build 1126`, `BCM20702B0 @ 20 MHz`,
   zero `command tx timeout` errors) — so the Broadcom firmware archaeology I'd braced
   for wasn't needed. The adapter was just soft-powered off.
5. **Closing the lid suspended the machine** and killed the SSH session mid-work — §3
   hadn't been done yet. Fixed with all three layers: `logind.conf`, Cinnamon's power
   manager (which overrides logind while a desktop session exists), and masking
   `sleep.target`/`suspend.target`/`hibernate.target`/`hybrid-sleep.target`. Verified:
   lid closed, still reachable over SSH.

**Findings worth keeping:**

- `dmesg` shows the Bluetooth stack initializing at **43 s** into boot while the USB
  device enumerates at 2.8 s. A sync service starting earlier finds no adapter — the
  classic "works by hand, never after a reboot" bug. Logged as R-005; `ring-sync.service`
  needs `After=bluetooth.target` and tolerance for an adapter that isn't ready.
- Hub has **bleak 3.0.2**, a new major release. `colmi_r02_client` targets bleak 0.2x and
  will conflict if installed. Mitigation: read it as source reference for packet layouts,
  never as a runtime dependency. Logged as R-006, and it matches the dependency-minimalism
  rule anyway.
- The hub belongs on **5 GHz WiFi**: the Broadcom chip shares one 2.4 GHz radio between
  WiFi and Bluetooth, and 2.4 GHz degrades BLE scanning intermittently — the worst kind
  of failure to debug later. Logged as R-003.

**Repo work this session:**

- Retired `TASKS.md`, `DESIGN_01`, `WAR_ROOM.md`, and the `ingest` /
  `run-project-routine` skills. The process machinery had outgrown a repo with zero
  lines of code — a 140-line design doc for a 60-line script was the tell.
- Rewrote `CLAUDE.md`, `PLAN.md`, and `README.md` against reality. `PLAN.md` now carries
  a numbered **session roadmap** rather than open-ended phases, since work happens in
  2–4 hour weekend blocks.
- Created `Bug_Backlog.md` (P1/P2/P3 + a RISK tier), seeded with six real risks.
- Created `.claude/skills/startup/` — the session-open briefing ritual.
- First code in the repo's history: `hub/schema.sql` (generic telemetry store),
  `hub/config.py` (MAC, sensing policy, cadence), and scaffolds for `protocol/packets.py`
  and `protocol/commands.py`. Scaffolds carry signatures, contracts, and traps — no
  bodies; Abhi fills those.
- Two schema decisions worth remembering: `samples`' primary key
  `(source_id, metric, ts_utc)` **is** the idempotency guarantee, so `INSERT OR IGNORE`
  makes re-syncing free and Architecture B's ingest needs no special casing. And
  `raw_payloads` archives every packet verbatim forever — reverse-engineering an
  undocumented protocol means an improved parser should re-read August in December
  rather than having lost it.

**Open for session 2:** GATT enumeration on `R06_D29C`, confirming the TODO(confirm)
UUIDs and opcodes in `protocol/commands.py`, a battery-command round trip as the cheapest
proof of the write/notify path — and **dumping the raw log before setting the clock**,
which is a one-shot observation on a factory-virgin ring.

**Not yet built:** `hub/db.py`, `hub/sync.py`, `hub/api.py`, `dashboard/`, and the
30-minute journal automation.

## 2026-08-02 — Session 2: first conversation with the ring

Baseline goal was "a battery percentage prints in the terminal." **Met**, and the
reconnaissance on the way there was worth more than the goal.

### The round trip

Sent `03 00 00 00 00 00 00 00 00 00 00 00 00 00 00 03`. Got back
`03 50 00 00 00 00 00 00 00 00 00 00 00 00 00 53`.

- `byte[0] = 0x03` — the ring **echoes the command byte**. Every reply is
  self-identifying, which means one notification handler can dispatch packets to the
  right parser instead of the caller tracking what it asked for. That's the shape of
  the real sync service, now known rather than assumed.
- `byte[1] = 0x50` = **80% battery**. Plausible: charged full, worn since 00:30.
- `byte[15] = 0x53` = 83 = 3 + 80. **`checksum_ok=True`.**

The checksum is now confirmed **in both directions**: the ring accepted a packet built
with `sum(data[:15]) & 0xFF`, and the ring's own reply validates under the same
function. The ring's firmware served as the reference implementation — no external
oracle needed. `CMD_BATTERY = 0x03` confirmed at the same time.

### GATT enumeration — two services, not one

The scaffold assumed a single vendor channel. There are two, both with the same
notify/write shape:

- `6e40fff0…` with `6e400002` (write) / `6e400003` (notify) — the command channel,
  matching the community UUIDs exactly.
- `de5bf728…` with `de5bf72a` (write) / `de5bf729` (notify) — **unidentified**.
  Working hypothesis: two identically-shaped channels usually means short commands on
  one and bulk transfer on the other, so this is the likely home of sleep records and
  large history dumps. Worth knowing before concluding a sleep parser is broken because
  data never arrives on the channel being listened to.

No Battery Service (`180f`), so there was no shortcut — the protocol path was the only
path, which is what the goal wanted anyway.

### Device Information — the chipset answer

| Field | Value |
| --- | --- |
| Manufacturer | **Bluex** |
| Model Number | BX-BLE-5.0 |
| Firmware Revision | **R06_1.00.06_240921** |
| Hardware Revision | R06_V1.0 |
| System ID | `9c d2 87 00 00 4a 5f 81` |
| PnP ID | `02 5e 04 40 00 00 03` |

**The R06 is BlueX-based**, which is exactly the family ATC_RF03 targets. Phase 3 went
from "plausible, chipset unverified" to "confirmed viable" on one read. Firmware build
date is encoded as `240921` — 2024-09-21, recent enough that stock HRV, REM staging,
and temperature reporting are likely present.

**System ID is the MAC, burned into firmware.** Decoded as the spec's EUI-64
construction, little-endian: `9c d2 87` reverses to the MAC's low three bytes,
`4a 5f 81` to the high three, `00 00` is the filler. The address cannot rotate — it's
in a read-only characteristic. That settles the database-key stability question
permanently; no week-long re-verification needed.

**PnP ID decodes to Microsoft's USB vendor ID (`0x045E`)** — a placeholder, not a
BlueX confirmation. But combined with serial `BX-DEVICE-001` and regulatory data of
`ff ee dd cc bb aa`, that's **three of eight DIS fields left at SDK defaults**. This
firmware sits close to a stock BlueX reference build with minimal vendor divergence,
which is a genuine positive signal for Phase 3: the closer to reference, the more
directly ATC_RF03's findings transfer.

### What broke

- `raw.hex("")` — `ValueError: sep must be length 1`. `bytes.hex()` takes exactly one
  separator character or no argument; empty string satisfies neither. Killed script 2
  after the five text fields and before the three binary ones. Re-ran for the rest.
- **The charging-flag test failed to connect.** With the ring in the charging case,
  `BleakClient.__aenter__` timed out after 20 s — no protocol involved, the peripheral
  simply wasn't connectable. Most likely the ring stops advertising while charging, or
  the case shields the antenna; not yet distinguished. Logged as R-007.

That last one is a **design finding, not just a failed experiment**: the sync service
must treat "unreachable" during charging windows as normal, since charging happens
roughly daily. `sync_runs.status` already has `no_device` for exactly this.

### Repo work

- Ported into `protocol/`: `checksum`, `build_packet`, `is_valid`, `parse_command_id`,
  `parse_battery` (percent confirmed, charging flag left explicitly unverified), and
  `request_battery`.
- Added `__init__.py` to `protocol/` and `hub/` — cross-module imports needed real
  packages, which is what actually blocked `request_battery`, not the one-line body.
- Confirmed constants written back into the scaffolds with their evidence, so the
  files record *why* a value is trusted, not just what it is.
- Adopted a git workflow: session branches named for the roadmap row, squash-merged via
  PR, `main` kept as the hub's deployment target so a half-written sync service can
  never land on the running machine.
- Added the `/shutdown` skill, completing the session handshake with `/startup`.
  Includes a lint stage bounded to mechanical fixes — scaffolded `NotImplementedError`
  stubs are explicitly never "fixed."

### Open

- Charging flag (`byte[2]`) unverified; blocked on R-007.
- `de5bf728` service purpose unknown.
- **Buffer-depth experiment still running and untouched** — a battery request doesn't
  pull the onboard log, so the clock from 00:30 is intact.
- `set_time` deliberately untouched. The raw log dump must come first, and it's a
  one-shot observation on a never-paired ring.

## 2026-08-09 — Session 3: the log was empty because the ring was never recording

Goal was "capture the onboard log and find out how many days back it goes." **Met — but
the answer was zero, and the reason took most of the session to find.**

### The finding

Thirty-plus log requests across nine local midnights and both candidate factory epochs
(1970, 2000), on the finger and on the charger, all returned the same sixteen bytes:

```text
15 ff 00 00 00 00 00 00 00 00 00 00 00 00 00 14
```

`sub_type = 0xFF` is the ring's **"no data for this day" sentinel** — undocumented
upstream, now confirmed. Every reply was truthful. The cause, found by reading
`CMD_HR_LOG_SETTINGS` (0x16):

```text
16 01 02 1e 05 00 ... 3c   ->   DISABLED, every 30 min
```

**Automatic heart-rate logging ships disabled from the factory.** The R06 spent a week
on a finger recording nothing. The buffer-depth experiment measured an empty buffer,
correctly. Enabling it (`16 02 01 1e`) returned `16 01 01 1e 05 ... 3b` — logging on,
and the undocumented `byte[4] = 0x05` survived the write, which closed R-011.

### The clock, finally

With three virgin captures banked, the RTC was written for the first time —
`01 26 08 09 07 07 01 01 ... 48`, BCD, UTC, 2026-08-09T07:07:01Z. BCD makes the date
legible straight off the wire. The ring acked with `01 00 01 00 22 ...` and emitted an
undocumented `2f f1 00 ... 20` immediately beforehand. A replay of every virgin
timestamp afterwards still returned the sentinel — expected, since nothing had been
recorded to find.

The virgin-timestamp experiment ended weaker than hoped: logging was only enabled about
an hour before the clock write, at a 30-minute interval, so at most one or two samples
could have existed. It answered "did an hour of clockless logging produce anything
retrievable?" (no) rather than "does a virgin ring log at all?" Three captures preserve
the state regardless; it cannot be re-observed on this unit.

### Protocol confirmed this session

| Item | Value |
| --- | --- |
| No-data sentinel | `sub_type = 0xFF` |
| HR log settings | `0x16`; byte[1] 0x01 reads / 0x02 writes; byte[2] 1=on **2=off**; byte[3] interval |
| Settings ack | `16 02 01 ...` — writes are acknowledged, not silent |
| Set time | `0x01`, 7 BCD bytes + language, **UTC** (not local, as the scaffold assumed) |
| Battery | byte[1] percent, byte[2] charging — confirmed by controlled test |
| Unsolicited push | `0x73` (`73 0c 63 01` = 99%, charging) |
| Unknown | `0x2f` before the clock ack; `byte[4]` of the settings frame |

### What broke — all of it mine

- **`probe_hr_log.py` lost an entire run.** The ring dropped the link mid-probe and the
  exception escaped before the capture was written — the one failure the tool existed
  to prevent. Fixed: persistence moved into a `finally`, plus one reconnect attempt per
  probe.
- **Then `set_ring_clock.py` did exactly the same thing**, because the fix was applied
  to one file and not its sibling. The post-clock-write capture was lost. Now refactored
  to reuse the hardened loop.
- **Probes used local midnight while the ring keeps UTC** — four hours off the ring's
  day boundary here. Corrected before it could produce a confusing empty result.
- The hub cannot push to GitHub (HTTPS password auth is dead). Captures came back over
  `scp`; logged as R-013 with an SSH key as the real fix.

### Measurements

- **~12%/day drain at factory settings with PPG disabled** (80% → 1% over 6.8 days).
  Since HR logging was off, the drain was *not* PPG. Advertising and the accelerometer
  are the suspects → R-012, and it questions whether the battery contract targets the
  right consumer.
- **Body-worn costs ~21 dB.** Same desk, same battery level: −60 dBm in the case,
  −81 dBm on the finger → R-010. Range from another room is now an open question.
- No low-battery warning exists without the vendor app; the ring silently ran to 1%
  → R-009.

### State at session end

Clock set (UTC), HR logging enabled at 30 min, ring worn from ~03:10 local on a near-full
charge. That starts two experiments at once: the real buffer-depth measurement, and the
drain rate at HR=30min to compare against the 12%/day factory baseline.

**Next session opens by probing UTC midnight for 2026-08-09** — if a night of heart rate
comes back, the read path is proven end to end and session 4 becomes storage.

## 2026-08-09 — Session 4: the first real heartbeat (~35 min)

**The read path works end to end.** A probe at UTC midnight for 2026-08-09 came back
with **24 frames** instead of the `0xFF` sentinel, and after one offset fix it parsed
into 28 heart-rate samples that look unmistakably like a person.

### The burst

```text
15 00 18 05 00 ... 32    sub_type 0 = header: 24 frames, 5-minute slots
15 01 00 c3 77 6a 00 ... sub_type 1 = timestamp + 9 values
15 02 00 00 ... 17       sub_type 2+ = 13 values each
```

Header decoded exactly as scaffolded, sub_types 1–23 with none missing. **And `byte[3] =
0x05` resolved an older mystery:** it is the log's *slot* granularity, the same
undocumented `byte[4]` seen in the HR-settings frame. The day is always 288 five-minute
slots regardless of the measurement interval — at 30-minute measurement only one slot in
six is filled and the rest are zeros. That makes "zero means not measured" load-bearing
rather than pedantic.

### The bug, and how it announced itself

First parse gave 31 samples, `min=51 max=195`, and an hourly bucket at 20:00 local — a
time before logging was even enabled. The ring's embedded timestamp read `0`.

Both symptoms, one cause: **the 4-byte timestamp precedes the nine values, not follows
them.** colmi_r02_client's description reads the other way round, and taking it
literally parsed the timestamp bytes as heart rates. The three phantom samples were
`0xc3 = 195`, `0x77 = 119`, `0x6a = 106` — **their mean is exactly 140.0**, which matched
the anomalous bucket to one decimal place. The "ring timestamp" read zero because bytes
11–14 are padding.

Fixed offsets: timestamp at bytes 2–5, first-frame values at bytes 6–14.

### Why the corrected result is trustworthy

```text
28 non-zero samples   min 51   max 115   mean 81.9 bpm
first 07:30 UTC   last 21:00 UTC   = 13.5 h
13.5 h x 2/hour + 1 = 28
ring's own ts: 1786233600 = UTC midnight 2026-08-09
```

The sample count is not approximately right, it is arithmetically exact — which means
measurement interval, slot arithmetic, frame reassembly and timestamp anchoring are all
correct *simultaneously*. Three independent things agreeing is much stronger evidence
than any one of them looking plausible.

The curve reads as a life: 115 bpm winding down at 03:00 local, a night bottoming at
**51 bpm resting**, a step up at midday, 84–106 through a working afternoon.

### Corrections and findings

- **R-002 expectation walked back.** The frame-1 timestamp *echoes the requested day
  start*; it is not the ring's independent clock. It confirms the ring understood the
  request but supplies no drift measurement. Real clock offset needs a different source
  — comparing when samples appear against events of known wall-clock time.
- **Battery: 100% → 96% in 14.3 h at HR=30min (~6.7%/day)** against ~13%/day during the
  factory week *with HR logging disabled*. Roughly half the drain while doing strictly
  more sensing. Rate is provisional — voltage-based gauges are non-linear near full
  charge — but the direction sharpens R-012: something was running that week which is
  not running now. Only the HR settings (`0x16`) have ever been queried; the SpO2 /
  stress / HRV / temperature enable flags are the next target, and it is a battery
  question rather than a features question.

### What broke this session

- **Ran the inspector twice against unpushed code.** Byte-identical output both times
  was the giveaway — not a partial fix but no fix at all. The parser change was sitting
  uncommitted on the desktop while the hub ran the old offsets.
- `requested_iso` rendered in local time, making a correct UTC-midnight request look
  like it landed the previous evening. Fixed to UTC.
- Getting captures off the hub still needs `scp` (R-013). Two files came across; the
  hub's untracked copies were removed with `git clean` and restored by pull.
- The capture commit `c08b8f2` carries a mangled message — a pasted file listing. Left
  as-is deliberately: **squash-merging this PR discards it**, which is what `CLAUDE.md`
  has asked for since PR #1 and what the two previous merge commits skipped.

### Built

`tools/inspect_capture.py` — decodes a saved capture offline: verifies structure
(header, sub_type sequencing, missing frames, slot capacity, embedded timestamp) *before*
parsing values, then reports samples with an hourly mean in local time. Structure first
is deliberate; a plausible heart rate built on a misread header is worse than an obvious
failure. It runs with no radio and no battery, which is the entire justification for
archiving raw frames.

**Archive state:** five capture files, 84 frames, zero checksum failures.

### Open after session 4

- Buffer depth — finally measurable. Probe 2026-08-09 again tomorrow and see whether
  yesterday survives. That number has gated Architecture B since session 1.
- Storage. 28 parsed `Sample` objects exist in memory and `hub/schema.sql` has never
  been executed.
- Sleep (R-008) remains the largest unmapped piece of the protocol.

## 2026-08-13 — Session 5: storage, an API, and a dashboard

Autonomous session — free rein to build and triage, reviewed at the end. **The vertical
slice is complete: ring → parser → SQLite → JSON API → dashboard.**

### The battery number changed everything about the battery plan

A reading of **18%** landed the picture that four days of guessing hadn't:

```text
100% -> 96%   first 14 h     =  6.7 %/day   <- the misleading one
 96% -> 18%   next 4.2 days  = 18.8 %/day
100% -> 18%   overall        = 17.2 %/day
```

**~5.5 days per charge.** And because the factory week ran ~13%/day with HR logging
*disabled*, PPG at 30-minute intervals costs only about **5%/day** — the other 13 is an
idle floor that no sensing schedule can reach. Tuning the HR interval is therefore
nearly pointless; halving it buys ~2.5%/day. The whole battery strategy in `CLAUDE.md`
was aimed at the wrong consumer and has been rewritten.

Last session's 6.7%/day estimate was wrong by ~3×, from exactly the trap flagged when it
was made: the gauge runs 0.28%/h for the first 14 hours and 0.78%/h after. That is now a
standing rule in `CLAUDE.md` — never estimate this ring's drain from day one of a charge.

### Built this session

- **`hub/db.py`** — thin I/O over the schema. Idempotent inserts, sync-run bookkeeping,
  raw-frame archival, query helpers. No parsing, no analytics.
- **`hub/api.py`** — read-only JSON API plus PWA host. It has no write path at all, so a
  bug in the reader cannot corrupt the store.
- **`dashboard/`** — dark, phone-first PWA. Tiles, a heart-rate line chart with 24 h /
  7 d / 30 d ranges, a per-day min-mean-max chart, and sync history.
- **`tools/ingest_capture.py`** — capture JSON → parser → database, entirely offline.
- `requirements.txt`, a systemd user unit for the dashboard, and an `RAVENX_DATA_DIR`
  override so development never touches the real store.

**No Chart.js**, despite `PLAN.md` naming it. A CDN breaks offline use and puts a third
party in the request path of a project whose premise is not having one; vendoring a
bundle is dead weight. Two line charts and a bar chart came to ~80 lines of hand-written
SVG. Recorded in `dashboard/README.md` so the deviation is a decision, not drift.

### Two bugs I wrote and caught

**`raw_payloads` was silently discarding a third of every capture.** After the first
ingest the table held 48 rows where 76 were expected. `store_raw_payloads` restarted
`seq` at 0 for each probe, so `UNIQUE (sync_run_id, seq)` quietly swallowed all fourteen
sentinel frames sitting behind the 24-frame burst. The archive built specifically so no
byte is ever lost was losing bytes. Found only by counting rows against expectation —
nothing errored, nothing warned. `seq_start` is now an explicit parameter with the trap
written into its docstring, and the ingest tool reports a mismatch if it recurs.

**The dashboard lied about its own window.** Switching to 7 d left the tiles reading
"Lowest 24 h" and "Mean 24 h" over seven days of data. Found by opening the page and
clicking the button — not by reading the code, which looked fine. Also fixed: per-reading
dots are suppressed above 60 points, since 30 days would have drawn ~1,400 circles.

Both are the same lesson from different angles: **verify against the artefact, not the
intention.** Counting rows and clicking a button each found something a code read did not.

### Verified, not asserted

Storage is portable by design, so all of this ran on the Windows desktop with no ring
attached:

```text
ingest run 1 : 38 frames archived, 28 samples parsed, 28 newly stored
ingest run 2 : 38 frames archived, 28 samples parsed,  0 newly stored
sentinel-only captures: ingest cleanly, 0 samples, no crash
```

The dashboard was checked in a real browser at 375 px: no console errors, no horizontal
overflow, range switching correct, axis labels flipping from clock times to dates on
multi-day windows.

### Triage

- **R-004 escalated to P1.** There is now irreplaceable data on a decade-old SSD with no
  backup. `sqlite3 .backup` rather than `cp`, off the hub, and **restore one** before
  believing it.
- **R-001 escalated to P2.** A dashboard exists that the phone cannot reach. Tailscale
  Serve also solves the HTTPS the PWA needs for a service worker.
- **R-006 closed** — the bleak/colmi conflict was avoided rather than managed; the
  reference is read, never installed.
- Roadmap re-sequenced. The old "FastAPI + dashboard" row is gone, and the next two
  sessions are the **sync service** and **backups + remote access** — neither adds a
  metric, and both matter more than the next metric does.

### Second half: the pipeline learns to run itself

- **`hub/sync.py`** — scan, connect, reconcile the sensing policy, read battery, pull
  the last few UTC days of heart rate, archive every frame, store, disconnect. One
  attempt per invocation, then exit: a script under a timer rather than a daemon, so
  there is no long-lived connection to leak and every sync is a discrete journald entry.
  It reads the ring's HR settings before writing them, so a pointless flash write is
  avoided on every sync *and* any drift the hub didn't cause shows up in the log rather
  than as an unexplained battery cliff.
- **Four systemd user units** — `ring-sync.service` + `.timer` (08:00, 14:00, 22:00
  local, `Persistent=true`), and `ring-backup.service` + `.timer` (04:00 nightly).
- **`tools/backup.py`** — R-004, the standing P1. Uses SQLite's backup API rather than
  `cp`, because the store runs in WAL mode and a file copy taken mid-write can produce a
  database that restores corrupt. Verifies every backup it writes with
  `PRAGMA integrity_check` plus a row-count comparison against the source, and rotates.
- **`HUB_SETUP.md` §5 rewritten** as a Tailscale runbook that treats Mullvad as the
  hazard it is: disconnect Mullvad, prove Tailscale works, add `tailscale serve` for the
  HTTPS the PWA needs, *then* reintroduce Mullvad and see what breaks. One change at a
  time, on a headless machine you can lock yourself out of.

**`serve`, not `funnel`.** Serve is tailnet-only, so nothing is exposed publicly and the
privacy claim survives intact. Funnel would only be needed for Architecture B's
`/ingest`, which doesn't exist.

### Two more bugs, both caught by deliberate hostility

**The scan sat outside the try block in `sync.py`.** A powered-off or not-yet-ready
adapter would have escaped as an uncaught traceback instead of being recorded as a
failed run — which is *precisely* the "works by hand, never after a reboot" symptom
R-005 was logged to predict eight days ago. Writing the unit file is what surfaced it:
adding `After=bluetooth.target` prompted the question "and what happens if it fires
anyway?"

**`verify()` in the backup tool leaked an exception instead of reporting.** The first
corruption test zeroed 200 bytes and `integrity_check` said "ok" — correctly, as it
turned out; those bytes were page-1 free space. A weak test that passes is worse than no
test, so the second attempt truncated one file, zeroed a whole data page in another, and
added an empty one. All three now fail cleanly and the tool exits non-zero:

```text
FAIL  truncated    unreadable: database disk image is malformed
FAIL  zeroed page  integrity_check: btreeInitPage() returns error code 11
OK    intact       integrity ok, 75 rows across 7 tables
FAIL  empty        missing or empty
```

That is three bugs in one session found by attacking the artefact rather than reading
the code — the `seq` collision, the dashboard's mislabelled window, and this. The code
looked right in all three cases.

### Third half: the ring talks to the hub without being asked

**The end goal, reached.** BLE → parser → SQLite → API → dashboard, on a timer, with
nobody typing anything.

```text
INFO sensing policy already correct (HR every 30 min)
INFO battery 62% (on battery)
INFO 2026-08-17: 24 frames -> 2 samples
INFO 2026-08-16: 24 frames -> 46 samples
INFO 2026-08-15: 24 frames -> 48 samples
INFO stored 136 new of 136 parsed samples
```

**48/48 on 2026-08-15** — a flawless day at 30-minute intervals. Measurement interval,
slot arithmetic and clock all agreeing across 24 hours.

### The buffer question, finally answered — with a caveat that matters

Walking back 12 days: full 24-frame bursts for every UTC day from **08-09 to 08-17**,
and the `0xFF` sentinel for 08-08 and earlier.

**That floor is not the buffer's edge.** 08-09 is the day HR logging was enabled, so
08-08 is empty because nothing was recorded, not because anything expired. The honest
reading is **at least 9 days, upper bound still unknown**. Re-measure at ~20 days.

Consequence for Architecture B: a weekend away loses *nothing*, and a week probably
doesn't either — sync on return and the gap backfills. The ESP32 satellite drops from
"necessary" to "wanted for its own sake", which is what it was always claimed to be.
The decision to build it stands; its urgency doesn't.

**Two things validated the chain beyond the sample counts.** 2026-08-09 returned 33
samples — exactly the 16 h 53 m left in that UTC day after the clock was written at
07:07. And re-pulling four already-stored days added zero rows: 333 parsed, 198 new,
arithmetic exact. Idempotency proven on real hardware rather than a fixture.

### The design landed

Found the *RavenX Instruments branding* project — it holds an **RX-06 Dashboard**
design built on Nocturne's tokens, and it is better than the generic dark theme I had
invented. Rebuilt `dashboard/` against it: signal green for live, shop orange for
not-yet, blurple for the data, one status line, a single elevated night panel, and the
raven mark in the header.

Its best idea is that **empty is a state, not a gap** — awaiting cards name the session
that will fill them, so the dashboard reads as a build log you happen to wear. That is
exactly honest right now: sleep and steps are dashed placeholders because neither parser
exists.

Two deviations, both recorded in `dashboard/README.md`: no Google Fonts `@import` (an
external request would break offline use and put a third party in the path of a project
premised on not having one), and the mark sits at 30 px rather than 20 px because the
raven is hairline line art that turns to a smudge below ~28.

### Three failures on the way to a working system

- **`request_heart_rate_log` was never implemented.** Its signature was corrected in
  session 4 and the body left raising `NotImplementedError`; `tools/probe_hr_log.py`
  built that packet inline, which is exactly why the probe worked and the service died
  on its first real run. Fixed, then verified by walking `hub/sync.py`'s call graph
  against both protocol modules **programmatically** — eyeballing is what let it through.
- **The venv had a dangling shebang.** It was created at `~/projectring` before the
  directory became `~/Projects/RavenXSmartRing-IOT`, and venvs bake absolute paths into
  every console script. It failed *selectively*: `.venv/bin/python3` is a symlink and
  kept working, so `hub.sync` ran while `ring-dashboard.service` would have died calling
  `.venv/bin/uvicorn`.
- **`ufw` was silently eating the dashboard.** Active by default with deny-incoming and
  a single port-22 rule that `openssh-server` added back in session 1. SSH walked through
  the one door in the wall while every service since was invisible — dropped, not
  refused, so nothing logged anywhere. It presents as "the server stopped responding".

All three are now documented in `HUB_SETUP.md`, because each cost real time and each
will recur on the next machine.

### Open after session 5

- **Tailscale.** The last piece of the original brief. The dashboard is LAN-only behind
  a `ufw` rule that should be deleted once Serve is running, and iOS will not register a
  service worker over plain HTTP — so "Add to Home Screen" gives a bookmark, not an app.
- **No backup has been restored.** `tools/backup.py` verifies its own output; restoring
  one and looking at it is still unowned, and R-004 stays P1 until it happens.
- **`sync.py` never fills `ring_clock_utc` or `clock_offset_s`.** The columns exist for
  R-002 and the sync leaves them null, so clock drift remains unmeasured on real runs.
- Sleep (R-008) and the idle-drain sensing flags (R-014) are still the two big unknowns.
- Buffer depth needs re-measuring at ~20 days to find its real limit.
