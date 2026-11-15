"""orchestrate(): broken build -> hypotheses -> N patches -> N worlds -> judge -> (beam round) -> collapse.

Daytona (`worlds`) and Nosana (`llm`) are injected so the whole flow runs offline in tests.
"""
from __future__ import annotations

import asyncio
import difflib
import time
from dataclasses import dataclass, field

from . import patches as P
from .context import rank_sources, test_snippets
from .events import (BaseReady, BaseTests, Collapse, EventBus, Hypothesis, HypothesesProposed, PatchApplied,
                     PatchProposed, PatchRejected, RoundStarted, RunFailed, RunFinished, RunStarted, RunStats,
                     TestProgress, UniverseDisposed, UniverseForked, UniverseObserved)
from .selection import Outcome, beam, judge, winner


@dataclass
class Spec:
    repo: str
    bug_id: str
    bug_patch: str
    n_worlds: int = 32
    n_boxes: int = 8
    k_hyp: int = 4
    max_rounds: int = 2
    beam_k: int = 4
    beam_children: int = 4
    context_chars: int = 24000


@dataclass
class World:
    id: str
    parent: str | None
    round: int
    hyp: str
    files: dict[str, str] = field(default_factory=dict)
    diff_lines: int = 0
    outcome: Outcome | None = None


def _pct(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(len(xs) * p))] if xs else 0


