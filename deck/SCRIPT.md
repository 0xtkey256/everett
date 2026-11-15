# Everett — pitch script (2:30)

_≈ 382 words at ~150 words/min. Stage directions in [brackets]._

## 1. Title  (0:00–0:09)

Hi, I'm Taiki. This is Everett. Generate many fixes, run all of them, and keep only what's proven. Many-worlds debugging, for satellite pipelines.

## 2. Why now  (0:09–0:34)

Two signals from this fall. Anthropic's engineering blog says it moved its monorepo off Git, to a new system called Scion, and merges per day went from about twenty-five hundred to over thirty thousand. GitHub rebuilt its Git storage so thousands of agents can push to one repository at once. Writing code is nearly free. The bottleneck moved to deciding what to keep.

## 3. The problem  (0:34–0:53)

Yet when CI goes red, we still debug serially: one person, or one AI guess at a time. A single model sample is usually wrong, and you can't trust it until it runs. In satellite pipelines, a one-character bug doesn't crash. It silently fetches the wrong place on Earth.

## 4. Hugh Everett III  (0:53–1:09)

The name comes from Hugh Everett. His 1957 thesis said every possible outcome happens, each in its own branch: many worlds. So Everett doesn't guess which fix is right. It lets every fix happen in its own world, then observes.

## 5. How it works  (1:09–1:35)

Here's the loop. On Nosana, Qwen 2.5 Coder proposes four hypotheses and thirty-two patches. A cheat filter disqualifies anything that touches tests or config, or sneaks in a skip. Each survivor gets its own world on Daytona and runs the full test suite. Green means every failing test passes, with zero regressions. Nothing green? Branch again from the closest worlds. Then collapse: the smallest green diff wins.

## 6. The demo result  (1:35–1:57)

[switch to the live site] This is a real run. We broke mercantile, the map-tile library used by satellite-imagery pipelines, by swapping x and y. Ask for Tokyo Tower, and you get polar ice at eighty degrees south. Thirty-two worlds, four found the fix, and the smallest diff wins: one line, a hundred thirty-six tests green, fifty-three seconds end to end. [back to the slides]

## 7. Daytona & sandbox.fork()  (1:57–2:11)

Everett is designed around Daytona's sandbox fork: clone a running, already-built world. Fork isn't enabled on our tier yet, so today we fan out from a snapshot, and worlds still start in about two seconds.

## 8. Nosana  (2:11–2:23)

The model is a seven-billion-parameter coder on one RTX 3090 on Nosana. A whole run costs about a fifth of a cent. Width is GPU time, not a token bill.

## 9. Closing  (2:23–2:30)

Agents shouldn't guess. Branch the world, then observe. The live replay and the code are linked here. Thank you.
