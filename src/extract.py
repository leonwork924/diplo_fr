"""
extract.py — Extraction nom/poste/pays depuis les extraits JusticeLibre.

Travaille sur le champ `extract` renvoyé par search_jorf (snippet FTS5 centré
sur les mots-clés recherchés, pas le texte intégral) -- suffisant dans tous
les cas observés pendant les tests (voir fixtures/justicelibre_samples.json,
capturés lors de vraies requêtes), mais si un extrait s'avère trop tronqué
en usage réel, il faudra passer par le texte intégral (pas encore branché).

Trois catégories reconnues, chacune avec son motif de localisation propre :
- ambassadeur : "de la République française {préposition+pays}"
- consul général : "de France à {ville}" (+ prédécesseur si mentionné)
- attaché de défense : "près l'ambassade de France à {ville}" (+ date si mentionnée)
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

# --- Nom : prénom(s) + particule optionnelle (du/de/de la) + NOM DE FAMILLE
# en majuscules, juste avant "nommé"/"est nommé". Le grade/la fonction qui
# précède parfois (ex. "M. le contre-amiral ") est ignoré naturellement :
# ces mots commencent en minuscule et cassent l'accumulation du prénom.
NAME_RE = re.compile(
    r"(?P<given>(?:[A-ZÀ-Ý][\wÀ-ÿ'’.-]*\s+){1,3})"
    r"(?P<particle>d[eu]'?\s+|de\s+la\s+)?"
    r"(?P<surname>[A-ZÀ-Ý][A-ZÀ-Ÿ'’-]+(?:\s+[A-ZÀ-Ý][A-ZÀ-Ÿ'’-]+)?)"
    r"\s*(?:,[^.]*?)?\s*(?:est\s+)?nommé\b"
)

PREDECESSOR_RE = re.compile(
    r"en remplacement de\s+(?:M\.|Mme)\s+"
    r"((?:[A-ZÀ-Ý][\wÀ-ÿ'’.-]*\s+){1,3}[A-ZÀ-Ý][A-ZÀ-Ÿ'’-]+(?:\s+[A-ZÀ-Ý][A-ZÀ-Ÿ'’-]+)?)"
)

DATE_EFFECTIVE_RE = re.compile(
    r"à compter du\s+(\d{1,2})(?:\s*er)?\s+(\w+)\s+(\d{4})", re.IGNORECASE
)
_MONTHS_FR = {"janvier":1,"février":2,"mars":3,"avril":4,"mai":5,"juin":6,"juillet":7,
              "août":8,"septembre":9,"octobre":10,"novembre":11,"décembre":12}


def _clean_name(m: re.Match) -> str:
    given = m.group("given").strip()
    particle = (m.group("particle") or "").strip()
    surname = m.group("surname").strip()
    parts = [p for p in (given, particle, surname) if p]
    return re.sub(r"\s+", " ", " ".join(parts))


def _predecessor(extract: str) -> str | None:
    m = PREDECESSOR_RE.search(extract)
    if not m:
        return None
    return re.sub(r"\s+", " ", m.group(1).strip())


def _effective_date(extract: str) -> str | None:
    m = DATE_EFFECTIVE_RE.search(extract)
    if not m:
        return None
    day, month_name, year = m.groups()
    month = _MONTHS_FR.get(month_name.lower())
    if not month:
        return None
    return f"{int(year):04d}-{month:02d}-{int(day):02d}"


@dataclass
class Nomination:
    jorf_id: str
    category: str  # "ambassadeur" | "consul_general" | "attache_defense"
    name: str
    location: str  # phrase pays (ambassadeur) ou ville (consul/attaché)
    predecessor: str | None = None
    effective_date: str | None = None


def extract_ambassadeur(jorf_id: str, extract: str) -> Nomination | None:
    name_m = NAME_RE.search(extract)
    loc_m = re.search(r"de la République française\s+(.+?)(?:\.\s|\.$|$)", extract)
    if not name_m or not loc_m:
        return None
    location = loc_m.group(1).strip().rstrip(".,")
    return Nomination(jorf_id, "ambassadeur", _clean_name(name_m), location)


def extract_consul_general(jorf_id: str, extract: str) -> Nomination | None:
    name_m = NAME_RE.search(extract)
    loc_m = re.search(
        r"consul général de France (?:à|au)\s+([^,\.…]+?)(?:\s+à compter du|[,\.…]|$)",
        extract, re.IGNORECASE,
    )
    if not name_m or not loc_m:
        return None
    return Nomination(
        jorf_id, "consul_general", _clean_name(name_m),
        loc_m.group(1).strip(), predecessor=_predecessor(extract),
        effective_date=_effective_date(extract),
    )


def extract_attache_defense(jorf_id: str, extract: str) -> Nomination | None:
    name_m = NAME_RE.search(extract)
    loc_m = re.search(
        r"près l'ambassade de France à\s+([^,\.…]+?)(?:\s+à compter du|[,\.…]|$)",
        extract, re.IGNORECASE,
    )
    if not name_m or not loc_m:
        return None
    location = loc_m.group(1).strip()
    # Filet de sécurité : un extrait tronqué juste après "l'ambassade" (avant
    # "de France à {ville}") laisse un nom sans localisation exploitable --
    # ex. observé sur JORFTEXT000049862744. Mieux vaut ne rien renvoyer que
    # d'inventer un lieu, ou de garder un fragment de phrase suivante happé
    # par erreur.
    if not location or len(location.split()) > 3:
        return None
    return Nomination(
        jorf_id, "attache_defense", _clean_name(name_m),
        location, effective_date=_effective_date(extract),
    )


CATEGORY_DISPATCH = [
    (re.compile(r"attaché de défense", re.IGNORECASE), extract_attache_defense),
    (re.compile(r"consul général", re.IGNORECASE), extract_consul_general),
    (re.compile(r"ambassadeur", re.IGNORECASE), extract_ambassadeur),
]


HTML_TAG_RE = re.compile(r"<[^>]+>")


def extract_nomination(jorf_id: str, extract: str) -> Nomination | None:
    """Route vers le bon extracteur selon les mots-clés présents. L'ordre du
    dispatch compte : "attaché de défense" et "consul général" avant
    "ambassadeur" (générique), pour ne pas prendre le mauvais motif de
    localisation sur un texte qui contient les deux mots incidemment."""
    # JusticeLibre entoure les termes de la requête de balises <em>...</em>
    # (surlignage) -- confirmé sur un vrai run (17/09/2026) où ça cassait
    # 100% des extractions "consul général" (la requête contient "nommé",
    # "consul" ET "général", donc les trois se retrouvent scindés par des
    # balises). Les retirer avant tout le reste du traitement.
    extract = HTML_TAG_RE.sub("", extract)
    # Normalisation Unicode NFC : conservée par précaution (accents encodés
    # différemment entre deux sources), même si ce n'était pas la vraie
    # cause du bug ci-dessus.
    extract = unicodedata.normalize("NFC", extract)
    for pattern, fn in CATEGORY_DISPATCH:
        if pattern.search(extract):
            result = fn(jorf_id, extract)
            if result:
                return result
    return None
