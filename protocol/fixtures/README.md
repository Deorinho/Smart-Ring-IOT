# protocol/fixtures/

Captured packets from real hardware — raw bytes plus the context needed to interpret
them later.

These exist because the QRing protocol is reverse-engineered and incomplete. When a
parser improves, it gets re-run against captures already on disk instead of requiring
the ring to be in the right state again. Same principle as the `raw_payloads` table in
`hub/schema.sql`, applied at development time.

**Never delete a capture.** Some describe states that cannot be reproduced — most
notably anything recorded from R06_D29C before its RTC was first set. The ring is
factory-virgin exactly once.

Captures are written by scripts in `tools/`. They land on the hub, since that is where
the radio is, and need copying back into this directory to be committed.
