"""Restore a backup and prove the restored copy actually works.

Bug_Backlog R-004, the half that `tools/backup.py` cannot do. That tool verifies what
it writes — `PRAGMA integrity_check` plus a row count — and both checks run against the
file it just created, in the same process that created it. That is a useful smoke test
and it is *not* a restore. It answers "did the write succeed?", never "could I get my
data back?"

An untested backup is a belief. This is the test.

Three things happen here, in an order that matters:

1. **Copy** the chosen backup to a scratch directory. Never in place — see the guard in
   `_guard_target`. Overwriting the live store while proving you can recover it would be
   a memorable way to lose the data you were protecting.
2. **Verify** the copy with `tools.backup.verify`, which is reused rather than
   reimplemented so there is exactly one definition of "this file is intact."
3. **Read it through the real read path** — `hub.db`'s own query functions, the same
   ones `hub/api.py` calls to render the dashboard. This is the step that makes it a
   restore rather than a checksum: a file can pass `integrity_check` and still be
   useless if the schema the application expects is not in it.

Order matters because step 3 would otherwise hide a failure. `hub.db.connect` applies
the schema to a database that lacks it, so pointing it at an empty or truncated file
would silently produce a valid, empty store reporting "0 samples" instead of an error.
Verification runs first so that cannot happen.

    .venv/bin/python -m tools.restore --list
    .venv/bin/python -m tools.restore --latest
    .venv/bin/python -m tools.restore --from ~/.../backups/ring-2026-08-16T040000Z.db
    .venv/bin/python -m tools.restore --latest --into ~/restore-check

The hub has no bare `python`; Mint ships `python3`, and the venv is what the systemd
units call. On the Windows desktop plain `python` is correct.

Exit status is 0 only if the restored copy verified *and* served the read path. That
makes it safe to run from a timer later — a backup regime nobody checks decays into a
belief again about six months in.
"""

from __future__ import annotations

import argparse
import shutil
import sqlite3
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from hub import db
from hub.config import DATA_DIR, DB_PATH
from tools.backup import BACKUP_DIR, verify

# Metrics worth reporting on individually. Not the API's allowlist: this is a recovery
# tool and it should describe whatever it finds, including a metric added after this
# file was written. Anything outside the list still lands in the totals.
REPORT_METRICS = ("heart_rate", "battery", "steps", "skin_temp", "spo2")


@dataclass(frozen=True)
class MetricSummary:
    metric: str
    samples: int
    first_utc: str | None
    last_utc: str | None
    lo: float | None
    hi: float | None


@dataclass(frozen=True)
class StoreSummary:
    """What a store contains, in the terms a human uses to recognise their own data."""

    samples: int
    sources: int
    sync_runs: int
    raw_payloads: int
    metrics: tuple[MetricSummary, ...]

    def headline(self) -> str:
        # ASCII only, deliberately. This runs on the Linux hub and on the Windows
        # desktop, and the Windows console is cp1252 by default -- a bullet or an
        # en-dash comes out as a replacement character there.
        return (
            f"{self.samples} samples | {self.sources} sources | "
            f"{self.sync_runs} sync runs | {self.raw_payloads} raw frames"
        )


# --- Finding a backup ------------------------------------------------------
def find_backups(backup_dir: Path = BACKUP_DIR) -> list[Path]:
    """Backups oldest first. The filename stamp sorts chronologically by construction."""
    return sorted(backup_dir.glob("ring-*.db"))


def latest_backup(backup_dir: Path = BACKUP_DIR) -> Path | None:
    backups = find_backups(backup_dir)
    return backups[-1] if backups else None


