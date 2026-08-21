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
 *   shell (html/css/js/icons)  ->  network-first, cache as offline fallback
 *   /api/*                     ->  network only, never cached
 *
 * The shell was originally stale-while-revalidate, which paints instantly and refreshes
 * in the background. That is the right policy for a finished app and the wrong one for
 * this project: it means the first load after every deploy shows the OLD files, and a
 * dashboard that is half-new-markup and half-old-stylesheet looks like a bug rather
 * than a cache. It cost a debugging round on 2026-08-20 doing exactly that.
 *
 * Network-first inverts the trade. A cold launch costs a few hundred milliseconds while
 * the shell is fetched, and in exchange what you see is always what is deployed. The
 * offline behaviour is unchanged -- the cache is still there, it is just the fallback
 * rather than the first choice -- so airplane mode still paints the shell.
 *
 * The API is never cached, and that is not an oversight. This dashboard's entire premise
 * is that the status line tells you whether the numbers under it are true. A cached
 * reading replayed as though it were current would break that quietly and in the one
 * direction that matters — you would look at your heart rate from yesterday and believe
 * it was now. Offline, the fetch simply fails and app.js already renders
 * "Hub unreachable", which is an honest thing for a screen to say.
 */

const CACHE = "rx06-shell-0820b";

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
      // Network first. What is deployed is what you see.
      try {
        const fresh = await fetch(request);
        // Opaque and error responses are never written to the cache; storing a 502
        // would persist the outage past the point where the hub came back.
        if (fresh && fresh.ok && fresh.type === "basic") {
          cache.put(request, fresh.clone());
        }
        if (fresh && fresh.ok) return fresh;
        // A real 404 from a reachable hub is the honest answer -- do not paper over it
        // with a stale copy of a file that no longer exists.
        if (fresh) return fresh;
      } catch (err) {
        /* offline; fall through to the cache below */
      }

      const cached = await cache.match(request, { ignoreSearch: false });
      if (cached) return cached;

      if (request.mode === "navigate") {
        const shell = await cache.match("/");
        if (shell) return shell;
      }
      return Response.error();
    })
  );
});
