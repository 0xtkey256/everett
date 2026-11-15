# Everett — pitch script (2:27)

_≈ 409 words at ~150 words/min. Stage directions in [brackets]._

## 1. Title  (0:00–0:12)

Everyone is coding right now — well, not coding, but building. I'm Taiki. This is Everett: when CI is red, try thirty-two fixes at once, and keep only what the tests prove.

## 2. Why now  (0:12–0:35)

Why now? Anthropic's blog says it moved its monorepo off Git to a new system, Scion, and merges per day went from about twenty-five hundred to over thirty thousand. GitHub rebuilt its storage so thousands of agents can push to one repo at once. AI writes code faster than we can check it. The bottleneck is choosing what to keep.

## 3. The problem  (0:35–0:53)

And a red CI blocks everyone. Someone stops, reads logs, guesses a fix, and waits for CI again. One AI suggestion is just a guess; you only know after it runs. In data pipelines, a one-line bug may not even crash. It quietly returns the wrong data.

## 4. Hugh Everett III  (0:53–1:08)

The name comes from Hugh Everett. In 1957 he proposed that every possible outcome happens, each in its own branch. So Everett doesn't guess which fix is right. It tries every fix in its own world, then keeps the one that works.

## 5. How it works  (1:08–1:34)

Here's how. CI fails. A small AI model suggests four causes and writes thirty-two fixes. Fixes that edit or skip tests are thrown out. Each one left gets its own Daytona sandbox and runs every test. A fix passes only if the failing tests pass and nothing else breaks. None pass? Try again from the closest ones. Then merge the smallest passing fix, and delete the rest.

## 6. Example: satellite imagery  (1:34–1:54)

I work with satellite imagery at Solafune, so here's an example from our world. [switch to the live site] We broke one line of mercantile, an open-source map-tile library. Ask it for Tokyo Tower, and it downloads polar ice. Thirty-two worlds, four found the fix, and the smallest won: one line, all hundred thirty-six tests green, in fifty-three seconds. Why thirty-two? One AI attempt fixes this bug under five percent of the time. With thirty-two worlds, six of seven runs found it. [back to the slides]

## 7. Daytona & sandbox.fork()  (1:54–2:05)

Everett is designed around Daytona's sandbox fork: copy a running, ready-to-test world. Fork isn't on our tier yet, so today worlds start from a snapshot, in about two seconds.

## 8. Nosana  (2:05–2:23)

The model runs on our own GPU: one RTX 3090 rented from Nosana for nineteen cents an hour. vLLM serves it as an OpenAI-style API. Each request asks for eight patches at once, back in about two seconds. A whole run costs about a third of a cent.

## 9. Proof: it really ran

[show for a few seconds while finishing the Nosana line — real Daytona and Nosana dashboards from today]

## 10. Closing  (2:23–2:27)

Agents shouldn't guess. Branch the world, then observe. Thank you.
