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
