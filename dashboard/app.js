/* RX-06 dashboard.
 *
 * Dependency-free by design. Nocturne's guidance is to take every value from its
 * tokens, which style.css does; the one chart here is hand-written SVG rather than a
 * library, because a CDN would break offline use and put a third party in the request
 * path of a project built on not having one.
 *
 * Every timestamp arrives as UTC ISO-8601 and is converted to local time here. This is
 * the display layer and the only place that conversion may happen.
 */

const $ = (id) => document.getElementById(id);
const pad = (n) => String(n).padStart(2, "0");

async function getJSON(url) {
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) throw new Error(`${res.status} ${url}`);
  return res.json();
}

const clock = (iso) => {
  const d = new Date(iso);
  return `${pad(d.getHours())}:${pad(d.getMinutes())}`;
};

function ago(iso) {
  const mins = Math.round((Date.now() - new Date(iso)) / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins} min ago`;
  const hours = Math.round(mins / 60);
  if (hours < 48) return `${hours} h ago`;
  return `${Math.round(hours / 24)} d ago`;
}

function duration(points) {
  if (points.length < 2) return "";
  const ms = new Date(points.at(-1).t) - new Date(points[0].t);
  const h = Math.floor(ms / 3600000);
  const m = Math.round((ms % 3600000) / 60000);
  return h ? `${h} h ${pad(m)} m` : `${m} m`;
}

/* --- the one chart ------------------------------------------------------ */

const W = 220;
const H = 44;

/* Below this many readings the series is drawn as discrete dots rather than a line.
 * A polyline through six samples implies continuity the ring never measured — it
 * sampled twice an hour. Dots stay honest about that; once the series is dense
 * enough for the gaps to be small, a line reads better. */
const LINE_THRESHOLD = 14;

function sparkline(el, points) {
  if (!points.length) {
    el.innerHTML = "";
    return;
  }

  const xs = points.map((p) => new Date(p.t).getTime());
  const ys = points.map((p) => p.v);
  const x0 = Math.min(...xs);
  const x1 = Math.max(...xs);
  const lo = Math.min(...ys) - 3;
  const hi = Math.max(...ys) + 3;

  const px = (t) => ((t - x0) / (x1 - x0 || 1)) * W;
  const py = (v) => H - 6 - ((v - lo) / (hi - lo || 1)) * (H - 12);

  // The resting baseline: a dashed accent rule at the window minimum, which is the
  // number shown large above. It gives the sparkline something to be read against.
  const baseline = `<line x1="0" y1="${py(Math.min(...ys)).toFixed(1)}" x2="${W}"
    y2="${py(Math.min(...ys)).toFixed(1)}" stroke="#9184d9" stroke-opacity="0.3"
    stroke-width="0.6" stroke-dasharray="3 3"/>`;

  let series;
  if (points.length >= LINE_THRESHOLD) {
    const pts = points.map((p, i) => `${px(xs[i]).toFixed(1)},${py(p.v).toFixed(1)}`);
    series =
      `<polyline points="${pts.join(" ")}" fill="none" stroke="#9184d9"
         stroke-width="1.6" stroke-linejoin="round" stroke-linecap="round"
         vector-effect="non-scaling-stroke"/>` +
      `<circle cx="${px(xs.at(-1)).toFixed(1)}" cy="${py(ys.at(-1)).toFixed(1)}"
         r="2.6" fill="#b8f24a"/>`;
  } else {
    series = points
      .map(
        (p, i) =>
          `<circle cx="${px(xs[i]).toFixed(1)}" cy="${py(p.v).toFixed(1)}"
             r="1.9" fill="#b8f24a"/>`
      )
      .join("");
  }

  el.innerHTML = `<svg class="spark" viewBox="0 0 ${W} ${H}"
    preserveAspectRatio="none" style="overflow:visible"
    xmlns="http://www.w3.org/2000/svg">${baseline}${series}
    <line class="scrub-line" id="scrub-line" x1="0" y1="0" x2="0" y2="${H}" opacity="0"/>
    <circle class="scrub-dot" id="scrub-dot" r="3.2" cx="0" cy="0" opacity="0"/>
  </svg>`;

  // Hand the scrub handler the same arrays the chart was drawn from, so the readout
  // cannot drift from the line. Recomputing them would be a second source of truth.
  attachScrub(el, points, xs, px, py);
}

/* --- scrubbing ----------------------------------------------------------
 *
 * The chart is drawn in an unscaled viewBox and stretched by CSS, so a pointer's
 * client x has to be mapped back through the element's rendered width -- not through
 * the viewBox width, which is a coordinate space and not pixels.
 *
 * Nearest-sample rather than interpolated: the ring measures twice an hour, and a
 * number invented between two real readings would be a fabrication rendered in the
 * same style as a measurement. */
function attachScrub(el, points, xs, px, py) {
  const readout = $("scrub");
  const line = $("scrub-line");
  const dot = $("scrub-dot");
  if (!line || !dot || points.length === 0) return;

  const show = (clientX) => {
    const box = el.getBoundingClientRect();
    if (!box.width) return;
    const ratio = Math.min(Math.max((clientX - box.left) / box.width, 0), 1);
    const target = ratio * W;

    let best = 0;
    let bestGap = Infinity;
    for (let i = 0; i < xs.length; i++) {
      const gap = Math.abs(px(xs[i]) - target);
      if (gap < bestGap) {
        bestGap = gap;
        best = i;
      }
    }

    const point = points[best];
    const x = px(xs[best]);
    line.setAttribute("x1", x);
    line.setAttribute("x2", x);
    line.setAttribute("opacity", "1");
    dot.setAttribute("cx", x);
    dot.setAttribute("cy", py(point.v));
    dot.setAttribute("opacity", "1");

    $("scrub-bpm").textContent = Math.round(point.v);
    // Multi-day windows need the date; a bare clock time on a 30 d chart is a lie.
    const when = new Date(point.t);
    $("scrub-time").textContent =
      days === 1
        ? clock(point.t)
        : `${when.toLocaleDateString(undefined, { month: "short", day: "numeric" })} ${clock(point.t)}`;
    readout.hidden = false;
  };

  const hide = () => {
    line.setAttribute("opacity", "0");
    dot.setAttribute("opacity", "0");
    readout.hidden = true;
  };

  // Pointer events cover mouse and touch in one path. touch-action: pan-y in the CSS
  // lets a vertical page scroll through the chart while claiming horizontal drags.
  el.addEventListener("pointerdown", (e) => {
    // Capture keeps the readout tracking if the finger slides off the chart mid-drag.
    // It throws for a pointer id the element does not own, which must not take the
    // scrub down with it -- the readout is the feature, capture is the polish.
    try {
      el.setPointerCapture(e.pointerId);
    } catch (err) {
      /* not capturable; scrubbing still works within the element's bounds */
    }
    show(e.clientX);
  });
  el.addEventListener("pointermove", (e) => {
    if (e.pressure > 0 || e.buttons || e.pointerType === "mouse") show(e.clientX);
  });
  el.addEventListener("pointerup", hide);
  el.addEventListener("pointercancel", hide);
  el.addEventListener("pointerleave", hide);
}

/* --- panels ------------------------------------------------------------- */

function renderBattery(latest) {
  const batt = latest.battery;
  if (!batt) {
    $("batt-pct").textContent = "—";
    $("batt-fill").style.width = "0";
    return;
  }
  const pct = Math.round(batt.value);
  $("batt-pct").textContent = `${pct}%`;
  $("batt-fill").style.width = `${Math.max(2, Math.min(100, pct))}%`;

  /* Charging is only ever sampled at sync time -- the ring is not polled -- so this
   * reading is as old as the last sync. Trust it only if it belongs to the same sync
   * that produced the percentage; a charging flag from yesterday next to a fresh
   * battery level would be the dashboard asserting something it does not know. */
  const flag = latest.battery_charging;
  const charging = Boolean(flag && flag.value === 1 && flag.ts_utc === batt.ts_utc);

  $("batt").classList.toggle("is-charging", charging);
  $("batt-fill").classList.toggle("charging", charging);
  // Shop orange below 30%: the gauge is non-linear near empty and the ring gives no
  // warning of its own, so the threshold sits early on purpose. Charging outranks it --
  // a low battery on the charger is being handled and does not need attention.
  $("batt-fill").classList.toggle("low", pct < 30 && !charging);
}

function renderStatus(health) {
  const el = $("status");
  const text = $("status-text");
  const runs = health.runs_today || { ok: 0, expected: 3 };

  if (!health.last_sample_utc) {
    el.className = "status num dead";
    text.textContent = "No readings stored yet · run a sync";
    return;
  }

  const hours = (Date.now() - new Date(health.last_sample_utc)) / 3600000;
  el.className = "status num" + (hours > 24 ? " dead" : hours > 10 ? " stale" : "");

  // A bare clock time reads as today. Once the last sync is far enough back that
  // "21:00" would be a lie, switch to elapsed time — the status line's whole job is
  // telling you whether to believe the numbers under it.
  const parts = [
    hours < 20
      ? `Synced ${clock(health.last_sample_utc)}`
      : `Synced ${ago(health.last_sample_utc)}`,
  ];
  parts.push(`${runs.ok}/${runs.expected} runs`);
  const offset = health.last_sync && health.last_sync.clock_offset_s;
  parts.push(
    offset === null || offset === undefined
      ? "clock offset unmeasured"
      : `clock ${offset >= 0 ? "+" : ""}${Number(offset).toFixed(1)} s`
  );
  text.textContent = parts.join(" · ");
}

function renderHeartRate(series, windowLabel) {
  const points = series.points;

  if (!points.length) {
    $("hr-value").textContent = "—";
    $("hr-aside").textContent = "";
    $("hr-foot-left").textContent = `no readings in the last ${windowLabel}`;
    $("hr-foot-right").textContent = "";
    sparkline($("hr-spark"), []);
    return;
  }

  const vals = points.map((p) => p.v);
  const lowest = Math.min(...vals);

  // The large number is the window minimum, not a modelled resting rate. Honest
  // naming: a real resting-HR figure needs sleep detection, which does not exist yet.
  $("hr-value").textContent = Math.round(lowest);
  $("hr-aside").textContent = `low over ${windowLabel}`;
  $("hr-foot-left").textContent = `${points.length} samples · ${duration(points)}`;
  $("hr-foot-right").textContent =
    `range ${Math.round(lowest)} – ${Math.round(Math.max(...vals))}`;

  sparkline($("hr-spark"), points);
}

/* --- boot --------------------------------------------------------------- */

let days = 1;
const windowLabel = () => (days === 1 ? "24 h" : `${days} d`);

async function refresh() {
  try {
    const [health, latest, series] = await Promise.all([
      getJSON("/api/health"),
      getJSON("/api/latest"),
      getJSON(`/api/series/heart_rate?days=${days}`),
    ]);

    renderStatus(health);
    renderBattery(latest);
    renderHeartRate(series, windowLabel());

    const ring = (health.rings || [])[0];
    if (ring) {
      $("ring-name").textContent = ring.name;
      $("ring-addr").textContent = ring.address;
    }
  } catch (err) {
    $("status").className = "status num dead";
    $("status-text").textContent = `Hub unreachable · ${err.message}`;
  }
}

/* --- manual sync --------------------------------------------------------
 *
 * The button does not sync. It asks the hub to ask systemd to run the same BLE unit the
 * timer runs, then watches for a new row in sync_runs. Nothing on this page ever
 * touches the store, which is the property the API is built around.
 *
 * A real sync takes ~25 s of radio time, so this is a poll rather than a wait: an iPhone
 * will happily suspend a pending fetch when the screen locks, and a request held open
 * across that comes back as a network error rather than a result. */

const POLL_MS = 2000;
const POLL_LIMIT = 90000 / POLL_MS; // 90 s -- comfortably past a slow sync, not forever

let syncing = false;

function setSyncState(state, label) {
  const btn = $("sync-btn");
  btn.classList.remove("busy", "ok", "err");
  if (state) btn.classList.add(state);
  btn.disabled = state === "busy";
  $("sync-label").textContent = label;
}

async function runSync() {
  if (syncing) return;
  syncing = true;
  setSyncState("busy", "Syncing");

  try {
    // The run id before we start is what makes "finished" detectable. A failed sync
    // still writes a row, so a changed id means "it ran", not "it worked" -- the two
    // are reported differently below.
    const before = await getJSON("/api/sync/status");
    const beforeId = before.last_run ? before.last_run.id : null;

    const res = await fetch("/api/sync", { method: "POST" });
    if (res.status === 429) {
      const body = await res.json().catch(() => ({}));
      setSyncState("err", "Too soon");
      $("status-text").textContent = body.detail || "Synced too recently";
      return;
    }
    if (!res.ok) throw new Error(`${res.status}`);

    const started = await res.json();
    if (!started.started && started.reason) {
      // Already running -- fall through to polling rather than treating it as an error.
      $("status-text").textContent = started.reason;
    }

    for (let i = 0; i < POLL_LIMIT; i++) {
      await new Promise((r) => setTimeout(r, POLL_MS));
      const now = await getJSON("/api/sync/status");
      const run = now.last_run;
      /* Three conditions, and the third is the load-bearing one. db.start_sync_run
       * inserts its row with status "running" the moment a sync begins, so a changed id
       * means "a run started", not "a run finished". systemd's view is a useful second
       * opinion but it can be unavailable; the row is always there. */
      const finished =
        run && run.id !== beforeId && !now.running && run.status !== "running";

      if (finished) {
        await refresh();
        if (run.status === "ok") {
          setSyncState("ok", run.rows_ingested ? `+${run.rows_ingested}` : "Up to date");
        } else {
          // no_device is the common one and is not a fault: the ring is on a hand that
          // leaves the house, and the sync service records that rather than failing.
          setSyncState("err", run.status === "no_device" ? "No ring" : "Failed");
        }
        setTimeout(() => setSyncState(null, "Sync"), 6000);
        return;
      }
    }

    setSyncState("err", "Timed out");
    setTimeout(() => setSyncState(null, "Sync"), 6000);
  } catch (err) {
    setSyncState("err", "Failed");
    $("status-text").textContent = `Sync failed · ${err.message}`;
    setTimeout(() => setSyncState(null, "Sync"), 6000);
  } finally {
    syncing = false;
  }
}

const sheet = $("sync-sheet");
const openSheet = () => { sheet.hidden = false; };
const closeSheet = () => { sheet.hidden = true; };

$("sync-btn").addEventListener("click", openSheet);
$("sync-cancel").addEventListener("click", closeSheet);
$("sync-cancel-bg").addEventListener("click", closeSheet);
$("sync-go").addEventListener("click", () => {
  closeSheet();
  runSync();
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && !sheet.hidden) closeSheet();
});

$("range").addEventListener("click", (e) => {
  const btn = e.target.closest("button");
  if (!btn) return;
  days = Number(btn.dataset.days);
  for (const b of $("range").querySelectorAll("button")) {
    b.setAttribute("aria-pressed", String(b === btn));
  }
  refresh();
});

refresh();
// The hub syncs three times a day, so polling harder buys nothing. Five minutes keeps
// a tab left open honest without pretending this is real-time.
setInterval(refresh, 5 * 60 * 1000);

/* Register the service worker, which is what makes this installable rather than a
 * bookmark. It requires a secure context: over Tailscale Serve's HTTPS this succeeds,
 * over plain http on the LAN the promise rejects and the dashboard carries on working
 * exactly as before. The failure is logged rather than swallowed — silence here would
 * make "is it actually installed?" unanswerable from the phone. */
if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker
      .register("/sw.js")
      .catch((err) => console.info("service worker not registered:", err.message));
  });
}
