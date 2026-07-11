# protocol/

QRing BLE protocol parsers — pure functions, no I/O.

- Packet parsers for the QRing protocol (shared across R09/R10; expect minor per-model variations).
- `fixtures/` — JSON test vectors: raw captured bytes + expected parsed output.
- pytest suite validates parsers against fixtures. This suite is also the Phase 3 regression gate:
  if custom firmware output still passes these fixtures, the app layer above is untouched.
