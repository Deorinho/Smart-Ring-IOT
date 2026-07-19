# Phase 0a — Task List

Ordered, independently-reviewable breakdown of PLAN.md §5's zero-hardware framework
phase. Each task gets its own design doc (`DESIGN_NN_<taskname>.md`) before any code is
written, per CLAUDE.md's design-before-code rule.

**Ordering note:** Task 1 is sequenced first to match PLAN.md's explicit priority ("hub
foundation plug-and-play ready before rings arrive") and because it's cheap and
de-risking. Tasks 2–6 (`protocol/` and most of `hub/`) run entirely on the desktop PC per
CLAUDE.md and have no hard dependency on Task 1 passing — they could be interleaved. The
one genuine hard dependency is at the tail: Tasks 7–8's definition of done (FastAPI
reachable over Tailscale, PWA installed on the iPhone) requires Task 1's Tailscale/
systemd verification to already be true.

---

## 1. Hub environment verification

Confirm HUB_SETUP.md's build-out is actually done and provable, not just "probably
fine": pytest-based checks for the scriptable §8 items (Bluetooth powered, Python venv
imports, systemd unit + linger config), plus a runbook pointer — not a duplicated
document — for the inherently manual/time-gated items (lid closed 10 minutes, reboot
survival, iPhone reaches the hub over Tailscale with WiFi off). Design doc:
`DESIGN_01_hub_environment_verification.md`.

## 2. `protocol/` — packet parsers + fixtures (first vertical slice)

Pure-function parsers for the core packet types (HR, SpO2, steps, sleep, battery/device
info) built against `colmi_r02_client` source and Gadgetbridge's Yawell/Colmi device page

+ source, each backed by a JSON fixture (raw bytes → expected parsed dict) checked into
`protocol/fixtures/`. Fixture-first per CLAUDE.md: a fixture is added before or alongside
the parser it exercises, never after.

## 3. `protocol/` — pytest harness generalization

Turn the ad hoc tests written alongside Task 2 into a generic parametrized suite that
discovers every JSON fixture in `protocol/fixtures/` automatically, so adding a new
fixture later never requires new test code. Establishes the fixture file naming/schema
convention as a short `protocol/fixtures/README.md` note. Tasks 2 and 3 will likely be
developed together in practice — the split marks a review boundary between "packet-format
domain knowledge" and "generic test-discovery mechanism," not a strict two-phase
schedule.

## 4. `hub/` — SQLite schema

Time-series schema for the metrics in scope (see Task 5), UTC ISO-8601 TEXT timestamps
per CLAUDE.md, a `(metric, timestamp)` uniqueness constraint enforcing the idempotent-
ingest rule, and a minimal creation script. No sync logic yet — schema and insert/query
helpers only.

## 5. `hub/` — synthetic-data generator

A script producing realistic fake raw time-series rows into the Task 4 schema, unlocking
every downstream task without hardware.

**Scope correction:** the plan's originally suggested shape said "metrics 1-15," but
PLAN.md §3 numbers metrics 1–21, with 16–19 reserved/deferred and 20–21 (temperature)
explicitly named as in-scope in the very Phase 0a bullet this task implements ("...fake
sleep/HR/SpO2/step/**temperature** rows"). A literal 1–15 range is wrong twice over: it
sweeps in 5b/6/7 (tagged **Phase 3 only** — beat-to-beat HRV, respiratory rate, breathing
regularity, all requiring raw PPG waveform + custom firmware that doesn't exist even
conceptually yet) and excludes 20/21. **Resolved scope: generate every metric tagged
"Phase 1–2" in §3** — metrics {1, 2, 3, 4, 5, 8, 9, 10, 11, 12, 13, 14, 15, 20, 21}. This
happens to also be 15 metrics by count, but a different *set* than the literal range.
Excludes 5b/6/7 (Phase 3) and 16–19 (deferred composite scores — PLAN.md defers their
formula design to the Interlude week once real baseline data exists; faking them now
produces numbers with nothing behind them).

Generate at raw sample granularity (periodic HR/SpO2/temp samples, per-night sleep stage
sequences, per-day step counts), not pre-aggregated rows, so Task 6 has real rollup work
to do against a known-input fixture.

## 6. `hub/` — analytics rollups (daily/weekly/monthly)

Pure functions turning raw synthetic rows into daily/weekly/monthly summaries (resting
HR, sleep duration/stages, step totals, activity buckets, temperature baseline/
deviation), tested against hand-computed expected values from a fixed synthetic dataset —
the same fixture-over-mocks pattern as the parsers, applied to analytics.

## 7. `hub/` — FastAPI skeleton (JSON API)

Read-only JSON endpoints serving the Task 6 rollups plus raw series, and static-file
wiring for the dashboard build (Task 8) to be served from the same app, per
`hub/README.md`'s "FastAPI (JSON API + PWA)" scope. No `/ingest` route yet — that's
Travel Protocol, currently shelved (PLAN.md §2.1). Deployed to the hub as a systemd user
unit per HUB_SETUP.md §6, reusing the pattern Task 1 proves out.

## 8. `dashboard/` — bare-bones PWA (Chart.js)

Installable PWA (manifest, dark theme per CLAUDE.md style guidance) showing a week of
synthetic sleep and activity via Chart.js, calling Task 7's API. Definition of done
includes actually installing it on the iPhone via Tailscale and confirming data renders —
this *is* Phase 0a's third exit criterion, not a separate step to remember later.
