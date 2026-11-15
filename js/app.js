import { initialState, reduce, liveSandboxes, median, REASON_TEXT } from "./reducer.js?v=153223";
import { t as tr, applyStatic, onToggle } from "./i18n.js?v=153223";
import { Replay, connectLive } from "./replay.js?v=153223";

const $ = (id) => document.getElementById(id);
const params = new URLSearchParams(location.search);
let S = initialState();
let dirty = true;
const tiles = new Map();      // world id -> {el, parts}
let collapseShown = false;

/* ---------------- boot ---------------- */
const replayId = params.get("replay");
const src = params.get("src");
const api = (params.get("api") || "").replace(/\/$/, "");
const admin = new URLSearchParams(location.hash.slice(1)).get("admin");   // fragment: never sent anywhere
applyStatic();
onToggle(() => { dirty = true; probeShown = false; tiles.forEach((x) => { x.status = null; }); });
// the landing page has its own toggle button; mirror clicks onto the main one
document.getElementById("lang-btn-land")?.addEventListener("click", () => document.getElementById("lang-btn").click());
if (!replayId && !src && !api) {
  $("landing").hidden = false;
  $("live-form").addEventListener("submit", (e) => {
    e.preventDefault();
    location.search = "?src=" + encodeURIComponent($("live-src").value.trim());
  });
} else {
  $("view").hidden = false;
  drawQR();
  requestAnimationFrame(loop);
  if (api) followLatest(api); else if (src) startLive(src); else startReplay(replayId);
}

function apply(e) { reduce(S, e); dirty = true; }
function reset() {
  probeShown = false; $("probe").hidden = true;
  S = initialState(); tiles.clear(); $("wall").innerHTML = ""; $("collapse").hidden = true; collapseShown = false; dirty = true;
}

async function startReplay(id) {
  const res = await fetch(`replays/${encodeURIComponent(id)}.json`);
  if (!res.ok) { $("phase").textContent = `replay "${id}" not found`; return; }
  const events = await res.json();
  const r = new Replay(events, apply, reset);
  r.setSpeed(1);
  const seek = $("c-seek");
  seek.max = r.end;
  $("c-status").textContent = "replay";
  $("c-play").textContent = tr("pause");
  $("c-play").onclick = () => { r.playing ? r.pause() : r.play(); $("c-play").textContent = tr(r.playing ? "pause" : "play"); };
  $("c-restart").onclick = () => { r.seek(0); r.play(); $("c-play").textContent = tr("pause"); };
  document.querySelectorAll("[data-speed]").forEach((b) => b.onclick = () => {
    r.setSpeed(+b.dataset.speed);
    document.querySelectorAll("[data-speed]").forEach((x) => x.classList.toggle("on", x === b));
  });
  seek.oninput = () => { r.seek(+seek.value); };
  setInterval(() => { if (document.activeElement !== seek) seek.value = r.t; }, 200);
  r.play();
}

function liveControls() {
  $("c-play").hidden = true; document.querySelector(".speeds").hidden = true; $("c-seek").hidden = true; $("c-restart").hidden = true;
}

function startLive(url) {
  liveControls();
  connectLive(url, apply, (st) => { $("c-status").textContent = st; });
}

// Follow whatever run is live on the tower; switch automatically when a new one starts.
function followLatest(base) {
  liveControls();
  let current = null, es = null;
  if (admin) {
    const b = document.createElement("button");
    b.className = "btn primary sm"; b.type = "button"; b.textContent = tr("fix_it");
    b.onclick = async () => {
      b.disabled = true; b.textContent = "starting…";
      try {
        const r = await fetch(`${base}/runs`, { method: "POST", headers: { "Content-Type": "application/json", "X-Everett-Admin": admin }, body: "{}" });
        b.textContent = r.ok ? "running…" : `error ${r.status}`;
      } catch (e) { b.textContent = "network error"; }
      setTimeout(() => { b.disabled = false; b.textContent = tr("fix_it"); }, 8000);
    };
    $("controls").prepend(b);
  }
  // Poll for new events instead of SSE: quick tunnels buffer text/event-stream, plain JSON always flows.
  let lastSeq = 0, busy = false, finished = false;
  const poll = async () => {
    if (busy) return;
    busy = true;
    try {
      const r = await fetch(`${base}/runs/latest`, { cache: "no-store" });
      const j = await r.json();
      if (j.run_id && j.run_id !== current) { current = j.run_id; lastSeq = 0; finished = false; reset(); }
      if (!j.run_id) { $("c-status").textContent = tr("waiting_run"); return; }
      if (!finished) {
        const evs = await (await fetch(`${base}/runs/${current}/log.json?after=${lastSeq}`, { cache: "no-store" })).json();
        for (const e of evs) { apply(e); lastSeq = Math.max(lastSeq, e.seq); if (e.type === "run.finished" || e.type === "run.failed") finished = true; }
      }
      $("c-status").textContent = `${finished ? "finished" : "live"} · ${current}`;
    } catch (e) { $("c-status").textContent = "tower unreachable"; }
    finally { busy = false; }
  };
  poll(); setInterval(poll, 1000);
}

