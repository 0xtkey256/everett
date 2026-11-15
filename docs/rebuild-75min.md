# Rebuilding in 75 minutes (if pre-written code isn't allowed)

1. (10 min) `events.py` types + `fake.py` → replay JSON.
2. (20 min) Static UI: `reducer.js` + `app.js` wall/meters/collapse; play the fake.
3. (20 min) `patches.py` (SEARCH/REPLACE + cheat rules) and `selection.py` (green = fixed + no regressions).
4. (15 min) `worlds.py` (snapshot → N sandboxes × K checkouts, `process.exec` pytest + junit) and `nosana.py` (`n` candidates per hypothesis).
5. (10 min) `run.py` round 1 only; save a live run as a replay.
