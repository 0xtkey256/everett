"""P0: measure Daytona fork() for Everett.

  python scripts/probe_fork.py [--sizes 8 16 32] [--repo URL]

1. base world: python sandbox -> git clone -> pip install -> pytest (each stage timed)
2. fork once: latency, files/site-packages/.pytest_cache present, pytest passes in the fork
3. concurrent forks at each size: p50/p95 latency and any error text
4. fork of a fork
5. write docs/eval-results.md, then delete every sandbox this run created

Every sandbox gets labels {app: everett, run: <id>, role: ...} and a TTL so nothing outlives the probe.
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

from daytona import CreateSandboxFromSnapshotParams, Daytona, DaytonaConfig

ROOT = Path(__file__).resolve().parent.parent
RUN = "probe-" + uuid.uuid4().hex[:6]
TTL_MIN = 45
WORK = "/home/daytona/repo"


def load_env():
    for line in (ROOT / ".env").read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.split(" #")[0].strip())


def ms(t0):
    return round((time.perf_counter() - t0) * 1000)


def pct(xs, p):
    xs = sorted(xs)
    if not xs:
        return None
    k = (len(xs) - 1) * p / 100
    lo, hi = int(k), min(int(k) + 1, len(xs) - 1)
    return round(xs[lo] + (xs[hi] - xs[lo]) * (k - lo))


def sh(sb, cmd, timeout=600):
    r = sb.process.exec(cmd, cwd=WORK if cmd.split()[0] not in ("git",) else None, timeout=timeout)
    return r.exit_code, (r.result or "")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sizes", type=int, nargs="+", default=[8, 16, 32])
    ap.add_argument("--repo", default="https://github.com/un33k/python-slugify.git")
    ap.add_argument("--snapshot", default="daytona-vm-small", help="fork() needs a linux-vm class snapshot")
    a = ap.parse_args()
    load_env()
    d = Daytona(DaytonaConfig(api_key=os.environ["DAYTONA_API_KEY"]))
    created: list = []
    rep: dict = {"run": RUN, "repo": a.repo, "stages": {}, "fork1": {}, "batches": [], "fork_of_fork": {}}

    def track(sb):
        created.append(sb)
        return sb

    try:
        # ---- 1. base world
        t = time.perf_counter()
        base = track(d.create(CreateSandboxFromSnapshotParams(
            snapshot=a.snapshot, labels={"app": "everett", "run": RUN, "role": "base"},
            ttl_minutes=TTL_MIN), timeout=300))
        rep["snapshot"] = a.snapshot
        rep["stages"]["create_ms"] = ms(t)
        code, out = base.process.exec("python3 --version && git --version").exit_code, None
        t = time.perf_counter()
        r = base.process.exec(f"git clone --depth 1 {a.repo} {WORK}", timeout=180)
        rep["stages"]["clone_ms"] = ms(t)
        assert r.exit_code == 0, f"clone failed: {r.result[-400:]}"
        t = time.perf_counter()
        r = base.process.exec("pip install -q -e . pytest", cwd=WORK, timeout=600)
        rep["stages"]["install_ms"] = ms(t)
        assert r.exit_code == 0, f"install failed: {r.result[-400:]}"
        t = time.perf_counter()
        r = base.process.exec("python -m pytest -q", cwd=WORK, timeout=300)
        rep["stages"]["pytest_ms"] = ms(t)
        rep["stages"]["pytest_tail"] = (r.result or "").strip().splitlines()[-1:]
        print("base:", rep["stages"])

        # ---- 2. single fork
        t = time.perf_counter()
        f1 = track(base.fork())
        rep["fork1"]["fork_ms"] = ms(t)
        r = f1.process.exec(
            "test -d .git && echo REPO_OK; python -c 'import slugify,sys;print(\"SITE_OK\", slugify.__file__)'; "
            "test -d .pytest_cache && echo CACHE_OK", cwd=WORK, timeout=60)
        rep["fork1"]["checks"] = [l for l in (r.result or "").splitlines() if "_OK" in l]
        t = time.perf_counter()
        r = f1.process.exec("python -m pytest -q", cwd=WORK, timeout=300)
        rep["fork1"]["pytest_ms"] = ms(t)
        rep["fork1"]["pytest_exit"] = r.exit_code
        rep["fork1"]["labels"] = getattr(f1, "labels", None)
        print("fork1:", rep["fork1"])

        # ---- 4. fork of a fork (do it before the big batches)
        t = time.perf_counter()
        try:
            ff = track(f1.fork())
            rep["fork_of_fork"] = {"ok": True, "fork_ms": ms(t)}
            r = ff.process.exec("python -m pytest -q", cwd=WORK, timeout=300)
            rep["fork_of_fork"]["pytest_exit"] = r.exit_code
        except Exception as e:  # noqa: BLE001
            rep["fork_of_fork"] = {"ok": False, "error": f"{type(e).__name__}: {e}"[:300]}
        print("fork_of_fork:", rep["fork_of_fork"])

        # ---- 3. concurrent batches (each batch deleted before the next)
        for n in a.sizes:
            lat, errs, kids = [], [], []

            def one(_):
                t0 = time.perf_counter()
                try:
                    kid = base.fork()
                    return ms(t0), kid, None
                except Exception as e:  # noqa: BLE001
                    return ms(t0), None, f"{type(e).__name__}: {e}"[:200]

            t = time.perf_counter()
            with ThreadPoolExecutor(n) as pool:
                for dt, kid, err in pool.map(one, range(n)):
                    if kid is not None:
                        kids.append(track(kid))
                        lat.append(dt)
                    else:
                        errs.append(err)
            wall = ms(t)
            # quick liveness check: run a trivial command in every fork in parallel
            t = time.perf_counter()
            with ThreadPoolExecutor(max(1, len(kids))) as pool:
                alive = sum(pool.map(lambda k: k.process.exec("true", timeout=60).exit_code == 0, kids))
            b = {"n": n, "ok": len(kids), "errors": len(errs), "p50_ms": pct(lat, 50), "p95_ms": pct(lat, 95),
                 "max_ms": max(lat) if lat else None, "wall_ms": wall, "alive": alive, "exec_all_ms": ms(t),
                 "error_samples": sorted(set(errs))[:3]}
            rep["batches"].append(b)
            print("batch:", b)
            for k in kids:
                try:
                    k.delete()
                    created.remove(k)
                except Exception:  # noqa: BLE001
                    pass
            time.sleep(3)
    finally:
        for sb in created:
            try:
                sb.delete()
            except Exception:  # noqa: BLE001
                pass
        # belt and braces: anything still labelled with this run
        try:
            for sb in list(d.list()):
                if (getattr(sb, "labels", None) or {}).get("run") == RUN:
                    sb.delete()
        except Exception:  # noqa: BLE001
            pass
        out = ROOT / "runs" / f"{RUN}.json"
        out.parent.mkdir(exist_ok=True)
        out.write_text(json.dumps(rep, indent=1, default=str))
        write_doc(rep)
        print("report:", out)


def write_doc(rep):
    doc = ROOT / "docs" / "eval-results.md"
    doc.parent.mkdir(exist_ok=True)
    s = rep["stages"]
    lines = [f"## P0 — Daytona fork() ({datetime.now():%Y-%m-%d %H:%M}, run `{rep['run']}`)", "",
             f"Base repo: {rep['repo']} · snapshot `{rep.get('snapshot')}`", "",
             "| Base stage | ms |", "|---|---|"]
    for k in ("create_ms", "clone_ms", "install_ms", "pytest_ms"):
        lines.append(f"| {k} | {s.get(k, '—')} |")
    f1 = rep["fork1"]
    lines += ["", f"Single fork: **{f1.get('fork_ms', '—')} ms**; checks {f1.get('checks')}; "
              f"pytest in fork exit {f1.get('pytest_exit')} ({f1.get('pytest_ms')} ms)", "",
              f"Fork of a fork: {rep['fork_of_fork']}", "",
              "| Concurrent forks | ok | errors | p50 ms | p95 ms | max ms | batch wall ms | exec in all ms |",
              "|---|---|---|---|---|---|---|---|"]
    for b in rep["batches"]:
        lines.append(f"| {b['n']} | {b['ok']} | {b['errors']} | {b['p50_ms']} | {b['p95_ms']} | {b['max_ms']} | "
                     f"{b['wall_ms']} | {b['exec_all_ms']} |")
    errs = [e for b in rep["batches"] for e in b["error_samples"]]
    if errs:
        lines += ["", "Errors seen:", *[f"- `{e}`" for e in errs]]
    prev = doc.read_text() if doc.exists() else "# Eval results\n\n"
    doc.write_text(prev.rstrip() + "\n\n" + "\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