/* ---------------- render loop ---------------- */
function loop() {
  if (dirty) { dirty = false; render(); }
  requestAnimationFrame(loop);
}

function render() {
  const s = S;
  if (s.run) $("m-bug").textContent = `${s.run.repo} · ${s.run.bug_id}`;
  setNum("m-created", s.counters.created);
  setNum("m-disposed", s.counters.disposed);
  setNum("m-merged", s.counters.merged);
  setNum("m-boxes", liveSandboxes(s) + (s.base && !s.collapse ? 1 : 0));
  const m = s.stats?.fork_ms_p50 || median(s.forkMs.filter((x) => x > 0));
  $("m-fork").textContent = !m ? "—" : (m / 1000).toFixed(1) + "s";
  $("m-time").textContent = (s.stats ? s.stats.wall_ms / 1000 : s.ts).toFixed(1) + "s";
  $("m-tokens").textContent = s.stats ? fmtK(s.stats.tokens_prompt + s.stats.tokens_completion) : "—";
  $("phase").innerHTML = phaseText(s);
  renderProbe(s);
  $("probe").classList.toggle("solo", s.order.length === 0);
  for (const id of s.order) renderTile(s.worlds[id]);
  if (s.collapse) markCollapse(s);
  renderGraph(s);
}

function phaseText(s) {
  if (s.failed) return tr("ph_failed", { stage: esc(s.failed.stage), msg: esc(s.failed.message) });
  if (s.stats) return tr("ph_done", { c: s.counters.created, d: s.counters.disposed, m: s.counters.merged });
  if (s.collapse) return s.collapse.winner_id ? tr("ph_proven", { id: esc(s.collapse.winner_id) }) : tr("ph_none");
  if (s.round > 1) return tr("ph_r2", { r: s.round });
  if (s.order.length) return tr("ph_r1", { n: s.order.length });
  if (Object.keys(s.hyps).length) return tr("ph_hyp", { n: Object.keys(s.hyps).length });
  if (s.base) return tr("ph_red", { n: s.base.failing_tests.length, total: s.base.tests_total, err: esc(s.base.error_summary) });
  if (s.run) return tr("ph_base");
  return tr("ph_wait");
}

