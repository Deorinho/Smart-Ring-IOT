# hub/

Python running on the 2014 MacBook Air.

| File | What it is |
| --- | --- |
| `config.py` | Paths, ring identities, the sensing policy, sync cadence. Nothing else hardcodes a MAC or an interval. |
| `schema.sql` | The telemetry store. Generic by design — scalar series in `samples`, structured things in `events`, every raw frame in `raw_payloads`. |
| `db.py` | Thin I/O over the schema. Idempotent inserts, sync-run bookkeeping, query helpers. No parsing, no analytics. |
| `api.py` | Read-only JSON API and PWA host. Cannot write, by construction. |
| `systemd/` | User units. `enable-linger` is required or they stop when you log out. |

**Not here yet:** `sync.py`, the BLE service. It is the only hub-only module — everything
above runs identically on Windows and Linux, which is why storage could be built and
tested on the desktop without a ring attached.

Run the API:

```bash
.venv/bin/uvicorn hub.api:app --host 0.0.0.0 --port 8000
```

Point it at a throwaway store while developing:

```bash
RAVENX_DATA_DIR=/tmp/ravenx .venv/bin/uvicorn hub.api:app --port 8000
```
