# dashboard/

Installable PWA, served by `hub/api.py`. Dark, phone-first, glanceable.

Four files and no build step: `index.html`, `style.css`, `app.js`, `manifest.json`.
Edit and reload.

**No Chart.js.** `PLAN.md` originally named it, which would mean either a CDN — breaking
offline use and putting a third party in the request path of a project whose entire
premise is not having one — or vendoring a bundle into the repo. Two line charts and a
bar chart are about eighty lines of hand-written SVG, so neither cost was worth paying.

Everything the API returns is UTC. Conversion to local time happens here and only here.

## Notes

- Refreshes every five minutes. The hub syncs three times a day, so polling harder buys
  nothing.
- Installing to the iPhone home screen needs HTTPS for the service worker; Tailscale
  Serve provides a real certificate for the tailnet name. Until then it is a LAN page.
- Tile labels follow the selected range — "Lowest 24 h" becomes "Lowest 30 d" — and the
  per-reading dots disappear above 60 points to keep long ranges readable.
