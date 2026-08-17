"""Read-only JSON API and PWA host.

Serves what `hub/db.py` stores. No writing, no syncing, no parsing — a browser hitting
this can only ever read. The BLE service will be a separate process on a timer; keeping
the reader incapable of mutation means a bug here cannot corrupt the store.

Every timestamp leaving this API is UTC ISO-8601, exactly as stored. Conversion to
local time happens in the browser, which is the display layer and the only place it
belongs.

    uvicorn hub.api:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from hub import db
from hub.config import DB_PATH, MANAGED_RINGS, REPO_ROOT, SYNC_HOURS_LOCAL

DASHBOARD_DIR = REPO_ROOT / "dashboard"

# Metrics the dashboard is allowed to ask for. An allowlist rather than free-form
# input: `metric` reaches a SQL query, and while it is parameterised, constraining the
# surface costs one tuple and removes the question entirely.
KNOWN_METRICS = ("heart_rate", "steps", "skin_temp", "spo2", "battery", "hrv", "stress")

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


# --- PWA -------------------------------------------------------------------
# Mounted last so the /api routes above win. The dashboard is plain files; there is no
# build step and nothing to compile.
if DASHBOARD_DIR.is_dir():

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(DASHBOARD_DIR / "index.html")

    app.mount("/", StaticFiles(directory=DASHBOARD_DIR), name="dashboard")
