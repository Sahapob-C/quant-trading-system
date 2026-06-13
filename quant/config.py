"""Tiny YAML config loader.

Backtests can be driven entirely from the command line, but a config file keeps
runs reproducible and reviewable. See ``config/example.yaml``.
"""
from __future__ import annotations

from typing import Any, Dict


def load_config(path: str) -> Dict[str, Any]:
    import yaml

    with open(path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}
