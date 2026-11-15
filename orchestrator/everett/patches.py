"""SEARCH/REPLACE patches: parse, apply locally (deterministic), diff, and reject cheats before any world runs."""
from __future__ import annotations

import difflib
import fnmatch
import re
from dataclasses import dataclass, field

BLOCK = re.compile(
    r"(?m)^(?P<path>[^\s`<>=][^\n`<>=]*?)\s*\n(?:```[a-z]*\n)?<<<<<<< SEARCH\n(?P<search>.*?)\n?=======\n(?P<replace>.*?)\n?>>>>>>> REPLACE",
    re.S)
TEST_GLOBS = ["tests/*", "*/tests/*", "test/*", "*/test/*", "test_*.py", "*/test_*.py", "*_test.py", "*/*_test.py",
              "conftest.py", "*/conftest.py", "pytest.ini", "tox.ini", "setup.cfg", "pyproject.toml", "noxfile.py"]
SKIP_TOKENS = ["pytest.skip", "pytest.mark.skip", "xfail", "unittest.skip", "sys.exit", "os._exit"]


@dataclass
class Block:
    path: str
    search: str
    replace: str


@dataclass
class Patch:
    files: dict[str, str] = field(default_factory=dict)   # path -> new full content
    diff: str = ""
    added: int = 0
    removed: int = 0
    reject: str | None = None


def parse(text: str) -> list[Block]:
    out = []
    for m in BLOCK.finditer(text or ""):
        path = m.group("path").strip().strip("`").lstrip("./")
        out.append(Block(path, m.group("search"), m.group("replace")))
    return out


def is_test_path(path: str) -> bool:
    p = path.lstrip("./")
    return any(fnmatch.fnmatch(p, g) for g in TEST_GLOBS) or p.split("/")[-1] in ("conftest.py",)


def _replace_once(src: str, search: str, replace: str) -> str | None:
    if search and src.count(search) == 1:
        return src.replace(search, replace, 1)
    # retry ignoring trailing whitespace on each line
    strip = lambda s: "\n".join(l.rstrip() for l in s.split("\n"))
    s2, q2 = strip(src), strip(search)
    if q2 and s2.count(q2) == 1:
        return s2.replace(q2, strip(replace), 1)
    return None


def apply(text: str, read) -> Patch:
    """`read(path) -> str | None` returns the current file content from the base world."""
    blocks = parse(text)
    if not blocks:
        return Patch(reject="parse_error")
    for b in blocks:
        if is_test_path(b.path):
            return Patch(reject="touches_tests")
        if any(tok in b.replace and tok not in b.search for tok in SKIP_TOKENS):
            return Patch(reject="skip_injection")
    files: dict[str, str] = {}
    orig: dict[str, str] = {}
    for b in blocks:
        cur = files.get(b.path)
        if cur is None:
            cur = read(b.path)
            if cur is None:
                return Patch(reject="no_match")
            orig[b.path] = cur
        new = _replace_once(cur, b.search, b.replace)
        if new is None:
            return Patch(reject="no_match")
        files[b.path] = new
    if all(files[p] == orig[p] for p in files):
        return Patch(reject="empty")
    diff, add, rem = [], 0, 0
    for p in files:
        d = list(difflib.unified_diff(orig[p].splitlines(), files[p].splitlines(), f"a/{p}", f"b/{p}", lineterm=""))
        add += sum(1 for l in d if l.startswith("+") and not l.startswith("+++"))
        rem += sum(1 for l in d if l.startswith("-") and not l.startswith("---"))
        diff += d
    return Patch(files=files, diff="\n".join(diff) + "\n", added=add, removed=rem)
