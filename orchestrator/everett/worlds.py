"""Daytona worlds.

fork() needs the linux-vm sandbox class, which this org doesn't have, and Tier 1 caps total CPU at 10.
So: 1 base sandbox + B world sandboxes (1 vCPU each, from the pre-built snapshot), each holding K isolated
checkouts. A "world" is one checkout + one pytest run. B*K = 32 worlds within 9 vCPU.
"""
from __future__ import annotations

import asyncio
import shlex
import time
from dataclasses import dataclass, field

from daytona import CreateSandboxFromSnapshotParams, Daytona, DaytonaConfig

from . import config
from .pytest_run import CMD, first_error, parse_junit

REPO = "/home/daytona/repo"


@dataclass
class Box:
    sb: object
    idx: int
    slots: int
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    @property
    def id(self) -> str:
        return self.sb.id


@dataclass
class TestRun:
    results: dict[str, str]
    order: str            # result chars in junit order ('.', 'F', 'E', 's')
    collected: int
    first_error: str
    duration_ms: int
    exit_code: int
    log: str = ""


class Worlds:
    def __init__(self, run_id: str, snapshot: str = "everett-base-ct"):
        self.d = Daytona(DaytonaConfig(api_key=config.require("DAYTONA_API_KEY")))
        self.run_id, self.snapshot = run_id, snapshot
        self.base = None
        self.boxes: list[Box] = []
        self.create_ms: list[int] = []

    # ---------- lifecycle ----------
    def _create(self, role: str):
        t = time.perf_counter()
        sb = self.d.create(CreateSandboxFromSnapshotParams(
            snapshot=self.snapshot, labels={"app": "everett", "run": self.run_id, "role": role},
            ttl_minutes=30, auto_stop_interval=10), timeout=300)
        self.create_ms.append(int((time.perf_counter() - t) * 1000))
        return sb

    async def start(self, n_boxes: int, slots: int, bug_patch: str):
        """Create base + world sandboxes in parallel; apply the bug everywhere; lay out `slots` checkouts per box."""
        sbs = await asyncio.gather(asyncio.to_thread(self._create, "base"),
                                   *[asyncio.to_thread(self._create, "world") for _ in range(n_boxes)])
        self.base, worlds = sbs[0], sbs[1:]
        await asyncio.gather(*[asyncio.to_thread(self._prep, sb, bug_patch, slots) for sb in sbs])
        self.boxes = [Box(sb, i, slots) for i, sb in enumerate(worlds)]

    def _prep(self, sb, bug_patch: str, slots: int):
        sb.fs.upload_file(bug_patch.encode(), "/tmp/bug.patch")
        cmd = f"cd {REPO} && git apply /tmp/bug.patch"
        if slots:
            cmd += " && " + " && ".join(f"rm -rf /home/daytona/w{k} && cp -a {REPO} /home/daytona/w{k}" for k in range(slots))
        r = sb.process.exec(cmd, timeout=120)
        if r.exit_code != 0:
            raise RuntimeError(f"prep failed on {sb.id}: {(r.result or '')[-300:]}")

    def dispose_all(self):
        for sb in [self.base] + [b.sb for b in self.boxes]:
            if sb is None:
                continue
            try:
                sb.delete()
            except Exception:  # noqa: BLE001
                pass

    # ---------- base world ----------
    def read_file(self, path: str) -> str | None:
        try:
            return self.base.fs.download_file(f"{REPO}/{path}").decode()
        except Exception:  # noqa: BLE001
            return None

    def source_files(self) -> list[str]:
        """Tracked non-test Python files, smallest first (so the context budget keeps whole files)."""
        r = self.base.process.exec(f"cd {REPO} && git ls-files '*.py' | xargs wc -c | sort -n", timeout=30)
        out = []
        for line in (r.result or "").splitlines():
            parts = line.split()
            if len(parts) == 2 and parts[1] != "total":
                from .patches import is_test_path
                if not is_test_path(parts[1]) and not parts[1].startswith(("docs/", "tools/", "setup.py")):
                    out.append(parts[1])
        return out

    def run_base(self) -> TestRun:
        return self._pytest(self.base, REPO, "base")

    # ---------- a world ----------
    async def run_world(self, box: Box, slot: int, files: dict[str, str]) -> TestRun:
        wdir = f"/home/daytona/w{slot}"
        await asyncio.to_thread(self._reset_slot, box.sb, wdir, files)
        return await asyncio.to_thread(self._pytest, box.sb, wdir, f"w{slot}")

    def _reset_slot(self, sb, wdir: str, files: dict[str, str]):
        r = sb.process.exec(f"rm -rf {wdir} && cp -a {REPO} {wdir}", timeout=60)
        if r.exit_code != 0:
            raise RuntimeError(f"reset failed: {(r.result or '')[-200:]}")
        for path, content in files.items():
            sb.fs.upload_file(content.encode(), f"{wdir}/{path}")

    def _pytest(self, sb, wdir: str, tag: str) -> TestRun:
        xml = f"/tmp/{tag}.xml"
        t = time.perf_counter()
        r = sb.process.exec(f"cd {shlex.quote(wdir)} && rm -f {xml} && timeout 60 {CMD.replace('/tmp/r.xml', xml)}",
                            timeout=90)
        dur = int((time.perf_counter() - t) * 1000)
        try:
            text = sb.fs.download_file(xml).decode()
            res = parse_junit(text)
            err = first_error(text)
        except Exception:  # noqa: BLE001  (no xml: import error / timeout)
            res, err = {}, ((r.result or "").strip().splitlines() or ["no test report"])[-1][:160]
        order = "".join({"passed": ".", "failed": "F", "error": "E", "skipped": "s"}[v] for v in res.values())
        return TestRun(res, order, len(res), err, dur, r.exit_code, (r.result or "")[-4000:])