# --- Reading a store -------------------------------------------------------
def summarise(conn: sqlite3.Connection) -> StoreSummary:
    """Describe a store using the same query helpers the API uses.

    Deliberately routed through `hub.db` rather than raw SQL: the point of this function
    is to prove the application layer can read the restored file, so it must go through
    the application layer. Raw SQL here would test SQLite and nothing else.
    """
    counts = {
        table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in ("samples", "sources", "sync_runs", "raw_payloads")
    }

    seen = {row["metric"] for row in conn.execute("SELECT DISTINCT metric FROM samples")}
    ordered = [m for m in REPORT_METRICS if m in seen]
    ordered += sorted(seen - set(REPORT_METRICS))

    metrics = []
    for metric in ordered:
        # metric_days is what the dashboard's weekly view calls; exercising it here
        # means a restored file that breaks that view fails now rather than on a phone.
        days = db.metric_days(conn, metric)
        latest = db.latest_sample(conn, metric)
        total = sum(d["n"] for d in days)
        metrics.append(
            MetricSummary(
                metric=metric,
                samples=total,
                first_utc=f"{days[0]['day']}" if days else None,
                last_utc=latest["ts_utc"] if latest else None,
                lo=min(d["lo"] for d in days) if days else None,
                hi=max(d["hi"] for d in days) if days else None,
            )
        )

    return StoreSummary(
        samples=counts["samples"],
        sources=counts["sources"],
        sync_runs=counts["sync_runs"],
        raw_payloads=counts["raw_payloads"],
        metrics=tuple(metrics),
    )


def exercise_read_path(path: Path) -> tuple[StoreSummary, str | None]:
    """Open a restored store exactly as the API does. Returns (summary, error)."""
    try:
        conn = db.connect(path)
    except sqlite3.Error as exc:
        return _empty_summary(), f"cannot open through hub.db: {exc}"

    try:
        summary = summarise(conn)

        # One windowed query, because that is what the dashboard actually issues and it
        # uses a different index path than the aggregate above.
        end = datetime.now(timezone.utc)
        # timedelta, not replace(year=...): on 29 February that raises ValueError,
        # which would turn a once-every-four-years date into a failed restore.
        start = end - timedelta(days=365 * 5)
        db.samples_between(conn, "heart_rate", db.to_iso_utc(start), db.to_iso_utc(end))
        db.recent_sync_runs(conn, limit=5)
        return summary, None
    except sqlite3.Error as exc:
        return _empty_summary(), f"read path failed: {exc}"
    finally:
        conn.close()


def _empty_summary() -> StoreSummary:
    return StoreSummary(samples=0, sources=0, sync_runs=0, raw_payloads=0, metrics=())


# --- Restoring -------------------------------------------------------------
def _guard_target(target: Path) -> None:
    """Refuse to write anywhere near the live store.

    The failure this prevents is not hypothetical: the obvious way to test a restore is
    to put the backup back where the original lives, and doing that destroys the only
    copy that has data newer than the backup.
    """
    resolved = target.resolve()
    if resolved == DB_PATH.resolve():
        raise SystemExit(f"refusing to restore over the live store at {DB_PATH}")
    if resolved.parent == DATA_DIR.resolve():
        raise SystemExit(
            f"refusing to restore into the live data directory {DATA_DIR}\n"
            "pass --into with a scratch directory instead"
        )


def restore(source: Path, into: Path) -> tuple[bool, Path]:
    """Copy a backup into a scratch directory and prove it reads. Returns (ok, path)."""
    if not source.exists():
        print(f"FAIL  no such backup: {source}")
        return False, source

    into.mkdir(parents=True, exist_ok=True)
    target = into / "ring.db"
    _guard_target(target)

    # A backup written by SQLite's backup API is a complete standalone database with no
    # -wal sidecar, so a plain file copy is the honest recovery action. Anything cleverer
    # here would be testing the clever thing rather than the backup.
    shutil.copy2(source, target)
    size_kb = target.stat().st_size / 1024
    print(f"restored  {source.name}  ->  {target}  ({size_kb:.0f} KB)")

    ok, reason = verify(target)
    print(f"{'OK  ' if ok else 'FAIL'} integrity   {reason}")
    if not ok:
        return False, target

    summary, error = exercise_read_path(target)
    if error:
        print(f"FAIL read path   {error}")
        return False, target

    print(f"OK   read path   {summary.headline()}")
    _print_metrics(summary)

    if summary.samples == 0:
        # Not a crash, but not a successful restore either. A backup taken before the
        # first sync is intact and worthless, and saying "OK" here would train someone
        # to trust the word rather than the number.
        print("\nFAIL  restored store contains no samples")
        return False, target

    _compare_with_live(summary)
    return True, target


