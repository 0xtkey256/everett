import json
from pathlib import Path

import pytest

from everett import patches, pytest_run, selection
from everett.events import EVENT_LIST, EventBus, RunStarted, load_jsonl
from everett.fake import build

SRC = {"pkg/mod.py": "def f(n):\n    if n > 0:   \n        return n - 1\n    return 0\n",
       "pkg/other.py": "X = 1\n"}
read = SRC.get


def blk(path, search, replace):
    return f"{path}\n<<<<<<< SEARCH\n{search}\n=======\n{replace}\n>>>>>>> REPLACE\n"


# ---------------- patches ----------------
def test_apply_single_match_and_diff_counts():
    p = patches.apply(blk("pkg/mod.py", "        return n - 1", "        return n"), read)
    assert p.reject is None and p.files["pkg/mod.py"].count("return n\n") == 1
    assert (p.added, p.removed) == (1, 1) and "+++ b/pkg/mod.py" in p.diff


def test_no_match_and_ambiguous_match():
    assert patches.apply(blk("pkg/mod.py", "nope", "x"), read).reject == "no_match"
    dup = {"a.py": "x = 1\nx = 1\n"}
    assert patches.apply(blk("a.py", "x = 1", "x = 2"), dup.get).reject == "no_match"


def test_trailing_whitespace_tolerated():
    p = patches.apply(blk("pkg/mod.py", "    if n > 0:", "    if n >= 0:"), read)
    assert p.reject is None and "n >= 0" in p.files["pkg/mod.py"]


def test_multiple_blocks_same_and_other_file():
    t = blk("pkg/mod.py", "        return n - 1", "        return n") + blk("pkg/other.py", "X = 1", "X = 2")
    p = patches.apply(t, read)
    assert p.reject is None and set(p.files) == {"pkg/mod.py", "pkg/other.py"}


@pytest.mark.parametrize("path", ["tests/test_mod.py", "test_slugify.py", "pkg/conftest.py", "pytest.ini", "pyproject.toml",
                                  "setup.cfg", "pkg/thing_test.py"])
def test_touching_tests_or_config_is_disqualified(path):
    assert patches.apply(blk(path, "a", "b"), {path: "a\n"}.get).reject == "touches_tests"


@pytest.mark.parametrize("tok", ["pytest.skip('x')", "@pytest.mark.skip", "pytest.mark.xfail", "sys.exit(0)", "os._exit(0)"])
def test_skip_injection_is_disqualified(tok):
    assert patches.apply(blk("pkg/mod.py", "    return 0", f"    {tok}\n    return 0"), read).reject == "skip_injection"


def test_empty_and_unparseable():
    assert patches.apply(blk("pkg/mod.py", "    return 0", "    return 0"), read).reject == "empty"
    assert patches.apply("I think the bug is in mod.py", read).reject == "parse_error"


# ---------------- pytest output ----------------
def test_progress_parser_handles_split_chunks():
    p = pytest_run.ProgressParser()
    got = p.feed("test_a.py ..") + p.feed("F.") + p.feed("x\ntest_b.py ...  [100%]\n") + p.feed("=== 1 failed, 6 passed ===\n")
    assert got == "..F.x..."


def test_junit_parse_and_first_error():
    xml = """<testsuites><testsuite>
      <testcase classname="test_slugify.TestSlugify" name="test_ok"/>
      <testcase classname="test_slugify.TestSlugify" name="test_bad"><failure message="AssertionError: 'a' != 'b'"/></testcase>
      <testcase classname="tests.test_x" name="test_skip"><skipped/></testcase>
    </testsuite></testsuites>"""
    r = pytest_run.parse_junit(xml)
    assert r == {"test_slugify.py::TestSlugify::test_ok": "passed", "test_slugify.py::TestSlugify::test_bad": "failed",
                 "tests/test_x.py::test_skip": "skipped"}
    assert pytest_run.first_error(xml).startswith("AssertionError")


# ---------------- selection ----------------
BF, BP = {"t1"}, {"t2", "t3"}


def oc(i, res, collected=3, diff=2, t=1.0):
    return selection.Outcome(id=i, results=res, collected=collected, diff_lines=diff, finished_at=t)


def test_green_requires_fix_and_no_regression():
    g = selection.judge(oc("a", {"t1": "passed", "t2": "passed", "t3": "passed"}), BF, BP, 3)
    r = selection.judge(oc("b", {"t1": "passed", "t2": "failed", "t3": "passed"}), BF, BP, 3)
    assert g.status == "green" and r.status == "red" and r.failing == ["t2"]


def test_fewer_tests_collected_is_stillborn():
    assert selection.judge(oc("c", {"t1": "passed"}, collected=1), BF, BP, 3).status == "stillborn"


