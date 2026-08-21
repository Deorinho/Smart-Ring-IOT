"""JSON API and PWA host. Reads the store; never writes to it.

Serves what `hub/db.py` stores. No writing, no parsing — a browser hitting this cannot
mutate a single row. That property is deliberate and load-bearing: a bug or compromise
in the reader cannot corrupt the store.

**One qualification, added with the dashboard's Sync button.** `POST /api/sync` exists,
so this is no longer a strictly read-only surface. It does not write either: it asks
systemd to start `ring-sync-now.service`, the same BLE path the timer already uses, and
that separate process does the writing under its own identity. The blast radius of this
endpoint is therefore "can cause a sync to happen", not "can change stored data" — and
`MANUAL_SYNC_COOLDOWN_S` bounds even that. If a future change makes this module able to
touch the database directly, the property is gone and the docstring is a lie.

Every timestamp leaving this API is UTC ISO-8601, exactly as stored. Conversion to
local time happens in the browser, which is the display layer and the only place it
belongs.

    uvicorn hub.api:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import subprocess
import sqlite3
import time
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from hub import db
from hub.config import (
    BATTERY_ALERT_PERCENT,
    DB_PATH,
    MANAGED_RINGS,
    MANUAL_SYNC_COOLDOWN_S,
    REPO_ROOT,
    SYNC_HOURS_LOCAL,
    STALE_SYNC_ALERT_HOURS,
    SYNC_STATUS_CMD,
    SYNC_TRIGGER_CMD,
)

DASHBOARD_DIR = REPO_ROOT / "dashboard"

# Metrics the dashboard is allowed to ask for. An allowlist rather than free-form
# input: `metric` reaches a SQL query, and while it is parameterised, constraining the
# surface costs one tuple and removes the question entirely.
KNOWN_METRICS = (
    "heart_rate",
    "steps",
    "skin_temp",
    "spo2",
    "battery",
    "battery_charging",
    "hrv",
    "stress",
)

app = FastAPI(title="RavenX Smart Ring", docs_url=None, redoc_url=None)


def _conn() -> sqlite3.Connection:
    return db.connect(DB_PATH)


def _require_metric(metric: str) -> str:
    if metric not in KNOWN_METRICS:
        raise HTTPException(404, f"unknown metric: {metric}")
    return metric


@app.get("/api/health")
def health() -> dict:
    """Liveness plus enough state to tell whether the pipeline is actually working.

    `last_sample_utc` is the field that matters: a store that is up but hasn't received
    a reading in two days looks identical to a healthy one from any other angle.

    `runs_today` backs the dashboard's single status line. Three scheduled syncs a day
    means "2/3" is a legible statement about whether the machinery is keeping up —
    more useful at a glance than a raw timestamp, and cheap to compute.
    """
    conn = _conn()
    try:
        latest = db.latest_sample(conn, "heart_rate")
        runs = db.recent_sync_runs(conn, limit=1)
        total = conn.execute("SELECT COUNT(*) AS c FROM samples").fetchone()["c"]

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        counted = conn.execute(
            "SELECT status, COUNT(*) AS c FROM sync_runs"
            " WHERE started_utc LIKE ? GROUP BY status",
            (f"{today}%",),
        ).fetchall()
        by_status = {r["status"]: r["c"] for r in counted}

        return {
            "ok": True,
            "samples": total,
            "last_sample_utc": latest["ts_utc"] if latest else None,
            "last_sync": dict(runs[0]) if runs else None,
            "runs_today": {
                "ok": by_status.get("ok", 0),
                "total": sum(by_status.values()),
                "expected": len(SYNC_HOURS_LOCAL),
            },
            "rings": [{"name": r.name, "address": r.address} for r in MANAGED_RINGS],
        }
    finally:
        conn.close()


@app.get("/api/latest")
def latest() -> dict:
    """Most recent reading for every known metric — what the glance view needs."""
    conn = _conn()
    try:
        out: dict[str, dict | None] = {}
        for metric in KNOWN_METRICS:
            row = db.latest_sample(conn, metric)
            out[metric] = dict(row) if row else None
        return out
    finally:
        conn.close()


@app.get("/api/series/{metric}")
def series(
    metric: str,
    days: int = Query(default=1, ge=1, le=90, description="how far back, in days"),
) -> dict:
    """Raw readings for a metric over the last N days, oldest first."""
    _require_metric(metric)
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)

    conn = _conn()
    try:
        rows = db.samples_between(
            conn, metric, db.to_iso_utc(start), db.to_iso_utc(end)
        )
        return {
            "metric": metric,
            "start_utc": db.to_iso_utc(start),
            "end_utc": db.to_iso_utc(end),
            "points": [{"t": r["ts_utc"], "v": r["value"]} for r in rows],
        }
    finally:
        conn.close()


@app.get("/api/days/{metric}")
def days(metric: str) -> dict:
    """Per-UTC-day count, min, max and mean. The weekly/monthly view."""
    _require_metric(metric)
    conn = _conn()
    try:
        return {
            "metric": metric,
            "days": [dict(r) for r in db.metric_days(conn, metric)],
        }
    finally:
        conn.close()


@app.get("/api/sync-runs")
def sync_runs(limit: int = Query(default=20, ge=1, le=200)) -> dict:
    """Recent sync attempts, successful or not. Failures are the interesting ones."""
    conn = _conn()
    try:
        return {"runs": [dict(r) for r in db.recent_sync_runs(conn, limit)]}
    finally:
        conn.close()


# --- Alerting --------------------------------------------------------------


@app.get("/api/alert")
def alert() -> dict:
    """One question: is there anything about the ring I should act on right now?

    Bug_Backlog R-009. Built for an iOS Shortcuts automation rather than Web Push, and
    that is a deliberate choice. Web Push works on an installed iOS PWA, but Apple expires
    push subscriptions for apps you have not opened in a while -- so a warning needed once
    every 5.5 days would run on a mechanism designed to garbage-collect exactly that kind
    of dormancy, and its failure mode is silence. You would discover it was broken by not
    being warned, which is the same trap as an unrestored backup.

    A daily Shortcut cannot silently expire, needs no keys, no crypto, no third party, and
    no dependency. It also does not need to be fast: at ~17-18%/day you cannot act on a
    low battery sooner than the next time you pass a charger.

    All the thinking happens here so the phone side stays three steps. Shortcuts' JSON
    handling is clumsy, and logic split across a hub and a phone automation is logic that
    rots on the side you cannot read.

    Two conditions, because a flat ring and a stopped hub are equally invisible and only
    one of them is what people think to check.
    """
    conn = _conn()
    try:
        now = datetime.now(timezone.utc)
        reasons: list[str] = []

        battery = db.latest_sample(conn, "battery")
        if battery is not None and battery["value"] <= BATTERY_ALERT_PERCENT:
            pct = int(battery["value"])
            # Days remaining from the measured drain rate, not a guess. Deliberately not
            # shown below one day: "0.4 days" invites precision the gauge cannot support,
            # and CLAUDE.md's standing rule is that this gauge is badly non-linear.
            days_left = pct / 17.5
            whole = round(days_left)
            tail = (
                f"about {whole} day{'s' if whole != 1 else ''} left"
                if days_left >= 1
                else "charge it today"
            )
            reasons.append(f"Ring battery {pct}% - {tail}")

        latest = db.latest_sample(conn, "heart_rate")
        if latest is None:
            reasons.append("No readings stored at all")
        else:
            age_h = (now - _parse_iso(latest["ts_utc"])).total_seconds() / 3600
            if age_h >= STALE_SYNC_ALERT_HOURS:
                reasons.append(f"No new readings for {age_h:.0f} h - hub may not be syncing")

        return {
            "alert": bool(reasons),
            "message": " | ".join(reasons) if reasons else "Ring OK",
            "checked_utc": db.to_iso_utc(now),
        }
    finally:
        conn.close()


def _parse_iso(ts: str) -> datetime:
    """Parse the project's one canonical timestamp format back into an aware datetime.

    Everything in storage is written by `db.to_iso_utc`, so the trailing Z is guaranteed
    -- but `fromisoformat` did not accept Z before Python 3.11 and the hub runs 3.12
    while the desktop runs 3.14. Swapping it for +00:00 costs nothing and removes the
    version question entirely.
    """
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


# --- Manual sync -----------------------------------------------------------
# The only non-GET route in this module. See the module docstring for why it does not
# break the "the reader cannot mutate the store" property.

_last_trigger = 0.0


def _sync_running() -> bool:
    """True while ring-sync-now.service is starting or running.

    `is-active` exits non-zero for inactive and failed units, so the return code is
    useless on its own -- a failed sync and an idle one are both non-zero. The stdout
    word is what carries the meaning.
    """
    try:
        done = subprocess.run(
            SYNC_STATUS_CMD, capture_output=True, text=True, timeout=5
        )
    except (OSError, subprocess.SubprocessError):
        # systemd unreachable is not the same as "a sync is running". Reporting False
        # lets the UI stop waiting instead of spinning forever on a hub that cannot
        # answer, and the sync-run row is the source of truth for what happened anyway.
        return False
    return done.stdout.strip() in ("active", "activating", "reloading")


@app.post("/api/sync", status_code=202)
def trigger_sync() -> dict:
    """Ask systemd to run one forced BLE sync. Returns immediately; poll for the result.

    202 rather than 200 on purpose: nothing has synced yet when this returns. A real sync
    takes ~25 s of radio time, which is far too long to hold a request open on a phone
    that may lock its screen halfway through.
    """
    global _last_trigger

    if _sync_running():
        # Not an error. The user pressed twice, or a scheduled run is already going.
        return {"started": False, "reason": "a sync is already running"}

    waited = time.monotonic() - _last_trigger
    if waited < MANUAL_SYNC_COOLDOWN_S:
        raise HTTPException(
            429,
            f"wait {MANUAL_SYNC_COOLDOWN_S - waited:.0f}s before syncing again",
        )

    try:
        done = subprocess.run(
            SYNC_TRIGGER_CMD, capture_output=True, text=True, timeout=10
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise HTTPException(503, f"could not reach systemd: {exc}") from exc

    if done.returncode != 0:
        # Most likely the unit is not installed. Say so rather than leaving the phone
        # spinning -- this is the failure a fresh hub will hit first.
        raise HTTPException(
            503,
            f"systemd refused to start the sync: {done.stderr.strip() or 'unknown error'}",
        )

    _last_trigger = time.monotonic()
    return {"started": True}


@app.get("/api/sync/status")
def sync_status() -> dict:
    """Whether a sync is in flight, plus the most recent run.

    The dashboard polls this after triggering. It compares `last_run.id` against the one
    it saw before pressing, which is what distinguishes "finished" from "has not started
    yet" -- a run that fails still writes a row, so the id moving is a reliable signal in
    a way that "did new samples appear" is not.
    """
    conn = _conn()
    try:
        runs = db.recent_sync_runs(conn, limit=1)
        return {
            "running": _sync_running(),
            "last_run": dict(runs[0]) if runs else None,
        }
    finally:
        conn.close()


# --- PWA -------------------------------------------------------------------
# Mounted last so the /api routes above win. The dashboard is plain files; there is no
# build step and nothing to compile.
if DASHBOARD_DIR.is_dir():

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(DASHBOARD_DIR / "index.html")

    app.mount("/", StaticFiles(directory=DASHBOARD_DIR), name="dashboard")