/* ---------------- tiles ---------------- */
function renderTile(w) {
  let t = tiles.get(w.id);
  if (!t) {
    const el = document.createElement("div");
    el.className = "tile new";
    setTimeout(() => el.classList.remove("new"), 500);
    el.innerHTML = `<img class="t-sat" alt=""><div class="t-top"><span class="t-id"></span><span class="t-hyp"></span></div>
      <div class="t-term"></div><canvas class="t-bar" width="240" height="8"></canvas><span class="t-box"></span>`;
    $("wall").appendChild(el);
    t = { el, id: el.querySelector(".t-id"), hyp: el.querySelector(".t-hyp"), term: el.querySelector(".t-term"),
      bar: el.querySelector(".t-bar"), box: el.querySelector(".t-box"), sat: el.querySelector(".t-sat"), drawn: -1, status: null, tileKey: null };
    tiles.set(w.id, t);
    t.hyp.textContent = S.hyps[w.hyp]?.label || w.hyp;
    t.box.textContent = w.box;
    if (w.round > 1) el.classList.add("r2");
  }
  if (t.status !== w.status) {
    t.el.classList.remove("forking", "patching", "testing", "green", "red", "stillborn", "new");
    t.el.classList.add(w.status);
    t.status = w.status;
    const mark = w.status === "green" ? "✓" : w.status === "red" ? "✗" : w.status === "stillborn" ? "⊘" : "";
    t.id.innerHTML = `${esc(w.id)}${mark ? `<span class="mark">${mark}</span>` : ""}`;
  }
  let term;
  if (w.status === "stillborn") term = REASON_TEXT[w.reason] ? tr(w.reason) : (w.reason || "rejected");
  else if (w.status === "forking") term = tr("starting");
  else if (w.status === "patching") term = `$ git apply ${w.files[0] || ""}`;
  else if (w.status === "red" && w.firstError) term = [w.tail[w.tail.length - 1] || "", w.firstError].join("\n");
  else term = (w.tail.length ? w.tail : ["$ pytest -q"]).join("\n");
  if (t.term.textContent !== term) t.term.textContent = term;
  if (w.tile && t.tileKey !== w.tile.join("/")) {
    t.tileKey = w.tile.join("/");
    t.el.style.setProperty("--sat", `url("${satUrl(w.tile)}")`);
    t.el.classList.add("has-sat");
    const lat = document.createElement("span");
    lat.className = "t-lat"; lat.textContent = fmtLat(w.tile);
    t.term.before(lat);
  }
  if (t.drawn !== w.results.length) { drawBar(t.bar, w.results, S.tests.length || w.total || 60); t.drawn = w.results.length; }
  t.el.classList.toggle("lost", !!(S.collapse && w.id !== S.collapse.winner_id && (w.disposed || S.collapse)));
}

function drawBar(cv, results, total) {
  const ctx = cv.getContext("2d");
  const W = cv.width, H = cv.height, cw = W / total;
  ctx.fillStyle = "#222b38"; ctx.fillRect(0, 0, W, H);
  for (let i = 0; i < results.length && i < total; i++) {
    const c = results[i];
    ctx.fillStyle = c === "." ? "#42e08a" : c === "s" || c === "x" ? "#7f8ea3" : "#d9434b";
    ctx.fillRect(Math.floor(i * cw), 0, Math.max(1, Math.ceil(cw) - (cw > 3 ? 1 : 0)), H);
  }
}

/* ---------------- collapse ---------------- */
function markCollapse(s) {
  if (collapseShown) return;
  collapseShown = true;
  const c = s.collapse;
  let k = 0;
  for (const id of s.order) {
    const t = tiles.get(id);
    if (!t) continue;
    if (id === c.winner_id) t.el.classList.add("winner");
    else { t.el.style.transitionDelay = `${(k++) * 20}ms`; }
  }
  if (!c.winner_id) return;
  setTimeout(() => {
    const w = s.worlds[c.winner_id];
    $("col-id").textContent = `${c.winner_id} · round ${w?.round ?? ""} · ${w?.box ?? ""}`;
    $("col-hyp").textContent = S.hyps[c.hypothesis_id]?.label || c.hypothesis_id || "";
    const total = S.tests.length || w?.total || 0;
    $("col-tests").textContent = `${total - (w?.failed ?? 0)}/${total}`;
    $("col-worlds").textContent = s.counters.created;
    $("col-time").textContent = s.ts.toFixed(0) + "s";
    const wt = w?.tile;
    $("col-sat").parentElement.classList.toggle("none", !wt);
    if (wt) { $("col-sat").src = satUrl(wt); $("col-sat-cap").textContent = `${S.base?.probe?.label || "target"} · ${fmtLat(wt)}`; }
    $("col-diff").innerHTML = c.diff.split("\n").map((l) => {
      const cls = l.startsWith("+++") || l.startsWith("---") ? "meta" : l.startsWith("@@") ? "hunk"
        : l.startsWith("+") ? "add" : l.startsWith("-") ? "del" : "";
      return cls ? `<span class="${cls}">${esc(l)}</span>` : esc(l) + "\n";
    }).join("");
    $("collapse").hidden = false;
  }, 900);
  $("col-close").onclick = () => { $("collapse").hidden = true; };
}

