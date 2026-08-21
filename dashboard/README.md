# dashboard/

Installable PWA, served by `hub/api.py`.

Built to the **RX-06 Dashboard** design in the *RavenX Instruments branding* project,
on **Nocturne**'s tokens. Four files, no build step: `index.html`, `style.css`,
`app.js`, `manifest.json`. Edit and reload.

## Where the design lives

Claude Design projects, reachable with the `DesignSync` tool:

| Project | ID | Type |
| --- | --- | --- |
| RavenX Instruments branding | `871fe223-6035-4a78-bf0d-77d7144460d8` | `PROJECT` |
| Nocturne (design system) | `d5af71cd-d450-48ea-8f46-811902de8b15` | `DESIGN_SYSTEM` |

**The branding project does not appear in `list_projects`** — that call returns only
design-system projects, and this one is a regular project. Address it by ID via
`get_project` / `list_files` / `get_file`, or it looks like it doesn't exist.

Files worth knowing: `RX-06 Dashboard.dc.html` (this dashboard's design, both a
first-light and a mature state), `RavenX Brand.dc.html`, `RavenX Ethos.dc.html`,
`brand/mark-*.png`, and Nocturne vendored under `_ds/`. `mark-light.png` is the raven in
`dashboard/mark.png`.

## The design's rules, and why the code follows them

- **One status line.** Sync time, run count, clock offset — the three numbers that
  decide whether anything below them is true. The rest of the machinery stays in the hub.
- **Empty is a state, not a gap.** Awaiting cards name the session that fills them, so
  the dashboard reads as a build log you happen to wear. Sleep and steps are dashed
  placeholders today because neither parser exists; that is honest, not broken.
- **Card order never changes.** The screen fills in rather than rearranging, so a glance
  lands in the same place on day 1 and day 400.
- **Green means live** (in tolerance, current), **orange means attention** (not yet),
  **violet carries the data**. Elevation is used once, on the night panel.
- **No composite scores.** Raw metrics only until a personal baseline earns them.

## Two deliberate deviations

**No Google Fonts.** Nocturne's stylesheet opens with an `@import` of Inter. Reproducing
it would break offline use and put a third party in the request path of a project whose
entire premise is not having one. `"Inter", system-ui` falls back to SF on iOS, which is
Inter's close cousin.

**No Chart.js**, which `PLAN.md` originally named. Same reasoning — a CDN or a vendored
bundle, for one sparkline that is twenty lines of hand-written SVG.

## Notes

- Below 14 readings the series draws as dots rather than a line. A polyline through six
  samples implies continuity the ring never measured — it sampled twice an hour.
- The large number is the window **minimum**, labelled as such. A real resting-HR figure
  needs sleep detection, which does not exist yet.
- The status line switches from a clock time to elapsed time past ~20 hours, because
  "Synced 21:00" reads as today when it was three days ago.
- Refreshes every five minutes. The hub syncs three times a day; polling harder buys
  nothing.
- Installing to the iPhone home screen needs HTTPS for the service worker — see
  `HUB_SETUP.md` §5 for Tailscale Serve. Until then it is a LAN page.

## The service worker

`sw.js` exists so this is an installed app rather than a bookmark that hides Safari's
chrome, and because it is the prerequisite for push — the still-open half of R-009, the
ring having once run 80% → 1% unnoticed.

Its caching policy is asymmetric on purpose:

| Request | Policy | Why |
| --- | --- | --- |
| shell (html/css/js/icons) | network-first, cache as offline fallback | What is deployed is what you see. Stale-while-revalidate was tried first and is wrong for a project under active change: the first load after every deploy served the OLD files, producing a page of new markup styled by an old stylesheet — which looks like a bug, not a cache. Cost a debugging round on 2026-08-20. |
| `/api/*` | **network only, never cached** | A cached reading replayed as current would break the one promise this design makes. Offline, the fetch fails and the status line says "Hub unreachable", which is an honest thing for a screen to say. |

**It requires a secure context.** Over plain http on the LAN, registration rejects and
the dashboard carries on working exactly as before — the failure is logged via
`console.info` rather than swallowed, so "is it actually installed?" stays answerable
from the phone.

**Verified on iOS 2026-08-17** over Tailscale Serve: added to the home screen, launched
in airplane mode, shell painted from cache with the status line reading
`Hub unreachable · Load failed`. That string is the proof rather than a fault — it is
Safari's fetch error arriving through `app.js`'s catch, which only runs if the document
itself was served without a network.

