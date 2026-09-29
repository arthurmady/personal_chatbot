# MadyGPT

Assistant personnel conversationnel qui présente une personne, en remplaçant la fonction d'un CV. Il répond uniquement à partir d'une base de faits en JSON, avec une divulgation progressive : l'essentiel d'abord, les détails seulement quand l'utilisateur les demande.

## Fonctionnalités

- **Chat IA contextuel** — réponses strictement limitées aux faits du contexte (jamais de connaissances inventées), en français, format Markdown.
- **États de faits** — chaque fait suit un état (`not_discussed` → `essential_given` → `partial_details` → `details_complete`) : les détails `[id]` restent verrouillés tant que l'essentiel n'a pas été donné.
- **Suggestions anti-spoil** — les questions de suggestion portent un `fact_id` / `detail_id` déclaré : elles restent volontairement vagues pour ne rien révéler du détail non donné, et au clic la cible exacte est transmise au modèle.
- **Résumé latéral** — résumé par tag (idées de l'essentiel uniquement), fusionné côté client à chaque tour.
- **Persistance des sessions** — historique, résumés et états de faits sauvegardés en JSON sur disque (écriture atomique, verrouillage thread).
- **Import GitHub** — régénère des faits "Projets" à partir des README de vos dépôts.
- **Panneau d'admin** — stats, sessions, visualisation des fichiers de données (vue faits + JSON brut), upload/suppression, génération IA des suggestions et résumés, refresh GitHub (`/admin`).
- **Personnage animé** — avatar SVG interactif (Wobbi) réactif aux états du chat (idle, thinking, sleeping…).
- **Sécurité** — rate limiting IP (chat + login), cookie admin `httponly`, comparaison de mot de passe en temps constant, contrôle des uploads.

## Stack

| Couche | Technologies |
|---|---|
| Backend | Python, FastAPI, LangChain (`langchain-openai`), OpenRouter, Pydantic |
| Frontend | React 19, Vite, Tailwind CSS 4, react-markdown, oxlint |
| Données | Fichiers JSON (faits + sessions) |
| LLM | `openai/gpt-oss-120b` via OpenRouter (fournisseur Groq, fallback activé) |
| Déploiement | GitHub Actions → SSH → VPS (systemd `chatbot`) |

## Architecture

```
backend/
  api.py                  # FastAPI : /chat, /session, /admin/*, statique frontend
  config.py               # Variables d'environnement
  src/
    llm_client.py         # Client LangChain → OpenRouter
    session_store.py      # Persistance sessions (JSON atomique + Lock)
    admin_auth.py         # Login / tokens admin
    fetch_github.py       # Import des README GitHub → faits JSON
    generation/
      prompts.py          # SYSTEM_PROMPT + FOLLOWUP_TEMPLATE
      context_builder.py  # Construction du contexte selon états des faits
      precompute.py       # Génération des suggestions/résumés à l'upload (1 appel LLM)
      conversation.py     # Cœur de la logique : parsing, états, suggestions, filtres
  data/                   # Fichiers de faits + sessions.json
    derived/              # Suggestions/résumés pré-calculés (générés à l'upload)
frontend/
  src/App.jsx             # Chat
  src/AdminPanel.jsx      # Panel /admin
  character/              # Avatar SVG (Wobbi)
deploy/                   # setup.sh (serveur) + deploy.sh (mise à jour)
```

### Génération à l'upload (`POST /admin/data`)

1. Le fichier est écrit dans `data/`, puis `precompute.py` est lancé en tâche de fond.
2. Un unique appel LLM produit, pour chaque tag une question de suggestion (`tags`), et pour chaque fait `summary_keywords` (idées de l'essentiel) et `details` (1 question vague par détail). Aucune suggestion n'est produite pour les essentiels : ce sont les tags qui ouvrent l'accès aux essentiels.
3. Le résultat est validé puis écrit dans `data/derived/<fichier>.json` ; le statut (`none` / `running` / `ok` / `error`) est visible dans l'onglet Données, avec un bouton de relance.
4. Chaque contenu généré est éditable à la main depuis le bouton « Généré » : résumé, questions essentielles et questions détail, écrit via `PUT /admin/data/{fichier}/derived` (validation + normalisation côté serveur).

### Flux d'une requête (`POST /chat`)

1. `context_builder` assemble le contexte : essentiels toujours visibles, détails `[id]` affichés en clair seulement si le fait est `essential_given`, sinon verrouillés (`contenu réservé`).
2. **Un seul appel LLM** répond en JSON strict : `response`, `fact_ids`, `level`.
3. `conversation.py` détecte les détails réellement utilisés (n-grammes + overlap), met à jour les états, puis lit dans `data/derived/` les suggestions et le résumé — sans appel LLM supplémentaire. Les suggestions sont de 2 formes : une question par tag restant à couvrir (cible `[tag: X]`, réponse = tous les essentiels du tag) ou une question de détail pour un fait déjà donné (filtrée : déjà donnée, anti-spoil).

## Installation

### Prérequis

- Python 3.11+
- Node.js 20+
- Une clé [OpenRouter](https://openrouter.ai)

### 1. Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # puis renseigner OPENROUTER_API_KEY, etc.
```

### 2. Frontend

```bash
cd frontend
npm install
npm run build               # les fichiers sont servis par FastAPI (frontend/dist)
```

### 3. Lancer

```bash
cd backend
source venv/bin/activate
uvicorn api:app --host 0.0.0.0 --port 1234
```

- Chat : `http://localhost:1234`
- Admin : `http://localhost:1234/admin`

> Mode dev frontend (`npm run dev`, port 5173) : aucune extension de proxy API n'est configurée — le chat complet fonctionne via le build servi par FastAPI.

## Configuration (`backend/.env`)

| Variable | Description | Défaut |
|---|---|---|
| `OPENROUTER_API_KEY` | Clé API OpenRouter (obligatoire) | — |
| `OPENROUTER_MODEL` | Modèle utilisé | `openai/gpt-oss-120b` |
| `OPENROUTER_BASE_URL` | Endpoint OpenRouter | `https://openrouter.ai/api/v1` |
| `FRONTEND_URL` | Origine CORS autorisée | `http://localhost:5173` |
| `ADMIN_PASSWORD` | Mot de passe du panneau admin | — |
| `ADMIN_TOKEN_TTL` | Durée de vie du token admin (s) | `1800` |
| `GITHUB_USER_URL` | URL profil GitHub (import README) | — |
| `LOG_LEVEL` | Niveau de logging | `INFO` |
| `DEV` | Si défini : cookie admin non `secure` | — |

## Structure des données

Chaque fichier `backend/data/*.json` (hors `sessions.json`) :

```json
{
  "facts": [
    {
      "id": "exp_acme",
      "tags": ["Expériences"],
      "essential": "Stage en développement web chez Acme en 2024…",
      "plus": "Contexte complémentaire déjà public…",
      "details": [
        { "id": "acme_equipe", "content": "Contenu verrouillé tant que l'essentiel n'est pas donné…" }
      ]
    }
  ]
}
```

- **`essential`** — toujours visible, premier à être donné.
- **`plus`** — accompagnement de l'essentiel, visible dès que le fait est discuté.
- **`details[].content`** — réservé : dévoilé uniquement quand l'utilisateur pose une question ciblée sur le fait.
- **`details[].id`** — slug stable (généré par l'import GitHub), réutilisé par les suggestions.

### Données pré-calculées (`backend/data/derived/*.json`)

Générées à l'upload par `precompute.py`, une entrée par fichier source :

```json
{
  "schema_version": 2,
  "source": "data.json",
  "generated_at": 1790000000.0,
  "fact_count": 32,
  "tag_count": 12,
  "tags": {
    "Expériences": "Quelles ont été ses principales expériences ?"
  },
  "facts": {
    "exp_acme": {
      "tags": ["Expériences"],
      "summary_keywords": ["Acme : stage 2024"],
      "details": { "acme_equipe": "Avec qui a-t-il travaillé ?" }
    }
  }
}
```

- **`tags`** — 1 question de suggestion par tag. Cliquée, elle cible `[tag: X]` : la réponse donne les essentiels de TOUS les faits de ce tag (tous passent en `done`), et le résumé s'affiche.
- **`summary_keywords`** — idées extraites de l'essentiel, regroupées par tag au moment du chat.
- **`details`** — 1 question vague (zéro spoil) par détail, utilisée tant que le détail n'est pas donné.

### Import des projets GitHub

```bash
cd backend
python -m src.fetch_github     # écrit data/github_projects.json
```

ou bouton **Rafraîchir** dans l'onglet GitHub du panneau admin (`GITHUB_USER_URL` requis).

## Admin

`POST /admin/login` (cookie `admin_token`, 30 min) puis :

| Endpoint | Rôle |
|---|---|
| `GET /admin/stats` | Nombre de sessions / messages |
| `GET /admin/sessions` | Liste des sessions |
| `GET /admin/sessions/{id}` | Détail d'une session |
| `DELETE /admin/sessions/{id}` | Suppression |
| `GET|POST /admin/data` | Liste (avec statut de génération) / upload de fichiers de faits (10 Mo max) |
| `GET /admin/data/{file}` | Contenu d'un fichier (structure + JSON brut) |
| `GET /admin/data/{file}/derived` | Contenu généré d'un fichier (structure + JSON brut) |
| `PUT /admin/data/{file}/derived` | Écriture manuelle du contenu généré (édition admin) |
| `POST /admin/data/{file}/recompute` | Relance la génération IA d'un fichier |
| `DELETE /admin/data/{file}` | Suppression d'un fichier (et de son dérivé) |
| `POST /admin/refresh-github` | Régénère les faits GitHub |

## Déploiement

1. **Serveur initial** : `bash deploy/setup.sh` (dépendances, venv, build, `.env`, service systemd `chatbot`).
2. **Mise à jour** : push sur `main` → GitHub Actions (`deploy.yml`) se connecte en SSH et exécute `deploy/deploy.sh` (pull, pip, build, restart).

Secrets GitHub requis : `VPS_HOST`, `VPS_USER`, `VPS_SSH_KEY`.

## Lint

```bash
cd frontend && npm run lint   # oxlint
```

## Licence

Projet personnel. Les contenus (CV, faits, textes) sont la propriété d'Arthur Mady.
