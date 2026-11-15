# Day-of runbook

| Time | Do |
|---|---|
| 15:00–15:10 | `.env` keys in place → `make test` → Nosana `/v1/models` returns `coder` |
| 15:10–15:35 | `make fix` once end to end; fix anything that breaks |
| 15:35–15:50 | Publish the site (GitHub Pages) and check the QR on a phone |
| 15:50–16:05 | Save a successful run as `web/replays/live.json` (backup for the demo) |
| 16:05–16:15 | Rehearse twice, timed at 2 minutes |

After the demo: `make cleanup`, stop the Nosana deployment.
