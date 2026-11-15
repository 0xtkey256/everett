"""Whole orchestrate() flow with fake Daytona + fake Nosana: round-1 win, round-2 win, and total failure."""
import asyncio

from everett.events import EVENT_LIST, EventBus
from everett.run import Spec, orchestrate
from everett.worlds import TestRun

SRC = "def cut(n, m):\n    if n < m:\n        return n - 1\n    return m\n"   # two bugs: n <= m, and return n
TESTS = ["tests/test_a.py::test_edge", "tests/test_a.py::test_small", "tests/test_a.py::test_big"]


def run_tests(src: str) -> TestRun:
    ok_edge = "n <= m" in src
    ok_small = "return n\n" in src
    res = {TESTS[0]: "passed" if ok_edge else "failed", TESTS[1]: "passed" if ok_small else "failed",
           TESTS[2]: "passed"}
    order = "".join("." if v == "passed" else "F" for v in res.values())
    return TestRun(res, order, len(res), "" if ok_edge else "AssertionError: edge", 50, 0, "1 failed")


class FakeBox:
    def __init__(self, i):
        self.idx, self.slots, self.id = i, 4, f"sbx-{i:02d}-xxxx"


class FakeWorlds:
    def __init__(self):
        self.base = type("B", (), {"id": "sbx-base"})()
        self.boxes, self.disposed = [], False

    async def start(self, n_boxes, slots, bug_patch):
        self.boxes = [FakeBox(i) for i in range(n_boxes)]

    def run_base(self):
        return run_tests(SRC)

    def source_files(self):
        return ["pkg/mod.py"]

    def read_file(self, path):
        return SRC if path == "pkg/mod.py" else None

    async def run_world(self, box, slot, files):
        await asyncio.sleep(0)
        return run_tests(files.get("pkg/mod.py", SRC))

    def dispose_all(self):
        self.disposed = True


def blk(search, replace):
    return f"pkg/mod.py\n<<<<<<< SEARCH\n{search}\n=======\n{replace}\n>>>>>>> REPLACE\n"


GOOD = blk("    if n < m:\n        return n - 1", "    if n <= m:\n        return n")
BREAKS = blk("        return n\n", "        return n + 0 if False else m\n")
NOOP_FAIL = blk("    return m", "    return m  # tweak")
CHEAT = "tests/test_a.py\n<<<<<<< SEARCH\nx\n=======\ny\n>>>>>>> REPLACE\n"


class FakeLLM:
    def __init__(self, r1, r2):
        self.r1, self.r2 = r1, r2
        self.tokens_prompt = self.tokens_completion = self.requests = 0

    async def hypotheses(self, context, k):
        assert "pkg/mod.py" in context and "tests/test_a.py::test_edge" in context
        return [{"id": f"h{i + 1}", "label": f"idea {i + 1}", "rationale": ""} for i in range(k)]

    async def patches(self, context, h, n, temperature, extra=""):
        self.requests += 1
        src = self.r2 if extra else self.r1
        return [src[i % len(src)] for i in range(n)]


def go(r1, r2, rounds=2):
    bus, worlds = EventBus("t", t0=0), FakeWorlds()
    spec = Spec(repo="r", bug_id="b", bug_patch="", n_worlds=8, n_boxes=2, k_hyp=2, max_rounds=rounds, beam_k=2,
                beam_children=2)
    out = asyncio.run(orchestrate(spec, bus, worlds, FakeLLM(r1, r2)))
    EVENT_LIST.validate_python(bus.events)
    assert worlds.disposed
    return out, bus.events


def types(ev, t):
    return [e for e in ev if e["type"] == t]


def test_round1_win_and_cheats_are_disqualified():
    out, ev = go([NOOP_FAIL, GOOD, CHEAT, NOOP_FAIL], [GOOD])
    assert out["winner"] and not types(ev, "round.started")
    rej = [e["reason"] for e in types(ev, "patch.rejected")]
    assert "touches_tests" in rej
    col = types(ev, "collapse")[0]
    assert "+    if n <= m:" in col["diff"]
    fin = types(ev, "run.finished")[0]["stats"]
    assert fin["worlds_created"] == 8 and fin["merged"] == 1 and fin["worlds_disposed"] == 7


def test_round2_branches_from_closest_world():
    # round 1 can't win (nobody fixes the edge); round 2 children of a red world do
    near = blk("        return n - 1", "        return n")  # fixes one of two failures -> closer, still red
    good_on_top = blk("    if n < m:", "    if n <= m:")
    out, ev = go([near, CHEAT], [good_on_top])
    rs = types(ev, "round.started")
    assert out["winner"] and rs and rs[0]["round"] == 2
    kids = [e for e in types(ev, "universe.forked") if e["round"] == 2]
    assert kids and all(k["parent_id"] in rs[0]["parents"] for k in kids)


def test_everything_fails_cleanly():
    out, ev = go([NOOP_FAIL, CHEAT], [NOOP_FAIL], rounds=2)
    assert out["winner"] is None
    assert types(ev, "collapse")[0]["winner_id"] is None
    assert types(ev, "run.finished")[0]["stats"]["merged"] == 0
