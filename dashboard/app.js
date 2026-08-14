/* RavenX dashboard.
 *
 * Deliberately dependency-free. PLAN.md named Chart.js, but that means either a CDN
 * (which breaks offline and puts a third party in the path of a project whose whole
 * premise is not having one) or vendoring a bundle. Two line charts and a bar chart
 * are ~80 lines of SVG, so neither is worth it.
 *
 * All timestamps arrive as UTC ISO-8601 and are converted to local time here. This is
 * the display layer and the only place that conversion is allowed to happen.
 */

const $ = (sel) => document.querySelector(sel);
const pad = (n) => String(n).padStart(2, "0");

async function getJSON(url) {
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) throw new Error(`${res.status} ${url}`);
  return res.json();
}

function localTime(iso) {
  const d = new Date(iso);
  return `${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

/* A 24 h window starts and ends at nearly the same clock time, so bare HH:MM makes
 * both ends look identical. Show the date instead once the span passes a day. */
function axisLabel(iso, spanMs) {
  const d = new Date(iso);
  if (spanMs > 36 * 3600 * 1000) {
    return `${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
  }
  return localTime(iso);
}

function ago(iso) {
  const mins = Math.round((Date.now() - new Date(iso)) / 60000);
  if (mins < 60) return `${mins} min ago`;
  const hours = Math.round(mins / 60);
  if (hours < 48) return `${hours} h ago`;
  return `${Math.round(hours / 24)} d ago`;
}

/* --- charts ------------------------------------------------------------- */

const W = 640;
const H = 200;
const PADL = 34;
const PADB = 20;
const PADT = 10;

function svg(children, h = H) {
  return `<svg viewBox="0 0 ${W} ${h}" preserveAspectRatio="none"
    xmlns="http://www.w3.org/2000/svg">${children}</svg>`;
}

function empty(el, msg) {
  el.innerHTML = `<div class="empty">${msg}</div>`;
}

function lineChart(el, points) {
  if (!points.length) return empty(el, "no readings yet");

  const xs = points.map((p) => new Date(p.t).getTime());
  const ys = points.map((p) => p.v);
  const x0 = Math.min(...xs);
  const x1 = Math.max(...xs);
  // Pad the value axis so a flat series doesn't collapse to a zero-height line.
  const lo = Math.floor(Math.min(...ys) - 5);
  const hi = Math.ceil(Math.max(...ys) + 5);

  const px = (t) => PADL + ((t - x0) / (x1 - x0 || 1)) * (W - PADL - 8);
  const py = (v) => PADT + (1 - (v - lo) / (hi - lo || 1)) * (H - PADT - PADB);

  const path = points
    .map((p, i) => `${i ? "L" : "M"}${px(xs[i]).toFixed(1)},${py(p.v).toFixed(1)}`)
    .join("");

  const grid = [lo, Math.round((lo + hi) / 2), hi]
    .map(
      (v) =>
        `<line x1="${PADL}" x2="${W - 8}" y1="${py(v)}" y2="${py(v)}"
           stroke="#21262d" stroke-width="1"/>
         <text x="4" y="${py(v) + 4}" fill="#8b949e" font-size="11">${v}</text>`
    )
    .join("");

  // Dots help when you can count the readings and become noise when you can't.
  const dots =
    points.length > 60
      ? ""
      : points
          .map(
            (p, i) => `<circle cx="${px(xs[i])}" cy="${py(p.v)}" r="2.5" fill="#f7776d"/>`
          )
          .join("");

  const span = x1 - x0;
  const anchors = ["start", "middle", "end"];
  const ticks = [0, Math.floor((points.length - 1) / 2), points.length - 1]
    .filter((v, i, a) => a.indexOf(v) === i)
    .map(
      (i, n) =>
        `<text x="${px(xs[i])}" y="${H - 5}" fill="#8b949e" font-size="11"
           text-anchor="${anchors[n] || "end"}">${axisLabel(points[i].t, span)}</text>`
    )
    .join("");

  el.innerHTML = svg(`
    ${grid}
    <path d="${path}" fill="none" stroke="#f7776d" stroke-width="2"
      stroke-linejoin="round" stroke-linecap="round"/>
    ${dots}${ticks}`);
}

