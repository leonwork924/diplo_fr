# diplo_fr

Surveille les nominations d'ambassadeurs, consuls généraux et attachés de
défense français (source : Journal Officiel, via JusticeLibre) et notifie
la filiale AGS concernée par email — infos + modèle de prise de contact.

## Ce qui est testé (vraiment, avec de vraies données)

- **Extraction** (`extract.py`) : testée contre 11 vrais extraits JusticeLibre
  capturés pendant la conception (`fixtures/justicelibre_samples.json`) —
  9/11 reconnus correctement, 2 écartés proprement (extrait trop tronqué
  pour contenir le lieu, pas une erreur de motif).
- **Matching lieu → filiale** (`match_location.py`) : testé sur les mêmes
  fixtures — résolution correcte quand le pays/la ville est dans notre
  réseau, `None` proprement quand ce n'est pas le cas (ex. Nouvelle-Zélande,
  Italie : pas de filiale AGS là-bas).
- **Routing** (`routing.json`) : 93 pays, croisés à la main avec Leon contre
  deux fichiers Excel (`Code_Agences.xlsx`, `Sales_Organogram_-AGS.xlsx`).
  Deux erreurs de retranscription trouvées et corrigées en cours de route
  (Algérie oubliée, accent "Libéria" vs "Liberia") — voir l'historique de
  conversation si un doute survient sur une entrée.
- **Mémoire du déjà-vu** (`seen.py`) : testée sur deux passages successifs,
  le deuxième ne renvoie bien aucune notification.
- **Pipeline complet** (`main.py --dry-run`) : testé de bout en bout avec
  les fixtures à la place d'un vrai appel réseau.

## Ce qui N'EST PAS testé

- **`fetch_jorf.py`** : parle le protocole MCP en HTTP brut vers
  `justicelibre.org/mcp`. L'API du client Python (`mcp.client.streamable_http`)
  est réelle et installée (`pip install mcp`), le code est écrit contre cette
  API confirmée -- mais `justicelibre.org` n'était pas joignable depuis le
  bac à sable où ce projet a été écrit, donc **aucun appel réel n'a pu être
  fait**. C'est le premier vrai test à faire.
- **L'envoi Brevo** (`main.py:send_email`) : écrit contre la doc de l'API
  Brevo, jamais appelé en vrai (pas de compte/clé à ce stade).

## Avant le premier run réel

```bash
pip install -r requirements.txt
cd src
python3 main.py --dry-run --days-back 30
```

Si `fetch_jorf` échoue : regarder en premier le nom exact de l'outil MCP
("search_jorf") et si une étape d'authentification est en fait requise
malgré le "sans clé" annoncé.

Si ça marche, vérifie que le nombre de résultats et les extractions ont
l'air sains, puis configure les secrets GitHub (`BREVO_API_KEY`,
`BREVO_SENDER_EMAIL`) et laisse tourner le workflow.

## Configuration Brevo requise

1. Créer un compte gratuit sur brevo.com (300 emails/jour, largement assez)
2. Récupérer une clé API (SMTP & API → API Keys)
3. Ajouter `BREVO_API_KEY` et `BREVO_SENDER_EMAIL` comme secrets du repo
   GitHub (Settings → Secrets and variables → Actions)

## Structure

```
src/
  fetch_jorf.py       — appel JusticeLibre (MCP/HTTP) — NON TESTÉ EN DIRECT
  extract.py           — nom/pays/prédécesseur depuis le texte — testé
  match_location.py    — lieu → clé de routing.json — testé
  notify.py             — construit le contenu de l'email
  routing.json          — pays → email(s) de filiale
  routing.py             — charge routing.json
  seen.py                 — mémoire du déjà-vu
  main.py                  — orchestration
fixtures/
  justicelibre_samples.json — vrais extraits capturés, pour les tests
data/
  seen.json (généré au premier run)
```
