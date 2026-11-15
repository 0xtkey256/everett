"""P0 fallback: fan out by creating N sandboxes from the pre-built base snapshot in parallel.

  python scripts/probe_create.py [--snapshot everett-base-ct] [--sizes 8 16 32]

For each size: create N sandboxes concurrently, run pytest in every one concurrently, record
create p50/p95, pytest p50/p95, errors, then delete them. Appends a table to docs/eval-results.md.
"""
from __future__ import annotations

import argparse
import json
import os
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

from daytona import CreateSandboxFromSnapshotParams, Daytona, DaytonaConfig

ROOT = Path(__file__).resolve().parent.parent
RUN = "create-" + uuid.uuid4().hex[:6]
REPO_DIR = "/home/daytona/repo"


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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", default="everett-base-ct")
    ap.add_argument("--sizes", type=int, nargs="+", default=[8, 16, 32])
    a = ap.parse_args()
    load_env()
    d = Daytona(DaytonaConfig(api_key=os.environ["DAYTONA_API_KEY"]))
    rep = {"run": RUN, "snapshot": a.snapshot, "batches": []}
    try:
        for n in a.sizes:
            def make(i):
                t0 = time.perf_counter()
                try:
                    sb = d.create(CreateSandboxFromSnapshotParams(
                        snapshot=a.snapshot, labels={"app": "everett", "run": RUN, "role": "world"},
                        ttl_minutes=20), timeout=300)
                    return ms(t0), sb, None
                except Exception as e:  # noqa: BLE001
                    return ms(t0), None, f"{type(e).__name__}: {e}"[-200:]

            t = time.perf_counter()
            with ThreadPoolExecutor(n) as pool:
                res = list(pool.map(make, range(n)))
            wall = ms(t)
            sbs = [sb for _, sb, _ in res if sb]
            lat = [dt for dt, sb, _ in res if sb]
            errs = [e for _, _, e in res if e]

            def test(sb):
                t0 = time.perf_counter()
                r = sb.process.exec("python -m pytest -q -p no:cacheprovider", cwd=REPO_DIR, timeout=300)
                return ms(t0), r.exit_code

            t = time.perf_counter()
            with ThreadPoolExecutor(max(1, len(sbs))) as pool:
                tests = list(pool.map(test, sbs))
            b = {"n": n, "ok": len(sbs), "errors": len(errs), "create_p50": pct(lat, 50), "create_p95": pct(lat, 95),
                 "create_wall": wall, "pytest_p50": pct([x for x, _ in tests], 50),
                 "pytest_p95": pct([x for x, _ in tests], 95), "pytest_wall": ms(t),
                 "pytest_pass": sum(1 for _, c in tests if c == 0), "error_samples": sorted(set(errs))[:3]}
            rep["batches"].append(b)
            print("batch:", json.dumps(b))
            with ThreadPoolExecutor(max(1, len(sbs))) as pool:
                list(pool.map(lambda s: s.delete(), sbs))
            time.sleep(3)
    finally:
        for sb in list(d.list()):
            if (getattr(sb, "labels", None) or {}).get("run") == RUN:
                try:
                    sb.delete()
                except Exception:  # noqa: BLE001
                    pass
        (ROOT / "runs").mkdir(exist_ok=True)
        (ROOT / "runs" / f"{RUN}.json").write_text(json.dumps(rep, indent=1))
        lines = [f"## P0 fallback — parallel create from snapshot ({datetime.now():%Y-%m-%d %H:%M}, run `{RUN}`)", "",
                 f"Snapshot `{a.snapshot}` (python 3.12, git, pytest, python-slugify cloned + installed).", "",
                 "| N | ok | errors | create p50 ms | create p95 ms | create wall ms | pytest p50 ms | pytest p95 ms | pytest wall ms | pytest passed |",
                 "|---|---|---|---|---|---|---|---|---|---|"]
        for b in rep["batches"]:
            lines.append(f"| {b['n']} | {b['ok']} | {b['errors']} | {b['create_p50']} | {b['create_p95']} | {b['create_wall']} | "
                         f"{b['pytest_p50']} | {b['pytest_p95']} | {b['pytest_wall']} | {b['pytest_pass']} |")
        errs = [e for b in rep["batches"] for e in b["error_samples"]]
        if errs:
            lines += ["", "Errors seen:", *[f"- `{e}`" for e in errs]]
        doc = ROOT / "docs" / "eval-results.md"
        doc.parent.mkdir(exist_ok=True)
        prev = doc.read_text() if doc.exists() else "# Eval results\n"
        doc.write_text(prev.rstrip() + "\n\n" + "\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
