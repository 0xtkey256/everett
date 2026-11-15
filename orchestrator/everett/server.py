"""FastAPI control tower.

POST /runs              (header X-Everett-Admin)  -> {run_id}; one run at a time (409 otherwise)
GET  /runs/{id}/events  SSE; resends after Last-Event-ID, then follows; keep-alive every 15 s
GET  /runs/{id}/log.json full event list (replay)
GET  /runs/latest       {run_id} of the most recent run (lets the phone page find the live run)
GET  /healthz
"""
from __future__ import annotations

import asyncio
import json
import uuid
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from . import config
from .events import EventBus, load_jsonl
from .nosana import Nosana
from .run import Spec, orchestrate
from .worlds import Worlds

ROOT = config.ROOT
app = FastAPI(title="Everett")
app.add_middleware(CORSMiddleware, allow_origins=config.CORS_ORIGINS, allow_methods=["GET", "POST"],
                   allow_headers=["X-Everett-Admin", "Last-Event-ID", "Content-Type"])
BUSES: dict[str, EventBus] = {}
STATE = {"active": None, "latest": None}


class RunReq(BaseModel):
    bug: str = "mercantile/xy-swap"
    n_worlds: int = 32
    n_boxes: int = 8
    max_rounds: int = 2


def load_bug(bug: str) -> Spec:
    d = ROOT / "bugs" / bug
    meta = {}
    for line in (d / "meta.yaml").read_text().splitlines():
        if ":" in line and not line.startswith(" "):
            k, v = line.split(":", 1)
            v = v.strip()
            if len(v) >= 2 and v[0] == v[-1] == '"':
                v = v[1:-1]          # only unwrap fully quoted values; keep quotes inside commands
            meta[k.strip()] = v
    repo = meta.get("repo", "").removeprefix("https://github.com/").removesuffix(".git")
    truth = [int(x) for x in meta["truth"].split(",")] if meta.get("truth") else None
    return Spec(repo=repo, bug_id=bug.replace("/", "-"), bug_patch=(d / "bug.patch").read_text(),
                snapshot=meta.get("snapshot", "everett-base-ct"), probe=meta.get("probe") or None,
                landmark=meta.get("landmark"), truth=truth)


async def _run(run_id: str, req: RunReq):
    spec = load_bug(req.bug)
    spec.n_worlds, spec.n_boxes, spec.max_rounds = req.n_worlds, req.n_boxes, req.max_rounds
    try:
        await orchestrate(spec, BUSES[run_id], Worlds(run_id, spec.snapshot, spec.probe), Nosana())
    finally:
        STATE["active"] = None


@app.get("/healthz")
def healthz():
    return {"ok": True, "active": STATE["active"]}


@app.post("/runs")
async def start(req: RunReq, x_everett_admin: str = Header(default="")):
    if not config.ADMIN_TOKEN or x_everett_admin != config.ADMIN_TOKEN:
        raise HTTPException(401, "admin token required")
    if STATE["active"]:
        raise HTTPException(409, f"run {STATE['active']} is still going")
    run_id = uuid.uuid4().hex[:10]
    BUSES[run_id] = EventBus(run_id, root=config.RUNS)
    STATE["active"] = STATE["latest"] = run_id
    asyncio.create_task(_run(run_id, req))
    return {"run_id": run_id}


@app.get("/runs/latest")
def latest():
    return {"run_id": STATE["latest"], "active": STATE["active"]}


def _events_of(run_id: str) -> list[dict]:
    if run_id in BUSES:
        return BUSES[run_id].events
    p = config.RUNS / run_id / "events.jsonl"
    if not p.exists():
        raise HTTPException(404, "unknown run")
    return load_jsonl(p)


@app.get("/runs/{run_id}/log.json")
def log(run_id: str):
    return _events_of(run_id)


@app.get("/runs/{run_id}/events")
async def events(run_id: str, request: Request, last_event_id: str | None = Header(default=None)):
    after = int(last_event_id or request.query_params.get("after", 0) or 0)
    bus = BUSES.get(run_id)
    if bus is None:
        past = _events_of(run_id)

        async def replay():
            for e in past:
                if e["seq"] > after:
                    yield {"id": str(e["seq"]), "data": json.dumps(e, ensure_ascii=False)}
        return EventSourceResponse(replay(), ping=15)
    backlog, q = bus.subscribe(after)

    async def gen():
        try:
            for e in backlog:
                yield {"id": str(e["seq"]), "data": json.dumps(e, ensure_ascii=False)}
            if bus.done and not backlog or (backlog and backlog[-1]["type"] in ("run.finished", "run.failed")):
                return
            while True:
                e = await q.get()
                if e is None:
                    return
                yield {"id": str(e["seq"]), "data": json.dumps(e, ensure_ascii=False)}
        finally:
            if q in bus.subs:
                bus.subs.remove(q)
    return EventSourceResponse(gen(), ping=15)
