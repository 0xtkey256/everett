# Everett — many-worlds debugging for CI/CD

**CI is red? Try 32 fixes at once. Keep only what the tests prove.**

When your tests fail, Everett opens 32 parallel worlds — isolated sandboxes on **Daytona** — and an open AI model on our own **Nosana** GPU writes a different fix in each. Every world runs the full test suite; only the fix that passes everything (and breaks nothing else) is merged. The other 31 are thrown away. The agent doesn't guess — it branches, then observes.

**Watch a real run:** https://0xtkey256.github.io/everett/?replay=tokyo  ·  EN / 日本語 switch in the header

**Today's example comes from the satellite-imagery world:** a one-line bug in [mapbox/mercantile](https://github.com/mapbox/mercantile) (the map-tile library imagery pipelines use to find "which tile covers this place") makes `tile()` return x and y swapped — ask for Tokyo Tower and you get **polar ice at 80°S**. Every world also asks its own patched code where Tokyo Tower is, and the wall shows the real satellite image each world would fetch. In the recorded run 4 of 32 worlds found the fix and the smallest diff was merged (`return Tile(ytile, xtile, zoom)` → `return Tile(xtile, ytile, zoom)`, 136/136 tests, 53 s).

## Why now
Code is nearly free to write: agents now produce more changes than people can review, and source control is being rebuilt to absorb that volume. The bottleneck moved from *writing* to *choosing what to keep*. Execution environments should be **disposable by default** — spin up one per idea, run them all, merge the one that's proven. Everett is that selection layer.

## How it works
1. **Base world** — a Daytona sandbox from a pre-built snapshot applies the breaking change and runs the suite (136 tests, 20 failing in the satellite demo) plus a probe: which tile is Tokyo Tower in?
2. **Hypotheses** — function-level fault localization picks the relevant functions; Qwen2.5-Coder-7B on Nosana reads them with the failing tests and the observed symptom, and proposes 4 *different* root causes.
3. **32 patches** — for each hypothesis, one request with `n=8` returns 8 candidate patches (SEARCH/REPLACE), at different temperatures.
4. **Cheat filter (before anything runs)** — patches that edit tests or test config, or inject `skip`/`xfail`/`exit`, are disqualified. Patches that don't apply are discarded.
5. **32 worlds** — 8 Daytona sandboxes × 4 isolated checkouts each run the full suite in parallel.
6. **Judge** — a world is *green* only if every failing test passes **and nothing regresses**; collecting fewer tests than the base is disqualified.
7. **Branch again** — if no world is green, the 4 closest worlds branch into 4 children each, building on their own patch.
8. **Collapse** — the smallest green diff wins; the PR text is generated; all other worlds are disposed.

The UI is rebuilt entirely from an event stream, so the same screen plays live (SSE) or as a replay.

## Partner technologies

| | Where | What it does |
|---|---|---|
| **Daytona** | `orchestrator/everett/worlds.py`, `scripts/build_snapshot.py`, `scripts/probe_*.py` | Pre-built snapshot (Python 3.12 + repo + deps). 1 base + 8 world sandboxes created in parallel (~1.4–2.0 s each), 4 isolated checkouts per sandbox, `process.exec` to run pytest, `fs.upload_file` to place patches, labels + TTL on every sandbox, disposal at the end. |
| **Nosana** | `orchestrator/everett/nosana.py`, `nosana/job.json` | One NVIDIA RTX 3090 (24 GB) rented from Nosana's decentralized GPU network ($0.19/h). The Nosana job is a container spec: vLLM 0.8.5 serving **Qwen2.5-Coder-7B-Instruct** as `coder` on port 9000 (OpenAI-compatible, health-checked on `/v1/models`, public HTTPS endpoint; stateless deployment is rescheduled on another GPU if a host fails). Engine: 14.25 GiB weights, 16k context, 113k-token KV cache (~7 full-length requests at once). Hypotheses in JSON mode; each patch request uses `n=8` — vLLM computes the shared prompt once and samples 8 fixes in parallel (~2.3 s). A run ≈ 35k tokens ≈ $0.003 of GPU time. |

## Measured (Daytona, Tier 1 account)

| | |
|---|---|
| Sandbox start from snapshot (8 in parallel) | p50 **2.0 s**, p95 2.8 s |
| Base + 1 world sandbox ready (incl. bug + 2 checkouts) | **3.3 s** |
| Full suite (133 tests) in a world | **~1.8 s** |
| Concurrency cap | 10 vCPU total on Tier 1 → 1 base + 8 boxes × 4 worlds |
| `fork()` | not available: requires the `linux-vm` class, which has no runners for this org (see `docs/eval-results.md`) |

## Run it
```bash
uv venv -p 3.12 .venv && uv pip install --python .venv/bin/python -e "orchestrator[dev]"
cp .env.example .env          # DAYTONA_API_KEY, NOSANA_BASE_URL (…/v1), EVERETT_ADMIN_TOKEN
make test                     # 29 pytest + 3 node tests, no network
make snapshot                 # once: builds the base snapshot on Daytona
make fix                      # one live run in the terminal, saves web/replays/live.json
make serve                    # FastAPI + SSE on :8000 (POST /runs needs X-Everett-Admin)
make web                      # static UI on :8790  → /?replay=demo or /?src=<sse url>
make cleanup                  # deletes only sandboxes labelled app=everett
```

## Honest limits
- The demo bug is injected into a real open-source library (python-slugify, MIT); the fixer never sees the injected patch.
- 7B models make mistakes — that's the point: width plus a strict judge beats one confident guess. Results per run are in `docs/eval-results.md`, unedited.
