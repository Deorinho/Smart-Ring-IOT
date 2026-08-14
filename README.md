# RavenX Smart Ring

Personal health tracker. A Colmi R06 smart ring syncs over BLE to a home hub — a 2014
MacBook Air running Linux Mint — which stores, analyzes, and serves a PWA dashboard to
an iPhone. No cloud, no accounts, no subscriptions; the data never leaves hardware the
owner controls.

```text
[Colmi R06] --BLE--> [MacBook Air hub] --Tailscale--> [iPhone PWA]
   PPG + accel          protocol parsers               dark-theme
   logs to a            SQLite telemetry store         charts,
   288-slot day         FastAPI read-only API          glanceable
```

**Status (2026-08-13):** real heart-rate data flows from ring to parser to SQLite to a
dashboard. Resting HR measured at 51 bpm. Still manual — the BLE sync service and
remote access are next.

## What works

- **Protocol** — the QRing dialect is mapped far enough to be useful: battery, heart-rate
  log, log settings, and clock, with the checksum and framing verified bidirectionally
  against the ring itself.
- **Storage** — a generic telemetry schema keyed by `(source, metric, ts_utc)`. Ingest is
  idempotent by construction, so re-syncing is free.
- **Dashboard** — dark, phone-first, zero dependencies. Charts are hand-rolled SVG.

## What doesn't yet

- Nothing syncs on its own; captures are pulled by hand with `tools/`.
- The dashboard is LAN-only until Tailscale goes in.
- Sleep — the top-priority metric — is still unmapped.
- `ring.db` has no backup. See `Bug_Backlog.md` R-004.

## Layout

- `protocol/` — packet parsers and command builders (pure functions) + captured fixtures
- `hub/` — SQLite store, read-only API, config, systemd units
- `dashboard/` — the PWA
- `tools/` — probes, capture inspection, offline ingest
- `firmware/` — ESP32-C3 satellite, Architecture B, not started

## Docs

- `PLAN.md` — mission, architecture, metrics, session roadmap
- `HUB_SETUP.md` — building the MacBook Air into an always-on hub
- `RESOURCES.md` — external protocol references
- `notebook.md` — session log, and the script skeleton for the video
- `Bug_Backlog.md` — open defects and known risks
- `CLAUDE.md` — engineering rules and conventions for AI-assisted work
