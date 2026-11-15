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


def localize(sources: dict[str, str], clues: str, budget: int = 9000, top: int = 5) -> dict[str, str]:
    """Function-level fault localization: score top-level functions by overlap with the failing tests,
    errors and symptom text, add the functions they call (one level), return {path: excerpt} with the
    exact source lines (so SEARCH blocks copied from it still match the file)."""
    import ast
    words = set(_IDENT.findall(clues))
    funcs = []   # (score, path, name, src, calls)
    for path, src in sources.items():
        try:
            tree = ast.parse(src)
        except SyntaxError:
            continue
        lines = src.split("\n")
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                start = (node.decorator_list[0].lineno if node.decorator_list else node.lineno) - 1
                body = "\n".join(lines[start:node.end_lineno])
                calls = {n.func.id for n in ast.walk(node) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
                name_hit = 5 if node.name in words or node.name.lstrip("_") in words else 0
                score = name_hit + sum(1 for w in words if w in body and len(w) > 4)
                funcs.append((score, path, node.name, body, calls))
    funcs.sort(key=lambda f: -f[0])
    by_name = {f[2]: f for f in funcs}
    picked, seen = [], set()
    for f in funcs[:top]:
        for g in [f] + [by_name[c] for c in sorted(f[4]) if c in by_name]:
            if g[2] not in seen:
                seen.add(g[2])
                picked.append(g)
    out: dict[str, list[str]] = {}
    used = 0
    for _, path, name, body, _ in picked:
        if used + len(body) > budget:
            continue
        out.setdefault(path, []).append(body)
        used += len(body)
    return {p: "\n\n# ...\n\n".join(bs) for p, bs in out.items()}
