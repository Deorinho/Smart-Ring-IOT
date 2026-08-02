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
| Colmi R06, size 10 | **DAILY + DEV** | Worn every day; the ring the hub is built against. Factory-virgin — never paired, RTC never set. `R06_D29C` @ `81:5F:4A:87:D2:9C` |
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

**Open measurement gating B:** the R06's buffer depth. Ring put on 2026-08-02 00:30
local, synced to nothing. Measured on first successful sync by walking `day_offset`
backwards until the ring returns nothing.

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
| 2 | GATT enumeration + first connect | Service/characteristic table captured; battery command round-trips; **raw log dumped before the clock is set** |
| 3 | Packet parsers: battery, steps, heart rate | Real bytes from `R06_D29C` parse into typed values |
| 4 | SQLite store wired up | First real rows land; re-running the sync changes nothing |
| 5 | Sleep parsing + events | One real night renders as a stage sequence |
| 6 | Analytics rollups | Daily/weekly summaries from real data |
| 7 | FastAPI + dashboard | Charts render on the iPhone over Tailscale |
| 8 | Automation | systemd timer syncs 3×/day unattended, survives reboot |
| 9 | Hardening | Backups with verified restore; clock-offset correction; sanity checks |
| 10+ | Architecture B | ESP32-C3 satellite, then video production |

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
| Ring buffer depth | Measured session 2; gates Architecture B |
| GATT UUIDs and command opcodes | Marked TODO(confirm) in `protocol/`; enumeration is session 2 |
| Whether the ring wants local or UTC time on the RTC | Session 2. Convert exactly once; storage stays UTC |
| Tailscale + Mullvad coexistence on the hub | Bug_Backlog R-001; both manage routing |
| SQLite backup with verified restore | Bug_Backlog R-004; session 9 |
| Dashboard layout preferences | Iterative once real data is on screen |
