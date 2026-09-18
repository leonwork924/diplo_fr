#!/usr/bin/env python3
"""
main.py — Orchestration complète.

Logique de routage (confirmée avec Leon, 18/09/2026) : ce qui compte, c'est
où la personne se trouve PHYSIQUEMENT maintenant, pas la destination finale.
- Nomination (event="arrivee") = la personne est encore en France, sur le
  point de partir -> notif à Sophie/Dorina (l'équipe France peut la joindre
  tant qu'elle est là).
- Départ (event="depart") = la personne est actuellement dans le pays
  qu'elle quitte -> notif à LA FILIALE DE CE PAYS (celui qu'elle quitte, pas
  la destination suivante -- on ne la connaît généralement pas).

Trois sources de "départ", pas juste une :
1. Vraie cessation de fonction publiée au JORF (ambassadeurs seulement --
   voir extract.py, pas de décret équivalent trouvé pour consuls/attachés).
2. Prédécesseur mentionné dans la nomination du remplaçant (consuls
   généraux) -- on en déduit un départ pour le prédécesseur, même lieu.
3. Estimation à ~4 ans depuis la nomination, si aucun signal réel 1 ou 2
   n'est arrivé entre-temps (voir postings.py) -- marqué comme estimation
   dans l'email, pas présenté comme confirmé.

Usage : python main.py [--days-back 8] [--dry-run] [--test-recipient EMAIL] [--limit N]
"""

from __future__ import annotations

import argparse
import os
from dataclasses import replace
from datetime import date, timedelta

import requests

from extract import Nomination, extract_nomination
from fetch_jorf import fetch_all_nominations
from match_location import resolve
from notify import build_email
from postings import add_posting, due_for_4y_check, load_postings, remove_posting, save_postings
from routing import ROUTING
from seen import load_seen, save_seen

BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"
SENDER = {"name": "Diplo FR — veille JORF", "email": os.environ.get("BREVO_SENDER_EMAIL", "")}


def send_email(to_emails: list[str], subject: str, body: str) -> None:
    api_key = os.environ.get("BREVO_API_KEY")
    if not api_key:
        raise RuntimeError("BREVO_API_KEY manquant -- voir README pour la configuration du secret.")
    resp = requests.post(
        BREVO_API_URL,
        headers={"api-key": api_key, "Content-Type": "application/json"},
        json={"sender": SENDER, "to": [{"email": e} for e in to_emails], "subject": subject, "textContent": body},
        timeout=30,
    )
    resp.raise_for_status()


def route(nomination: Nomination) -> tuple[str | None, list[str]]:
    """Retourne (branch_key ou None, destinataires) selon la règle
    arrivée->France / départ->pays quitté."""
    if nomination.event == "arrivee":
        return None, ROUTING["France"]
    branch_key = resolve(nomination.category, nomination.location)
    recipients = ROUTING.get(branch_key) if branch_key else None
    return branch_key, (recipients if recipients else ROUTING["France"])


class Budget:
    """Petit compteur partagé pour --limit, utilisé par les 3 sources de notifs."""
    def __init__(self, limit: int | None):
        self.limit = limit
        self.sent = 0

    def available(self) -> bool:
        return self.limit is None or self.sent < self.limit


def dispatch(nomination: Nomination, *, args, budget: Budget, note: str | None = None) -> bool:
    """Route, construit l'email, envoie (ou affiche en dry-run). Retourne
    True si une notification a été traitée (envoyée ou affichée)."""
    if not budget.available():
        return False
    branch_key, real_recipients = route(nomination)
    recipients = [args.test_recipient] if args.test_recipient else real_recipients

    email = build_email(nomination, branch_key, note=note)
    arrow = f"{nomination.name} [{nomination.event}] -> " + (branch_key or "France (Sophie/Dorina)") + f" -> {real_recipients}"
    if args.test_recipient:
        arrow += f"  [redirigé vers {args.test_recipient}]"
    print(f"  {arrow}")

    if not args.dry_run:
        send_email(recipients, email["subject"], email["body"])
    budget.sent += 1
    return True


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--days-back", type=int, default=8)
    parser.add_argument("--dry-run", action="store_true", help="N'envoie aucun email, affiche seulement.")
    parser.add_argument("--test-recipient", default=None,
                         help="Si fourni, TOUS les emails partent à cette adresse au lieu des vrais destinataires.")
    parser.add_argument("--limit", type=int, default=None,
                         help="Traite au maximum N notifications au total (nominations + départs + estimation 4 ans).")
    args = parser.parse_args()

    date_min = (date.today() - timedelta(days=args.days_back)).isoformat()
    seen = load_seen()
    postings = load_postings()
    budget = Budget(args.limit)

    raw_textes = fetch_all_nominations(date_min)
    print(f"{len(raw_textes)} texte(s) JORF récupéré(s) depuis {date_min}")

    new_count = 0
    for texte in raw_textes:
        if not budget.available():
            print(f"  (--limit {args.limit} atteint, arrêt anticipé)")
            break
        jorf_id = texte["id"]
        if jorf_id in seen:
            continue
        new_count += 1

        nomination = extract_nomination(jorf_id, texte.get("extract", ""))
        if not nomination:
            print(f"  [SAUTÉ] {jorf_id} : extraction impossible (extrait insuffisant ou motif non reconnu)")
            print(f"          extrait brut : {texte.get('extract', '')!r}")
            seen.add(jorf_id)
            continue

        dispatch(nomination, args=args, budget=budget)
        seen.add(jorf_id)

        if nomination.event == "arrivee":
            add_posting(
                postings, jorf_id=jorf_id, name=nomination.name, category=nomination.category,
                location=nomination.location, nomination_date=texte.get("date_publi") or date.today().isoformat(),
            )
        else:
            remove_posting(postings, nomination.name)  # vrai départ vu -> plus besoin de l'estimation à 4 ans

        # Consul général : le prédécesseur mentionné = un départ dérivé, même lieu.
        if nomination.category == "consul_general" and nomination.predecessor:
            synth_id = f"{jorf_id}-predecessor"
            if synth_id not in seen and budget.available():
                predecessor_event = replace(
                    nomination, name=nomination.predecessor, event="depart",
                    predecessor=None, effective_date=None,
                )
                dispatch(predecessor_event, args=args, budget=budget)
                seen.add(synth_id)
                remove_posting(postings, nomination.predecessor)

    # Estimation à 4 ans : postes actifs sans départ confirmé depuis longtemps.
    for p in due_for_4y_check(postings):
        if not budget.available():
            break
        synth = Nomination(
            jorf_id=p["jorf_id"] + "-4y", category=p["category"], name=p["name"],
            location=p["location"], event="depart",
        )
        dispatch(synth, args=args, budget=budget,
                 note="Estimation : ~4 ans depuis la nomination, aucun départ officiel confirmé au JORF.")
        p["flagged_4y"] = True

    if not args.dry_run:
        save_seen(seen)
        save_postings(postings)
    print(f"\n{new_count} nouvelle(s) nomination(s) JORF, {budget.sent} notification(s) "
          f"{'(dry-run, rien envoyé, mémoire non modifiée)' if args.dry_run else 'envoyée(s)'}.")


if __name__ == "__main__":
    main()
