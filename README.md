# MadyGPT

Assistant personnel conversationnel qui présente une personne à la troisième personne, en remplaçant la fonction d'un CV : parcours, compétences et projets se découvrent en conversation plutôt qu'en lecture. Il répond uniquement à partir d'une base de faits en JSON, avec une divulgation progressive : l'essentiel d'abord, les détails seulement quand l'utilisateur les demande.

## Fonctionnalités

- **Chat IA contextuel** — réponses strictement limitées aux faits du contexte (jamais de connaissances inventées), en français, format Markdown.
- **États de faits** — chaque fait suit un état (`not_discussed` → `essential_given` → `partial_details` → `details_complete`) : les détails `[id]` restent verrouillés tant que l'essentiel n'a pas été donné.
- **Suggestions anti-spoil** — les questions de suggestion portent un `fact_id` / `detail_id` déclaré : elles restent volontairement vagues pour ne rien révéler du détail non donné, et au clic la cible exacte est transmise au modèle.
- **Résumé latéral** — résumé par tag (idées de l'essentiel uniquement), fusionné côté client à chaque tour.
- **Persistance des sessions** — historique, résumés et états de faits sauvegardés en JSON sur disque (écriture atomique, verrouillage thread).
- **Import GitHub** — régénère des faits "Projets" à partir des README de vos dépôts.
- **Panneau d'admin** — stats, sessions, upload/suppression des fichiers de données, refresh GitHub (`/admin`).
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
      conversation.py     # Cœur de la logique : parsing, états, suggestions, filtres
  data/                   # Fichiers de faits + sessions.json
frontend/
  src/App.jsx             # Chat
  src/AdminPanel.jsx      # Panel /admin
  character/              # Avatar SVG (Wobbi)
deploy/                   # setup.sh (serveur) + deploy.sh (mise à jour)
```

### Flux d'une requête (`POST /chat`)

1. `context_builder` assemble le contexte : essentiels toujours visibles, détails `[id]` affichés en clair seulement si le fait est `essential_given`, sinon verrouillés (`contenu réservé`).
2. Le LLM répond en JSON strict : `response`, `summary`, `fact_ids`, `level`, `suggestions`.
3. `conversation.py` détecte les détails réellement utilisés (n-grammes + overlap), met à jour les états, filtre les suggestions (déjà données, hors périmètre, ancrage/anti-spoil) et garantit au besoin une question vague générée par un second appel LLM (repli déterministe si échec).

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
| `GET|POST /admin/data` | Liste / upload de fichiers de faits (10 Mo max) |
| `DELETE /admin/data/{file}` | Suppression d'un fichier |
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
