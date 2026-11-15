"""Judging worlds. The rules are fixed and are never relaxed to make a demo pass."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Outcome:
    id: str
    results: dict[str, str]          # test_id -> passed/failed/error/skipped
    collected: int
    diff_lines: int = 0
    finished_at: float = 0.0
    status: str = "red"
    failing: list[str] = field(default_factory=list)


def judge(o: Outcome, base_failing: set[str], base_passing: set[str], base_collected: int) -> Outcome:
    """green = every originally failing test passes AND nothing that passed before regresses.
    stillborn = fewer tests collected than the base (tests deleted or import broken)."""
    if o.collected < base_collected:
        o.status, o.failing = "stillborn", []
        return o
    bad = {t for t, r in o.results.items() if r in ("failed", "error")}
    missing = {t for t in base_failing | base_passing if t not in o.results}
    o.failing = sorted(bad | missing)
    fixed = all(o.results.get(t) == "passed" for t in base_failing)
    regressed = any(o.results.get(t) != "passed" for t in base_passing)
    o.status = "green" if fixed and not regressed else "red"
    return o


def winner(outcomes: list[Outcome]) -> Outcome | None:
    greens = [o for o in outcomes if o.status == "green"]
    return min(greens, key=lambda o: (o.diff_lines, o.finished_at)) if greens else None


def beam(outcomes: list[Outcome], base_fail_count: int, k: int = 4) -> list[Outcome]:
    """Red worlds that got closer than the base, fewest failures first."""
    reds = [o for o in outcomes if o.status == "red" and len(o.failing) < base_fail_count]
    return sorted(reds, key=lambda o: (len(o.failing), o.diff_lines, o.finished_at))[:k]
