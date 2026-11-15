"""A realistic fake run, built from the real event types, so the UI can be finished before the backend.

  python -m everett.fake --seed 7 --out web/replays/demo.json
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

from .events import (EVENT_LIST, BaseReady, BaseTests, Collapse, EventBus, Hypothesis, HypothesesProposed,
                     PatchApplied, PatchProposed, PatchRejected, RoundStarted, RunFinished, RunStarted, RunStats,
                     TestProgress, UniverseDisposed, UniverseForked, UniverseObserved)

HYPS = [("h1", "off-by-one boundary"), ("h2", "unicode normalisation"), ("h3", "separator collapse"),
        ("h4", "max_length truncation"), ("h5", "regex anchor")]
FAILING = ["test_slugify.py::TestSlugify::test_max_length", "test_slugify.py::TestSlugify::test_max_length_cutoff_not_required",
           "test_slugify.py::TestSlugify::test_word_boundary", "test_slugify.py::TestSlugify::test_save_order"]
DIFF = """--- a/slugify/slugify.py
+++ b/slugify/slugify.py
@@ -158,7 +158,7 @@ def slugify(text, entities=True, decimal=True, hexadecimal=True, max_length=0,
     # smart truncate if requested
     if max_length > 0:
-        text = smart_truncate(text, max_length - 1, word_boundary, separator, save_order)
+        text = smart_truncate(text, max_length, word_boundary, separator, save_order)
"""


def test_ids(n=60):
    names = ["phonetic_conversion", "accented_text", "max_length", "max_length_cutoff_not_required", "word_boundary",
             "save_order", "separator", "stopwords", "regex_pattern", "lowercase", "numbers", "html_entities",
             "html_decimal", "html_hexadecimal", "custom_replacements", "unicode", "contains_numbers", "emoji"]
    ids = [f"test_slugify.py::TestSlugify::test_{x}" for x in names]
    i = 0
    while len(ids) < n:
        ids.append(f"test_slugify.py::TestSlugifyUnicode::test_case_{i:02d}")
        i += 1
    for f in FAILING:
        if f not in ids:
            ids[len(ids) // 2] = f
    return ids[:n]


def build(seed: int = 7, n: int = 32, per_box: int = 4) -> list[dict]:
    rnd = random.Random(seed)
    bus = EventBus("demo-" + str(seed), t0=0)
    tests = test_ids()
    T = len(tests)
    fail_idx = {tests.index(f) for f in FAILING}
    bus.emit(RunStarted(repo="un33k/python-slugify", bug_id="slugify-L1-maxlen", n_worlds=n, model="qwen2.5-coder-7b",
                        max_rounds=2, worlds_per_sandbox=per_box), 0.2)
    bus.emit(BaseTests(test_ids=tests), 3.6)
    bus.emit(BaseReady(setup_ms=4200, sandbox_id="sbx-base", tests_total=T, failing_tests=FAILING,
                       error_summary="AssertionError: 'jaja-lol-mememeoo' != 'jaja-lol-mememeo'"), 4.4)
    bus.emit(HypothesesProposed(items=[Hypothesis(id=h, label=l, rationale="") for h, l in HYPS]), 7.6)

    created, fork_ms, timeline = [], [], []

    def world(wid, parent, rnd_no, hyp, box, t_birth, outcome, n_fail, t_test, reason=None):
        fm = rnd.randint(900, 2300)
        fork_ms.append(fm)
        created.append(wid)
        timeline.append((t_birth, UniverseForked(id=wid, parent_id=parent, round=rnd_no, fork_ms=fm, hypothesis_id=hyp,
                                                 sandbox_id=f"sbx-{box:02d}")))
        timeline.append((t_birth + 0.4, PatchProposed(id=wid, files=["slugify/slugify.py"] if reason != "touches_tests"
                                                       else ["test_slugify.py"], lines_added=rnd.randint(1, 4),
                                                       lines_removed=rnd.randint(1, 3))))
        if reason:
            timeline.append((t_birth + 1.0, PatchRejected(id=wid, reason=reason)))
            timeline.append((t_birth + 1.1, UniverseObserved(id=wid, status="stillborn", failing=[], first_error=reason,
                                                             duration_ms=0, collected=0)))
            return
        timeline.append((t_birth + 0.9, PatchApplied(id=wid)))
        # which tests fail in this world
        pool = list(fail_idx) + rnd.sample(range(T), 6)
        fails = set(rnd.sample(pool, n_fail)) if n_fail else set()
        start, dur = t_birth + 1.2, t_test
        chunks = 8
        per = T // chunks
        passed = failed = 0
        for c in range(chunks):
            seg = range(c * per, T if c == chunks - 1 else (c + 1) * per)
            res = "".join("F" if i in fails else "." for i in seg)
            passed += res.count(".")
            failed += res.count("F")
            tail = [f"test_slugify.py {res}", f"{passed} passed, {failed} failed"]
            timeline.append((start + dur * (c + 1) / chunks,
                             TestProgress(id=wid, results=res, passed=passed, failed=failed, total=T, tail=tail)))
        status = "green" if outcome == "green" else "red"
        failing = [tests[i] for i in sorted(fails)]
        err = "" if status == "green" else f"AssertionError in {failing[0].split('::')[-1]}" if failing else ""
        timeline.append((start + dur + 0.1, UniverseObserved(id=wid, status=status, failing=failing, first_error=err,
                                                             duration_ms=int(dur * 1000), collected=T)))

    # round 1: 32 worlds over 8 sandboxes, 3 stillborn, 27 red with varied failures, 0 green
    stillborn = {5: "touches_tests", 13: "no_match", 22: "skip_injection"}
    for i in range(n):
        hyp = HYPS[i % len(HYPS)][0]
        t_birth = 8.0 + i * 0.06
        n_fail = rnd.choice([1, 1, 2, 2, 3, 3, 4, 5, 6])
        world(f"w{i:02d}", None, 1, hyp, i // per_box, t_birth, "red", n_fail, rnd.uniform(14, 28), stillborn.get(i))
    # round 2: best 4 parents x 4 children; one is green
    timeline.sort(key=lambda x: x[0])
    for t, ev in timeline:
        bus.emit(ev, t)
    timeline.clear()
    reds = [e for e in bus.events if e["type"] == "universe.observed" and e["status"] == "red"]
    parents = [e["id"] for e in sorted(reds, key=lambda e: len(e["failing"]))[:4]]
    bus.emit(RoundStarted(round=2, parents=parents), 41.0)
    winner = None
    k = 0
    for p in parents:
        hyp = next(e["hypothesis_id"] for e in bus.events if e["type"] == "universe.forked" and e["id"] == p)
        for j in range(4):
            wid = f"{p}.{j + 1}"
            green = (p == parents[0] and j == 2)
            if green:
                winner = (wid, hyp)
            world(wid, p, 2, hyp, k // per_box, 41.5 + k * 0.08, "green" if green else "red",
                  0 if green else rnd.choice([1, 1, 2]), rnd.uniform(9, 15) if not green else 11.0)
            k += 1
    timeline.sort(key=lambda x: x[0])
    for t, ev in timeline:
        bus.emit(ev, t)
    wid, hyp = winner
    label = dict(HYPS)[hyp]
    pr = (f"### Everett fix: {label}\n\n`smart_truncate` was called with `max_length - 1`, cutting one character too many.\n\n"
          f"- Tests: {T}/{T} passing, 0 regressions\n- Worlds tried: {len(created)} · merged: 1\n")
    bus.emit(Collapse(winner_id=wid, hypothesis_id=hyp, diff=DIFF, pr_markdown=pr), 62.0)
    t = 62.6
    for w in created:
        if w != wid:
            bus.emit(UniverseDisposed(id=w), t)
            t += 0.05
    fs = sorted(fork_ms)
    bus.emit(RunFinished(stats=RunStats(worlds_created=len(created), worlds_disposed=len(created) - 1, merged=1,
                                        fork_ms_p50=fs[len(fs) // 2], fork_ms_p95=fs[int(len(fs) * 0.95)],
                                        wall_ms=69500, tokens_prompt=61200, tokens_completion=18400,
                                        nosana_requests=11, est_cost_usd=0.01, sandboxes_used=9)), 69.5)
    EVENT_LIST.validate_python(bus.events)  # contract check
    return bus.events


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", default=str(Path(__file__).resolve().parents[2] / "web" / "replays" / "demo.json"))
    a = ap.parse_args()
    ev = build(a.seed)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(ev, ensure_ascii=False))
    print(f"{len(ev)} events, {ev[-1]['ts']}s -> {a.out}")


if __name__ == "__main__":
    main()
