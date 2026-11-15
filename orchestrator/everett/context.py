"""Pick what the model sees: failing test bodies (read-only reference) + the source files they exercise."""
from __future__ import annotations

import re


def test_snippets(failing: list[str], read, max_chars: int = 6000) -> str:
    """Source of each failing test function (by id file::Class::name), trimmed to a budget."""
    out, used = [], 0
    for tid in failing:
        parts = tid.split("::")
        path, name = parts[0], parts[-1]
        src = read(path) or ""
        m = re.search(rf"^(\s*)def {re.escape(name)}\(.*?(?=^\1def |^\1@|^class |\Z)", src, re.S | re.M)
        if not m:
            continue
        body = m.group(0).rstrip()[:2000]
        if used + len(body) > max_chars:
            break
        out.append(f"# {tid}\n{body}")
        used += len(body)
    return "\n\n".join(out)


_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]{3,}")
_COMMON = {"self", "assert", "assertEqual", "true", "false", "none", "return", "import", "from", "test", "class", "with"}


def rank_sources(sources: list[str], tests_src: str, read, min_bytes: int = 400) -> list[str]:
    """Order source files by how many identifiers from the failing tests they mention; skip tiny boilerplate."""
    terms = {t for t in _IDENT.findall(tests_src) if t.lower() not in _COMMON}
    scored = []
    for p in sources:
        body = read(p) or ""
        if len(body) < min_bytes:
            continue
        hits = sum(1 for t in terms if t in body)
        scored.append((hits, -len(body), p))
    scored.sort(reverse=True)
    return [p for h, _, p in scored if h > 0] or [p for _, _, p in scored] or list(sources)
