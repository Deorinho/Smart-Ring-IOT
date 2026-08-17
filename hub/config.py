"""Hub configuration — paths, devices, and the ring's power budget.

Boilerplate, owned by Claude per CLAUDE.md's division of labor. Edit values freely;
the point of this module is that nothing else in the codebase hardcodes a MAC, a
path, or a sensing interval.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

# --- Paths -----------------------------------------------------------------
# Hub layout (2026-08-08): the repo is cloned at ~/Projects/RavenXSmartRing-IOT.
# Data deliberately sits OUTSIDE the working tree so a git pull, branch switch, or
# clean can never touch it — the SQLite file is the one irreplaceable thing here.
REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(
    os.environ.get("RAVENX_DATA_DIR", Path.home() / "Projects" / "RavenXSmartRing-data")
)
DB_PATH = DATA_DIR / "ring.db"
SCHEMA_PATH = REPO_ROOT / "hub" / "schema.sql"

# RAVENX_DATA_DIR exists so the API and dashboard can be pointed at a throwaway store
# during development without touching the real one. Nothing in production sets it.


# --- Devices ---------------------------------------------------------------
@dataclass(frozen=True)
class Ring:
    """A ring in the fleet.

    `address` is the BLE MAC as reported by BlueZ on Linux. Note that bleak reports
    a system-assigned UUID instead of a MAC on macOS — irrelevant here, since the hub
    is Linux, but it means this value is not portable across platforms.
    """

    name: str
    address: str
    role: str


# Confirmed by BLE scan on the hub, 2026-08-02. The advertised name encodes the last
# two bytes of the address (D2:9C), which indicates a fixed device address rather
# than a rotating private one — safe to use as a permanent database key.
R06 = Ring(name="R06_D29C", address="81:5F:4A:87:D2:9C", role="daily")

# The R09 is on the stock QRing app as a validation oracle and is deliberately NOT
# hub-managed yet. Fill in its address when it migrates. Never point the sync service
# at it while it is still paired to the phone.
R09 = Ring(name="R09_UNKNOWN", address="", role="showcase")

MANAGED_RINGS: tuple[Ring, ...] = (R06,)


# --- Power budget ----------------------------------------------------------
# CLAUDE.md: battery is the top constraint, and the hub OWNS the ring's sensing
# schedule — it is written on every connect, never inherited from whatever the QRing
# app last set. PPG optical duty cycle dominates the power draw; MCU compute does not.
#
# These are the knobs, in descending order of battery impact.
@dataclass(frozen=True)
class SensingPolicy:
    hr_interval_minutes: int = 30    # biggest single lever
    spo2_enabled: bool = False       # red + IR LEDs; deprioritized metric
    stress_enabled: bool = False     # more PPG duty cycle, deferred metric
    hrv_enabled: bool = False        # ditto
    temperature_enabled: bool = True  # cheap, and the illness early-warning signal
    # The accelerometer is always on and is not listed: MEMS draw is microamps.


DEFAULT_SENSING = SensingPolicy()


# --- Sync cadence ----------------------------------------------------------
# Three attempts a day. Sync frequency barely affects battery — total bytes moved per
# day is roughly constant regardless of cadence, and only connection setup scales.
# Three is chosen for "glance at it occasionally", not for freshness.
SYNC_HOURS_LOCAL: tuple[int, ...] = (8, 14, 22)

# An attempt connects if the ring is reachable and exits quietly if not. These bound
# how hard it tries before giving up until the next scheduled run.
SCAN_TIMEOUT_S = 15.0
CONNECT_TIMEOUT_S = 20.0
SYNC_TIMEOUT_S = 180.0
MIN_SECONDS_BETWEEN_SYNCS = 1800  # guard against a misbehaving trigger draining the ring

# How many past UTC days to request on each sync, today included. Re-pulling a day
# already stored is free — ingest is idempotent — so this is cheap insurance against
# gaps from a missed sync or an unreachable ring, not a retention policy.
SYNC_DAYS_BACK = 3

# Waiting for a multi-frame reply: stop once the stream has been quiet this long, and
# never wait longer than the cap. The ring declares its frame count in the header, but
# quiet-detection also terminates correctly on a malformed or truncated burst.
REPLY_QUIET_S = 1.5
REPLY_CAP_S = 10.0
