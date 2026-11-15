"""Event contract shared with the web UI (web/js/reducer.js). Every screen is rebuilt from this stream.

Common fields: seq (monotonic, also the SSE id), ts (seconds since run start), run_id, type.
"""
from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Annotated, Literal, Optional, Union

from pydantic import BaseModel, Field, TypeAdapter


class _E(BaseModel):
    seq: int = 0
    ts: float = 0.0
    run_id: str = ""


class RunStarted(_E):
    type: Literal["run.started"] = "run.started"
    repo: str
    bug_id: str
    n_worlds: int
    model: str
    max_rounds: int
    worlds_per_sandbox: int = 1


class BaseReady(_E):
    type: Literal["base.ready"] = "base.ready"
    setup_ms: int
    sandbox_id: str
    tests_total: int
    failing_tests: list[str]
    error_summary: str


class BaseTests(_E):
    type: Literal["base.tests"] = "base.tests"
    test_ids: list[str]


class Hypothesis(BaseModel):
    id: str
    label: str
    rationale: str = ""


class HypothesesProposed(_E):
    type: Literal["hypotheses.proposed"] = "hypotheses.proposed"
    items: list[Hypothesis]


class UniverseForked(_E):
    type: Literal["universe.forked"] = "universe.forked"
    id: str
    parent_id: Optional[str]
    round: int
    fork_ms: int
    hypothesis_id: str
    sandbox_id: str


class PatchProposed(_E):
    type: Literal["patch.proposed"] = "patch.proposed"
    id: str
    files: list[str]
    lines_added: int
    lines_removed: int


class PatchApplied(_E):
    type: Literal["patch.applied"] = "patch.applied"
    id: str


RejectReason = Literal["no_match", "parse_error", "touches_tests", "skip_injection", "empty", "collect_shrank"]


class PatchRejected(_E):
    type: Literal["patch.rejected"] = "patch.rejected"
    id: str
    reason: RejectReason


class TestProgress(_E):
    type: Literal["test.progress"] = "test.progress"
    id: str
    results: str
    passed: int
    failed: int
    total: int
    tail: list[str] = Field(default_factory=list)


class UniverseObserved(_E):
    type: Literal["universe.observed"] = "universe.observed"
    id: str
    status: Literal["green", "red", "stillborn"]
    failing: list[str]
    first_error: str
    duration_ms: int
    collected: int


class RoundStarted(_E):
    type: Literal["round.started"] = "round.started"
    round: int
    parents: list[str]


class UniverseDisposed(_E):
    type: Literal["universe.disposed"] = "universe.disposed"
    id: str


class Collapse(_E):
    type: Literal["collapse"] = "collapse"
    winner_id: Optional[str]
    hypothesis_id: Optional[str]
    diff: str
    pr_markdown: str


class RunStats(BaseModel):
    worlds_created: int
    worlds_disposed: int
    merged: int
    fork_ms_p50: int
    fork_ms_p95: int
    wall_ms: int
    tokens_prompt: int
    tokens_completion: int
    nosana_requests: int
    est_cost_usd: float
    sandboxes_used: int = 0


class RunFinished(_E):
    type: Literal["run.finished"] = "run.finished"
    stats: RunStats


class RunFailed(_E):
    type: Literal["run.failed"] = "run.failed"
    stage: str
    message: str


Event = Annotated[Union[RunStarted, BaseReady, BaseTests, HypothesesProposed, UniverseForked, PatchProposed,
                        PatchApplied, PatchRejected, TestProgress, UniverseObserved, RoundStarted,
                        UniverseDisposed, Collapse, RunFinished, RunFailed], Field(discriminator="type")]
EVENT = TypeAdapter(Event)
EVENT_LIST = TypeAdapter(list[Event])


class EventBus:
    """Assigns seq/ts, appends to runs/<run_id>/events.jsonl, and fans out to subscribers."""

    def __init__(self, run_id: str, root: Path | None = None, t0: float | None = None):
        self.run_id, self.seq, self.t0 = run_id, 0, t0 if t0 is not None else time.monotonic()
        self.events: list[dict] = []
        self.subs: list[asyncio.Queue] = []
        self.done = False
        self.path = (root / run_id / "events.jsonl") if root else None
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)

    def emit(self, ev: BaseModel, ts: float | None = None) -> dict:
        self.seq += 1
        ev.seq, ev.run_id = self.seq, self.run_id
        ev.ts = round(ts if ts is not None else time.monotonic() - self.t0, 3)
        d = ev.model_dump(mode="json")
        self.events.append(d)
        if self.path:
            with self.path.open("a") as f:
                f.write(json.dumps(d, ensure_ascii=False) + "\n")
        for q in self.subs:
            q.put_nowait(d)
        if d["type"] in ("run.finished", "run.failed"):
            self.done = True
            for q in self.subs:
                q.put_nowait(None)
        return d

    def subscribe(self, after: int = 0) -> tuple[list[dict], asyncio.Queue]:
        q: asyncio.Queue = asyncio.Queue()
        self.subs.append(q)
        return [e for e in self.events if e["seq"] > after], q


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
