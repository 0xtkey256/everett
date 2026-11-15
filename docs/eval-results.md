# Eval results

## P0 — Daytona fork() (2026-11-15 14:29)

`fork()` (copy-on-write clone) is **not available on this org**:

| Attempt | Result |
|---|---|
| `daytona-small` (container, us) | created in 1.8 s; `fork()` → 422 *Forking is not supported for this sandbox* |
| `daytona-vm`, `daytona-vm-small` (us, eu) | *Snapshot … is not available in region* |
| own snapshot, `sandbox_class=linux-vm`, declarative image | *Declarative (Dockerfile) builds are not supported for the 'linux-vm' sandbox class* |
| own snapshot, `sandbox_class=linux-vm`, image `python:3.12-bookworm` | *No runners are configured in region 'us' for sandbox class 'linux-vm'* |
| container class in `eu` | *Region eu is not available to the organization for class container* |

Conclusion: fork needs the `linux-vm` sandbox class, which has no runners for this org. Ask Daytona to enable it,
or fan out by creating sandboxes from a pre-built snapshot (below).

## P0 fallback — parallel create from snapshot (2026-11-15 14:32, run `create-fc557b`)

Snapshot `everett-base-ct` (python 3.12, git, pytest, python-slugify cloned + installed).

| N | ok | errors | create p50 ms | create p95 ms | create wall ms | pytest p50 ms | pytest p95 ms | pytest wall ms | pytest passed |
|---|---|---|---|---|---|---|---|---|---|
| 8 | 8 | 0 | 2008 | 2823 | 3262 | 1620 | 2069 | 2222 | 8 |
| 16 | 10 | 6 | 1365 | 2308 | 2942 | 1044 | 2164 | 2386 | 10 |
| 32 | 10 | 22 | 1404 | 2095 | 2101 | 1081 | 1552 | 1560 | 10 |

Errors seen:
- `estError: Failed to create sandbox: Total CPU limit exceeded. Maximum allowed: 10.
To increase concurrency limits, upgrade your organization's Tier by visiting https://app.daytona.io/dashboard/limits.`
- `estError: Failed to create sandbox: Total CPU limit exceeded. Maximum allowed: 10.
To increase concurrency limits, upgrade your organization's Tier by visiting https://app.daytona.io/dashboard/limits.`

## Live runs — slugify L1 (word-boundary off-by-one), Qwen2.5-Coder-7B on Nosana, 32 worlds on 8 Daytona sandboxes

| Run | Context / parser change | green | red | stillborn (no_match / parse / other) | wall |
|---|---|---|---|---|---|
| 1 | all sources, placeholder path in prompt | 0 | 0 | 32 (29 / 3 / 0) | 46 s |
| 2 | real path in prompt, retarget by unique match | 0 | 9 | 23 (incl. 7 collection failures) | 54 s |
| 3 | + failing test bodies in context | 0 | 10 | 22 | 46 s |
| 4 | + context = 2 most relevant files only | 0 | 5 | 27 (22 no_match) | 44 s |
| 5 | + whitespace-tolerant unique match with re-indent | **1** | 15 | 16 (13 / 2 / 1 collect_shrank) | **35 s** |

Run 5 winner `w20` (hypothesis "Word Boundary Logic"): `if next_length < max_length:` → `if next_length <= max_length:` —
133/133 tests collected, all 4 failing tests pass, 0 regressions. Nosana: 5 requests, 25.8k prompt + 5.5k completion
tokens, ~$0.002 of GPU time. Replay: `web/replays/real-1.json`.

1 green out of 32 is the point: a single sample would almost certainly have missed it.


## Live runs — mercantile (satellite tile pipeline), probe: tile of Tokyo Tower at z12 (truth x=3637, y=1613)

| Bug | Run | green | red | stillborn | rounds | wall | note |
|---|---|---|---|---|---|---|---|
| sign flip in `_xy` (Tokyo → 35.6°S) | 1 | 0 | 12 | 20 | 1 + crash | 56 s | round-2 prompt exceeded 16k context → fixed |
| sign flip | 2 | 0 | 3 | 29 | 1 | 45 s | whole 23 KB file in context |
| sign flip | 3 | 0 | 23 | 17 | 2 (40 worlds) | 77 s | function-level localization; still unsolved by the 7B model |
| `tile()` x/y swap (Tokyo → 80°S polar ice) | 4 | **4** | 11 | 17 | 1 | 53 s | winner `w07`, smallest diff; replay `web/replays/tokyo.json` |
| x/y swap, via the live tower + tunnel | 5 | 0 | — | — | 2 | 39 s | live UI path verified; model found no fix this time |

Success varies run to run with a 7B model; the replay of run 4 is unedited.
| x/y swap, fork-first mode (fork refused → snapshot fallback) | 6 | **1** | 13 | 18 | 1 | 47 s | winner `w16`; replay `tokyo-run-a.json` |
| x/y swap | 7 | **2** | 21 | 9 | 1 | 47 s | winner `w04`; replay `tokyo-run-b.json` |
| x/y swap | 8 | **1** | 15 | 16 | 1 | 46 s | winner `w11`; replay `tokyo-run-c.json` |

**Reliability on the x/y-swap bug: 4 of 5 live runs found the fix (runs 4, 6, 7, 8), ~46–53 s each; the miss was run 5.**
Each green world is verified by the full suite (136 tests) and the Tokyo Tower probe; nothing is hand-picked.
