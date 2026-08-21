# RavenX Smart Ring — Plan

**Owner:** Abhi
**Last updated:** 2026-08-02

---

## 1. Mission

Own my health data end to end. A ~$25 smart ring, my software, my hardware, my
analysis — no cloud account, no subscription, no company between my body and my data.
The ring senses and buffers; a repurposed 2014 MacBook Air syncs, stores, and scores;
my phone displays. Everything runs on hardware I already own, and it keeps working for
as long as I choose to maintain it.

Two guardrails:

- **The ring stays dumb.** It senses and relays. All intelligence lives on the hub.
- **Battery is the top constraint.** I want to glance at this occasionally, not tend
  it. The ring should lose charge to daily wear and nothing else.

## 2. The fleet (final)

| Unit | Role | State |
| --- | --- | --- |
| Colmi R06, size 10 | **DAILY + DEV** | Worn every day; the ring the hub is built against. `R06_D29C` @ `81:5F:4A:87:D2:9C`. Never connected to QRing. RTC set to UTC 2026-08-09; HR logging enabled at 30 min. ~5.5 days per charge. |
| Colmi R09, size 12 | **SHOWCASE + ORACLE** | For the video. On the stock QRing app as a validation oracle; migrates to the hub at the end. |

No further ring purchases. End state: both rings running the same software, then one
chosen for teardown.

## 3. Architecture

```text
A (now)
  [R06] --BLE--> [MacBook Air hub, Linux Mint] --Tailscale--> [iPhone PWA]
                  sync service (bleak, systemd timer, 3x/day)
                  SQLite store (generic telemetry schema)
                  analytics rollups (pure functions)
                  FastAPI (JSON API + static PWA)

B (next)
  [R06] --BLE--> [ESP32-C3 satellite] --HTTPS+token--> [hub /ingest]
                  at the second location, 5.5h away
```

**A** is a single hub with no relay. Trips longer than the ring's onboard buffer lose
data — accepted for now.

**B** adds an ESP32-C3 satellite at the second location, where stays run from a weekend
to three weeks. Three weeks exceeds any plausible onboard buffer, so this is a data-loss
problem, not a freshness problem. A peer-node alternative (a Pi-class box running the
same Python, cheaper and roughly six sessions faster) was **deliberately declined** —
the embedded firmware work is wanted for its own sake.

Design rules that hold across both:

- **Dumb radio, smart hub.** Protocol parsing lives only in `protocol/` and `hub/`.
  The satellite forwards raw payloads unparsed.
- **Idempotent ingest.** The `samples` primary key `(source_id, metric, ts_utc)` makes
  re-ingesting a no-op. Local syncs and satellite posts are equally safe.
- **The satellite's buffer is sacred.** It may only mark a payload delivered after the
  hub acknowledges receipt. If the hub is unreachable, it does not pull.
- **Storage is generic, not ring-shaped.** The hub is a personal telemetry store whose
  first source happens to be a ring, so the next hub project doesn't start from zero.

**Still open — the R06's buffer ceiling and how it expires.** Measured 2026-08-16 by
walking `day_offset` backwards: full 24-frame bursts for every UTC day back to
2026-08-09, and the no-data sentinel before that. But 08-09 is the day HR logging was
enabled, so that floor is *the start of recording, not the buffer's edge* — **at least
9 days, upper bound unknown.**

This no longer gates B. Nine days covers a weekend and probably a week, so the satellite
is wanted rather than needed. The number is still wanted for its own sake, and two
separate things remain unmeasured:

- **Capacity** — how many days the ring actually holds.
- **Eviction** — how it expires. A ring that drops the oldest day cleanly behaves very
  differently from one that wraps mid-day or returns a garbled partial, and the sync
  service's idea of "this day is empty" depends on which.

Both fall out of the same experiment: keep walking `day_offset` back as history
accumulates — first around 2026-08-29 (~20 days), then periodically — until a day that
was previously readable comes back as the sentinel. **That transition is the
measurement.** The first day to disappear names the ceiling and the eviction policy at
once, which is why it's worth catching rather than inferring.

## 4. Metrics — priority order

Priority is **sleep, activity, and heart rate.** Everything else is secondary.