function dayChart(el, days) {
  if (!days.length) return empty(el, "no days recorded yet");

  const lo = Math.floor(Math.min(...days.map((d) => d.lo)) - 5);
  const hi = Math.ceil(Math.max(...days.map((d) => d.hi)) + 5);
  const py = (v) => PADT + (1 - (v - lo) / (hi - lo || 1)) * (H - PADT - PADB);

  const slot = (W - PADL - 8) / days.length;
  const barW = Math.min(26, slot * 0.5);

  const bars = days
    .map((d, i) => {
      const cx = PADL + slot * (i + 0.5);
      const top = py(d.hi);
      const bottom = py(d.lo);
      return `
        <rect x="${cx - barW / 2}" y="${top}" width="${barW}"
          height="${Math.max(2, bottom - top)}" rx="4" fill="#30363d"/>
        <line x1="${cx - barW / 2}" x2="${cx + barW / 2}"
          y1="${py(d.avg)}" y2="${py(d.avg)}" stroke="#f7776d" stroke-width="2.5"/>
        <text x="${cx}" y="${H - 5}" fill="#8b949e" font-size="10"
          text-anchor="middle">${d.day.slice(5)}</text>`;
    })
    .join("");

  const grid = [lo, hi]
    .map(
      (v) =>
        `<line x1="${PADL}" x2="${W - 8}" y1="${py(v)}" y2="${py(v)}"
           stroke="#21262d"/>
         <text x="4" y="${py(v) + 4}" fill="#8b949e" font-size="11">${v}</text>`
    )
    .join("");

  el.innerHTML = svg(`${grid}${bars}`);
}

/* --- tiles -------------------------------------------------------------- */

function tile(label, value, unit, sub) {
  return `<div class="tile">
    <div class="label">${label}</div>
    <div class="value">${value}<span class="unit">${unit || ""}</span></div>
    <div class="sub">${sub || ""}</div>
  </div>`;
}

function renderTiles(latest, series, health, windowLabel) {
  const hr = latest.heart_rate;
  const batt = latest.battery;
  const vals = series.points.map((p) => p.v);

  // "Resting" here is the minimum over the window, not a modelled resting HR. Honest
  // naming matters: a real resting-HR figure needs sleep detection, which does not
  // exist yet.
  const lowest = vals.length ? Math.min(...vals) : null;
  const mean = vals.length
    ? Math.round(vals.reduce((a, b) => a + b, 0) / vals.length)
    : null;

  $("#tiles").innerHTML = [
    tile(
      "Latest HR",
      hr ? Math.round(hr.value) : "—",
      hr ? "bpm" : "",
      hr ? ago(hr.ts_utc) : "no data"
    ),
    tile(`Lowest ${windowLabel}`, lowest ?? "—", lowest ? "bpm" : "", "window minimum"),
    tile(`Mean ${windowLabel}`, mean ?? "—", mean ? "bpm" : "", `${vals.length} readings`),
    tile(
      "Ring battery",
      batt ? Math.round(batt.value) : "—",
      batt ? "%" : "",
      batt ? ago(batt.ts_utc) : "never recorded"
    ),
    tile("Stored", health.samples, "", "samples total"),
  ].join("");
}

function renderSyncs(runs) {
  if (!runs.length) return empty($("#syncs"), "no sync runs recorded");
  $("#syncs").innerHTML = runs
    .slice(0, 6)
    .map(
      (r) => `<div class="sync-row ${r.status === "ok" ? "" : "fail"}">
        <span><span class="dot">&#9679;</span> ${r.status}</span>
        <span>${r.rows_ingested} rows</span>
        <span>${ago(r.started_utc)}</span>
      </div>`
    )
    .join("");
}

function renderFreshness(health) {
  const el = $("#freshness");
  if (!health.last_sample_utc) {
    el.textContent = "no data yet";
    el.className = "freshness dead";
    return;
  }
  const hours = (Date.now() - new Date(health.last_sample_utc)) / 3600000;
  el.textContent = `updated ${ago(health.last_sample_utc)}`;
  el.className = "freshness" + (hours > 24 ? " dead" : hours > 8 ? " stale" : "");
}

/* --- boot --------------------------------------------------------------- */

let days = 1;

const windowLabel = () => (days === 1 ? "24 h" : `${days} d`);

async function refresh() {
  try {
    const [health, latest, series, byDay, syncs] = await Promise.all([
      getJSON("/api/health"),
      getJSON("/api/latest"),
      getJSON(`/api/series/heart_rate?days=${days}`),
      getJSON("/api/days/heart_rate"),
      getJSON("/api/sync-runs?limit=6"),
    ]);

    renderFreshness(health);
    renderTiles(latest, series, health, windowLabel());
    lineChart($("#hr-chart"), series.points);
    dayChart($("#day-chart"), byDay.days);
    renderSyncs(syncs.runs);
    $("#footnote").textContent =
      `${health.rings.join(", ")} · all times local · data never leaves this network`;
  } catch (err) {
    $("#freshness").textContent = "hub unreachable";
    $("#freshness").className = "freshness dead";
    $("#footnote").textContent = String(err);
  }
}

$("#range").addEventListener("click", (e) => {
  const btn = e.target.closest("button");
  if (!btn) return;
  days = Number(btn.dataset.days);
  document.querySelectorAll("#range button").forEach((b) => b.classList.remove("on"));
  btn.classList.add("on");
  refresh();
});

refresh();
// The hub syncs three times a day, so polling hard buys nothing. Five minutes keeps a
// left-open tab honest without pretending this is real-time.
setInterval(refresh, 5 * 60 * 1000);
