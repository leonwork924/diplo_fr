"""notify.py — Construit le contenu de la notification envoyée à la filiale.

Info + template, comme demandé : les faits de la nomination, puis un modèle
de prise de contact générique que la filiale peut adapter si elle choisit
de contacter le diplomate elle-même. Pas personnalisé nominativement ici
(le générateur de lettre complet avec accord grammatical pays/préposition
existe déjà dans le projet "onglet France", en pause -- réutilisable plus
tard si besoin d'une vraie lettre prête à envoyer plutôt qu'un modèle)."""

from __future__ import annotations

from extract import Nomination

CATEGORY_LABELS = {
    "ambassadeur": "Ambassadeur/Ambassadrice de France",
    "consul_general": "Consul général de France",
    "attache_defense": "Attaché(e) de défense",
}

GENERIC_TEMPLATE = """Madame, Monsieur,

Permettez-moi de vous adresser mes sincères félicitations à l'occasion de votre nomination.

En tant que [Titre] d'AGS [Filiale], j'accompagne les administrations, institutions et
collaborateurs en mobilité dans la gestion de leurs transferts internationaux.

Si votre mutation devait nécessiter un accompagnement particulier, je serais ravi(e)
d'échanger avec vous et de vous présenter les solutions que nos équipes peuvent mettre
à votre disposition.

Bien cordialement,
[Signature]"""


def build_email(nomination: Nomination, branch_country: str | None) -> dict:
    label = CATEGORY_LABELS.get(nomination.category, nomination.category)
    subject = f"[Diplo FR] {label} — {nomination.name} — {nomination.location}"

    lines = [
        f"Nouvelle nomination repérée au Journal Officiel :",
        "",
        f"  Personne : {nomination.name}",
        f"  Poste : {label}",
        f"  Lieu : {nomination.location}",
    ]
    if nomination.predecessor:
        lines.append(f"  En remplacement de : {nomination.predecessor}")
    if nomination.effective_date:
        lines.append(f"  Prise de fonction : {nomination.effective_date}")
    lines += [
        f"  Référence JORF : https://jorfsearch.steinertriples.ch/JORFTEXT{nomination.jorf_id.replace('JORFTEXT','')}",
        "",
        "Ce mouvement représente potentiellement un déménagement international --",
        "à vous de juger si un contact est pertinent selon le contexte.",
        "",
        "--- Modèle de prise de contact (à adapter et personnaliser) ---",
        "",
        GENERIC_TEMPLATE,
    ]
    return {"subject": subject, "body": "\n".join(lines)}
