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
