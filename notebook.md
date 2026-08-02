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
