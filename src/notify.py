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

GENERIC_TEMPLATE_ARRIVEE = """Madame, Monsieur,

Permettez-moi de vous adresser mes sincères félicitations à l'occasion de votre nomination.

En tant que [Titre] d'AGS [Filiale], j'accompagne les administrations, institutions et
collaborateurs en mobilité dans la gestion de leurs transferts internationaux.

Si votre mutation devait nécessiter un accompagnement particulier, je serais ravi(e)
d'échanger avec vous et de vous présenter les solutions que nos équipes peuvent mettre
à votre disposition.

Bien cordialement,
[Signature]"""

GENERIC_TEMPLATE_DEPART = """Madame, Monsieur,

Nous avons noté que votre mandat actuel touche à sa fin.

En tant que [Titre] d'AGS [Filiale], j'accompagne les administrations, institutions et
collaborateurs en mobilité dans la gestion de leurs transferts internationaux.

Si votre prochaine affectation devait nécessiter un accompagnement pour votre
déménagement, je serais ravi(e) d'échanger avec vous et de vous présenter les
solutions que nos équipes peuvent mettre à votre disposition.

Bien cordialement,
[Signature]"""


def build_email(nomination: Nomination, branch_country: str | None, note: str | None = None) -> dict:
    label = CATEGORY_LABELS.get(nomination.category, nomination.category)

    if nomination.event == "depart":
        subject = f"[Diplo FR] Fin de mandat — {label} — {nomination.name} — {nomination.location}"
        context_line = (
            f"Fin de mandat repérée au Journal Officiel -- cette personne quitte "
            f"prochainement {nomination.location} :"
        )
        pitch = (
            "Cette personne est actuellement sur place et pourrait bientôt déménager "
            "(retour en France ou nouvelle affectation) -- à vous de juger si un contact "
            "local est pertinent avant son départ."
        )
    else:
        subject = f"[Diplo FR] {label} — {nomination.name} — {nomination.location}"
        context_line = "Nouvelle nomination repérée au Journal Officiel -- cette personne est actuellement en France :"
        pitch = (
            "Ce mouvement représente potentiellement un déménagement international au "
            "départ de la France -- à vous de juger si un contact est pertinent."
        )

    lines = [context_line, ""]
    if note:
        lines += [f"⚠ {note}", ""]
    lines += [
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
        pitch,
        "",
        "--- Modèle de prise de contact (à adapter et personnaliser) ---",
        "",
        GENERIC_TEMPLATE_DEPART if nomination.event == "depart" else GENERIC_TEMPLATE_ARRIVEE,
    ]
    return {"subject": subject, "body": "\n".join(lines)}
