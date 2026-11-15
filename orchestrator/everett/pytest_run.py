"""pytest command, streaming progress parser, and junit XML parser."""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET

CMD = "python -m pytest -q -p no:cacheprovider --color=no --tb=short -o console_output_style=classic --junitxml=/tmp/r.xml"
PROGRESS_CHARS = set(".FEsx")
_LINE = re.compile(r"^(?:\S+\.py\s+)?([.FEsx]+)(?:\s+\[\s*\d+%\])?\s*$")


class ProgressParser:
    """Feeds raw stdout chunks; yields the new result characters ('.', 'F', 'E', 's', 'x') in order.

    Handles chunks that split a line, and ignores summary/traceback lines."""

    def __init__(self):
        self.buf = ""

    def feed(self, chunk: str) -> str:
        self.buf += chunk
        out = []
        while "\n" in self.buf:
            line, self.buf = self.buf.split("\n", 1)
            m = _LINE.match(line.strip())
            if m:
                out.append(m.group(1))
        # partial progress line still being written: emit what's there and keep the position
        tail = self.buf.strip()
        if tail and set(tail) <= PROGRESS_CHARS:
            out.append(tail)
            self.buf = ""
        return "".join(out)


def parse_junit(xml_text: str) -> dict[str, str]:
    """-> {test_id: 'passed'|'failed'|'error'|'skipped'} with ids like 'test_x.py::Class::test_name'."""
    res: dict[str, str] = {}
    root = ET.fromstring(xml_text)
    for tc in root.iter("testcase"):
        cls, name = tc.get("classname", ""), tc.get("name", "")
        parts = cls.split(".")
        # classname "test_slugify.TestSlugify" -> file test_slugify.py, class TestSlugify
        mod_end = next((i for i, p in enumerate(parts) if p and p[0].isupper()), len(parts))
        file = "/".join(parts[:mod_end]) + ".py"
        tid = "::".join([file] + parts[mod_end:] + [name])
        state = "passed"
        for child in tc:
            if child.tag in ("failure",):
                state = "failed"
            elif child.tag == "error":
                state = "error"
            elif child.tag == "skipped":
                state = "skipped"
        res[tid] = state
    return res


def first_error(xml_text: str) -> str:
    root = ET.fromstring(xml_text)
    for tc in root.iter("testcase"):
        for child in tc:
            if child.tag in ("failure", "error"):
                msg = (child.get("message") or child.text or "").strip().splitlines()
                return (msg[0] if msg else child.tag)[:160]
    return ""