| Priority | Metric | Sensor | Computed by |
| --- | --- | --- | --- |
| 1 | Sleep detection, duration, stages | Accel + HR | Ring assists; hub refines |
| 1 | Steps, activity levels, sedentary time | Accel | Ring → hub |
| 1 | Heart rate: resting, daytime, overnight curve | PPG | Ring samples → hub derives |
| 2 | Skin temperature + deviation from baseline | Temp | Ring → hub (illness signal) |
| 2 | HRV daily average, stress index | PPG | Ring-reported |
| 3 | Blood oxygen (SpO2) | PPG red/IR | Ring → hub. **Sensing off by default** |
| 3 | Calorie estimate, workout auto-detection | Accel + HR | Hub |
| — | VO2max | — | Deferred. Revisit if running becomes a hobby. |
| — | Composite scores (sleep score, readiness) | — | Deferred until ~2 weeks of baseline data exist |

Raw metrics ship first. Scores are arbitrary numbers until there's a personal baseline
behind them.

**Phase 3 (custom firmware, open-ended):** raw PPG waveform access unlocks beat-to-beat
HRV, respiratory rate, and breathing regularity. Note this is **battery-negative** —
raw PPG streaming is the most expensive mode the hardware has. Not scheduled; happens
after both rings run the same software and one is chosen for teardown.

## 5. The battery contract

The hub owns the ring's sensing schedule and writes it on every connect. It is never
inherited from whatever the QRing app last set.

| Knob | Default | Rationale |
| --- | --- | --- |
| Auto HR interval | 30 min | Biggest single lever |
| SpO2 auto | off | Red + IR LEDs; deprioritized metric |
| Stress / HRV auto | off | More PPG duty cycle for deferred metrics |
| Accelerometer | on | Microamps. Effectively free. |
| Temperature | on | Cheap, and it's the illness early-warning signal |
| Hub sync cadence | 3×/day | Freshness is not a priority here |

PPG optical duty cycle dominates the power budget; MCU compute is a rounding error.
"Offload computation to the hub" is not a battery strategy — reducing LED-on time is.

**Planned experiment, and a genuinely novel result:** chart battery percentage against
configured sensing interval over a week. Nobody has published that number for this class
of ring.

## 6. Session roadmap

Calibrated to 2–4 hour sessions, roughly two per weekend plus one midweek.

| # | Goal | Exit criterion |
| --- | --- | --- |
| **1** | **Hub foundation + repo reset** ✅ *(2026-08-02)* | Lid closed, SSH reachable, ring visible to bleak |
| **2** | **GATT enumeration + battery round-trip** ✅ *(2026-08-02)* | Both vendor services mapped, chipset identified, `03 → 03 50 … 53` with checksum verified |
| **3** | **Raw log dump + why it was empty** ✅ *(2026-08-09)* | Three virgin captures banked; `0xFF` no-data sentinel identified; **HR logging found disabled from the factory** and enabled; RTC set in UTC |
| **4** | **First real data** ✅ *(2026-08-09)* | 24-frame burst parsed into 28 samples over 13.5 h; resting HR 51 bpm; burst layout confirmed and frame-1 offsets corrected |
| **5** | **Storage + read path** ✅ *(2026-08-13)* | Real samples in `ring.db`; re-ingest adds nothing; JSON API and dashboard render them |
| **6** | **Sync service** ⚠️ *(2026-08-16)* | `hub/sync.py` under a systemd timer pulls and stores 3×/day unattended — **true while the machine stays up, false across a reboot.** The user units live in an eCryptfs home that does not decrypt until interactive login, so nothing starts at boot (R-018, found 2026-08-17). The sync logic itself is sound and verified; only its startup is broken. Completed by session 8 |
| **7** | **Remote access + a restored backup** ✅ *(2026-08-17)* | Tailscale Serve gives the tailnet a real cert; the PWA is installed on the iPhone and works **over cellular with WiFi off** and offline in airplane mode; the LAN `ufw` rule is deleted and the dashboard is tailnet-only; a real hub backup restored to 334 samples and rendered in a browser. **R-004 and R-001 both closed** — Mullvad and Tailscale coexist with no configuration. Reboot persistence carries over as R-017 |
| 8 | **Boot survival — move off the encrypted home** | Repo, venv and data at `/srv/ravenx`; all four units are system units with `User=warlock`; `ring-sync.service` finally gets a `bluetooth.target` ordering that can actually apply. **Exit criterion is a reboot**: the phone loads the dashboard with nobody logging in (R-018 P1, R-005) |
| 9 | Sleep | A real night renders as a stage sequence. Reverse-engineering, not porting (R-008) |
| 10 | Analytics rollups | Resting HR, sleep duration, activity buckets, temperature baseline |
| 11 | Sensing-flag hunt + hardening | Find what burns the 13%/day idle floor (R-014); longitudinal sanity checks |
| 12+ | Architecture B | ESP32-C3 satellite, then video production |

