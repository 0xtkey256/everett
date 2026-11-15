"""Nosana-hosted Qwen2.5-Coder (vLLM, OpenAI-compatible): hypotheses, then many patches per hypothesis via `n`."""
from __future__ import annotations

import asyncio
import json
import re

import httpx

from . import config

SYSTEM_PATCH = """You fix a failing Python test suite by editing SOURCE files only.
Output ONLY one or more SEARCH/REPLACE blocks, nothing else. The first line of each block is the real
relative path of the file you edit, exactly as given in the context headers (for example {path}):

{path}
<<<<<<< SEARCH
exact lines copied from the current file
=======
replacement lines
>>>>>>> REPLACE

Rules: SEARCH must match the file exactly (including indentation) and appear once. Keep the change minimal.
Never edit tests, conftest.py or config files. Never skip, xfail or exit."""


class Nosana:
    def __init__(self, base_url: str | None = None, model: str | None = None, concurrency: int = 8):
        self.base = (base_url or config.NOSANA_BASE_URL).rstrip("/")
        self.model = model or config.NOSANA_MODEL
        self.sem = asyncio.Semaphore(concurrency)
        self.tokens_prompt = self.tokens_completion = self.requests = 0

    async def _chat(self, messages, n=1, temperature=0.3, max_tokens=900, json_mode=False) -> list[str]:
        body = {"model": self.model, "messages": messages, "n": n, "temperature": temperature, "max_tokens": max_tokens}
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        async with self.sem, httpx.AsyncClient(timeout=90) as c:
            r = await c.post(f"{self.base}/chat/completions", json=body,
                             headers={"Authorization": f"Bearer {config.NOSANA_API_KEY}"})
            r.raise_for_status()
            d = r.json()
        self.requests += 1
        u = d.get("usage") or {}
        self.tokens_prompt += u.get("prompt_tokens", 0)
        self.tokens_completion += u.get("completion_tokens", 0)
        return [ch["message"]["content"] or "" for ch in d["choices"]]

    async def hypotheses(self, context: str, k: int = 4) -> list[dict]:
        msg = [{"role": "system", "content": "You are a senior Python debugger. Reply with JSON only."},
               {"role": "user", "content": f"{context}\n\nGive {k} DIFFERENT hypotheses for the root cause. "
                f'JSON: {{"hypotheses":[{{"id":"h1","label":"<=4 words","rationale":"one sentence"}}]}}'}]
        for attempt in range(2):
            try:
                txt = (await self._chat(msg, temperature=0.3, max_tokens=500, json_mode=True))[0]
                hs = json.loads(re.search(r"\{.*\}", txt, re.S).group(0))["hypotheses"]
                out = []
                for i, h in enumerate(hs[:k]):
                    label = " ".join(str(h.get("label", "")).split()[:4]) or f"hypothesis {i + 1}"
                    out.append({"id": f"h{i + 1}", "label": label, "rationale": str(h.get("rationale", ""))[:200]})
                if out:
                    return out
            except Exception:  # noqa: BLE001
                continue
        return [{"id": "h1", "label": "generic fix", "rationale": "hypothesis generation failed"}]

    async def patches(self, context: str, hypothesis: dict, n: int, temperature: float,
                      extra: str = "", example_path: str = "pkg/module.py") -> list[str]:
        msg = [{"role": "system", "content": SYSTEM_PATCH.replace("{path}", example_path)},
               {"role": "user", "content": f"{context}\n\nHypothesis to pursue: {hypothesis['label']} — "
                f"{hypothesis.get('rationale', '')}\n{extra}\nWrite the fix."}]
        return await self._chat(msg, n=n, temperature=temperature, max_tokens=700)
