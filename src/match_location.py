"""
match_location.py — Relie le lieu extrait d'une nomination (pays pour les
ambassadeurs, ville pour les consuls/attachés) à une clé de routing.json.

Deux mécanismes, chacun construit à partir de données vérifiables plutôt que
de mémoire :
- Pays (ambassadeurs) : table pycountry + babel(fr), comme pour le projet
  diplomats/ -- noms de pays FR/EN vérifiés par bibliothèque, pas tapés à la main.
- Villes (consuls, attachés) : geonamescache (base de ~34 000 villes, code
  pays ISO) + une couche d'exonymes français courants (Alger/Algiers,
  Kiev/Kyiv, etc.) -- géographie standard, pas une liste risquée inventée.

Ce que routing.json utilise comme clés est un mélange de noms de pays et
quelques cas particuliers (DOM-TOM, "Congo (Brazzaville)" vs "DR Congo").
ROUTING_KEY_BY_ISO fait le pont ISO -> clé de routing.json.
"""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

import pycountry
import geonamescache
from babel import Locale


def _fold(s: str) -> str:
    """Insensible aux accents : 'Libéria' et 'Liberia' (l'orthographe
    utilisée par babel/CLDR pour ce pays) doivent matcher pareil -- ce genre
    d'écart existe pour plusieurs pays, pas seulement celui-ci."""
    nfkd = unicodedata.normalize("NFKD", s)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower()

_HERE = Path(__file__).resolve().parent
ROUTING = json.loads((_HERE / "routing.json").read_text(encoding="utf-8"))

# --- Pays : variantes FR/EN -> nom canonique pycountry ---
_COUNTRY_NAME_MAP: dict[str, str] = {}
for c in pycountry.countries:
    _COUNTRY_NAME_MAP[_fold(c.name)] = c.name
    if hasattr(c, "common_name"):
        _COUNTRY_NAME_MAP[_fold(c.common_name)] = c.name
_loc = Locale("fr")
for c in pycountry.countries:
    fr_name = _loc.territories.get(c.alpha_2)
    if fr_name:
        _COUNTRY_NAME_MAP[_fold(fr_name)] = c.name

# pycountry canonical name (lower) -> clé exacte dans routing.json
# (Volontairement absent de cette table : un pays hors réseau AGS comme la
# Nouvelle-Zélande -- reste donc "non résolu" plutôt que mal routé.)
_CANONICAL_TO_ROUTING_KEY: dict[str, str] = {
    "bosnia and herzegovina": "Bosnia and Herzegovina",
    "liberia": "Liberia", "kenya": "Kenya", "united kingdom": "United Kingdom",
    "spain": "Spain", "bulgaria": "Bulgaria", "croatia": "Croatia", "slovakia": "Slovakia",
    "albania": "Albania", "north macedonia": "North Macedonia", "czechia": "Czechia",
    "poland": "Poland", "belgium": "Belgium", "hungary": "Hungary", "romania": "Romania",
    "portugal": "Portugal", "ukraine": "Ukraine", "austria": "Austria",
    "netherlands": "Netherlands", "kosovo": "Kosovo", "montenegro": "Montenegro",
    "germany": "Germany", "morocco": "Morocco", "gambia": "Gambia",
    "equatorial guinea": "Equatorial Guinea", "tunisia": "Tunisia",
    "côte d'ivoire": "Côte d'Ivoire", "ivory coast": "Côte d'Ivoire", "gabon": "Gabon",
    "niger": "Niger", "benin": "Benin", "togo": "Togo", "cameroon": "Cameroon",
    "ghana": "Ghana", "congo": "Congo (Brazzaville)",
    "congo, the democratic republic of the": "DR Congo", "madagascar": "Madagascar",
    "mauritania": "Mauritania", "guinea": "Guinea", "mali": "Mali",
    "burkina faso": "Burkina Faso", "chad": "Chad", "senegal": "Senegal",
    "sierra leone": "Sierra Leone", "egypt": "Egypt", "uganda": "Uganda",
    "tanzania, united republic of": "Tanzania", "rwanda": "Rwanda",
    "mozambique": "Mozambique", "malawi": "Malawi", "nigeria": "Nigeria",
    "burundi": "Burundi", "angola": "Angola", "sudan": "Sudan", "ethiopia": "Ethiopia",
    "comoros": "Comoros", "guinea-bissau": "Guinea-Bissau", "south sudan": "South Sudan",
    "mauritius": "Mauritius", "sao tome and principe": "Sao Tome and Principe",
    "bahrain": "Bahrain", "oman": "Oman", "kuwait": "Kuwait", "algeria": "Algeria",
    "united arab emirates": "United Arab Emirates", "qatar": "Qatar",
    "thailand": "Thailand", "singapore": "Singapore", "taiwan, province of china": "Taiwan",
    "myanmar": "Myanmar", "cambodia": "Cambodia", "indonesia": "Indonesia",
    "india": "India", "china": "China", "korea, republic of": "South Korea",
    "philippines": "Philippines", "lao people's democratic republic": "Laos",
    "japan": "Japan", "malaysia": "Malaysia", "viet nam": "Vietnam", "aruba": "Aruba",
    "bonaire, sint eustatius and saba": "Bonaire", "curaçao": "Curaçao",
    "haiti": "Haiti", "zambia": "Zambia", "france": "France",
}