async def orchestrate(spec: Spec, bus: EventBus, worlds, llm, model_name: str = "qwen2.5-coder-7b") -> dict:
    t0 = time.monotonic()
    created: list[World] = []
    stage = "setup"
    try:
        bus.emit(RunStarted(repo=spec.repo, bug_id=spec.bug_id, n_worlds=spec.n_worlds, model=model_name,
                            max_rounds=spec.max_rounds, worlds_per_sandbox=spec.n_worlds // spec.n_boxes))
        await worlds.start(spec.n_boxes, spec.n_worlds // spec.n_boxes, spec.bug_patch)

        stage = "base"
        base = await asyncio.to_thread(worlds.run_base)
        test_ids = list(base.results)
        base_failing = {t for t, r in base.results.items() if r in ("failed", "error")}
        base_passing = {t for t, r in base.results.items() if r == "passed"}
        if not base_failing:
            raise RuntimeError("the bug did not break any test")
        bus.emit(BaseTests(test_ids=test_ids))
        bus.emit(BaseReady(setup_ms=int((time.monotonic() - t0) * 1000), sandbox_id=worlds.base.id,
                           tests_total=len(test_ids), failing_tests=sorted(base_failing), error_summary=base.first_error))

        stage = "context"
        sources = await asyncio.to_thread(worlds.source_files)
        cache: dict[str, str | None] = {}

        def read(path):
            if path not in cache:
                cache[path] = worlds.read_file(path)
            return cache[path]

        tests_src = test_snippets(sorted(base_failing), read)
        ordered = rank_sources(sources, tests_src, read)[:2]   # the two most relevant files, whole
        sources = ordered
        ctx_parts, used = [], 0
        for path in ordered:
            body = read(path) or ""
            if used + len(body) > spec.context_chars:
                continue
            ctx_parts.append(f"### {path}\n```python\n{body}\n```")
            used += len(body)
        context = (f"Repository files (source, editable — edit ONLY these files):\n" + "\n".join(ctx_parts) +
                   f"\n\nFailing tests (reference only — never edit tests):\n```python\n{tests_src}\n```\n" +
                   "\n".join(sorted(base_failing)) +
                   f"\n\nFirst error: {base.first_error}\n\nTest output tail:\n{base.log[-2500:]}")

        stage = "hypotheses"
        hyps = await llm.hypotheses(context, spec.k_hyp)
        bus.emit(HypothesesProposed(items=[Hypothesis(**h) for h in hyps]))

        slots: asyncio.Queue = asyncio.Queue()
        for b in worlds.boxes:
            for s in range(b.slots):
                slots.put_nowait((b, s))
        outcomes: list[Outcome] = []
        start_ms: list[int] = []

        async def run_world(w: World, text: str, base_files: dict[str, str]):
            created.append(w)
            box, slot = await slots.get()
            try:
                t = time.monotonic()
                bus.emit(UniverseForked(id=w.id, parent_id=w.parent, round=w.round, fork_ms=0, hypothesis_id=w.hyp,
                                        sandbox_id=box.id[:8]))
                rd = lambda p: base_files.get(p) if p in base_files else read(p)
                patch = P.apply(text, rd, candidates=sources)
                files_touched = list(patch.files) or [b.path for b in P.parse(text)][:3]
                bus.emit(PatchProposed(id=w.id, files=files_touched, lines_added=patch.added, lines_removed=patch.removed))
                if patch.reject:
                    bus.emit(PatchRejected(id=w.id, reason=patch.reject))
                    w.outcome = Outcome(w.id, {}, 0, status="stillborn")
                    bus.emit(UniverseObserved(id=w.id, status="stillborn", failing=[], first_error=patch.reject,
                                              duration_ms=0, collected=0))
                    return
                w.files = {**base_files, **patch.files}
                w.diff_lines = patch.added + patch.removed
                bus.emit(PatchApplied(id=w.id))
                tr = await worlds.run_world(box, slot, w.files)
                start_ms.append(int((time.monotonic() - t) * 1000) - tr.duration_ms)
                o = judge(Outcome(w.id, tr.results, tr.collected, w.diff_lines, time.monotonic() - t0),
                          base_failing, base_passing, len(test_ids))
                w.outcome = o
                # barcode in collected order (same order as base.tests)
                chars = "".join({"passed": ".", "failed": "F", "error": "E", "skipped": "s"}.get(tr.results.get(t), "E")
                                for t in test_ids)
                bus.emit(TestProgress(id=w.id, results=chars, passed=chars.count("."), failed=chars.count("F") + chars.count("E"),
                                      total=len(test_ids), tail=[f"{chars.count('.')} passed, {len(o.failing)} failing"]))
                if o.status == "stillborn":
                    bus.emit(PatchRejected(id=w.id, reason="collect_shrank"))
                bus.emit(UniverseObserved(id=w.id, status=o.status, failing=o.failing[:20],
                                          first_error=tr.first_error if o.status != "green" else "",
                                          duration_ms=tr.duration_ms, collected=tr.collected))
                outcomes.append(o)
            finally:
                slots.put_nowait((box, slot))

        # ---------- round 1 ----------
        stage = "round1"
        per = max(1, spec.n_worlds // len(hyps))
        temps = [0.4 + 0.6 * i / max(1, len(hyps) - 1) for i in range(len(hyps))]
        tasks, counter = [], 0

        async def gen_and_run(h, temp):
            nonlocal counter
            texts = await llm.patches(context, h, per, temp, example_path=ordered[0] if ordered else "pkg/module.py")
            for text in texts:
                wid = f"w{counter:02d}"
                counter += 1
                tasks.append(asyncio.create_task(run_world(World(wid, None, 1, h["id"]), text, {})))

        await asyncio.gather(*[gen_and_run(h, t) for h, t in zip(hyps, temps)])
        await asyncio.gather(*tasks)
        by_id = {w.id: w for w in created}
        best = winner([w.outcome for w in created if w.outcome])

        # ---------- round 2: branch again from the closest worlds ----------
        rnd = 1
        while best is None and rnd < spec.max_rounds:
            rnd += 1
            stage = f"round{rnd}"
            parents = beam([w.outcome for w in created if w.outcome and w.round == rnd - 1], len(base_failing), spec.beam_k)
            if not parents:
                break
            bus.emit(RoundStarted(round=rnd, parents=[o.id for o in parents]))
            tasks.clear()

            async def branch(po: Outcome):
                pw = by_id[po.id]
                h = next(x for x in hyps if x["id"] == pw.hyp)
                prev = "\n".join(_diff(read, pw.files))
                extra = (f"A previous attempt applied this change and still fails {len(po.failing)} test(s):\n{prev}\n"
                         f"Still failing: {', '.join(po.failing[:6])}\nImprove on it (the files below already include it).")
                ctx2 = context + "\n\nCurrent content of changed files:\n" + "\n".join(
                    f"### {p}\n```python\n{c}\n```" for p, c in pw.files.items())
                texts = await llm.patches(ctx2, h, spec.beam_children, 0.7, extra,
                                          example_path=next(iter(pw.files), ordered[0] if ordered else "pkg/module.py"))
                for j, text in enumerate(texts):
                    tasks.append(asyncio.create_task(
                        run_world(World(f"{pw.id}.{j + 1}", pw.id, rnd, pw.hyp), text, dict(pw.files))))

            await asyncio.gather(*[branch(o) for o in parents])
            await asyncio.gather(*tasks)
            by_id = {w.id: w for w in created}
            best = winner([w.outcome for w in created if w.outcome and w.round == rnd])

        # ---------- collapse ----------
        stage = "collapse"
        if best:
            ww = by_id[best.id]
            diff = "\n".join(_diff(read, ww.files)) + "\n"
            h = next((x for x in hyps if x["id"] == ww.hyp), {"label": ww.hyp})
            pr = (f"### Everett fix — {h['label']}\n\n{h.get('rationale', '')}\n\n```diff\n{diff}```\n\n"
                  f"- Tests: {len(best.results)}/{len(test_ids)} collected, all {len(base_failing)} failing tests now pass, "
                  f"0 regressions\n- Worlds tried: {len(created)} on {len(worlds.boxes)} Daytona sandboxes · model: {model_name} on Nosana\n")
            bus.emit(Collapse(winner_id=best.id, hypothesis_id=ww.hyp, diff=diff, pr_markdown=pr))
        else:
            bus.emit(Collapse(winner_id=None, hypothesis_id=None, diff="", pr_markdown="No world passed every test."))
        for w in created:
            if not best or w.id != best.id:
                bus.emit(UniverseDisposed(id=w.id))
        stats = RunStats(worlds_created=len(created), worlds_disposed=len(created) - (1 if best else 0),
                         merged=1 if best else 0, fork_ms_p50=_pct(start_ms, 0.5), fork_ms_p95=_pct(start_ms, 0.95),
                         wall_ms=int((time.monotonic() - t0) * 1000), tokens_prompt=llm.tokens_prompt,
                         tokens_completion=llm.tokens_completion, nosana_requests=llm.requests,
                         est_cost_usd=round(0.19 * (time.monotonic() - t0) / 3600, 4),
                         sandboxes_used=1 + len(worlds.boxes))
        bus.emit(RunFinished(stats=stats))
        return {"winner": best.id if best else None, "stats": stats.model_dump()}
    except Exception as e:  # noqa: BLE001
        bus.emit(RunFailed(stage=stage, message=f"{type(e).__name__}: {e}"[:300]))
        return {"winner": None, "error": str(e)}
    finally:
        await asyncio.to_thread(worlds.dispose_all)


def _diff(read, files: dict[str, str]) -> list[str]:
    out = []
    for p, new in files.items():
        old = read(p) or ""
        out += list(difflib.unified_diff(old.splitlines(), new.splitlines(), f"a/{p}", f"b/{p}", lineterm=""))
    return out
