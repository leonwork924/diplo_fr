"""postings.py — Suivi des postes actifs, pour l'estimation "~4 ans depuis la
nomination" quand aucune annonce de départ réelle n'est publiée (cas des
consuls généraux et attachés de défense, qui n'ont pas de décret de
cessation séparé -- voir extract.py).

Une entrée est retirée dès qu'un vrai signal de départ est vu pour cette
personne (cessation d'ambassadeur, ou remplacement mentionné pour un
consul) -- l'estimation à 4 ans ne sert que de filet de sécurité quand
aucun signal réel n'arrive.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path

POSTINGS_PATH = Path(__file__).resolve().parent.parent / "data" / "active_postings.json"

TENURE_DAYS = 4 * 365  # ~4 ans -- estimation, pas une durée officielle fixe


def load_postings() -> list[dict]:
    if not POSTINGS_PATH.exists():
        return []
    return json.loads(POSTINGS_PATH.read_text(encoding="utf-8"))


def save_postings(postings: list[dict]) -> None:
    POSTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    POSTINGS_PATH.write_text(
        json.dumps(postings, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def add_posting(postings: list[dict], *, jorf_id: str, name: str, category: str,
                 location: str, nomination_date: str) -> None:
    postings.append({
        "jorf_id": jorf_id, "name": name, "category": category,
        "location": location, "nomination_date": nomination_date,
        "flagged_4y": False,
    })


def remove_posting(postings: list[dict], name: str) -> None:
    """Retire un poste actif quand un vrai signal de départ arrive pour cette
    personne -- comparaison par nom exact, best-effort (pas d'identifiant
    stable reliant une nomination à sa cessation dans les données JORF)."""
    postings[:] = [p for p in postings if p["name"] != name]


def due_for_4y_check(postings: list[dict], today: date | None = None) -> list[dict]:
    """Postes ayant dépassé ~4 ans et pas encore signalés."""
    today = today or date.today()
    due = []
    for p in postings:
        if p.get("flagged_4y"):
            continue
        try:
            nom_date = datetime.fromisoformat(p["nomination_date"]).date()
        except (ValueError, KeyError):
            continue
        if today - nom_date >= timedelta(days=TENURE_DAYS):
            due.append(p)
    return due