Re-sequenced 2026-08-13. Session 5 delivered the dashboard early because storage made it
nearly free, so the old "FastAPI + dashboard" row is gone. The two things now standing
between this and a system that runs itself are the **sync service** and **backups** —
neither adds a metric, and both matter more than the next metric does.

Session 3 is the deferred half of session 2 — the log dump was split off deliberately
rather than rushed at the end of a session, since it's a one-shot observation on a
ring whose clock has never been set.

**Phase gate for the video:** filming begins at ~80% product completion, when every step
can be re-performed smoothly on camera. The dev pass is documentary-filmed as it
happens; `notebook.md` is the script skeleton.

## 7. Testing

Working code first — tests when they earn their place, not before.

- **Fixtures where they pay:** captured packets become JSON vectors (raw bytes →
  expected output) so parsers can be re-validated after every change. This matters here
  because the protocol is reverse-engineered and the parser will keep changing.
- **`raw_payloads` is the safety net.** Every packet is archived verbatim forever. When
  the parser improves, history gets re-parsed rather than lost.
- **Oracle validation:** the R09 on QRing is the reference. Compare hub-computed steps,
  HR, and sleep windows against vendor numbers on the same wrist-days, and document the
  deltas — that comparison is a video segment.
- **Longitudinal sanity:** a daily job flagging impossible values (HR 0 or 250, negative
  sleep) is a cheap canary for parser regressions.

## 8. Open items

| Item | Status |
| --- | --- |
| Ring buffer depth | **At least 9 days, upper bound still unknown.** Measured 2026-08-16: the ring returned full 24-frame bursts for every UTC day from 2026-08-09 to 2026-08-17 and the no-data sentinel for 08-08 and earlier. That floor is *when logging was enabled*, not where the buffer ends — the real limit is still beyond the data. Re-measure once ~20 days have accumulated. |
| Command opcodes beyond `CMD_BATTERY` | GATT UUIDs and `CMD_BATTERY = 0x03` confirmed 2026-08-02. Log, sleep, and time opcodes still `TODO(confirm)` |
| Purpose of the second vendor service (`de5bf728…`) | Found during enumeration; likely bulk transfer. Confirm before assuming sleep data arrives on the command channel |
| Ring reachability while charging | Bug_Backlog R-007; blocks `parse_battery`'s charging flag |
| Whether the ring wants local or UTC time on the RTC | Session 2. Convert exactly once; storage stays UTC |
| Tailscale + Mullvad coexistence on the hub | **Closed 2026-08-17 — they coexist with no configuration.** Mullvad reconnected after the Tailscale bring-up and SSH, `tailscale status` and the phone dashboard all kept working; no split tunnelling was needed. Reboot persistence is untested and carries forward as R-017 |
| SQLite backup with verified restore | **Closed 2026-08-17.** A real hub backup restored to 334 samples and rendered in a browser; `tools/restore.py` rejects seven corruption modes including a valid store with no rows. Automating the off-hub pull continues as R-016 |
| Ring HR coverage ~88% of theoretical | Not a defect. 48/48 on 2026-08-15 but 39 on 08-14, i.e. per-day variation rather than a uniform shortfall — consistent with the ring being off the finger while charging. Revisit only if a day is short with no charging to explain it |
| Dashboard layout preferences | Iterative once real data is on screen |
