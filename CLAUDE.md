# RavenX Smart Ring

Personal health tracker. A Colmi R06 smart ring (QRing protocol family) syncs over BLE
to a home hub — a 2014 MacBook Air running Linux Mint — which stores, analyzes, and
serves a PWA dashboard to an iPhone. No cloud, no accounts, no subscriptions; the data
never leaves hardware Abhi owns.

**Status (2026-08-08):** both rings in hand; session 2 merged to `main`.

- **Hub:** reachable over SSH with the lid closed, Bluetooth working, Python 3.12.3.
  Tailscale and systemd units are **not** set up yet.
- **Protocol:** confirmed against R06_D29C — both vendor GATT services mapped,
  `CMD_BATTERY = 0x03`, checksum is `sum(data[:15]) & 0xFF` (validated bidirectionally),
  and replies echo the command byte in position 0 so they are self-identifying.
- **Hardware:** chipset is **BlueX**, firmware `R06_1.00.06_240921`, hardware `R06_V1.0`.
  The ATC_RF03 custom-firmware groundwork applies to this unit. The BLE address is burned
  into the System ID characteristic and cannot rotate.
- **Running experiment:** the ring has been worn and unsynced since 2026-08-02 00:30 local.
  Buffer depth is measured on the first log dump.

## The fleet (final — do not re-litigate)

| Unit | Role | State |
| --- | --- | --- |
| Colmi R06, size 10 | **DAILY + DEV** | Worn every day; the ring the hub is built against. **Factory-virgin — never paired, RTC never set.** |
| Colmi R09, size 12 | **SHOWCASE + ORACLE** | For the YouTube video. Currently on the stock QRing app as a validation oracle; migrates to the hub at the end. |

No further ring purchases. End state is both rings running the same software, after
which one is chosen for teardown.

## Architecture

**Architecture A now, Architecture B next** — decided 2026-08-02.

```text
A (now):   [R06] --BLE--> [MBA hub] --Tailscale--> [iPhone PWA]

B (next):  [R06] --BLE--> [ESP32-C3] --HTTPS+token--> [MBA hub /ingest]
                          at the second location (5.5h away)
```

A is a single hub with no relay; trips longer than the ring's onboard buffer lose data,
accepted for now. B adds an ESP32-C3 satellite at the second location. A peer-node
alternative (a Pi-class box running the same Python) was costed as cheaper and faster
and **deliberately declined** — the embedded firmware work is wanted for its own sake.
Do not re-propose it.

**Open measurement that gates B:** the R06's onboard buffer depth. Ring put on
2026-08-02 00:30 local (04:30 UTC), synced to nothing. Measured on the first successful
hub sync. That number sets sync cadence, the battery ceiling, and how urgent B is.

## Source-of-truth documents

- `PLAN.md` — mission, architecture, metrics scope, phase plan. Authoritative. If a task
  conflicts with PLAN.md, stop and ask.
- `RESOURCES.md` — external protocol docs and references (colmi_r02_client, Gadgetbridge,
  ATC_RF03), plus the pre-purchase ring compatibility rule.
- `HUB_SETUP.md` — 2014 MacBook Air hub build-out: lid-closed 24/7, SSH, Bluetooth,
  Python env, Tailscale, systemd.
- `notebook.md` — curated session log, written at session end. This is the video's script
  skeleton. Machine-generated 30-minute summaries go to `journal/`, never here.
- `Bug_Backlog.md` — open bugs by priority. High-priority items surface at session start.

## Repo layout

- `protocol/` — QRing packet parsers and command builders (pure functions) + JSON fixtures.
  The single implementation of protocol truth; nothing else parses packets.
- `hub/` — Python: BLE sync service, SQLite store, analytics, FastAPI.
- `dashboard/` — PWA frontend (Chart.js, plain HTML/JS, no build tooling).
- `firmware/` — ESP32-C3 satellite (ESP-IDF/NimBLE), Architecture B. Out of scope until A ships.
- `tools/` — repo tooling (journal automation, session helpers).
- `journal/` — machine-written 30-minute change summaries. Append-only, not curated.

## Division of labor (non-negotiable)

- **Abhi writes the code.** Specifically `protocol/` (parsers, command builders),
  `hub/sync.py` (BLE service), and `hub/db.py` (storage). These are the project.
- **Claude scaffolds.** Create source files with signatures, type hints, docstrings, and
  TODO comments describing what each function must do — **never with function bodies.**
  Abhi fills every body.
- **Claude fully implements** `dashboard/`, `hub/api.py` route plumbing, and all
  boilerplate: requirements, systemd units, `.gitignore`, tooling.
- **Claude owns** documentation, diagrams, and architecture decisions, using Abhi's
  product direction as the guide. Propose improvements proactively rather than waiting.
- **Debugging:** narrow a bug to a function or line range and state what the symptom
  implies, then stop. Do not name the fix or edit the file unless asked.

## Non-negotiable engineering rules

- **Battery is the top constraint.** The ring's sensing schedule is owned by the hub and
  written on every connect — never inherited from whatever the QRing app last set. PPG
  optical duty cycle is the dominant drain; MCU compute is a rounding error, so
  "offload computation to the hub" is not a battery strategy. Default contract: auto-HR
  30 min, SpO2 off, stress/HRV off, accelerometer on, temperature on, **hub syncs 3×/day**.
