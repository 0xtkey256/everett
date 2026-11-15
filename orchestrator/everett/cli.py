"""Run one Everett fix from the terminal and save the replay.

  python -m everett.cli slugify/L1-word-boundary [--worlds 32 --boxes 8 --rounds 2] [--save NAME]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import uuid

from . import config
from .events import EventBus
from .nosana import Nosana
from .server import load_bug
from .run import orchestrate
from .worlds import Worlds


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("bug", nargs="?", default="mercantile/xy-swap")
    ap.add_argument("--worlds", type=int, default=32)
    ap.add_argument("--boxes", type=int, default=8)
    ap.add_argument("--rounds", type=int, default=2)
    ap.add_argument("--hyps", type=int, default=4)
    ap.add_argument("--save", default=None, help="also write web/replays/<NAME>.json")
    a = ap.parse_args()
    spec = load_bug(a.bug)
    spec.n_worlds, spec.n_boxes, spec.max_rounds, spec.k_hyp = a.worlds, a.boxes, a.rounds, a.hyps
    run_id = uuid.uuid4().hex[:10]
    bus = EventBus(run_id, root=config.RUNS)
    orig = bus.emit

    def emit(ev, ts=None):
        d = orig(ev, ts)
        t = d["type"]
        if t in ("run.started", "base.ready", "hypotheses.proposed", "round.started", "collapse", "run.finished", "run.failed"):
            brief = {k: v for k, v in d.items() if k not in ("seq", "run_id", "diff", "pr_markdown", "test_ids")}
            print(f"[{d['ts']:6.1f}s] {t}: {json.dumps(brief, ensure_ascii=False)[:300]}", flush=True)
        elif t == "universe.observed":
            print(f"[{d['ts']:6.1f}s]   {d['id']:>8} {d['status']:<9} fail={len(d['failing'])} {d['first_error'][:70]}", flush=True)
        return d

    bus.emit = emit
    out = asyncio.run(orchestrate(spec, bus, Worlds(run_id, spec.snapshot, spec.probe), Nosana()))
    print("RESULT", json.dumps(out))
    if a.save:
        p = config.ROOT / "web" / "replays" / f"{a.save}.json"
        p.write_text(json.dumps(bus.events, ensure_ascii=False))
        print("saved replay ->", p)


if __name__ == "__main__":
    main()
