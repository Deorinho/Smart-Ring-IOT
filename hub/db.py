"""SQLite storage for the hub — a personal telemetry store, not a ring database.

Thin I/O shell over `schema.sql`. No analytics, no parsing, no business logic: values
come in already typed from `protocol/`, rows go out for analytics and the API to shape.

Three properties this module exists to guarantee:

* **Idempotent ingest.** `insert_samples` uses `INSERT OR IGNORE` against a primary key
  of `(source_id, metric, ts_utc)`, so re-ingesting a capture is a no-op with no
  read-then-write race. Re-syncing stored data is harmless by construction rather than
  by care, which is what makes the Architecture B satellite safe later.
* **One timestamp format.** The primary key includes `ts_utc` as TEXT, so dedupe is
  *string* equality. `2026-08-09T07:30:00Z` and `2026-08-09T07:30:00+00:00` are the same
  instant and two different rows. Everything writing a timestamp goes through
  `to_iso_utc`; nothing formats one by hand.
* **Foreign keys actually enforced.** `PRAGMA foreign_keys` is per-connection, not a
  property of the file. Setting it once in `schema.sql` only affects the connection that
  ran the script, so `connect()` sets it every time.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable, Sequence
from datetime import datetime, timezone
from pathlib import Path

from hub.config import DB_PATH, SCHEMA_PATH, Ring
from protocol.packets import Sample

ISO_UTC = "%Y-%m-%dT%H:%M:%SZ"


def to_iso_utc(moment: datetime) -> str:
    """Render a datetime as the project's one canonical timestamp string.

    Naive datetimes are assumed to be UTC rather than local — a silent local
    interpretation on a hub that runs in EDT would shift every row by four hours.
    """
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc).strftime(ISO_UTC)


def utc_now_iso() -> str:
    return to_iso_utc(datetime.now(timezone.utc))


# --- Connection ------------------------------------------------------------
def connect(path: Path | None = None) -> sqlite3.Connection:
    """Open the store, creating and initialising it if this is a fresh disk.

    Applying the schema on connect rather than in a separate setup step means a service
    meeting an empty data directory just works, which matters for a box that may be
    reinstalled without ceremony.
    """
    db_path = path or DB_PATH
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    # Per-connection, every time. See the module docstring.
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")

    if not _is_initialised(conn):
        apply_schema(conn)

    return conn


def _is_initialised(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='samples'"
    ).fetchone()
    return row is not None


def apply_schema(conn: sqlite3.Connection, schema_path: Path | None = None) -> None:
    """Run `schema.sql`. Uses executescript because `execute` stops at the first `;`."""
    sql = (schema_path or SCHEMA_PATH).read_text(encoding="utf-8")
    conn.executescript(sql)
    conn.commit()


# --- Sources ---------------------------------------------------------------
def ensure_source(conn: sqlite3.Connection, ring: Ring) -> int:
    """Return the row id for a ring, registering it on first sight.

    Keyed on `name`, which is stable: the BLE address is burned into the ring's System
    ID characteristic and cannot rotate, and the advertised name derives from it.
    """
    conn.execute(
        "INSERT OR IGNORE INTO sources (name, kind, identifier) VALUES (?, 'ring', ?)",
        (ring.name, ring.address),
    )
    conn.commit()
    row = conn.execute(
        "SELECT id FROM sources WHERE name = ?", (ring.name,)
    ).fetchone()
    return int(row["id"])


# --- Samples ---------------------------------------------------------------
def insert_samples(
    conn: sqlite3.Connection, source_id: int, samples: Iterable[Sample]
) -> int:
    """Store scalar readings. Returns how many rows were actually new.

    That return value is the idempotency proof: ingest a capture twice and the second
    call returns 0. Counted from `total_changes` rather than `cursor.rowcount`, which
    is unreliable across `executemany` with `OR IGNORE`.
    """
    rows = [(source_id, s.metric, s.ts_utc, s.value) for s in samples]
    if not rows:
        return 0

    before = conn.total_changes
    conn.executemany(
        "INSERT OR IGNORE INTO samples (source_id, metric, ts_utc, value)"
        " VALUES (?, ?, ?, ?)",
        rows,
    )
    conn.commit()
    return conn.total_changes - before


def samples_between(
    conn: sqlite3.Connection, metric: str, start_utc: str, end_utc: str
) -> list[sqlite3.Row]:
    """Readings for one metric in a half-open window, oldest first."""
    return conn.execute(
        "SELECT ts_utc, value FROM samples"
        " WHERE metric = ? AND ts_utc >= ? AND ts_utc < ? ORDER BY ts_utc",
        (metric, start_utc, end_utc),
    ).fetchall()


def latest_sample(conn: sqlite3.Connection, metric: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT ts_utc, value FROM samples WHERE metric = ?"
        " ORDER BY ts_utc DESC LIMIT 1",
        (metric,),
    ).fetchone()


def metric_days(conn: sqlite3.Connection, metric: str) -> list[sqlite3.Row]:
    """Per-UTC-day count, min, max and mean for a metric — the cheap overview.

    Uses `substr(ts_utc, 1, 10)` for the day key, which is only correct because every
    timestamp is written in one fixed-width UTC format. Another reason nothing formats
    timestamps by hand.
    """
    return conn.execute(
        "SELECT substr(ts_utc, 1, 10) AS day, COUNT(*) AS n,"
        " MIN(value) AS lo, MAX(value) AS hi, AVG(value) AS avg"
        " FROM samples WHERE metric = ? GROUP BY day ORDER BY day",
        (metric,),
    ).fetchall()


# --- Sync runs -------------------------------------------------------------
def start_sync_run(conn: sqlite3.Connection, source_id: int | None) -> int:
    """Open a sync-run row. Every attempt gets one, successful or not.

    Recording failures is the point: a store that only remembers successes cannot tell
    you the ring has been unreachable for two days.
    """
    cur = conn.execute(
        "INSERT INTO sync_runs (source_id, started_utc, status) VALUES (?, ?, 'running')",
        (source_id, utc_now_iso()),
    )
    conn.commit()
    return int(cur.lastrowid)


def finish_sync_run(
    conn: sqlite3.Connection,
    run_id: int,
    status: str,
    rows_ingested: int = 0,
    ring_clock_utc: str | None = None,
    clock_offset_s: float | None = None,
    note: str | None = None,
) -> None:
    """Close a sync run. `status` is one of ok | no_device | ble_error | parse_error."""
    conn.execute(
        "UPDATE sync_runs SET finished_utc = ?, status = ?, rows_ingested = ?,"
        " ring_clock_utc = ?, clock_offset_s = ?, note = ? WHERE id = ?",
        (
            utc_now_iso(),
            status,
            rows_ingested,
            ring_clock_utc,
            clock_offset_s,
            note,
            run_id,
        ),
    )
    conn.commit()


def last_ok_sync_utc(conn: sqlite3.Connection, source_id: int) -> str | None:
    """When this source last synced successfully, or None.

    Feeds the minimum-interval guard. That guard protects the ring's battery from a
    misbehaving trigger — a timer that fires every minute because someone fat-fingered
    a systemd unit should cost nothing, not drain the ring by Thursday.
    """
    row = conn.execute(
        "SELECT finished_utc FROM sync_runs"
        " WHERE source_id = ? AND status = 'ok' AND finished_utc IS NOT NULL"
        " ORDER BY id DESC LIMIT 1",
        (source_id,),
    ).fetchone()
    return row["finished_utc"] if row else None


def recent_sync_runs(conn: sqlite3.Connection, limit: int = 10) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM sync_runs ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()


# --- Raw payloads ----------------------------------------------------------
def store_raw_payloads(
    conn: sqlite3.Connection,
    sync_run_id: int,
    payloads: Sequence[bytes],
    seq_start: int = 0,
) -> int:
    """Archive frames verbatim against a sync run. Returns rows written.

    The protocol is reverse-engineered and incomplete, so bytes that cannot be
    interpreted today are re-parsed later rather than lost. `seq` preserves arrival
    order, which has already mattered once — an unsolicited status push landed
    mid-burst and only its position revealed it wasn't a reply.

    **`seq_start` is not optional bookkeeping.** `seq` is unique per sync run, so a
    caller storing several batches must advance it. Restarting at 0 for each batch
    makes `INSERT OR IGNORE` silently drop every frame after the first batch — which is
    exactly the data loss this table exists to prevent, and it is invisible without
    counting rows.
    """
    if not payloads:
        return 0

    before = conn.total_changes
    conn.executemany(
        "INSERT OR IGNORE INTO raw_payloads (sync_run_id, seq, received_utc, payload)"
        " VALUES (?, ?, ?, ?)",
        [
            (sync_run_id, seq_start + offset, utc_now_iso(), payload)
            for offset, payload in enumerate(payloads)
        ],
    )
    conn.commit()
    return conn.total_changes - before