- **Never connect the R06 to the stock QRing app.** It feeds the vendor cloud and may mark
  the ring's buffered log as delivered, starving the hub. The R09 stays on QRing until its
  oracle role ends.
- **First R06 connect: dump the raw log BEFORE setting the clock.** The ring is
  factory-virgin and its RTC has never been set — a one-shot observation of virgin
  timestamp behavior. The R09 cannot substitute; QRing already time-set it.
- Parsers are pure functions: bytes in, values out. No I/O, no globals, no hidden state.
- All ingest paths are idempotent: dedupe by natural key before insert. Re-syncing stored
  data is harmless. This holds for local syncs and the satellite's `/ingest` equally.
- Dumb radio, smart hub: protocol parsing lives only in `protocol/` and `hub/` Python.
  Satellites forward raw payloads; never reimplement parsing elsewhere.
- **Timestamps: UTC ISO-8601 TEXT everywhere in storage and logic.** Convert to local time
  only at the display layer. The ring's own clock is a separate problem — record the
  ring↔hub offset at sync time; never assume the ring's timestamps are correct.
- **Storage is generic, not ring-shaped.** Scalar time series go in one table keyed by
  `(source, metric, ts_utc)`; structured events (sleep sessions, workouts) get their own
  tables rather than being forced into scalar rows. The hub is a personal telemetry store
  whose first source happens to be a ring — future hub projects must not start from zero.
- **Working code first.** Abhi is an embedded software engineer (C++/Python). Don't lead
  with test structure, don't gate implementation on a test plan, don't add pytest or
  fixture machinery unprompted. Tests come later or on request.
- **Design before code, above a threshold only.** A design doc (Mermaid flow/state/class
  diagrams, signatures not bodies) is required for anything crossing a module boundary or
  touching the protocol. Everything smaller goes straight to code. Do not write a design
  doc for a sixty-line script.
- No frameworks or abstractions beyond what PLAN.md names. Rule of three before any
  abstraction.

## Environment & commands

- Python 3.12.3, venv at `.venv/`; deps: bleak, fastapi, uvicorn[standard]
- Dev happens on the Windows desktop; the hub pulls via git and runs services (systemd
  user units in `hub/systemd/`). **Never assume code executes on the hub.**
- Portable vs. hub-only: `protocol/` parsers, `hub/db.py`, analytics, and FastAPI routes
  run identically on Windows and Linux. `hub/sync.py` (BlueZ via bleak) is hub-only and is
  *expected* to fail immediately on Windows — that is correct behavior, not a bug.
- **Mullvad VPN runs on the hub** (Abhi's decision, 2026-08-02). LAN sharing must stay
  enabled or SSH and the dashboard break. Mullvad and Tailscale both manage routing —
  plan that interaction deliberately when Tailscale goes in; don't let it surprise a session.
- The hub belongs on 5 GHz WiFi: its Broadcom chip shares one 2.4 GHz radio between WiFi
  and Bluetooth, and 2.4 GHz WiFi degrades BLE scanning intermittently.

## Session ritual

- **Session start:** Abhi types `/startup`. Respond with what happened last session, what
  today's session can realistically accomplish in 2–4 hours, a single baseline goal,
  stretch goals, and open high-priority bugs — then a detailed implementation strategy in
  prose. **Explain the approach and give starting ideas; do not write the code.**
- **Session end:** Abhi types `/shutdown`. Survey the working tree, reconcile every
  changed path (asking about anything half-finished before it lands in a PR), capture
  findings that live outside the repo, then update `notebook.md` (one curated entry —
  this is the video's script skeleton, so it carries the narrative), `PLAN.md` §6, and
  `Bug_Backlog.md`. Finish with a commit message and PR body. **Never commit, stage,
  push, or open the PR** — Abhi does those.
- Bugs found mid-session go to `Bug_Backlog.md` immediately, with priority.

## Git workflow

- **Work happens on a session branch, never on `main`.** Name it after the `PLAN.md` §6
  roadmap row: `session-02-gatt-enumeration`. Branch, roadmap row, and `notebook.md`
  entry then share one number.
- **`main` is the hub's deployment target.** The hub has `~/Projects/RavenXSmartRing-IOT` checked out on
  `main` and will eventually run `hub/sync.py` from it under a systemd timer. Anything
  merged to `main` is assumed runnable; half-finished work stays on the branch.
- **Squash-merge the PR at session end**, so `main` carries one commit per session.
- Keep the process thin: no PR templates, no required checks, no self-review ceremony.
  The value is the diff as a self-review surface and a clean `main` — nothing more.
- No `Co-Authored-By` trailer on commits in this repo.

## Style

- Dashboard v1: rudimentary but not ugly. Dark theme, glanceable daily/weekly/monthly
  charts. Priority metrics are **sleep, activity, and heart rate**; SpO2 and VO2max are
  deprioritized. Composite scores (sleep score, readiness, stress) stay deferred until
  ~2 weeks of real baseline data exist.
- Prefer editing existing files over creating new ones; no speculative modules.
- Language guidelines live in `.claude/skills/` (`python-engineering`, `cpp-embedded`).
