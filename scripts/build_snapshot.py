"""Build the base-world snapshot: Python 3.12 + git + pytest + the demo repo installed.

  python scripts/build_snapshot.py [--class linux-vm|container] [--name NAME] [--repo URL]

fork() needs a linux-vm class sandbox; if the org can't build that class we fall back to container
and fan out by creating N sandboxes from the snapshot in parallel instead.
"""
from __future__ import annotations

import argparse
import os
import time
from pathlib import Path

from daytona import CreateSnapshotParams, Daytona, DaytonaConfig, Image

ROOT = Path(__file__).resolve().parent.parent
REPO_DIR = "/home/daytona/repo"


def load_env():
    for line in (ROOT / ".env").read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.split(" #")[0].strip())


def image(repo: str, extra: list[str]) -> Image:
    return (Image.debian_slim("3.12")
            .run_commands("apt-get update -qq && apt-get install -y -qq git >/dev/null && rm -rf /var/lib/apt/lists/*")
            .pip_install(["pytest", "pytest-timeout", *extra])
            .run_commands(f"git clone --depth 1 {repo} {REPO_DIR}",
                          f"cd {REPO_DIR} && pip install -q -e . && python -m pytest -q -p no:cacheprovider || true",
                          f"chmod -R a+rwX {REPO_DIR}")
            .workdir(REPO_DIR))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--class", dest="klass", default="linux-vm")
    ap.add_argument("--name", default=None)
    ap.add_argument("--repo", default="https://github.com/un33k/python-slugify.git")
    ap.add_argument("--pip", nargs="*", default=[], help="extra packages (e.g. hypothesis)")
    a = ap.parse_args()
    load_env()
    d = Daytona(DaytonaConfig(api_key=os.environ["DAYTONA_API_KEY"]))
    name = a.name or f"everett-base-{'vm' if a.klass == 'linux-vm' else 'ct'}"
    kw = {"name": name, "image": image(a.repo, a.pip)}
    if a.klass != "container":
        kw["sandbox_class"] = a.klass
    t = time.perf_counter()
    snap = d.snapshot.create(CreateSnapshotParams(**kw),
                             on_logs=lambda l: print("  |", l.rstrip()[:160]) if l.strip() else None, timeout=1200)
    print(f"snapshot {snap.name} {getattr(snap, 'state', '')} in {time.perf_counter() - t:.0f}s")


if __name__ == "__main__":
    main()
