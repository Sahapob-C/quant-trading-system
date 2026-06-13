"""Runtime settings and broker credentials.

Secrets come from a ``.env`` file (never commit it — it's in .gitignore). Copy
``.env.example`` to ``.env`` and paste your Alpaca **paper** keys to get started.
"""
from __future__ import annotations

import os

from dotenv import load_dotenv

# Load .env from the project root if present (no-op if missing).
load_dotenv()


def get_alpaca_creds() -> tuple[str, str]:
    key = os.getenv("ALPACA_API_KEY")
    secret = os.getenv("ALPACA_SECRET_KEY")
    if not key or not secret:
        raise RuntimeError(
            "Missing Alpaca credentials. Copy .env.example to .env and set "
            "ALPACA_API_KEY and ALPACA_SECRET_KEY (use your *paper* keys)."
        )
    return key, secret


def use_paper() -> bool:
    """Default to paper trading unless ALPACA_PAPER is explicitly 'false'."""
    return os.getenv("ALPACA_PAPER", "true").strip().lower() != "false"
