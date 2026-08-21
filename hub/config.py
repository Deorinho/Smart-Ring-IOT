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
# Hub layout (2026-08-20): the repo is at /srv/ravenx/repo and data at /srv/ravenx/data.
#
# Both moved OUT of $HOME deliberately (Bug_Backlog R-018). /home/warlock is
# eCryptfs-encrypted and does not exist until someone logs in interactively, which meant
# no hub service survived a reboot and every scheduled sync while logged out died with
# status=203/EXEC — systemd could not execute an interpreter inside an unmounted home.
# Nothing a systemd service needs may live under $HOME on this machine.
#
# Data still sits outside the working tree so a git pull, branch switch, or clean can
# never touch it — the SQLite file is the one irreplaceable thing here.
#
# The trade this makes is recorded honestly in HUB_SETUP.md 7b: ring.db loses eCryptfs
# at-rest encryption. That protection only ever covered "stolen while powered off", and
# this box is powered on essentially always.
REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("RAVENX_DATA_DIR", "/srv/ravenx/data"))
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

# --- Manual sync trigger -----------------------------------------------------
# The dashboard's Sync button asks systemd to start a unit; hub/api.py never runs a BLE
# sync itself and never writes to the store. Keeping the command here rather than inline
# means the /srv migration (Bug_Backlog R-018), which turned these into SYSTEM units,
# changed one line instead of a hunt through route handlers. It did.
# `sudo -n` because the dashboard runs as a system service with no tty: -n fails fast
# instead of hanging on a password prompt that nobody will ever answer. The permission
# is one scoped line in hub/systemd/ravenx-sudoers naming this unit and nothing else.
SYNC_TRIGGER_CMD: tuple[str, ...] = (
    "sudo", "-n", "/usr/bin/systemctl", "start", "--no-block", "ring-sync-now.service",
)
# Reading state needs no privilege at all, so this one is a plain call.
SYNC_STATUS_CMD: tuple[str, ...] = (
    "systemctl", "is-active", "ring-sync-now.service",
)

# How often the API will honour a manual sync request. This is NOT the battery guard --
# MIN_SECONDS_BETWEEN_SYNCS above still governs scheduled runs, and the manual unit
# deliberately bypasses it with --force. This is only here so a stuck finger or a retry
# loop cannot start a BLE connection every second.
MANUAL_SYNC_COOLDOWN_S = 60


# --- Alerting --------------------------------------------------------------
# Bug_Backlog R-009. The ring has run itself flat twice unnoticed: 80% -> 1% during the
# factory week, and 4% on 2026-08-20 *after* the dashboard gained a battery indicator.
# An indicator informs; it does not notify. The gap it has to cover is nobody looking.
#
# 30% matches the dashboard's orange threshold and is not arbitrary: at ~17-18%/day that
# is roughly a day and a half of warning, which is enough to reach a charger without
# being so early that the alert becomes background noise you learn to dismiss.
BATTERY_ALERT_PERCENT = 30

# A hub that stopped syncing is the failure that actually loses data, and it is just as
# invisible as a flat battery. Three scheduled syncs a day means a 24 h silence is well
# past coincidence -- R-018 ate every scheduled run for days and nothing said so.
STALE_SYNC_ALERT_HOURS = 24


# Waiting for a multi-frame reply: stop once the stream has been quiet this long, and
# never wait longer than the cap. The ring declares its frame count in the header, but
# quiet-detection also terminates correctly on a malformed or truncated burst.
REPLY_QUIET_S = 1.5
REPLY_CAP_S = 10.0