def _print_metrics(summary: StoreSummary) -> None:
    if not summary.metrics:
        return
    print()
    for m in summary.metrics:
        span = f"{m.first_utc} .. {(m.last_utc or '')[:10]}"
        rng = f"{m.lo:g}-{m.hi:g}" if m.lo is not None else ""
        print(f"  {m.metric:<12} {m.samples:>6} samples  {span:<26} {rng}")


def _compare_with_live(restored: StoreSummary) -> None:
    """Put the restored copy next to the live store, if there is one to compare against.

    Expected result is that the backup holds *less* — it was taken earlier. The
    interesting outcome is the reverse: a restored copy with more samples than the live
    store means the live store lost something, which is the exact scenario this whole
    backup regime exists for and the one nobody is watching for.
    """
    if not DB_PATH.exists():
        return

    try:
        conn = db.connect(DB_PATH)
    except sqlite3.Error as exc:
        print(f"\n(could not open live store for comparison: {exc})")
        return

    try:
        live = summarise(conn)
    except sqlite3.Error as exc:
        print(f"\n(could not read live store for comparison: {exc})")
        return
    finally:
        conn.close()

    delta = live.samples - restored.samples
    print(f"\nlive store  {live.headline()}")
    if delta > 0:
        print(f"backup is behind live by {delta} samples - expected for an older backup")
    elif delta == 0:
        print("backup and live hold the same number of samples")
    else:
        print(
            f"WARNING: backup holds {-delta} MORE samples than the live store.\n"
            "         The live store has lost data, or was rebuilt. Investigate before\n"
            "         the next backup rotates this copy away."
        )


# --- CLI -------------------------------------------------------------------
def _list_backups() -> int:
    backups = find_backups()
    if not backups:
        print(f"no backups in {BACKUP_DIR}")
        return 1
    for path in backups:
        size_kb = path.stat().st_size / 1024
        print(f"{path.name:<34} {size_kb:>8.0f} KB")
    print(f"\n{len(backups)} backups in {BACKUP_DIR}")
    return 0


def _default_target() -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return Path(tempfile.gettempdir()) / f"ravenx-restore-{stamp}"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Restore a backup into a scratch directory and prove it reads."
    )
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--from", dest="from_path", type=Path, help="backup to restore")
    source.add_argument("--latest", action="store_true", help="restore the newest backup")
    parser.add_argument("--list", action="store_true", help="list backups and exit")
    parser.add_argument(
        "--into",
        type=Path,
        default=None,
        help="scratch directory (default: a timestamped directory under the temp dir)",
    )
    args = parser.parse_args()

    if args.list:
        return _list_backups()

    chosen = args.from_path
    if chosen is None:
        chosen = latest_backup()
        if chosen is None:
            print(f"no backups in {BACKUP_DIR}")
            print("write one first:  .venv/bin/python -m tools.backup")
            print("then check the timer:  systemctl --user list-timers --all | grep ring")
            return 1
        if not args.latest:
            print(f"(no --from given; using the newest backup: {chosen.name})")

    into = args.into or _default_target()
    ok, target = restore(chosen, into)

    print()
    if ok:
        print("RESTORE PROVEN - this backup contains a working store.")
        print("Point the dashboard at it to see it with your own eyes:")
        print(f"  RAVENX_DATA_DIR={target.parent} .venv/bin/uvicorn hub.api:app --port 8001")
        # No --host above, so this binds 127.0.0.1 and cannot be exposed by accident.
        # An SSH tunnel is how you look at it from another machine -- see HUB_SETUP 2a.
        print("then, from the desktop:")
        print("  ssh -L 8001:localhost:8001 hub   # open http://localhost:8001")
    else:
        print("RESTORE FAILED - this backup is not a backup. Investigate before trusting")
        print("the rest of the rotation; whatever produced it may have produced them all.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
