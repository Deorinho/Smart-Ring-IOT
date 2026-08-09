# Bug Backlog

Open defects and known risks. **P1 items are surfaced at every `/startup`.**

Priorities:

- **P1** — blocks the daily pipeline. Data is being lost, the ring isn't syncing, or the
  dashboard is wrong. Fix before new features.
- **P2** — degrades something that still works. Fix when convenient.
- **P3** — annoyance, cosmetic, or cleanup. Fix when idle.
- **RISK** — not a defect yet. A known failure mode that will become P1 if unhandled.

Entry format: one row per item. Add the date found; add the date closed and move the row
to Closed rather than deleting it — a fixed bug is video material.

## Open

| ID | Pri | Found | Area | Summary |
| --- | --- | --- | --- | --- |
| R-001 | RISK | 2026-08-02 | hub / network | Mullvad and Tailscale both manage routing and firewall rules on the hub. Tailscale is not installed yet; when it goes in, expect route conflicts. Mullvad LAN sharing must stay enabled or SSH and the dashboard break. |
| R-002 | RISK | 2026-08-02 | protocol / time | The R06's RTC has never been set, so its log timestamps run from an unknown factory epoch. Storage is UTC ISO-8601 everywhere, so the ring↔hub clock offset must be captured at sync time. Assuming ring timestamps are correct will silently corrupt the entire store. |
| R-003 | RISK | 2026-08-02 | hub / radio | The 2014 MacBook Air's Broadcom chip shares one 2.4 GHz radio between WiFi and Bluetooth. On a 2.4 GHz SSID, BLE scanning degrades intermittently — the hardest failure mode to diagnose later. Keep the hub on 5 GHz. |
| R-004 | RISK | 2026-08-02 | data durability | The SQLite file is the crown jewel and lives on a decade-old SSD with no backup, rotation, or verified restore. Single point of failure for the project's entire premise. |
| R-008 | RISK | 2026-08-08 | protocol / sleep | **Sleep is the top-priority metric and has no public Python reference.** colmi_r02_client has no `sleep.py` at all; Gadgetbridge's Colmi/Yawell classes are the only prior art. It may also ride the second vendor service (`de5bf728`) rather than the command channel, which nothing upstream documents. Budget session 6 as reverse-engineering, not porting — it is the largest genuinely unsolved piece of the protocol. |
| R-013 | P2 | 2026-08-09 | hub / workflow | **The hub cannot push to GitHub.** Password auth over HTTPS is disabled by GitHub, so `git push` from `~/Projects/RavenXSmartRing-IOT` fails. This blocks the normal path for every capture, since captures are always written on the hub. Workaround in use: `scp` the files to the desktop and commit there, then `git reset --hard origin/<branch>` on the hub to discard the orphan commit. Fix properly with an SSH key on the hub (`ssh-keygen`, add the public key to GitHub, switch the remote to `git@github.com:`) — durable and no token expiry. |
| R-012 | RISK | 2026-08-08 | hub / battery | **Unexplained idle drain, now with a counter-measurement.** Factory config: 80% → 1% in ~6 days (~13%/day) *with HR logging disabled*. After enabling HR at 30 min: 100% → 96% in 14.3 h (~6.7%/day) — **roughly half the drain while doing strictly more sensing.** Treat that rate as provisional; voltage-based fuel gauges are non-linear near full charge and 14 h is too short a window. The implication stands regardless: something was running during the factory week that is not running now. Only the HR settings (`0x16`) have ever been queried. **Next target: find the SpO2 / stress / HRV / temperature auto-monitoring enable flags** — if they ship on by default, the ring is spending power on metrics that are explicitly deprioritized. |
| R-010 | RISK | 2026-08-08 | hub / radio range | **Body-worn costs ~21 dB.** Measured at the same desk and the same battery level: −60 dBm in the charging case, **−81 dBm on the finger**. Human tissue absorbs 2.4 GHz heavily. If −81 is the figure beside the hub, range from another room may not support a reliable sync — and the shelved adaptive-policy thresholds (−85 present / −80 connect) were evidently calibrated against a ring on a table, not a hand. Measure RSSI at realistic distances (desk, next room, bedside) before designing the scheduler; the answer may dictate where the hub physically lives. |
| R-009 | RISK | 2026-08-08 | hub / battery | **No low-battery warning exists.** The R06 went from 80% to 1% in the ~6.8 days since it was first read, at factory sensing settings (~12%/day), and nothing told Abhi — that job belonged to the vendor app, which this ring will never run. The hub must own it: surface battery on the dashboard and alert below a threshold. Until then the ring will silently die and take a data gap with it. Becomes P1 the moment the pipeline is relied on. |
| R-006 | RISK | 2026-08-02 | protocol / deps | Hub has bleak 3.0.2 (new major release). `colmi_r02_client`, the reference implementation named in `RESOURCES.md`, targets bleak 0.2x and will likely conflict if installed as a dependency. Mitigation: treat it as **source reference** for packet layouts, not a runtime dependency. |
| R-005 | RISK | 2026-08-02 | hub / systemd | The Bluetooth stack initializes ~43 s into boot (USB device enumerates at ~2.8 s, `Bluetooth: Core ver 2.22` at 43.0 s). A sync service starting earlier will find no adapter. Symptom if unhandled: syncing works by hand but never after a reboot. `ring-sync.service` needs `After=bluetooth.target` and must tolerate an adapter that isn't ready yet. |

## Closed

| ID | Pri | Found | Closed | Summary |
| --- | --- | --- | --- | --- |
| R-011 | RISK | 2026-08-08 | 2026-08-09 | "Settings writes may clobber the undocumented byte[4]." **Disproven.** `set_hr_log_settings` sends only bytes 2 and 3, and byte[4] survived unchanged across an enable write (`16 01 02 1e 05 .. 3c` → `16 01 01 1e 05 .. 3b`). The field's meaning is still unknown and remains noted in `parse_hr_log_settings`, but it is not at risk. Also learned: writes ack with `16 02 01 ..`, so acceptance can be confirmed rather than assumed. |
| R-007 | RISK | 2026-08-02 | 2026-08-08 | "Ring unreachable over BLE while charging." **Not reproducible — the premise was wrong.** In a powered case beside the hub the ring scans at −61 dBm, connects, and completes a battery round trip normally. Session 2's timeout had another cause: most likely an unpowered case, greater distance, or a battery already too flat to hold a link (it read 1% six days later). Resolving this also settled `parse_battery`'s `is_charging` flag — `byte[2]` is 1 on the charger, 0 on the finger. Lesson kept: a single failed connect is not evidence of a mechanism. |
