/* Motion layer: orbiting satellite over a wireframe globe, drifting starfield,
   count-up posterior, typewriter claim, scroll progress. Respects reduced motion. */
(function () {
  "use strict";
  var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var DPR = Math.min(window.devicePixelRatio || 1, 2);

  /* ---------- starfield (whole page) ---------- */
  function starfield() {
    var c = document.createElement("canvas");
    c.className = "fx-stars";
    c.setAttribute("aria-hidden", "true");
    document.body.prepend(c);
    var ctx = c.getContext("2d"), w, h, stars = [], shoot = null;
    function size() {
      w = c.width = innerWidth * DPR; h = c.height = innerHeight * DPR;
      c.style.width = innerWidth + "px"; c.style.height = innerHeight + "px";
      var n = Math.round((innerWidth * innerHeight) / 5200);
      stars = [];
      for (var i = 0; i < n; i++) stars.push({ x: Math.random() * w, y: Math.random() * h, z: Math.random() * 0.8 + 0.2, t: Math.random() * 6.28 });
    }
    size(); addEventListener("resize", size);
    function frame(ts) {
      ctx.clearRect(0, 0, w, h);
      var sy = scrollY * DPR;
      for (var i = 0; i < stars.length; i++) {
        var s = stars[i];
        s.x -= s.z * 0.06 * DPR; if (s.x < 0) s.x += w;
        var y = (s.y - sy * s.z * 0.15) % h; if (y < 0) y += h;
        var a = 0.35 + 0.45 * Math.sin(ts / 900 * s.z + s.t);
        ctx.fillStyle = "rgba(200,225,255," + a.toFixed(3) + ")";
        ctx.fillRect(s.x, y, s.z * 1.6 * DPR, s.z * 1.6 * DPR);
      }
      // during a run the starfield is only a quiet backdrop: no shooting stars, dimmed
      var view = document.getElementById("view"), sim = !!(view && !view.hidden);
      c.style.opacity = sim ? "0.35" : "1";
      if (sim) shoot = null;
      if (!sim && !shoot && Math.random() < 0.004) shoot = { x: Math.random() * w, y: Math.random() * h * 0.5, l: 0 };
      if (shoot) {
        shoot.l += 14 * DPR;
        var g = ctx.createLinearGradient(shoot.x, shoot.y, shoot.x - 120 * DPR, shoot.y - 40 * DPR);
        g.addColorStop(0, "rgba(160,220,255,0.9)"); g.addColorStop(1, "rgba(160,220,255,0)");
        ctx.strokeStyle = g; ctx.lineWidth = 1.4 * DPR; ctx.beginPath();
        ctx.moveTo(shoot.x + shoot.l, shoot.y + shoot.l / 3);
        ctx.lineTo(shoot.x + shoot.l - 120 * DPR, shoot.y + shoot.l / 3 - 40 * DPR); ctx.stroke();
        if (shoot.l > w * 0.4) shoot = null;
      }
      requestAnimationFrame(frame);
    }
    requestAnimationFrame(frame);
  }

  /* ---------- hero orbit (globe + satellite + scan beam) ---------- */
  function orbit() {
    var hero = document.querySelector(".landing:not([hidden])");
    if (!hero) return;
    var c = document.createElement("canvas");
    c.className = "fx-orbit";
    c.setAttribute("aria-hidden", "true");
    hero.prepend(c);
    var ctx = c.getContext("2d"), w, h, R, cx, cy, visible = true;
    function size() {
      var r = hero.getBoundingClientRect();
      w = c.width = r.width * DPR; h = c.height = r.height * DPR;
      c.style.width = r.width + "px"; c.style.height = r.height + "px";
      var narrow = r.width < 760;
      R = Math.min(w, h) * (narrow ? 0.36 : 0.30);
      cx = narrow ? w * 0.5 : w * 0.80; cy = narrow ? h * 0.30 : h * 0.40;
    }
    size(); addEventListener("resize", size);
    new IntersectionObserver(function (e) { visible = e[0].isIntersecting; }).observe(hero);

    var tilt = 0.42, pings = [];
    // ---- continents as dots: Natural Earth 110m land (world-atlas), sampled on an equal-spacing grid ----
    var land = [];
    var TOKYO = [35.66 * Math.PI / 180, 139.75 * Math.PI / 180];
    // 31 capitals + Tokyo = 32 worlds. Each keeps a steady dot; a few at a time ping with a fading label.
    var CAPS = [
      ["WASHINGTON", 38.90, -77.04], ["OTTAWA", 45.42, -75.70], ["MEXICO CITY", 19.43, -99.13],
      ["BOGOTÁ", 4.71, -74.07], ["LIMA", -12.05, -77.04], ["BRASÍLIA", -15.79, -47.88],
      ["SANTIAGO", -33.45, -70.67], ["BUENOS AIRES", -34.60, -58.38], ["LONDON", 51.51, -0.13],
      ["PARIS", 48.86, 2.35], ["MADRID", 40.42, -3.70], ["BERLIN", 52.52, 13.40],
      ["ROME", 41.90, 12.50], ["STOCKHOLM", 59.33, 18.07], ["WARSAW", 52.23, 21.01],
      ["MOSCOW", 55.76, 37.62], ["ANKARA", 39.93, 32.86], ["CAIRO", 30.04, 31.24],
      ["ABUJA", 9.08, 7.40], ["NAIROBI", -1.29, 36.82], ["PRETORIA", -25.75, 28.19],
      ["RIYADH", 24.71, 46.68], ["NEW DELHI", 28.61, 77.21], ["BANGKOK", 13.76, 100.50],
      ["SINGAPORE", 1.35, 103.82], ["JAKARTA", -6.21, 106.85], ["BEIJING", 39.90, 116.41],
      ["MANILA", 14.60, 120.98], ["SEOUL", 37.57, 126.98], ["CANBERRA", -35.28, 149.13],
      ["WELLINGTON", -41.29, 174.78]
    ].map(function (c) { return { n: c[0], lat: c[1] * Math.PI / 180, lon: c[2] * Math.PI / 180, t0: -1e9 }; });
    var nextPing = 0, capIdx = 0;
    if (window.fetch) fetch("https://cdn.jsdelivr.net/npm/world-atlas@2.0.2/land-110m.json")
      .then(function (r) { return r.json(); })
      .then(function (topo) {
        if (!window.topojson) return;
        var geo = window.topojson.feature(topo, topo.objects.land), polys = [];
        (geo.features || [geo]).forEach(function (f) {
          var g = f.geometry || f;
          var cs = g.type === "Polygon" ? [g.coordinates] : g.type === "MultiPolygon" ? g.coordinates : [];
          cs.forEach(function (poly) {
            var b = [180, 90, -180, -90];
            poly[0].forEach(function (p) { b[0] = Math.min(b[0], p[0]); b[1] = Math.min(b[1], p[1]); b[2] = Math.max(b[2], p[0]); b[3] = Math.max(b[3], p[1]); });
            polys.push({ rings: poly, bb: b });
          });
        });
        function inRing(x, y, ring) {
          var inside = false;
          for (var i = 0, j = ring.length - 1; i < ring.length; j = i++) {
            var xi = ring[i][0], yi = ring[i][1], xj = ring[j][0], yj = ring[j][1];
            if (((yi > y) !== (yj > y)) && (x < (xj - xi) * (y - yi) / (yj - yi) + xi)) inside = !inside;
          }
          return inside;
        }
        function isLand(lon, lat) {
          for (var k = 0; k < polys.length; k++) {
            var P = polys[k], b = P.bb;
            if (lon < b[0] || lon > b[2] || lat < b[1] || lat > b[3]) continue;
            if (!inRing(lon, lat, P.rings[0])) continue;
            for (var hI = 1; hI < P.rings.length; hI++) if (inRing(lon, lat, P.rings[hI])) return false;
            return true;
          }
          return false;
        }
        var step = 2.3, out = [];
        for (var la = -82; la <= 84; la += step) {
          var dl = step / Math.max(Math.cos(la * Math.PI / 180), 0.25);
          for (var lo = -180; lo < 180; lo += dl) if (isLand(lo, la)) out.push([la * Math.PI / 180, lo * Math.PI / 180]);
        }
        land = out;
      })
      .catch(function () { /* offline: keep the plain wireframe */ });
    function proj(lat, lon, rot) {
      var x = Math.cos(lat) * Math.sin(lon + rot), y = Math.sin(lat), z = Math.cos(lat) * Math.cos(lon + rot);
      var y2 = y * Math.cos(tilt) - z * Math.sin(tilt), z2 = y * Math.sin(tilt) + z * Math.cos(tilt);
      return { x: cx + R * x, y: cy - R * y2, z: z2 };
    }
    function frame(ts) {
      requestAnimationFrame(frame);
      if (!visible) return;
      ctx.clearRect(0, 0, w, h);
      var rot = ts / 9000;
      // atmosphere
      var g = ctx.createRadialGradient(cx, cy, R * 0.6, cx, cy, R * 1.35);
      g.addColorStop(0, "rgba(79,209,255,0.10)"); g.addColorStop(1, "rgba(79,209,255,0)");
      ctx.fillStyle = g; ctx.beginPath(); ctx.arc(cx, cy, R * 1.35, 0, 6.283); ctx.fill();
      ctx.fillStyle = "rgba(8,16,32,0.85)"; ctx.beginPath(); ctx.arc(cx, cy, R, 0, 6.283); ctx.fill();
      // continents (dots, depth-shaded)
      for (var di = 0; di < land.length; di++) {
        var q2 = proj(land[di][0], land[di][1], rot);
        if (q2.z <= 0.03) continue;
        var rr = (0.75 + 1.05 * q2.z) * DPR;
        ctx.fillStyle = "rgba(110,231,183," + (0.18 + 0.72 * q2.z).toFixed(3) + ")";
        ctx.fillRect(q2.x - rr, q2.y - rr, rr * 2, rr * 2);
      }
      // capitals: steady dots; every 650 ms the next one on the visible side pings (stride 7 hops around the globe)
      if (land.length) {
        if (ts > nextPing) {
          for (var tries = 0; tries < CAPS.length; tries++) {
            capIdx = (capIdx + 7) % CAPS.length;
            var cand = CAPS[capIdx];
            if (proj(cand.lat, cand.lon, rot).z > 0.3) { cand.t0 = ts; break; }
          }
          nextPing = ts + 650;
        }
        ctx.font = "600 " + (9 * DPR) + "px 'JetBrains Mono', monospace";
        for (var ci = 0; ci < CAPS.length; ci++) {
          var C = CAPS[ci], cp = proj(C.lat, C.lon, rot);
          if (cp.z <= 0.05) continue;
          var dz = Math.min(1, cp.z * 2);
          ctx.fillStyle = "rgba(125,177,255," + (0.35 + 0.55 * dz).toFixed(3) + ")";
          ctx.beginPath(); ctx.arc(cp.x, cp.y, 1.8 * DPR, 0, 6.283); ctx.fill();
          var age = (ts - C.t0) / 1800;
          if (age >= 0 && age < 1) {
            ctx.strokeStyle = "rgba(79,209,255," + (0.85 * (1 - age) * dz).toFixed(3) + ")"; ctx.lineWidth = 1.3 * DPR;
            ctx.beginPath(); ctx.arc(cp.x, cp.y, (3 + 14 * age) * DPR, 0, 6.283); ctx.stroke();
            ctx.globalAlpha = Math.max(0, 1 - age * 1.2) * dz;
            ctx.fillStyle = "#c9d6e8"; ctx.fillText(C.n, cp.x + 7 * DPR, cp.y - 5 * DPR); ctx.globalAlpha = 1;
          }
        }
      }
      // Tokyo: where the demo's satellite pipeline should be looking
      var tk = proj(TOKYO[0], TOKYO[1], rot);
      if (land.length && tk.z > 0.05) {
        var ph = (ts / 1100) % 1;
        ctx.strokeStyle = "rgba(66,224,138," + (0.9 * (1 - ph)).toFixed(3) + ")"; ctx.lineWidth = 1.6 * DPR;
        ctx.beginPath(); ctx.arc(tk.x, tk.y, (4 + 16 * ph) * DPR, 0, 6.283); ctx.stroke();
        ctx.fillStyle = "#42e08a"; ctx.beginPath(); ctx.arc(tk.x, tk.y, 3.2 * DPR, 0, 6.283); ctx.fill();
        ctx.globalAlpha = Math.min(1, tk.z * 2.5);
        ctx.font = "700 " + (11 * DPR) + "px 'JetBrains Mono', monospace"; ctx.fillStyle = "#e8eef6";
        ctx.fillText("TOKYO", tk.x + 8 * DPR, tk.y - 7 * DPR); ctx.globalAlpha = 1;
      }
      // graticule (faint backdrop)
      ctx.lineWidth = 1 * DPR;
      for (var la = -60; la <= 60; la += 30) line(function (t) { return proj(la * Math.PI / 180, t, rot); }, 0, 6.283);
      for (var lo = 0; lo < 360; lo += 20) line(function (t) { return proj(t, lo * Math.PI / 180, rot); }, -1.57, 1.57);
      // satellite on inclined orbit
      var a = ts / 2600, inc = 0.9, oR = R * 1.32;
      var ox = Math.cos(a), oy = Math.sin(a) * Math.sin(inc), oz = Math.sin(a) * Math.cos(inc);
      var sx = cx + oR * ox, sy = cy - oR * oy * 0.55 - oR * oz * 0.25, front = oz > -0.2;
      // orbit path
      ctx.strokeStyle = "rgba(167,139,250,0.28)"; ctx.setLineDash([4 * DPR, 6 * DPR]); ctx.beginPath();
      for (var k = 0; k <= 64; k++) {
        var b = k / 64 * 6.283, px = cx + oR * Math.cos(b), py = cy - oR * Math.sin(b) * Math.sin(inc) * 0.55 - oR * Math.sin(b) * Math.cos(inc) * 0.25;
        k ? ctx.lineTo(px, py) : ctx.moveTo(px, py);
      }
      ctx.stroke(); ctx.setLineDash([]);
      if (front) {
        // scan beam to the surface point under the satellite
        var tx = cx + (sx - cx) * 0.72, ty = cy + (sy - cy) * 0.72;
        var bg = ctx.createLinearGradient(sx, sy, tx, ty);
        bg.addColorStop(0, "rgba(61,220,151,0.55)"); bg.addColorStop(1, "rgba(61,220,151,0.02)");
        ctx.fillStyle = bg; ctx.beginPath(); ctx.moveTo(sx, sy);
        var nx = -(ty - sy), ny = tx - sx, nl = Math.hypot(nx, ny) || 1, s = R * 0.16;
        ctx.lineTo(tx + nx / nl * s, ty + ny / nl * s); ctx.lineTo(tx - nx / nl * s, ty - ny / nl * s); ctx.closePath(); ctx.fill();
        if (Math.random() < 0.05) pings.push({ x: tx, y: ty, r: 0 });
      }
      // pings on the ground (observations)
      for (var p = pings.length - 1; p >= 0; p--) {
        var q = pings[p]; q.r += 0.9 * DPR;
        ctx.strokeStyle = "rgba(61,220,151," + Math.max(0, 0.7 - q.r / (40 * DPR)).toFixed(3) + ")";
        ctx.beginPath(); ctx.arc(q.x, q.y, q.r, 0, 6.283); ctx.stroke();
        if (q.r > 40 * DPR) pings.splice(p, 1);
      }
      // satellite body + panels
      ctx.save(); ctx.translate(sx, sy); ctx.rotate(a * 0.5);
      ctx.globalAlpha = front ? 1 : 0.35;
      ctx.fillStyle = "#4fd1ff"; ctx.fillRect(-14 * DPR, -3 * DPR, 9 * DPR, 6 * DPR); ctx.fillRect(5 * DPR, -3 * DPR, 9 * DPR, 6 * DPR);
      ctx.fillStyle = "#e6edf7"; ctx.fillRect(-4 * DPR, -4 * DPR, 8 * DPR, 8 * DPR);
      ctx.restore(); ctx.globalAlpha = 1;
    }
    function line(f, t0, t1) {
      var prev = null;
      for (var i = 0; i <= 48; i++) {
        var pt = f(t0 + (t1 - t0) * i / 48);
        if (prev && pt.z > 0 && prev.z > 0) {
          ctx.strokeStyle = "rgba(79,209,255," + (0.03 + 0.08 * pt.z).toFixed(3) + ")";
          ctx.beginPath(); ctx.moveTo(prev.x, prev.y); ctx.lineTo(pt.x, pt.y); ctx.stroke();
        }
        prev = pt;
      }
    }
    requestAnimationFrame(frame);
  }

  /* ---------- count-up posterior + typewriter claim ---------- */
  function liveText() {
    var post = document.getElementById("hc-posterior"), claim = document.getElementById("hc-claim");
    var moP, moC, pTimer = 0, cTimer = 0;
    // 自分の書き込みは takeRecords() で捨て、app.js からの更新だけに反応する
    function setP(v) { post.textContent = v; moP.takeRecords(); }
    function setC(v) { claim.textContent = v; moC.takeRecords(); }
    function countUp() {
      var target = parseFloat(post.textContent);
      if (isNaN(target)) return;
      cancelAnimationFrame(pTimer); var t0 = performance.now();
      (function step(t) {
        var k = Math.min(1, (t - t0) / 1100), e = 1 - Math.pow(1 - k, 3);
        setP((target * e).toFixed(3));
        if (k < 1) pTimer = requestAnimationFrame(step); else setP(target.toFixed(3));
      })(t0);
    }
    function type() {
      var full = claim.textContent;
      if (!full || full.indexOf("Loading") === 0) return;
      clearTimeout(cTimer); claim.classList.add("typing"); setC("");
      var i = 0;
      (function step() {
        setC(full.slice(0, ++i));
        if (i < full.length) cTimer = setTimeout(step, 28); else claim.classList.remove("typing");
      })();
    }
    if (post) { moP = new MutationObserver(countUp); moP.observe(post, { childList: true, characterData: true, subtree: true }); }
    if (claim) { moC = new MutationObserver(type); moC.observe(claim, { childList: true, characterData: true, subtree: true }); }
  }

  /* ---------- scroll progress ---------- */
  function progress() {
    var bar = document.createElement("div");
    bar.className = "fx-progress"; bar.setAttribute("aria-hidden", "true");
    document.body.appendChild(bar);
    function upd() { var m = document.documentElement.scrollHeight - innerHeight; bar.style.transform = "scaleX(" + (m > 0 ? scrollY / m : 0) + ")"; }
    addEventListener("scroll", upd, { passive: true }); upd();
  }

  function init() {
    if (reduce) return;
    starfield(); if (document.querySelector(".landing:not([hidden])")) orbit();
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init); else init();
})();
