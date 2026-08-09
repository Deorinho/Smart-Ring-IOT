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
| R-007 | RISK | 2026-08-02 | hub / sync policy | The ring is unreachable over BLE while in the charging case — `BleakClient` connect timed out after 20 s, no protocol involved. Cause not yet isolated: either the ring stops advertising while charging, or the case shields the antenna. Charging happens ~daily, so the sync service must treat this as a normal `no_device` outcome, not an error worth backing off or alerting on. Also blocks confirming `parse_battery`'s `is_charging` byte. Diagnostic: scan while in the case — if it advertises but won't connect, that's a different cause than not advertising at all. |
| R-006 | RISK | 2026-08-02 | protocol / deps | Hub has bleak 3.0.2 (new major release). `colmi_r02_client`, the reference implementation named in `RESOURCES.md`, targets bleak 0.2x and will likely conflict if installed as a dependency. Mitigation: treat it as **source reference** for packet layouts, not a runtime dependency. |
| R-005 | RISK | 2026-08-02 | hub / systemd | The Bluetooth stack initializes ~43 s into boot (USB device enumerates at ~2.8 s, `Bluetooth: Core ver 2.22` at 43.0 s). A sync service starting earlier will find no adapter. Symptom if unhandled: syncing works by hand but never after a reboot. `ring-sync.service` needs `After=bluetooth.target` and must tolerate an adapter that isn't ready yet. |

## Closed

| ID | Pri | Found | Closed | Summary |
| --- | --- | --- | --- | --- |
| — | — | — | — | *(nothing closed yet)* |
