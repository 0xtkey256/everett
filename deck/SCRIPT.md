# Everett — pitch script (2:37)

_≈ 440 words; the timings assume ~165 words/min (≈ 2:56 at 150). Stage directions in [brackets]._

## 1. Title  (0:00–0:12)

Everyone is coding right now — well, not coding, but building. I'm Taiki. This is Everett: when CI is red, try thirty-two fixes at once, and keep only what the tests prove.

## 2. Why now  (0:12–0:35)

Why now? Anthropic's blog says it moved its monorepo off Git to a new system, Scion, and merges per day went from about twenty-five hundred to over thirty thousand. GitHub rebuilt its storage so thousands of agents can push to one repo at once. AI writes code faster than we can check it. The bottleneck is choosing what to keep.

## 3. The problem  (0:35–0:53)

And a red CI blocks everyone. Someone stops, reads logs, guesses a fix, and waits for CI again. One AI suggestion is just a guess; you only know after it runs. In data pipelines, a one-line bug may not even crash. It quietly returns the wrong data.

## 4. Hugh Everett III  (0:53–1:10)

The name comes from Hugh Everett. In 1957 he proposed that every possible outcome happens, each in its own branch. In his words: not a life line, but a life tree. That's Everett: one broken build becomes thirty-two copies, and the tests pick the branch we keep.

## 5. How it works  (1:10–1:36)

Here's how. CI fails. A small AI model suggests four causes and writes thirty-two fixes. Fixes that edit or skip tests are thrown out. Each one left gets its own Daytona sandbox and runs every test. A fix passes only if the failing tests pass and nothing else breaks. None pass? Try again from the closest ones. Then merge the smallest passing fix, and delete the rest.

## 6. Example: satellite imagery  (1:36–1:56)

I work with satellite imagery at Solafune, so here's an example from our world. [switch to the live site] We broke one line of mercantile, an open-source map-tile library. Ask it for Tokyo Tower, and it downloads polar ice. Thirty-two worlds, four found the fix, and the smallest won: one line, all hundred thirty-six tests green, in fifty-three seconds. Why thirty-two? One AI attempt fixes this bug under five percent of the time. With thirty-two worlds, six of seven runs found it. [back to the slides]

## 7. Daytona & sandbox.fork()  (1:56–2:15)

Huge thanks to the Daytona devs: sandbox.fork() is what grows our life tree. One call clones a running sandbox, copy-on-write, with everything already installed. Fork a fork, and it branches again. That works for any agent that explores, not just CI. It's not on our tier yet, so today we start from snapshots.

## 8. Nosana  (2:15–2:33)

The model runs on our own GPU: one RTX 3090 rented from Nosana for nineteen cents an hour. vLLM serves it as an OpenAI-style API. Each request asks for eight patches at once, back in about two seconds. A whole run costs about a third of a cent.

## 9. Proof: it really ran

[show for a few seconds while finishing the Nosana line — real Daytona and Nosana dashboards from today]

## 10. Closing  (2:33–2:37)

Agents shouldn't guess. Branch the world, then observe. Thank you.
