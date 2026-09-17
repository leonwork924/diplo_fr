"""routing.py — Charge routing.json (pays -> liste d'emails de filiale)."""

from __future__ import annotations

import json
from pathlib import Path

ROUTING: dict[str, list[str]] = json.loads(
    (Path(__file__).resolve().parent / "routing.json").read_text(encoding="utf-8")
)
