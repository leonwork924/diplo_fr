#!/usr/bin/env python3
"""
main.py — Orchestration complète : récupère les nominations récentes,
extrait, route, notifie les filiales, mémorise ce qui a été traité.

Usage : python main.py [--days-back 8] [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import date, timedelta

from extract import extract_nomination
from fetch_jorf import fetch_all_nominations
from match_location import resolve
from notify import build_email
from routing import ROUTING
from seen import load_seen, save_seen

import requests

BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"
SENDER = {"name": "Diplo FR — veille JORF", "email": os.environ.get("BREVO_SENDER_EMAIL", "")}


def send_email(to_emails: list[str], subject: str, body: str) -> None:
    api_key = os.environ.get("BREVO_API_KEY")
    if not api_key:
        raise RuntimeError("BREVO_API_KEY manquant -- voir README pour la configuration du secret.")
    payload = {
        "sender": SENDER,
        "to": [{"email": e} for e in to_emails],
        "subject": subject,
        "textContent": body,
    }
    resp = requests.post(
        BREVO_API_URL,
        headers={"api-key": api_key, "Content-Type": "application/json"},
        json=payload, timeout=30,
    )
    resp.raise_for_status()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--days-back", type=int, default=8)
    parser.add_argument("--dry-run", action="store_true", help="N'envoie aucun email, affiche seulement.")
    parser.add_argument("--test-recipient", default=None,
                         help="Si fourni, TOUS les emails partent à cette adresse au lieu des vrais destinataires -- "
                              "pour tester un envoi réel sans déranger les filiales.")
    parser.add_argument("--limit", type=int, default=None,
                         help="Traite au maximum N nominations (utile pour un tout premier test réel, ex. --limit 2).")
    args = parser.parse_args()

    date_min = (date.today() - timedelta(days=args.days_back)).isoformat()
    seen = load_seen()

    raw_textes = fetch_all_nominations(date_min)
    print(f"{len(raw_textes)} texte(s) JORF récupéré(s) depuis {date_min}")

    new_count, sent_count = 0, 0
    for texte in raw_textes:
        if args.limit and sent_count >= args.limit:
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
            seen.add(jorf_id)  # évite de retenter indéfiniment sur un texte qui ne s'extrait pas
            continue

        branch_key = resolve(nomination.category, nomination.location)
        recipients = ROUTING.get(branch_key) if branch_key else None
        if not recipients:
            recipients = ROUTING.get("France")  # repli Sophie/Dorina

        real_recipients = recipients
        if args.test_recipient:
            recipients = [args.test_recipient]

        email = build_email(nomination, branch_key)
        print(f"  {nomination.name} -> {branch_key or '(non résolu, repli Sophie/Dorina)'} -> "
              f"{real_recipients}" + (f"  [redirigé vers {args.test_recipient} pour ce test]" if args.test_recipient else ""))

        if not args.dry_run:
            send_email(recipients, email["subject"], email["body"])
        sent_count += 1
        seen.add(jorf_id)

    if not args.dry_run:
        save_seen(seen)
    print(f"\n{new_count} nouvelle(s) nomination(s), {sent_count} notification(s) "
          f"{'(dry-run, rien envoyé, mémoire non modifiée)' if args.dry_run else 'envoyée(s)'}.")


if __name__ == "__main__":
    main()