The offline test is the cheapest way to re-confirm the worker after any change to `sw.js`
or the shell file list: airplane mode, relaunch, see whether it paints.

Bump `CACHE` in `sw.js` if a shell file ever needs to be force-evicted. With
network-first this is rarely necessary — the cache only serves when the hub is
unreachable, so a stale entry cannot mask a deploy.

**If the phone ever does look stale:** fully quit the PWA from the app switcher and
reopen twice. The first relaunch fetches the new worker, the second runs it.

## Round markers are HTML, not SVG

The chart stretches to the card width with `preserveAspectRatio="none"`, so a 220x44
viewBox is drawn into roughly 339x56 and x and y scale by different factors. Any
`<circle>` in that space renders as a visibly squashed ellipse — which is what the scrub
dot and the end-of-series dot both were until 2026-08-20.

Markers are therefore absolutely-positioned `div`s with `border-radius: 50%`, placed by
percentage. `.spark-wrap` carries the chart's top margin rather than `.spark` doing so,
because the wrapper has to be exactly the chart's box for those percentages to land.

Only line work stays in SVG, where the same distortion is harmless as long as
`vector-effect="non-scaling-stroke"` keeps stroke widths from stretching.

## Two iOS traps worth remembering

**`<button>` needs `appearance: none`.** Without it iOS paints its own chrome and the
sync button rendered as a white pill that ignored the theme entirely, while the desktop
looked correct.

**`color-mix()` as the only `background` is a trap.** If a Safari version does not
support the function the whole declaration is dropped and the UA default shows through.
Use `rgba()` for anything load-bearing, or pair `color-mix()` with a plain fallback
declared before it.

**Touch pointers report `pressure: 0`.** Scrubbing originally gated `pointermove` on
`e.pressure > 0 || e.buttons`, which is true for a mouse and false for an ordinary iOS
touch — so it worked on the desktop and did nothing on the phone, the device it exists
for. Track a `dragging` flag set on `pointerdown` instead of interrogating the event.

## The sync button

Pressing it does not sync. It `POST`s to `/api/sync`, which asks systemd to start
`ring-sync-now.service` — the same BLE path the timer already runs, just with `--force`
so a scheduled run twenty minutes ago does not make the button look broken. **The API
still never writes to the store**; the separate sync process does, under its own
identity. That property is why `hub/api.py` is safe to expose.

A confirm sheet sits in front of it, and it earns its place: the sync happens between the
ring and the hub over Bluetooth, and the phone is the one device in the system that can
tell you nothing about where either of them is. Body-worn costs about 21 dB (R-010), so
"another room" is a plausible failure and worth a sentence before a 25-second wait.

The flow is a poll, not a wait. iOS suspends pending fetches when the screen locks, so a
request held open across a real sync comes back as a network error rather than a result.
The client records `sync_runs.id` before triggering and watches for it to change **and**
for the row to stop saying `running` — `db.start_sync_run` inserts its row at the *start*
of a sync, so a changed id alone means "started", not "finished".

Outcomes are distinguished rather than flattened: `+N` on rows ingested, "Up to date"
when a successful sync found nothing new, and "No ring" for `no_device` — which is not a
fault. The ring is on a hand that leaves the house.

## Charging state

The battery pill turns amber with a bolt when the ring is on the charger, and the pulse
is deliberate: **charging is only ever sampled at sync time.** Nothing polls the ring, so
this reading is exactly as old as the last sync, and the animation says "as of then"
without needing a caption.

The flag is only believed when `battery_charging.ts_utc` matches `battery.ts_utc`. A
charging state from yesterday rendered beside a fresh percentage would be the dashboard
asserting something it does not know — the same rule the rest of this page follows.

Charging outranks the low-battery orange. A ring at 8% on the charger is being handled
and does not need attention.

## Scrubbing the chart

Drag across the heart-rate chart to read any point. The value is the **nearest real
sample**, never interpolated: the ring measures twice an hour, and a number invented
between two readings would be a fabrication rendered in the same style as a measurement.

The readout shows a bare clock time on the 24 h window and adds the date on 7 d and 30 d,
for the same reason the status line switches to elapsed time past ~20 hours.

`touch-action: pan-y` lets a vertical page scroll pass through the chart while horizontal
drags are claimed for scrubbing.
