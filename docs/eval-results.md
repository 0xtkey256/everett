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
