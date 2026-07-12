# Project Ring

Personal health tracker: a QRing-family smart ring (Ruofine R09/R10) syncs over BLE
to a home hub (2014 MacBook Air, Linux Mint) that stores, analyzes, and serves a PWA
dashboard. No cloud, no accounts, no subscriptions — data never leaves hardware the
owner controls. **Status:** framework phase — hardware purchase is deferred on
funding; hub, parsers, and dashboard are being built and proven against synthetic
data first (Phase 0a, see PLAN.md §5).

## Source-of-truth documents (read before structural or planning work)
- `PLAN.md` — mission, architecture (incl. the Travel Protocol satellite, §2.1),
  metrics scope, BOM, phase plan, testing strategy. Authoritative. If a task
  conflicts with PLAN.md, stop and ask.
- `RESOURCES.md` — external protocol docs and references (colmi_r02_client,
  Gadgetbridge, ATC_RF03), plus the reading order for the zero-hardware phase.
- `HUB_SETUP.md` — 2014 MacBook Air hub build-out: lid-closed 24/7, SSH,
  Bluetooth, Python env, Tailscale, systemd service pattern.
- `notebook.md` — running dev log. Append an entry after every working session:
  date, what was done, what broke, open questions.

## Repo layout
- `protocol/` — protocol documentation + JSON test vectors (shared fixtures)
- `hub/` — Python: BLE sync service, parsers, SQLite, analytics, FastAPI
  (including the `/ingest` route the Travel Protocol satellite posts to)
- `dashboard/` — PWA frontend (Chart.js, plain HTML/JS; no build tooling for v1)
- `firmware/` — Phase 3 ring firmware (C, R09 units only) and the ESP32-C3
  Travel Protocol satellite (ESP-IDF/NimBLE) — both out of scope until their
  respective phases (see PLAN.md §5)

## Non-negotiable engineering rules
- IMPORTANT: Parsers are pure functions validated against JSON test vectors in
  `protocol/fixtures/`. Every parser change runs the fixture suite. New packet
  knowledge becomes a fixture first, code second.
- All ingest paths are idempotent: dedupe by (metric, timestamp) before insert.
  Re-syncing already-stored data must be harmless — this covers local hub syncs
  and the satellite's `/ingest` posts equally.
- Dumb radio, smart hub: protocol parsing lives only in `hub/` Python. Satellites
  and clients forward raw payloads; never reimplement parsing elsewhere.
- IMPORTANT: never sync a project ring with the stock QRing app once the hub owns
  it, except the brief Phase 0b oracle-validation window called out in PLAN.md §6.
  The stock app feeds the vendor cloud and may mark the ring's buffered onboard
  log as delivered, starving the hub of data it hasn't pulled yet.
- The satellite's ring buffer is sacred: it may only mark a payload delivered
  after the hub acknowledges receipt. If WiFi/hub is unreachable, it does not pull.
- The owner is a Python test engineer: pytest-first, small pure functions,
  fixtures over mocks. Don't add frameworks or abstractions beyond what PLAN.md names.
- SQLite timestamps: store as UTC ISO-8601 TEXT everywhere. One convention, no exceptions.

## Environment & commands
- Python 3.12+, venv at `.venv/`; deps: bleak, fastapi, uvicorn[standard], pytest
- Tests: `pytest` from repo root
- Dev runs on the desktop PC; the hub only pulls via git and runs services
  (systemd user units live in `hub/systemd/`). Never assume code executes on the hub.
- Hardware not yet purchased (Phase 0b is funding-gated, see PLAN.md §8): all
  pipeline work runs against fixtures and the synthetic-data generator. Do not
  write code that requires a live ring, a real ESP32-C3, or other physical
  hardware unless asked.

## Style
- Keep dashboard v1 rudimentary but not ugly — dark theme, glanceable
  daily/weekly/monthly charts. Owner provides layout feedback iteratively.
- Prefer editing existing files over creating new ones; no speculative modules.
