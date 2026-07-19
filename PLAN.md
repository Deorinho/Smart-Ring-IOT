# RavenX Smart Ring — Planning Document

**Owner:** Abhi
**Status:** Hardware confirmed and in transit (ETA end of July): Colmi R09 sz 12 = **DAILY**, Colmi R06 sz 10 = **DEV** — both official Colmi, QRing-confirmed. HERO is a gated future purchase (second R09, only after DAILY survives the testing phase). R10 dropped from the active plan. Travel Protocol shelved. **Top priority: hub foundation plug-and-play ready before the rings arrive.**
**Last updated:** July 11, 2026

---

## 1. Mission statement

Own my health data end to end. A ~$20 smart ring, my software, my hardware, my analysis — no cloud account, no subscription, no company between my body and my data. The ring tracks; a repurposed 2014 MacBook Air syncs, stores, and scores; my phone displays. Everything runs on hardware I already own, and it keeps working for as long as I choose to maintain it.

Scope guardrail: the ring is deliberately rudimentary. It senses and relays. All intelligence lives on the hub. No bells, no whistles, no features I won't glance at.

## 2. Architecture summary

```
QRing-family rings            Hub (2014 MBA, Linux Mint)         Viewers
+-----------------+   BLE    +---------------------------+      +------------------+
| PPG + accel +   | -------> | Sync service (Python/bleak)|      | iPhone (PWA)     |
| temperature     |          | SQLite time-series store   | ---> | iPad (browser)   |
| Onboard log     |          | Analytics: baselines/scores|  LAN | Anywhere         |
| Stock firmware  |          | FastAPI: JSON API + PWA    |  or  |  (via Tailscale) |
| (custom: R09s)  |          | systemd, lid-closed, 24/7  |  TS  +------------------+
+-----------------+          +---------------------------+
```

- Ring logs onboard and syncs whenever in BLE range of the hub (morning coffee = data synced).
- Hub serves the dashboard as an installable PWA; Tailscale provides secure remote access with no port forwarding and no third-party data storage.
- Firmware path: **stock firmware first (Path A)**, validated app pipeline, then **custom firmware (Path B)** in Phase 3 behind a stable GATT interface contract so the app layer never changes.
- **Two chipsets in the fleet:** the R09s are RF03-class (BlueX, Cortex-M0) — the ATC_RF03 custom firmware groundwork applies. The R10 (DAILY) is Realtek RTL8762-based — it stays on stock firmware permanently; all Phase 3 work targets the R09s only. All three speak the QRing protocol, so the hub pipeline is shared; expect minor per-model parser variations.

### 2.1 The Travel Protocol — satellite collector for the second location

> **Status: SHELVED (July 18, 2026).** Deprioritized — not on the active critical path. Full design retained below for future revival; the ring's onboard buffer means typical Mississauga trips lose freshness, not data. Revive when continuous cross-city freshness starts mattering.

Problem: frequent stays in Mississauga exceed dashboard *freshness* (ring buffers onboard, ~days) even though no data is lost on typical trips. Solution: a permanently deployed satellite collector at the second location.

```
Ring (in Mississauga)          ESP32-C3 satellite            Hub (Montreal)
+---------------+    BLE      +--------------------+  HTTPS  +------------------+
| Onboard log   | ----------> | NimBLE central     | ------> | /ingest endpoint |
+---------------+             | Raw payload buffer |  POST   | (Tailscale Funnel|
                              | WiFi + HTTP client |  +token | + bearer token)  |
                              +--------------------+         | Python parsers   |
                                                             | as usual         |
                                                             +------------------+
```