/* ---------------- branch graph ---------------- */
function renderGraph(s) {
  const svg = $("graph");
  const W = svg.clientWidth || 160, H = svg.clientHeight || 600;
  const r1 = s.order.filter((id) => s.worlds[id].round === 1);
  const n = Math.max(r1.length, 1);
  const y = (i) => 20 + (H - 60) * (i + 0.5) / n;
  const pos = {};
  r1.forEach((id, i) => { pos[id] = { x: W * 0.42, y: y(i) }; });
  const parts = [`<line class="main" x1="10" y1="0" x2="10" y2="${H}"/>`];
  const yBase = 14;
  for (const id of r1) {
    const p = pos[id], w = s.worlds[id];
    parts.push(`<path class="br" d="M10 ${yBase} C ${W * 0.2} ${yBase}, ${W * 0.2} ${p.y}, ${p.x} ${p.y}"/>`);
  }
  // round 2: children fan out from their parent
  const kids = s.order.filter((id) => s.worlds[id].round > 1);
  const byParent = {};
  for (const id of kids) (byParent[s.worlds[id].parent] ||= []).push(id);
  for (const [par, ids] of Object.entries(byParent)) {
    const p = pos[par]; if (!p) continue;
    ids.forEach((id, j) => {
      const q = { x: W * 0.8, y: p.y + (j - (ids.length - 1) / 2) * 7 };
      pos[id] = q;
      const g = s.worlds[id].status === "green" ? " green" : "";
      parts.push(`<path class="br${g}" d="M${p.x} ${p.y} C ${W * 0.6} ${p.y}, ${W * 0.6} ${q.y}, ${q.x} ${q.y}"/>`);
    });
  }
  if (s.collapse?.winner_id && pos[s.collapse.winner_id]) {
    const q = pos[s.collapse.winner_id];
    parts.push(`<path class="merge" d="M${q.x} ${q.y} C ${W} ${q.y}, ${W} ${H - 20}, ${W * 0.5} ${H - 20} S 10 ${H - 20}, 10 ${H - 4}"/>`);
  }
  for (const id of s.order) {
    const p = pos[id]; if (!p) continue;
    const w = s.worlds[id];
    const gone = s.collapse && id !== s.collapse.winner_id ? " gone" : "";
    const r = w.status === "green" ? 5 : 3;
    parts.push(`<circle class="dot ${w.status}${gone}" cx="${p.x}" cy="${p.y}" r="${r}"/>`);
  }
  parts.push(`<circle cx="10" cy="${yBase}" r="5" fill="${s.collapse?.winner_id ? "#42e08a" : "#d9434b"}"/>`);
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  svg.innerHTML = parts.join("");
}

/* ---------------- satellite probe ---------------- */
function satUrl([x, y, z]) { return `https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/${z}/${y}/${x}`; }
function tileLat([x, y, z]) { const n = Math.PI - 2 * Math.PI * (y + 0.5) / Math.pow(2, z); return 180 / Math.PI * Math.atan(Math.sinh(n)); }
function fmtLat(t) { const la = tileLat(t); return `${Math.abs(la).toFixed(2)}°${la >= 0 ? "N" : "S"}`; }
let probeShown = false;
function renderProbe(s) {
  const p = s.base?.probe;
  if (!p || !p.tile || !p.truth || probeShown) return;
  probeShown = true;
  $("probe").hidden = false;
  $("pr-bad").src = satUrl(p.tile); $("pr-good").src = satUrl(p.truth);
  $("pr-bad-lat").textContent = fmtLat(p.tile); $("pr-good-lat").textContent = fmtLat(p.truth);
  $("pr-arrow").innerHTML = tr("pr_arrow", { label: esc(p.label || "target") });
  $("pr-bad-lat").textContent = fmtLat(p.tile) + (Math.abs(tileLat(p.tile)) > 66 ? " · " + tr("polar") : "");
}

/* ---------------- helpers ---------------- */
function setNum(id, v) { const el = $(id); if (el.textContent !== String(v)) el.textContent = v; }
function fmtK(n) { return n >= 1000 ? (n / 1000).toFixed(1) + "k" : String(n); }
function esc(x) { return String(x ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c])); }
function drawQR() {
  const url = location.origin + location.pathname + location.search;   // never include #admin
  try { new QRCode($("qr"), { text: url, width: 184, height: 184, correctLevel: QRCode.CorrectLevel.M }); }
  catch { $("qr-badge").hidden = true; }
}