def test_winner_prefers_smallest_diff_then_earliest():
    a = selection.judge(oc("a", {t: "passed" for t in "t1 t2 t3".split()}, diff=4, t=1), BF, BP, 3)
    b = selection.judge(oc("b", {t: "passed" for t in "t1 t2 t3".split()}, diff=2, t=5), BF, BP, 3)
    c = selection.judge(oc("c", {t: "passed" for t in "t1 t2 t3".split()}, diff=2, t=3), BF, BP, 3)
    assert selection.winner([a, b, c]).id == "c"


def test_beam_keeps_only_improvers():
    base_fail = 3
    outs = [selection.Outcome("x", {}, 3, status="red", failing=["a", "b"]),
            selection.Outcome("y", {}, 3, status="red", failing=["a", "b", "c"]),
            selection.Outcome("z", {}, 3, status="red", failing=["a"]),
            selection.Outcome("s", {}, 0, status="stillborn")]
    assert [o.id for o in selection.beam(outs, base_fail, k=4)] == ["z", "x"]


# ---------------- events ----------------
def test_fake_run_matches_contract_and_story():
    ev = build(seed=3)
    EVENT_LIST.validate_python(ev)
    seqs = [e["seq"] for e in ev]
    assert seqs == sorted(seqs) and len(set(seqs)) == len(seqs)
    types = {e["type"] for e in ev}
    assert {"run.started", "base.ready", "universe.forked", "test.progress", "universe.observed", "round.started",
            "collapse", "universe.disposed", "run.finished"} <= types
    obs = [e for e in ev if e["type"] == "universe.observed"]
    assert sum(e["status"] == "green" for e in obs) == 1
    assert sum(e["status"] == "stillborn" for e in obs) == 3


def test_bus_jsonl_roundtrip(tmp_path):
    bus = EventBus("r1", root=tmp_path, t0=0)
    bus.emit(RunStarted(repo="x", bug_id="b", n_worlds=1, model="m", max_rounds=1), ts=0.5)
    back = load_jsonl(tmp_path / "r1" / "events.jsonl")
    assert back[0]["seq"] == 1 and back[0]["type"] == "run.started"


def test_fixture_all_events_validates():
    fx = Path(__file__).resolve().parents[2] / "fixtures" / "all_events.json"
    EVENT_LIST.validate_python(json.loads(fx.read_text()))


def test_placeholder_path_is_retargeted_by_unique_match():
    t = blk("path/to/file.py", "        return n - 1", "        return n")
    p = patches.apply(t, read, candidates=["pkg/mod.py", "pkg/other.py"])
    assert p.reject is None and "pkg/mod.py" in p.files


def test_retarget_never_points_at_tests():
    src = {"tests/test_mod.py": "        return n - 1\n"}
    t = blk("path/to/file.py", "        return n - 1", "        return n")
    assert patches.apply(t, src.get, candidates=["tests/test_mod.py"]).reject == "touches_tests"


def test_test_snippets_extracts_failing_function():
    from everett.context import test_snippets
    src = "class T:\n    def test_a(self):\n        assert f(1) == 2\n\n    def test_b(self):\n        pass\n"
    out = test_snippets(["tests/t.py::T::test_a"], {"tests/t.py": src}.get)
    assert "assert f(1) == 2" in out and "test_b" not in out


def test_parse_tolerates_fences_and_header_prefixes():
    t = "```python\n### pkg/mod.py\n<<<<<<< SEARCH\n        return n - 1\n=======\n        return n\n>>>>>>> REPLACE\n```\n"
    p = patches.apply(t, read)
    assert p.reject is None and "pkg/mod.py" in p.files


def test_rank_sources_prefers_files_using_test_identifiers():
    from everett.context import rank_sources
    files = {"a/__init__.py": "x" * 500, "a/core.py": "def word_boundary(max_length):\n" + "y" * 500, "a/v.py": "1"}
    assert rank_sources(list(files), "slug(word_boundary=True, max_length=3)", files.get)[0] == "a/core.py"


def test_reindent_match_when_model_gets_indentation_wrong():
    t = blk("pkg/mod.py", "if n > 0:\n    return n - 1", "if n > 0:\n    return n")
    p = patches.apply(t, read)
    assert p.reject is None
    assert "    if n > 0:\n        return n\n" in p.files["pkg/mod.py"]


def test_reindent_still_requires_unique_match():
    dup = {"a.py": "def f():\n    x = 1\n\ndef g():\n    x = 1\n"}
    assert patches.apply(blk("a.py", "x = 1", "x = 2"), dup.get).reject == "no_match"
