"""
fetch_jorf.py — Interroge JusticeLibre (search_jorf) en dehors de Claude,
depuis un script Python autonome (GitHub Actions).

⚠️ Statut : le premier run réel (GitHub Actions, 17/09/2026) a confirmé un
bug dans la connexion -- `streamable_http_client` ne renvoie que 2 valeurs
(read, write), pas 3 comme le code le supposait sans avoir pu le tester en
direct depuis le bac à sable où il a été écrit. Corrigé. Ce que ça valide :
la connexion s'établit. Ce qui reste à confirmer par le prochain run : que
`session.initialize()` et `call_tool("search_jorf", ...)` renvoient bien des
résultats exploitables -- le code n'avait pas encore atteint ce point.
"""

from __future__ import annotations

import asyncio
import json

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

MCP_URL = "https://justicelibre.org/mcp"


async def _search_jorf_async(query: str, nature: str, date_min: str, limit: int = 50) -> list[dict]:
    async with streamable_http_client(MCP_URL) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(
                "search_jorf",
                {"query": query, "nature": nature, "date_min": date_min, "limit": limit},
            )
            # Le contenu revient en blocs "content" (souvent un unique bloc
            # texte JSON) -- voir le format déjà observé en usage direct.
            texts = []
            for block in result.content:
                if hasattr(block, "text"):
                    texts.append(block.text)
            if not texts:
                return []
            payload = json.loads(texts[0])
            return payload.get("textes", [])


def search_jorf(query: str, nature: str = "DECRET", date_min: str = "", limit: int = 50) -> list[dict]:
    """Version synchrone -- pratique pour un script simple appelé une fois
    par run, pas besoin d'exposer l'async plus loin."""
    return asyncio.run(_search_jorf_async(query, nature, date_min, limit))


QUERIES = [
    ("ambassadeur", "ambassadeur extraordinaire plénipotentiaire"),
    ("consul_general", "consul général nommé République française"),
    ("attache_defense", "attaché défense nommé ambassade"),
]


def fetch_all_nominations(date_min: str) -> list[tuple[str, dict]]:
    """Retourne une liste de (catégorie_devinée, texte_brut) pour toutes les
    catégories suivies. La catégorie précise est re-confirmée ensuite par
    extract.extract_nomination (basé sur le contenu, pas sur cette requête)."""
    results = []
    for _hint, query in QUERIES:
        for texte in search_jorf(query, nature="DECRET", date_min=date_min):
            results.append(texte)
    # Déduplique par id (une même nomination peut remonter sur plusieurs requêtes)
    seen_ids = set()
    unique = []
    for t in results:
        if t["id"] not in seen_ids:
            seen_ids.add(t["id"])
            unique.append(t)
    return unique