# Table ISO alpha-2 -> clé routing.json (construite manuellement, seulement
# pour les pays de notre réseau -- volontairement absente pour le reste :
# un pays hors réseau doit rester "non résolu", jamais un mauvais routage.
_ISO_TO_ROUTING_KEY = {
    "GB":"United Kingdom","ES":"Spain","BG":"Bulgaria","HR":"Croatia","SK":"Slovakia",
    "AL":"Albania","MK":"North Macedonia","BA":"Bosnia and Herzegovina","CZ":"Czechia",
    "PL":"Poland","BE":"Belgium","HU":"Hungary","RO":"Romania","PT":"Portugal",
    "UA":"Ukraine","AT":"Austria","NL":"Netherlands","XK":"Kosovo","ME":"Montenegro",
    "DE":"Germany","MA":"Morocco","GM":"Gambia","GQ":"Equatorial Guinea","TN":"Tunisia",
    "CI":"Côte d'Ivoire","GA":"Gabon","NE":"Niger","BJ":"Benin","TG":"Togo","CM":"Cameroon",
    "GH":"Ghana","CG":"Congo (Brazzaville)","MG":"Madagascar","MR":"Mauritania","GN":"Guinea",
    "ML":"Mali","BF":"Burkina Faso","TD":"Chad","SN":"Senegal","CD":"DR Congo",
    "SL":"Sierra Leone","EG":"Egypt","KE":"Kenya","UG":"Uganda","TZ":"Tanzania","RW":"Rwanda",
    "MZ":"Mozambique","MW":"Malawi","NG":"Nigeria","BI":"Burundi","AO":"Angola","SD":"Sudan",
    "LR":"Liberia","ET":"Ethiopia","KM":"Comoros","GW":"Guinea-Bissau","SS":"South Sudan",
    "MU":"Mauritius","ST":"Sao Tome and Principe","BH":"Bahrain","OM":"Oman","KW":"Kuwait",
    "DZ":"Algeria",
    "AE":"United Arab Emirates","QA":"Qatar","TH":"Thailand","SG":"Singapore","TW":"Taiwan",
    "MM":"Myanmar","KH":"Cambodia","ID":"Indonesia","IN":"India","CN":"China","KR":"South Korea",
    "PH":"Philippines","LA":"Laos","JP":"Japan","MY":"Malaysia","VN":"Vietnam","AW":"Aruba",
    "BQ":"Bonaire","CW":"Curaçao","HT":"Haiti","ZM":"Zambia","FR":"France",
}

# --- Villes : exonymes français courants -> nom anglais/local reconnu par geonamescache ---
_FRENCH_CITY_EXONYMS = {
    "alger": "algiers", "kiev": "kyiv", "le caire": "cairo", "caire": "cairo",
    "moscou": "moscow",
    "pékin": "beijing", "vienne": "vienna", "varsovie": "warsaw", "prague": "prague",
    "bruxelles": "brussels", "la haye": "the hague", "athènes": "athens",
    "lisbonne": "lisbon", "florence": "florence", "gênes": "genoa", "venise": "venice",
    "munich": "munich", "cologne": "cologne", "new york": "new york city",
}

_gc = geonamescache.GeonamesCache()
_CITY_TO_ISO: dict[str, list[str]] = {}
for _c in _gc.get_cities().values():
    _CITY_TO_ISO.setdefault(_c["name"].lower(), []).append(_c["countrycode"])


def resolve_country_phrase(phrase: str) -> str | None:
    """Pour un ambassadeur : phrase du type 'en Nouvelle-Zélande' ou 'auprès
    de la République du Kenya' -> clé routing.json, ou None si non résolu
    (pays hors réseau, ou non reconnu -- jamais un mauvais routage)."""
    text = _fold(phrase)
    for name, canonical in sorted(_COUNTRY_NAME_MAP.items(), key=lambda kv: -len(kv[0])):
        if name in text:
            key = _CANONICAL_TO_ROUTING_KEY.get(canonical.lower())
            return key
    return None


def resolve_city(city: str) -> str | None:
    """Pour un consul/attaché : nom de ville -> clé routing.json, ou None si
    non résolu (ville inconnue, ou pays hors réseau)."""
    normalized = _FRENCH_CITY_EXONYMS.get(city.strip().lower(), city.strip().lower())
    isos = _CITY_TO_ISO.get(normalized)
    if not isos:
        return None
    # Une ville peut exister dans plusieurs pays (ex. "Naples" IT/US) --
    # on ne retient que si un seul des codes correspond à notre réseau, pour
    # éviter un mauvais choix silencieux entre deux candidats plausibles.
    matches = {_ISO_TO_ROUTING_KEY[iso] for iso in isos if iso in _ISO_TO_ROUTING_KEY}
    if len(matches) == 1:
        return matches.pop()
    return None


def resolve(category: str, location: str) -> str | None:
    if category == "ambassadeur":
        return resolve_country_phrase(location)
    return resolve_city(location)
