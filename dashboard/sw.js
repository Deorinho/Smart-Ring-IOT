/* RX-06 service worker.
 *
 * Exists for one reason: iOS will not treat this as an installed app without it. The
 * manifest plus Apple's meta tags already give "Add to Home Screen" a standalone launch,
 * but a service worker is what makes it a PWA rather than a bookmark that hides Safari's
 * chrome — and it is the prerequisite for push, which is the still-open half of
 * Bug_Backlog R-009 (the ring ran 80% -> 1% unnoticed once already).
 *
 * A service worker requires a secure context, so this only registers over HTTPS or on
 * localhost. On the LAN over plain http it silently does nothing, which is correct:
 * see HUB_SETUP.md section 5 for Tailscale Serve, which issues a real certificate for
 * the tailnet name.
 *
 * The caching policy is deliberately asymmetric, and the asymmetry is the whole design:
 *
 *   shell (html/css/js/icons)  ->  stale-while-revalidate
 *   /api/*                     ->  network only, never cached
 *
 * The shell is static and has no build step, so serving it from cache costs nothing and
 * revalidating in the background means an edit on the hub shows up on the next load
 * rather than never. Cache-first without revalidation would have made every dashboard
 * tweak require bumping a version string by hand, which is the kind of chore that gets
 * skipped and then debugged for an hour.
 *
 * The API is never cached, and that is not an oversight. This dashboard's entire premise
 * is that the status line tells you whether the numbers under it are true. A cached
 * reading replayed as though it were current would break that quietly and in the one
 * direction that matters — you would look at your heart rate from yesterday and believe
 * it was now. Offline, the fetch simply fails and app.js already renders
 * "Hub unreachable", which is an honest thing for a screen to say.
 */

const CACHE = "rx06-shell-v2";

/* Everything needed to paint the dashboard with no network. Kept explicit rather than
 * globbed: there is no build step to generate a manifest from, and a short list that is
 * obviously complete beats a clever one that silently misses a file. */
const SHELL = [
  "/",
  "/style.css",
  "/app.js",
  "/manifest.json",
  "/icon.svg",
  "/mark.png",
];

self.addEventListener("install", (event) => {
  // Take over as soon as this worker is ready rather than waiting for every tab to
  // close. On a phone the dashboard tab is often never closed.
  self.skipWaiting();
  event.waitUntil(
    caches.open(CACHE).then((cache) =>
      /* addAll is atomic — one 404 rejects the whole install and leaves the previous
       * worker in place. That is the behaviour we want: a half-cached shell that boots
       * to a broken layout is worse than no service worker at all. */
      cache.addAll(SHELL)
    )
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((names) =>
        Promise.all(names.filter((n) => n !== CACHE).map((n) => caches.delete(n)))
      )
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // Only ever handle our own GETs. Anything else falls through to the browser, which
  // is the correct default for a read-only dashboard that issues no writes.
  if (request.method !== "GET" || url.origin !== self.location.origin) return;

  // Readings go to the network or they do not arrive. No respondWith at all here, so
  // the browser performs its normal fetch and app.js sees a normal failure.
  if (url.pathname.startsWith("/api/")) return;

  event.respondWith(
    caches.open(CACHE).then(async (cache) => {
      const cached = await cache.match(request, { ignoreSearch: false });

      const fromNetwork = fetch(request)
        .then((response) => {
          // Opaque and error responses are never written to the cache; storing a 502
          // would persist the outage past the point where the hub came back.
          if (response && response.ok && response.type === "basic") {
            cache.put(request, response.clone());
          }
          return response;
        })
        .catch(() => null);

      // Cached copy immediately if there is one, with the network refreshing it behind
      // the scenes. Otherwise wait for the network, and if that fails on a navigation,
      // fall back to the cached shell so a cold offline launch still paints.
      if (cached) return cached;

      const fresh = await fromNetwork;
      if (fresh) return fresh;

      if (request.mode === "navigate") {
        const shell = await cache.match("/");
        if (shell) return shell;
      }
      return Response.error();
    })
  );
});
