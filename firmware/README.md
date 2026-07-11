# firmware/

**Phase 3 — open-ended, C/C++, R09 units only.** The R10 (Realtek RTL8762) stays on stock firmware
permanently; there is no ATC groundwork for it.

Out of scope until Phase 1+2 (hub pipeline + dashboard) are done. Work here targets the RF03-class
R09s (DEV unit first, then HERO on camera in Phase 4), building on the ATC_RF03 tooling
(github.com/atc1441/ATC_RF03_Ring).

The GATT interface contract doc must be written before any flashing — the app layer must not care
which firmware answers.
