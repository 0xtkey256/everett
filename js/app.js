import { initialState, reduce, liveSandboxes, median, REASON_TEXT } from "./reducer.js";
import { Replay, connectLive } from "./replay.js";

const $ = (id) => document.getElementById(id);
const params = new URLSearchParams(location.search);
let S = initialState();
let dirty = true;
const tiles = new Map();      // world id -> {el, parts}
let collapseShown = false;

/* ---------------- boot ---------------- */
const replayId = params.get("replay");
const src = params.get("src");
if (!replayId && !src) {
  $("landing").hidden = false;
  $("live-form").addEventListener("submit", (e) => {
    e.preventDefault();
    location.search = "?src=" + encodeURIComponent($("live-src").value.trim());
  });
} else {
  $("view").hidden = false;
  drawQR();
  requestAnimationFrame(loop);
  if (src) startLive(src); else startReplay(replayId);
}

function apply(e) { reduce(S, e); dirty = true; }
function reset() {
  S = initialState(); tiles.clear(); $("wall").innerHTML = ""; $("collapse").hidden = true; collapseShown = false; dirty = true;
}

async function startReplay(id) {
  const res = await fetch(`replays/${encodeURIComponent(id)}.json`);
  if (!res.ok) { $("phase").textContent = `replay "${id}" not found`; return; }
  const events = await res.json();
  const r = new Replay(events, apply, reset);
  r.setSpeed(2);
  const seek = $("c-seek");
  seek.max = r.end;
  $("c-status").textContent = "replay";
  $("c-play").onclick = () => { r.playing ? r.pause() : r.play(); $("c-play").textContent = r.playing ? "Pause" : "Play"; };
  $("c-restart").onclick = () => { r.seek(0); r.play(); $("c-play").textContent = "Pause"; };
  document.querySelectorAll("[data-speed]").forEach((b) => b.onclick = () => {
    r.setSpeed(+b.dataset.speed);
    document.querySelectorAll("[data-speed]").forEach((x) => x.classList.toggle("on", x === b));
  });
  seek.oninput = () => { r.seek(+seek.value); };
  setInterval(() => { if (document.activeElement !== seek) seek.value = r.t; }, 200);
  r.play();
}

function startLive(url) {
  $("c-play").hidden = true; document.querySelector(".speeds").hidden = true; $("c-seek").hidden = true; $("c-restart").hidden = true;
  connectLive(url, apply, (st) => { $("c-status").textContent = st; });
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
  for (const id of s.order) renderTile(s.worlds[id]);
  if (s.collapse) markCollapse(s);
  renderGraph(s);
}

function phaseText(s) {
  if (s.failed) return `<b>run failed</b> at ${esc(s.failed.stage)}: ${esc(s.failed.message)}`;
  if (s.stats) return `<b>done.</b> ${s.counters.created} worlds tried · ${s.counters.disposed} thrown away · ${s.counters.merged} merged`;
  if (s.collapse) return s.collapse.winner_id ? `<b>proven:</b> ${esc(s.collapse.winner_id)} — throwing away every other world` : "<b>no world passed</b>";
  if (s.round > 1) return `<b>round ${s.round}:</b> branching again from the closest worlds`;
  if (s.order.length) return `<b>round 1:</b> ${s.order.length} worlds, each trying a different fix`;
  if (Object.keys(s.hyps).length) return `<b>Nosana</b> proposed ${Object.keys(s.hyps).length} hypotheses — writing patches`;
  if (s.base) return `<b>CI is red:</b> ${s.base.failing_tests.length} failing of ${s.base.tests_total} · ${esc(s.base.error_summary)}`;
  if (s.run) return "building the base world…";
  return "waiting for the broken build…";
}

/* ---------------- tiles ---------------- */
function renderTile(w) {
  let t = tiles.get(w.id);
  if (!t) {
    const el = document.createElement("div");
    el.className = "tile new";
    setTimeout(() => el.classList.remove("new"), 500);
    el.innerHTML = `<div class="t-top"><span class="t-id"></span><span class="t-hyp"></span></div>
      <div class="t-term"></div><canvas class="t-bar" width="240" height="8"></canvas><span class="t-box"></span>`;
    $("wall").appendChild(el);
    t = { el, id: el.querySelector(".t-id"), hyp: el.querySelector(".t-hyp"), term: el.querySelector(".t-term"),
      bar: el.querySelector(".t-bar"), box: el.querySelector(".t-box"), drawn: -1, status: null };
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
  if (w.status === "stillborn") term = REASON_TEXT[w.reason] || w.reason || "rejected";
  else if (w.status === "forking") term = "$ starting world…";
  else if (w.status === "patching") term = `$ git apply ${w.files[0] || ""}`;
  else if (w.status === "red" && w.firstError) term = [w.tail[w.tail.length - 1] || "", w.firstError].join("\n");
  else term = (w.tail.length ? w.tail : ["$ pytest -q"]).join("\n");
  if (t.term.textContent !== term) t.term.textContent = term;
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

/* ---------------- helpers ---------------- */
function setNum(id, v) { const el = $(id); if (el.textContent !== String(v)) el.textContent = v; }
function fmtK(n) { return n >= 1000 ? (n / 1000).toFixed(1) + "k" : String(n); }
function esc(x) { return String(x ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c])); }
function drawQR() {
  try { new QRCode($("qr"), { text: location.href, width: 184, height: 184, correctLevel: QRCode.CorrectLevel.M }); }
  catch { $("qr-badge").hidden = true; }
}
