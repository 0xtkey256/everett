// Pure reducer: event stream -> screen state. Same code for live (SSE) and replay.
export function initialState() {
  return {
    run: null, tests: [], hyps: {}, worlds: {}, order: [], base: null,
    counters: { created: 0, disposed: 0, merged: 0 }, forkMs: [], ts: 0, round: 1,
    collapse: null, stats: null, failed: null, lastSeq: 0,
  };
}

const ACTIVE = new Set(["forking", "patching", "testing"]);

export function reduce(s, e) {
  if (e.seq && e.seq <= s.lastSeq) return s; // idempotent on SSE resend
  s.lastSeq = e.seq || s.lastSeq;
  s.ts = Math.max(s.ts, e.ts || 0);
  const w = e.id ? s.worlds[e.id] : null;
  switch (e.type) {
    case "run.started": s.run = e; break;
    case "base.tests": s.tests = e.test_ids; break;
    case "base.ready": s.base = e; break;
    case "hypotheses.proposed": for (const h of e.items) s.hyps[h.id] = h; break;
    case "universe.forked":
      s.worlds[e.id] = { id: e.id, parent: e.parent_id, round: e.round, hyp: e.hypothesis_id, box: e.sandbox_id,
        status: "forking", results: "", passed: 0, failed: 0, total: s.tests.length, tail: [], reason: null,
        disposed: false, files: [], failing: [], firstError: "" };
      s.order.push(e.id); s.counters.created++; s.forkMs.push(e.fork_ms); break;
    case "patch.proposed": if (w) { w.status = "patching"; w.files = e.files; } break;
    case "patch.applied": if (w) w.status = "testing"; break;
    case "patch.rejected": if (w) { w.status = "stillborn"; w.reason = e.reason; } break;
    case "test.progress":
      if (w) { w.status = "testing"; w.results += e.results; w.passed = e.passed; w.failed = e.failed;
        w.total = e.total || w.total; w.tail = e.tail || w.tail; }
      break;
    case "universe.observed":
      if (w) { w.status = e.status; w.failing = e.failing; w.firstError = e.first_error;
        if (e.status === "stillborn" && !w.reason) w.reason = e.first_error; }
      break;
    case "round.started": s.round = e.round; break;
    case "universe.disposed": if (w && !w.disposed) { w.disposed = true; s.counters.disposed++; } break;
    case "collapse": s.collapse = e; if (e.winner_id) s.counters.merged = 1; break;
    case "run.finished": s.stats = e.stats; break;
    case "run.failed": s.failed = e; break;
  }
  return s;
}

export function liveSandboxes(s) {
  const boxes = new Set();
  for (const id of s.order) {
    const w = s.worlds[id];
    if (!w.disposed && ACTIVE.has(w.status)) boxes.add(w.box);
  }
  return boxes.size;
}

export function median(xs) {
  if (!xs.length) return null;
  const a = [...xs].sort((x, y) => x - y);
  return a[Math.floor(a.length / 2)];
}

export const REASON_TEXT = {
  touches_tests: "edited tests — disqualified",
  skip_injection: "skipped tests — disqualified",
  no_match: "patch did not apply",
  parse_error: "unreadable patch",
  empty: "empty patch",
  collect_shrank: "fewer tests collected — disqualified",
};