Design rules:
- **Dumb radio, smart hub.** The satellite pulls *raw* sync payloads over BLE and forwards them unparsed. All protocol parsing stays in the hub's Python — single implementation of protocol truth. Satellite firmware ≈ NimBLE central + HTTP client, a few hundred lines of C (ESP-IDF).
- **Connectivity:** ESP32 cannot join the Tailnet (no Tailscale client). The hub exposes *only* the `/ingest` route publicly via **Tailscale Funnel** (TLS via Tailscale relay, no port forwarding), locked with a bearer token. Dashboard and all other routes remain Tailnet-only. Alternative if a fully closed system is ever wanted: `esp_wireguard` point-to-point tunnel.
- **Ring buffer is sacred:** the satellite must receive hub acknowledgment of a payload before performing any operation that could mark the ring's onboard log as delivered. If WiFi/hub is unreachable, the satellite does not pull.
- **Idempotency holds end to end:** the hub's ingest dedupes by timestamp exactly like local syncs, so satellite and hub can both hear the ring with no double-counting.
- Deployment: ESP32-C3 on a USB wall adapter in Mississauga. ESP32-WROOM-32 boards serve as the at-home development testbed — the entire Travel Protocol is built and tested in Montreal before deployment.
- Strategic bonus: implementing a QRing BLE central in C on ESP-IDF is a low-risk rehearsal for Phase 3 (same protocol, same GATT services, debuggable hardware, nothing brickable).

### 2.2 Sync trigger design (decided 2026-07-18)

The sync service separates *when to sync* from *how to sync*:

