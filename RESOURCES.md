# RESOURCES.md — annotated documentation index

Every external resource this project depends on, ordered by when you'll need it.
Rule of thumb: read the protocol material during the zero-hardware phase; skim the
Phase 3 material now, study it later.

---

## Protocol & reverse engineering (read first — needed for parsers)

- **colmi_r02_client** — the reference Python client for the QRing ring family.
  Docs: https://tahnok.github.io/colmi_r02_client/colmi_r02_client.html
  Repo: https://github.com/tahnok/colmi_r02_client
  Why: working parser implementations for HR, SpO2, steps, sleep packets; the
  fastest way to understand the byte layout. Read the source, not just the docs.
  Use it as a library first; replace pieces with your own code as you learn.

- **Gadgetbridge — Yawell/Colmi device page** — https://gadgetbridge.org/gadgets/wearables/yawell/
  Why: authoritative model matrix (which ring = which hardware = which features),
  including the R09/R10 distinctions and firmware-version feature notes (HRV, REM,
  temperature, stress).

- **Gadgetbridge source code** — https://codeberg.org/Freeyourgadget/Gadgetbridge
  Why: a second, independent implementation of the QRing protocol (Java). When your
  parser disagrees with colmi_r02_client, this is the tiebreaker. Search the tree
  for the Colmi/Yawell device support classes. Also the best source of protocol
  handling for the R09/R10 generation specifically (temperature, HRV packets).

- **ATC_RF03 project (Aaron Christophel)** — https://github.com/atc1441/ATC_RF03_Ring
  Why: the custom-firmware foundation — RF03 SoC findings, SDK/datasheet links,
  OTA flasher (linked from the repo), example firmware. Phase 3's bible; skim the
  README now to understand what's possible. His accompanying YouTube teardown video
  (linked in the repo) is also the best visual reference for what's inside the ring.

## Python stack (zero-hardware phase)

- **bleak** — https://bleak.readthedocs.io — cross-platform BLE client library.
  Read: scanning, connecting, GATT characteristic read/write/notify. Your sync
  service is ~200 lines of bleak.
- **FastAPI** — https://fastapi.tiangolo.com — the hub's API + PWA server.
  Read: first-steps tutorial, StaticFiles, and the SQL databases section.
- **pytest** — https://docs.pytest.org — read: parametrize (one test, many packet
  fixtures) and fixtures.
- **SQLite** — https://sqlite.org/docs.html — stdlib `sqlite3` is enough; read
  the datatype notes (store timestamps as ISO-8601 TEXT or unix INTEGER, pick one).

## Dashboard (zero-hardware phase, with synthetic data)

- **Chart.js** — https://www.chartjs.org/docs/latest/ — read: line + bar charts,
  time axis (needs a date adapter), responsive options. Dark theme via CSS variables.
- **PWA basics (MDN)** — https://developer.mozilla.org/en-US/docs/Web/Progressive_web_apps
  Read: web app manifest (name, icons, display: standalone). That alone gets
  "Add to Home Screen" on iOS looking like a native app. Service worker optional
  for v1 — the hub is always reachable via Tailscale anyway.

## Hub & networking

- **HUB_SETUP.md** (this repo) — the 2014 MBA build-out, start to finish.
- **Tailscale docs** — https://tailscale.com/kb — read: quickstart, MagicDNS.
- **systemd user units** — `man systemd.service`, `man loginctl` (linger). The
  Arch Wiki's systemd/User page is the best readable overview regardless of distro.

## Tools

- **nRF Connect for Mobile** (Nordic Semiconductor — iOS App Store) — GATT
  browser for the recon step; also useful now to practice on any BLE device
  you own (headphones, iPad) so the workflow is familiar before the rings arrive.
- **asciinema** — https://asciinema.org — terminal session recorder; replays
  cleanly for the filmed pass.
- **OBS Studio** — https://obsproject.com — screen capture for dashboard footage.

## Travel Protocol satellite (needed once real rings are on hand; Phase 3 rehearsal)

- **ESP-IDF** — https://docs.espressif.com/projects/esp-idf/en/latest/esp32c3/
  Why: official SDK for the ESP32-C3. Read: getting-started (toolchain + flashing
  over the built-in USB Serial/JTAG), the NimBLE example, and `esp_https_ota` for
  the mandatory OTA self-update before deployment.
- **NimBLE (Apache, bundled with ESP-IDF)** — read the `nimble-central` example;
  this is the BLE central role the satellite plays to pull raw payloads from the
  ring, mirroring what `bleak` does on the hub.
- **Tailscale Funnel** — https://tailscale.com/kb/1223/funnel — read: quickstart.
  Why: exposes only the hub's `/ingest` route to the public internet (TLS via
  Tailscale's relay, no port forwarding); every other route stays Tailnet-only.
- **esp_wireguard** — https://github.com/trombik/esp_wireguard — fallback if a
  fully closed point-to-point tunnel is ever preferred over Funnel + bearer token.

## Phase 3 (skim now, study later)

- ATC_RF03 repo (above) — BlueX RF03 SDK + datasheet links inside it.
- SWD basics: any ST-Link/J-Link intro guide; concepts needed: SWDIO/SWCLK/GND/VCC,
  attach vs reset-halt, flash read-back before first write (dump stock firmware
  as the recovery image — non-negotiable first step).
- WebBluetooth flasher: linked from the ATC repo; runs in Chrome/Chromium on
  Linux or Windows desktop (not iOS Safari).

## Reading order for the zero-hardware phase

1. HUB_SETUP.md — working hub (one evening)
2. colmi_r02_client source — packet structures (one session)
3. Gadgetbridge Yawell page + relevant source files — R09/R10 deltas (one session)
4. bleak scanning tutorial — smoke-test scan on the hub (30 min)
5. Everything else on demand as the code needs it
