"""Reads environment once. Keys live only in .env (never printed or committed)."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNS = ROOT / "runs"


def _load():
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.split(" #")[0].strip())


_load()
NOSANA_BASE_URL = os.environ.get("NOSANA_BASE_URL", "").rstrip("/")
NOSANA_MODEL = os.environ.get("NOSANA_MODEL", "coder")
NOSANA_API_KEY = os.environ.get("NOSANA_API_KEY", "none")
ADMIN_TOKEN = os.environ.get("EVERETT_ADMIN_TOKEN", "")
CORS_ORIGINS = [o for o in os.environ.get("EVERETT_CORS", "http://localhost:8790,http://127.0.0.1:8790,https://0xtkey256.github.io").split(",") if o]


def require(name: str) -> str:
    v = os.environ.get(name, "")
    if not v:
        raise RuntimeError(f"{name} is not set (.env)")
    return v
