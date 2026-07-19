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
