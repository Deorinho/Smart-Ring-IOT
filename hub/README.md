# hub/

Runs on the 2014 MacBook Air (Linux Mint), 24/7, lid closed.

- Sync service (Python + `bleak`) — auto-detects ring in BLE range, pulls onboard log, dedupes, stores.
- SQLite time-series store.
- Analytics layer — daily/weekly/monthly rollups, sleep session detection, activity bucketing, calorie model.
- FastAPI — JSON API + serves the dashboard PWA.
- systemd unit(s) for always-on operation.
