-- RavenX hub — SQLite schema
--
-- Design rule (CLAUDE.md): this is a personal telemetry store whose first source
-- happens to be a ring, NOT a ring database. Scalar time series live in one generic
-- table keyed by (source, metric, ts_utc). Structured things with a duration and
-- internal shape (sleep sessions, workouts) get their own tables rather than being
-- crushed into scalar rows.
--
-- Timestamps are UTC ISO-8601 TEXT everywhere. No exceptions, no local time, no epochs.
-- Format: 'YYYY-MM-DDTHH:MM:SSZ'

PRAGMA journal_mode = WAL;      -- survives an unclean shutdown; the hub is a laptop
PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------------------
-- Sources: anything that produces telemetry. The ring is source #1; a furnace,
-- a car, or a second ring join later without a schema change.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sources (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE,   -- 'R06_D29C'
    kind        TEXT NOT NULL,          -- 'ring'
    identifier  TEXT,                   -- BLE MAC, '81:5F:4A:87:D2:9C'
    notes       TEXT
);

-- ---------------------------------------------------------------------------
-- Metric registry. Not enforced by a foreign key — it's a declaration of what a
-- metric means and what unit it carries, so a value read in 2028 is unambiguous.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS metrics (
    name        TEXT PRIMARY KEY,
    unit        TEXT NOT NULL,
    description TEXT
);

INSERT OR IGNORE INTO metrics (name, unit, description) VALUES
    ('heart_rate',  'bpm',     'Instantaneous PPG heart rate sample'),
    ('spo2',        'percent', 'Blood oxygen saturation'),
    ('skin_temp',   'celsius', 'Skin temperature at the finger'),
    ('steps',       'count',   'Steps accumulated in the reporting interval'),
    ('battery',     'percent', 'Ring battery level at sync time'),
    ('battery_charging', 'bool', '1 while the ring sits on the charger, 0 on the finger.
                                  Sampled only at sync time, so it is a snapshot of that
                                  moment and not a record of when charging started'),
    ('hrv',         'ms',      'Heart rate variability, ring-reported daily average'),
    ('stress',      'index',   'Ring-reported stress index, vendor scale');

-- ---------------------------------------------------------------------------
-- Samples: the generic scalar core.
--
-- The primary key IS the idempotency guarantee required by CLAUDE.md — re-ingesting
-- an already-stored reading is a no-op via INSERT OR IGNORE, with no read-then-write
-- race. This is what makes re-syncing harmless and what will make the Architecture B
-- satellite's /ingest safe without any extra logic.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS samples (
    source_id   INTEGER NOT NULL REFERENCES sources(id),
    metric      TEXT    NOT NULL,
    ts_utc      TEXT    NOT NULL,
    value       REAL    NOT NULL,
    PRIMARY KEY (source_id, metric, ts_utc)
) WITHOUT ROWID;

CREATE INDEX IF NOT EXISTS idx_samples_metric_time ON samples (metric, ts_utc);

-- ---------------------------------------------------------------------------
-- Events: things with a start, an end, and internal structure.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS events (
    id          INTEGER PRIMARY KEY,
    source_id   INTEGER NOT NULL REFERENCES sources(id),
    kind        TEXT    NOT NULL,       -- 'sleep_session' | 'workout'
    start_utc   TEXT    NOT NULL,
    end_utc     TEXT,
    UNIQUE (source_id, kind, start_utc)
);

CREATE TABLE IF NOT EXISTS event_stages (
    event_id    INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    seq         INTEGER NOT NULL,
    stage       TEXT    NOT NULL,       -- 'light' | 'deep' | 'rem' | 'awake'
    start_utc   TEXT    NOT NULL,
    end_utc     TEXT    NOT NULL,
    PRIMARY KEY (event_id, seq)
);

-- ---------------------------------------------------------------------------
-- Sync runs: one row per sync attempt, successful or not.
--
-- clock_offset_s exists because of Bug_Backlog R-002: the R06's RTC has never been
-- set, so the ring's idea of "now" is not the hub's. Every run records what the ring
-- believed the time was, so ring-relative timestamps can be corrected into real UTC
-- afterwards. Without this column the store silently fills with plausible-looking
-- wrong times.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sync_runs (
    id              INTEGER PRIMARY KEY,
    source_id       INTEGER REFERENCES sources(id),
    started_utc     TEXT    NOT NULL,
    finished_utc    TEXT,
    status          TEXT    NOT NULL,   -- 'ok'|'no_device'|'ble_error'|'parse_error'
    rows_ingested   INTEGER NOT NULL DEFAULT 0,
    ring_clock_utc  TEXT,               -- what the ring thought the time was
    clock_offset_s  REAL,               -- ring minus hub, in seconds
    note            TEXT
);

-- ---------------------------------------------------------------------------
-- Raw payload archive.
--
-- Every packet received, stored verbatim, forever. This exists because the QRing
-- protocol is reverse-engineered and incomplete: when the parser improves, history
-- gets RE-parsed instead of being lost. A byte you didn't understand in August is
-- still on disk in December.
--
-- This is also what makes Architecture B's "dumb radio" honest — the satellite
-- forwards raw payloads and they land here exactly like local ones.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS raw_payloads (
    id           INTEGER PRIMARY KEY,
    sync_run_id  INTEGER NOT NULL REFERENCES sync_runs(id),
    seq          INTEGER NOT NULL,
    received_utc TEXT    NOT NULL,
    payload      BLOB    NOT NULL,
    UNIQUE (sync_run_id, seq)
);
