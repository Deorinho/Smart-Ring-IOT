# RavenX Smart Ring

Personal health tracker. A Colmi R06 smart ring syncs over BLE to a home hub — a 2014
MacBook Air running Linux Mint — which stores, analyzes, and serves a PWA dashboard to
an iPhone. No cloud, no accounts, no subscriptions; the data never leaves hardware the
owner controls.

```text
[Colmi R06] --BLE--> [MacBook Air hub] --Tailscale--> [iPhone PWA]
             ring        sync service                    dark-theme
             buffers     SQLite store                    charts
             onboard     analytics + FastAPI
```

**Status (2026-08-02):** both rings in hand, hub build-out in progress. No application
code yet.

- `PLAN.md` — mission, architecture, metrics, phase plan
- `HUB_SETUP.md` — building the MacBook Air into an always-on hub
- `RESOURCES.md` — external protocol references
- `notebook.md` — session log
- `Bug_Backlog.md` — open defects and known risks
- `CLAUDE.md` — engineering rules and repo conventions for AI-assisted work
