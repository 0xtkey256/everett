import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { initialState, reduce, liveSandboxes } from "./reducer.js";

const demo = JSON.parse(readFileSync(new URL("../replays/demo.json", import.meta.url)));
const all = JSON.parse(readFileSync(new URL("../../fixtures/all_events.json", import.meta.url)));

test("demo replay ends merged with counters matching run.finished", () => {
  const s = initialState();
  for (const e of demo) reduce(s, e);
  const st = demo.at(-1).stats;
  assert.equal(s.counters.created, st.worlds_created);
  assert.equal(s.counters.disposed, st.worlds_disposed);
  assert.equal(s.counters.merged, 1);
  assert.equal(s.worlds[s.collapse.winner_id].status, "green");
  assert.equal(liveSandboxes(s), 0);
});

test("reducer is idempotent on resent events (SSE reconnect)", () => {
  const a = initialState(), b = initialState();
  for (const e of demo) reduce(a, e);
  for (const e of [...demo.slice(0, 200), ...demo]) reduce(b, e);
  assert.deepEqual(a.counters, b.counters);
});

test("every event type in the contract fixture is handled", () => {
  const s = initialState();
  for (const e of all) reduce(s, e);
  assert.ok(s.failed && s.collapse && s.stats);
});
