# Notebook

Session log — date, what worked, what broke, how long it took. This file is the script skeleton for Phase 4.

---

## 2026-07-11

- Added `PLAN.md` to the repo (see file for full plan).
- Scaffolded the monorepo per Phase 0 / Week 0: `protocol/`, `hub/`, `dashboard/`, `firmware/`, `notebook.md`.
- Status per plan: models selected (1x Ruofine R10 sz 10, 2x Ruofine R09 sz 9), order pending final size confirmation.
- Next: jeweler sizing confirmation for the R10, then place the parts order (blocking all Phase 0 hardware work).

## 2026-07-12

- Reframed the plan around a "zero-hardware framework" phase (Phase 0a/0b split in
  PLAN.md): hub, parsers, and dashboard get built and proven against synthetic data
  now, with the actual ring purchase deferred and gated on funding rather than only
  jeweler sizing.
- Added `HUB_SETUP.md` (2014 MacBook Air always-on hub build-out) and `RESOURCES.md`
  (annotated external doc index) to the repo root.
- Added the Travel Protocol design to PLAN.md (§2.1): an ESP32-C3 satellite that
  pulls raw ring payloads over BLE in Mississauga and forwards them, unparsed, to
  the hub's new `/ingest` route via Tailscale Funnel — doubles as a low-risk Phase 3
  rehearsal.
- Wrote `CLAUDE.md` with the repo's engineering rules (idempotent ingest, dumb
  radio/smart hub, no stock-app syncing once the hub owns a ring, UTC ISO-8601
  timestamps) and kept it in sync with PLAN.md as both evolved.
- Slimmed the four directory READMEs (`protocol/`, `hub/`, `dashboard/`,
  `firmware/`) to 2-4 lines each — what lives there plus a PLAN.md section
  pointer — removing stale phase/week specifics (dashboard/README.md had cited
  outdated "weeks 8-9").
- Verified `.gitignore` doesn't exist and `notebook.md` + all `README.md` files
  are tracked — nothing was being silently excluded from git.
- Committed the above as the baseline commit.
- Still no application code written; still $0 spent.