- **Pluggable SyncPolicy.** The trigger is an injected strategy; the executor (connect → pull log → parse → dedupe → store) is identical under every policy. Choosing a strategy is config, not architecture.
- **v1 — Scheduled (Policy B).** A systemd timer fires a run-once sync attempt: connect if the ring is reachable, skip quietly if not, exit either way. Cadence: every 60 min, tightened to 15 min during 05:00–10:00 local (the sleep-data window). Deterministic, trivially testable ("run once now" = invoking the script), observable as discrete journald events.
- **v2 — Adaptive (Policy C), designed and shelf-ready.** Passive advert listening (free presence + RSSI; the ring advertises regardless) feeds a **pure** `decide(now, last_sync, rssi, state)` gate — fixture-testable exactly like the parsers. State machine per ring: Listening → Present → Eligible → Syncing → Cooldown (success) / Backoff (failure) → Listening. Key design points: RSSI hysteresis (present at −85 dBm, connect only above −80) to stop range-edge flapping; per-ring state keyed by MAC (a DEV experiment must never block DAILY's morning pull); overnight quiet hours (23:00–05:00 — never connect while the ring records sleep); exactly one deliberate UTC→local conversion for time windows (storage stays UTC); scanner watchdog (no adverts from *any* device for minutes ⇒ the listener died, restart it).
- **Executor rules — policy-independent, written once:** per-ring connection lock (BLE peripheral is single-central; never two concurrent connects), exponential backoff with a cap on failures, and a minimum-interval guard protecting ring battery even from a misbehaving policy.
- **Migration path:** B is C with a trivial always-yes policy — nothing built for v1 is discarded at upgrade. The shelved Travel Protocol satellite is inherently Policy B (a timer on a microcontroller) posting to the same executor via `/ingest`.

## 3. Metrics — scope and source mapping

Temperature-derived metrics are **back in scope** — all three selected rings (R09/R10 generation) carry a temperature sensor, unlike the original R02 plan. Additionally, stock firmware on this generation syncs HRV (daily average) and REM sleep staging, moving metric 5 from Phase-3-only to available at day one; Phase 3 now targets HRV *quality* (beat-to-beat) rather than HRV existence. Composite scores (sleep score, readiness, stress, VO2max) remain **deferred** — formulas to be designed after raw metrics are flowing.

| # | Metric | Sensor | Computed by | Available |
|---|--------|--------|-------------|-----------|
| 1 | Resting heart rate | PPG | Hub (daily min/percentile of HR samples) | Phase 1–2 |
| 2 | Daytime heart rate | PPG | Ring (periodic samples) → hub | Phase 1–2 |
| 3 | Nighttime HR curve | PPG | Hub (overnight sample series) | Phase 1–2 |
| 4 | Blood oxygen (SpO2) | PPG (red/IR) | Ring → hub | Phase 1–2 |
| 5 | HRV (daily average) | PPG | Ring (recent stock fw) → hub | Phase 1–2 |
| 5b | HRV (beat-to-beat quality) | PPG raw waveform | Custom firmware + hub, R09 only | **Phase 3** |
| 6 | Respiratory rate | PPG raw waveform | Custom firmware + hub, R09 only | **Phase 3** |
| 7 | Breathing regularity | PPG raw waveform | Custom firmware + hub, R09 only | **Phase 3** |
| 8 | Steps | Accelerometer | Ring → hub | Phase 1–2 |
| 9 | Calorie estimate | Accel + HR | Hub (model from steps/HR/profile) | Phase 1–2 |
| 10 | Activity levels (sed/low/med/high) | Accel + HR | Hub (bucketing from samples) | Phase 1–2 |
| 11 | Inactivity / sedentary time | Accel | Hub | Phase 1–2 |
| 12 | Sleep detection (bed/wake/duration) | Accel + HR | Ring assists; hub refines | Phase 1–2 |
| 13 | Sleep stages (light/deep/REM/awake) | Accel + HR | Hub (estimate; accuracy caveat) | Phase 1–2 |
| 14 | Sleep latency / efficiency / restlessness | Accel + HR | Hub (derived from 12–13) | Phase 1–2 |
| 15 | Workout auto-detection | Accel + HR | Hub (motion + HR heuristics) | Phase 1–2 |
| 20 | Nighttime skin temperature | Temp sensor | Ring → hub | Phase 1–2 |
| 21 | Skin temp trend / deviation from baseline | Temp sensor | Hub (rolling baseline; illness early-warning signal) | Phase 1–2 |

Numbering note: 16–19 remain reserved for the deferred composite scores (16 sleep score, 17 readiness score, 18 stress estimate, 19 VO2max estimate) — design session scheduled once ~2 weeks of real data exist (baselines need data). Ring-reported stress values also sync from stock firmware and can feed metric 18.

## 4. Bill of materials and tools

### Hardware
| Item | Qty | Est. cost (CAD) | Notes |
|------|-----|------------------|-------|
| Colmi R09 smart ring, size 12 | 1 | ~$27 | **DAILY.** Official Colmi store, QRing confirmed. RF03-class, temperature sensor. ETA end of July. Undergoes the on-wrist testing phase before any further ring purchases are made. |
| Colmi R06 smart ring, size 10 | 1 | ~$4 | **DEV.** Official Colmi, QRing confirmed. RF03-class, R02-family drop-in — the tinker/sacrifice unit (SWD candidate, Phase 3 target). ETA end of July. Confirm via nRF Connect on arrival regardless (ground truth over listings). |
| Colmi R09 #2 (future) | 0/1 | ~$27 | **HERO — gated purchase.** Bought only after DAILY survives the testing phase. If DAILY shows issues, hold; if DAILY breaks or bricks, its replacement purchase doubles as this decision point. |
| ~~Ruofine R10, size 10~~ | — | — | **Dropped from active plan.** Was a contingent sensor/charging upgrade; the project fully functions on the R09/R06 pair. |
| ~~Ruofine R09, size 12~~ | ~~1~~ | ~~$25.39~~ | **Cancelled.** Confirmed JRing-protocol on the manual PDF before shipping — different hardware, different app, no compatibility with any project tooling. Kept here as a documented near-miss, not counted in fleet cost. Lesson: model numbers (R09, R06, etc.) are reused across incompatible hardware families by different resellers; verify the companion app name on the listing *before* purchase, not after. See RESOURCES.md.
| Ring sizing kit or jeweler measurement | 1 | $0–5 | US size + inner diameter in mm. Wide band → size up if between sizes. Measure late in day. Confirm size 10 for the R10 before ordering — it's the daily-wear unit. |
| USB BLE dongle (for desktop PC) | 1 | ~$15 | Optional — MBA has built-in BLE 4.0. |
| Chargers | — | included | R09s: magnetic charging case. R10: wireless charging dock (different ecosystem — keep the R10 dock at bedside, one R09 case at the hub). |
| ST-Link/J-Link + fine probes | 1 | ~$15–40 | **Phase 3 only.** SWD recovery/flash path. Defer purchase. |

### Existing hardware (no cost)
- 2014 MacBook Air, Linux Mint Cinnamon — the hub. Configure logind to ignore lid switch; runs 24/7 on wall power.
- Desktop PC — development machine, Claude Code host.
- iPhone — primary dashboard viewer (PWA).
- iPad Air — secondary viewer; optional Swift Playgrounds native app side quest.
- **ESP32-C3** — the Travel Protocol satellite. Development target *and* deployment unit (built-in USB Serial/JTAG: flash, monitor, debug over one cable). Must carry OTA self-update before deploying to Mississauga.
- **ESP32-WROOM-32 dev boards** — drawer spares / fallback; general BLE experimentation.

### Software / services (all free)
- Python 3.12+, `bleak`, `colmi_r02_client` (reference), pytest, FastAPI, SQLite
- Chart.js (dashboard skeleton; frontend design offloaded to Claude Code)
- nRF Connect (iOS/Android) — BLE inspection
- Tailscale (free tier) — secure remote dashboard access; **Tailscale Funnel** for the satellite's token-locked `/ingest` route
- ESP-IDF + NimBLE — Travel Protocol satellite firmware (C/C++)
- OBS / asciinema — screen and terminal capture for the video
- ATC_RF03 tooling (github.com/atc1441/ATC_RF03_Ring) + web OTA flasher — Phase 3
- BlueX RF03 SDK + datasheet — Phase 3

## 5. Phase plan (calibrated to ~5h dev + ~2h documentation per week)

### Phase 0a — Zero-hardware framework ($0, start now)
No purchase required; ~70% of the build happens here. Sequence:
- **Hub build-out** (see HUB_SETUP.md): lid-closed 24/7 operation, SSH, Bluetooth verified, Python env, Tailscale, systemd service pattern. General-purpose home server from day one.
- **Monorepo setup:** `protocol/`, `hub/`, `dashboard/`, `firmware/`, `notebook.md`. First notebook entry same day. Documentation set (PLAN, RESOURCES, HUB_SETUP) lives at the root.
- **Parsers first:** packet parsers built against community-published captures (colmi_r02_client + Gadgetbridge sources per RESOURCES.md); pytest suite with JSON test vectors from day one.
- **Synthetic-data generator:** a script producing realistic fake sleep/HR/SpO2/step/temperature rows into SQLite. This unlocks the entire downstream stack without hardware.
- **Full pipeline on fake data:** SQLite schema → analytics rollups → FastAPI → Chart.js PWA installed on the iPhone via Tailscale. The dashboard reaches near-final state against synthetic data.
- **Exit criteria:** hub passes its verification checklist; parsers pass the fixture suite; the PWA on the iPhone shows a (synthetic) week of sleep and activity.

### Phase 0b — Purchase and hardware bring-up (gated on funds)
- Confirm size 10, verify QRing on both listings, order (1× R10 sz 10, 2× R09 sz 9). Shipping ~1–3 weeks — dead time absorbed by remaining 0a work.
- Arrival: label units (DEV opened without ceremony per the two-pass production model; HERO stays sealed; DAILY charged and worn); pair DEV with the stock QRing app briefly (reference oracle); nRF Connect GATT enumeration on DEV (R09) and DAILY (R10) — capture and diff their service tables; first real sync from the hub.
- Integration is thin by design: point the tested sync service at real MAC addresses; real rows replace synthetic ones.
- **Exit criteria:** one real overnight of sleep data renders on the dashboard.

### Phase 1+2 — Real-data pipeline and dashboard hardening (weeks clocked from hardware arrival)
Much of the original scope lands early in Phase 0a against synthetic data; this phase converts it to real data and fixes what reality breaks.
- Weeks 1–2: sync service against real rings (scheduled v1 policy per §2.2: timer-driven pull of the onboard log, dedupe, store). Metrics 1–5, 8, 11–12, 20 flowing. Parser fixes for R09/R06 protocol deltas found in enumeration.
- Weeks 3–4: analytics against real data — recalibrate sleep session detection, stage estimation (13–14), activity bucketing (10), calorie model (9), workout heuristic (15), temperature baseline (21).
- Weeks 5–6: dashboard iteration with real data on screen; layout refinement via Claude Code with Abhi's input.
- **Exit criteria:** wake up → coffee → glance at phone → last night's sleep and yesterday's activity are just *there*, no user action.

### Interlude — Composite score design (Week ~10)
Two weeks of personal baseline data now exist. Design sleep score and readiness formulas as weighted blends vs. personal baselines. Ship v1, tune over time.

### Parallel track — Travel Protocol (**SHELVED** — see §2.1; design retained, revive on demand)
Prereq when revived: real rings on hand (BLE development needs a real peripheral); hub ingest endpoint live. Development happens directly on the ESP32-C3 (deployment target; built-in USB Serial/JTAG gives flash + monitor + debug over one cable). WROOM-32 boards are drawer spares / fallback only.
1. Hub side (Python, one session): `/ingest` route accepting raw payloads; reuse existing parsers + dedupe; expose via Tailscale Funnel with bearer token.
2. C3 firmware at home: NimBLE central connects to DEV ring, pulls a raw sync payload, POSTs to the hub.
3. **OTA self-update (required before deployment):** `esp_https_ota` — the satellite periodically checks the hub for a new firmware image and updates itself over WiFi. Once deployed there is no USB cable; without this, every firmware fix is a road trip.
4. Soak-test at home for a week: router reboots, ring absences, hub downtime (honoring the no-ack-no-pull rule), and at least one successful OTA update.
5. Deploy to Mississauga on a USB wall adapter. Dashboard freshness becomes continuous across both locations.
- **Exit criteria:** a night of sleep in Mississauga appears on the dashboard before returning to Montreal — and one post-deployment firmware update lands over OTA.

### Phase 3 — Custom firmware (open-ended, C/C++, **DEV unit only, provisionally the R06**)
- Scope: whichever confirmed RF03-class unit holds the DEV role (currently the Colmi R06, pending its own QRing verification). R10, if acquired, stays out of scope — Realtek chip, no ATC groundwork exists for it, stays on stock firmware.
- Write the GATT interface contract document *first* — the app must not care which firmware answers.
- OTA custom firmware via WebBluetooth flasher from Linux/desktop Chrome (not iOS). Verify the ATC_RF03 tooling recognizes the specific unit's hardware revision before any write.
- Wire SWD on DEV unit (epoxy scraping) as the un-brick recovery path before flashing anything risky.
- Goals: raw PPG access → metrics 5b–7 (beat-to-beat HRV, respiratory rate, breathing regularity); custom sampling schedule (stretch, per decision E); power tuning.
- **Blocked on a HERO unit existing** (see §8) before Phase 4 can re-perform this on camera.

### Phase 4 — Video production (begins at ~80% product completion)
- Gate: product works end to end (or ≥80%); confidence is high enough that every step can be re-performed smoothly on camera.
- Script written from `notebook.md`; every claimed nuance or time cost must have a captured artifact backing it.
- Re-perform the full journey on the HERO unit: unboxing → recon → sync → dashboard → (if in scope) epoxy scraping, SWD, custom flash. HERO receives the same modifications DEV did, on camera.
- Filming budget: the standing 1–2 h/week converts from documentation to production during this phase.

## 6. Testing strategy

- **Fixtures as the foundation:** every captured BLE packet becomes a JSON test vector (raw bytes + expected parsed output). Parsers are pure functions tested against these with pytest.
- **Oracle validation (two layers):** (1) wear DAILY ring with the stock QRing app on a spare profile for one overlap week; compare step counts, HR samples, sleep windows against the hub pipeline. (2) Cross-ring: wear HERO (R09) alongside DAILY (R10) for a week and compare the two sensor stacks against each other. Document deltas in the notebook — both are report sections.
- **Pipeline integration test:** replay a full day of captured packets through sync → store → analytics → API; assert rollup values.
- **Phase 3 regression:** the same fixture suite and interface contract validate custom firmware output. If fixtures pass, the app layer is untouched.
- **Longitudinal sanity checks:** automated daily job flags impossible values (HR 0 or 250, negative sleep) — cheap canary for firmware/parser regressions.
- **Buffer characterization (Phase 0b test):** the ring's onboard retention (~days) is community folklore, not a datasheet number. Leave DEV unsynced for N days, sync, measure what survived. The result is the real "maximum trip length without a satellite" and a hard number for the video.
- **One master rule:** never sync a project ring with the stock QRing app once the hub owns it (except the brief Phase 0b oracle window) — the stock app feeds the vendor cloud and may mark the ring's buffered log as delivered, starving the hub.

## 7. Video production and documentation plan

### Production model — two passes (revised July 18)
1. **Dev pass (Phases 0–3, DEV + DAILY units): documentary capture.** Filmed *and* noted as it happens — challenges, design issues, dead ends, and the growing understanding of the project. Raw and unpolished is the point; no retakes, no performance pressure. This footage is the **substance** of the final video.
2. **Filmed pass (Phase 4, HERO unit): production polish.** After ~80% completion, re-perform the journey on camera with full confidence. Focus: eye-catching, entertaining delivery — pacing, framing, b-roll, energy. This footage is the **presentation layer**; the dev-pass documentary material gets cut in as the real story.
3. Honesty beat: show the scarred DEV unit next to the pristine HERO on camera — "this is what the first attempt looks like." Acknowledges the re-staging, shows the real cost of figuring it out.

### Evidence rule (during the dev pass)
The camera now rolls during development, but the lightweight capture discipline still applies — footage without context is unusable, and some artifacts (logs, packets, errors) don't film well:
- `notebook.md` entry every session — date, what worked, what broke, how long it took. This file **is** the script skeleton.
- Screenshot anything surprising: weird packets, cryptic errors, the first rows landing in SQLite, dashboard milestones (skeleton → styled → on the home screen).
- asciinema for terminal sessions (replays cleanly for screen capture during the filmed pass).
- Screen-record the parts order; film the DEV/DAILY unboxing as documentary footage.
These become the "here's what this actually looked like" material that makes the polished footage credible.

### Editorial guidelines
- **Purpose:** present the idea to the masses — not a tutorial, not a buying guide. Story: "I didn't like the crop of smart wearables in the fitness industry, so I did something about it."
- **No product recommendations.** Dependencies named generically ("a ~$25 ring from AliExpress," "an old laptop running Linux," "an open-source BLE client") — no brand endorsements. Commentary limited to first-person experience: what was purchased, what it cost, how long things took, nuances encountered.
- **Privacy angle — frame as trust requirements, not accusations.** Do not claim any named company sells data. The stronger, safer framing: commercial wearables require trusting a privacy policy the user can't verify and that can change post-purchase; this ring requires trusting nothing — data never leaves the home network, no account exists, no subscription exists, and it survives every involved company disappearing.
- **Privacy segment demo beats:** ring syncing with WiFi off; opening the raw SQLite file directly; total lifetime cost = three rings + $0/month; the dashboard loading over Tailscale with no cloud in the path.

### Filmed-pass shot list (Phase 4)
- Unboxing HERO; the parts-order screen recording as insert.
- nRF Connect GATT browsing; first sync in the terminal (asciinema replay or live).
- Dashboard reveal on the iPhone — the "glance test."
- Whiteboard segment: designing the readiness formula.
- If Phase 3 is in scope: epoxy scraping and SWD wiring on HERO (macro shots); the web flasher mid-upload; first boot of custom firmware.
- DEV-vs-HERO side-by-side; 30 days of real data as the results segment.

## 8. Open items

| Item | Owner | Blocking |
|------|-------|----------|
| **Hub foundation plug-and-play before rings arrive** (HUB_SETUP.md checklist) | Abhi — top priority | Phase 0b bring-up |
| Monorepo + parsers + synthetic pipeline (Phase 0a) | Abhi + Claude Code | Nothing |
| Confirm R06 + R09 via nRF Connect on arrival (ground truth over listings) | Abhi | Trusting the fleet |
| Sync trigger strategy — **decided:** scheduled v1, adaptive v2 (see §2.2) | Resolved 2026-07-18 | Nothing |
| HERO unit: second Colmi R09 — gated purchase, only after DAILY survives the testing phase (a break/brick replacement doubles as the decision point) | Abhi — deferred by design | Phase 4 filmed pass |
| Travel Protocol | **Shelved** — design retained in §2.1 | Nothing; revive when cross-city freshness matters |
| Composite score formulas (16–18) | Joint design session | Interlude week (~2 weeks of data required) |
| Dashboard layout preferences | Abhi, iterative during dashboard weeks | Nothing — skeleton first |
| GATT interface contract doc | Written at start of Phase 3 | Phase 3 flashing |
