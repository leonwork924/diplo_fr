"""seen.py — Mémoire du déjà-vu : évite de renotifier chaque jour les mêmes
nominations. Un simple fichier JSON (liste d'IDs JORFTEXT), committé dans le
repo comme le reste des fichiers de données de ce projet."""

from __future__ import annotations

import json
from pathlib import Path

SEEN_PATH = Path(__file__).resolve().parent.parent / "data" / "seen.json"


def load_seen() -> set[str]:
    if not SEEN_PATH.exists():
        return set()
    return set(json.loads(SEEN_PATH.read_text(encoding="utf-8")))


def save_seen(ids: set[str]) -> None:
    SEEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    SEEN_PATH.write_text(
        json.dumps(sorted(ids), ensure_ascii=False, indent=2), encoding="utf-8"
    )
