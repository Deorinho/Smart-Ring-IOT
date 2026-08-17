"""Back up the telemetry store, verify the copy, and rotate old ones.

Bug_Backlog R-004. The database is the only irreplaceable thing this project produces:
the code can be rewritten and the ring re-read, but a day of your heart rate that was
never recorded elsewhere is gone.

Three things this does that `cp` does not:

* **Uses SQLite's own backup API**, which is safe against a live connection. The store
  runs in WAL mode, so copying the file while the sync service is mid-write can capture
  a database whose `-wal` sidecar it no longer matches. A copy that restores to a
  corrupt database is worse than no copy, because you believe in it.
* **Verifies every backup it writes** — `PRAGMA integrity_check`, plus a row count
  compared against the source. An unverified backup is a belief, not a backup.
* **Rotates**, keeping the most recent N and deleting the rest, so a decade-old SSD does
  not fill with copies of itself.

    python -m tools.backup                 # write, verify, rotate
    python -m tools.backup --keep 30
    python -m tools.backup --verify-only   # check existing backups, write nothing

**Still your job:** getting a copy off the hub. Everything here lives on the same disk
as the original, which protects against corruption and mistakes but not against that
disk dying. From the desktop:

    rsync -av warlock@10.0.0.213:~/Projects/RavenXSmartRing-data/backups/ ./backups/
"""

from __future__ import annotations

import argparse
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from hub.config import DATA_DIR, DB_PATH

BACKUP_DIR = DATA_DIR / "backups"
DEFAULT_KEEP = 14


def table_counts(conn: sqlite3.Connection) -> dict[str, int]:
    """Row counts per table — the cheap comparison that catches a truncated copy."""
    tables = [
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
            " AND name NOT LIKE 'sqlite_%'"
        )
    ]
    return {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in tables}


def verify(path: Path, expected: dict[str, int] | None = None) -> tuple[bool, str]:
    """Open a backup and prove it is usable. Returns (ok, reason)."""
    if not path.exists() or path.stat().st_size == 0:
        return False, "missing or empty"

    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    except sqlite3.Error as exc:
        return False, f"cannot open: {exc}"

    try:
        # A badly damaged file raises rather than returning a verdict — truncation and
        # zeroed pages both surface as DatabaseError from the check itself, so the
        # failure has to be caught here or verification crashes instead of reporting.
        try:
            result = conn.execute("PRAGMA integrity_check").fetchone()[0]
            if result != "ok":
                return False, f"integrity_check: {result}"
            counts = table_counts(conn)
        except sqlite3.DatabaseError as exc:
            return False, f"unreadable: {exc}"

        if expected is not None and counts != expected:
            diff = {
                k: (expected.get(k), counts.get(k))
                for k in set(expected) | set(counts)
                if expected.get(k) != counts.get(k)
            }
            return False, f"row counts differ (expected, got): {diff}"

        total = sum(counts.values())
        return True, f"integrity ok, {total} rows across {len(counts)} tables"
    finally:
        conn.close()


def write_backup(keep: int) -> int:
    if not DB_PATH.exists():
        print(f"no database at {DB_PATH} - nothing to back up")
        return 1

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")
    target = BACKUP_DIR / f"ring-{stamp}.db"

    source = sqlite3.connect(DB_PATH)
    try:
        expected = table_counts(source)
        dest = sqlite3.connect(target)
        try:
            # The backup API copies pages under a read lock rather than reading the
            # file, so a concurrent writer cannot tear the result.
            source.backup(dest)
        finally:
            dest.close()
    finally:
        source.close()

    ok, reason = verify(target, expected)
    size_kb = target.stat().st_size / 1024
    print(f"{'OK  ' if ok else 'FAIL'} {target.name}  {size_kb:.0f} KB  {reason}")

    if not ok:
        # Keep the bad file. Deleting the evidence of a failed backup makes the next
        # failure harder to diagnose, and it is a few hundred kilobytes.
        print("backup FAILED verification and was kept for inspection")
        return 1

    rotate(keep)
    return 0


def rotate(keep: int) -> None:
    backups = sorted(BACKUP_DIR.glob("ring-*.db"))
    stale = backups[:-keep] if keep > 0 else []
    for old in stale:
        old.unlink()
    if stale:
        print(f"rotated: removed {len(stale)}, kept {len(backups) - len(stale)}")


def verify_all() -> int:
    backups = sorted(BACKUP_DIR.glob("ring-*.db"))
    if not backups:
        print(f"no backups in {BACKUP_DIR}")
        return 1

    failures = 0
    for path in backups:
        ok, reason = verify(path)
        print(f"{'OK  ' if ok else 'FAIL'} {path.name}  {reason}")
        failures += not ok

    print(f"\n{len(backups) - failures}/{len(backups)} verified")
    return 1 if failures else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--keep", type=int, default=DEFAULT_KEEP)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()

    return verify_all() if args.verify_only else write_backup(args.keep)


if __name__ == "__main__":
    raise SystemExit(main())
