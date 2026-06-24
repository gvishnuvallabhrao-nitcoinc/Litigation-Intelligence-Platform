# Litigation Intelligence Platform

AI-powered legal research assistant for Indian courts — Phase 1 MVP.

## What it does

| Feature | Description |
|---|---|
| **Similar Case Finder** | Paste case facts → get ranked similar judgments via InLegalBERT embeddings |
| **Winning Precedents** | Find cases with the same facts that were *allowed* (won) |
| **Citation Recommendations** | Suggest citations that share the same Acts as your case |
| **Argument Strength Analysis** | Score your argument Weak / Moderate / Strong against historical patterns (Cohere) |
| **Judge Analytics** | Historical allow rates, dismiss rates, avg hearings per judge |

**Scope (MVP):** Delhi High Court · IPR cases · 1,000 judgments target

---

## Tech Stack

| Layer | Technology |
|---|---|
| Embeddings | InLegalBERT (`law-ai/InLegalBERT`) — 768-dim, fine-tuned on Indian legal corpus |
| Vector search | Supabase pgvector (primary) + FAISS (local fallback) |
| LLM | Cohere `command-r-plus-08-2024` — argument analysis |
| Backend | FastAPI + Uvicorn |
| Frontend | React 19 + Vite + TailwindCSS + Recharts + React Query |
| Database | Supabase (PostgreSQL + pgvector) |
| Data source | Indian Kanoon API |

---

## Project Structure

```
├── pipeline/
│   ├── scraper.py            # Indian Kanoon scraper (POST-based, rate-limited)
│   ├── extractor.py          # Judgment parser, outcome extraction
│   ├── embedder.py           # InLegalBERT embeddings → .npy + FAISS index
│   ├── db_loader.py          # Upsert cases + embeddings to Supabase
│   ├── judge_normalizer.py   # Judge name alias map → canonical keys
│   └── compute_judge_stats.py# Nightly aggregation → judge_stats table
├── search/
│   ├── similarity.py         # Similar case finder (pgvector + FAISS)
│   ├── judge_stats.py        # Judge profile lookup
│   └── citation_ranker.py   # Citation recommendations + winning precedents
├── strategy/
│   └── analyzer.py           # Argument strength analysis (Cohere)
├── api/
│   ├── main.py               # FastAPI app, CORS, routers
│   ├── schemas.py            # Pydantic request/response models
│   └── routers/
│       ├── search.py         # /search/* endpoints
│       └── strategy.py       # /strategy/analyze endpoint
├── frontend/                 # React + Vite app
│   └── src/
│       ├── pages/            # SearchPage, PrecedentsPage, AnalyzePage, JudgesPage
│       └── components/       # CaseCard, Spinner, Disclaimer
├── db/
│   └── schema.sql            # Supabase schema (cases, judge_stats, RLS, RPC)
├── requirements.txt
├── requirements-ml.txt       # PyTorch, transformers, faiss-cpu
└── .env.example
```

---

## Setup

### 1. Clone & install

```bash
git clone https://github.com/gvishnuvallabhrao-nitcoinc/Litigation-Intelligence-Platform.git
cd Litigation-Intelligence-Platform

python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Mac/Linux

pip install -r requirements.txt
pip install -r requirements-ml.txt   # PyTorch + FAISS (skip if CPU-only)
```

### 2. Configure environment

```bash
cp .env.example .env
# Fill in all values in .env
```

Required keys:
- `INDIAN_KANOON_API_KEY` — [indiankanoon.org](https://indiankanoon.org/api/)
- `COHERE_API_KEY` — [dashboard.cohere.com](https://dashboard.cohere.com/) (free tier works)
- `SUPABASE_URL` + `SUPABASE_SERVICE_KEY` — Supabase project settings

### 3. Set up the database

Run [`db/schema.sql`](db/schema.sql) in your Supabase SQL editor to create the `cases` and `judge_stats` tables, the `match_cases()` pgvector RPC, and RLS policies.

### 4. Run the data pipeline

```bash
# Scrape judgments (starts at 12 for quota safety, raise --max for production)
python -m pipeline.scraper --max 12 --out data/raw

# Extract structured records
python -m pipeline.extractor

# Generate InLegalBERT embeddings + build FAISS index
python -m pipeline.embedder

# Upload to Supabase
python -m pipeline.db_loader

# Compute judge stats
python -m pipeline.compute_judge_stats
```

---

## Running the App

**Terminal 1 — API:**
```bash
python -m uvicorn api.main:app --reload --port 8000
```

**Terminal 2 — Frontend:**
```bash
cd frontend
pnpm install
pnpm dev
```

Open **http://localhost:3000**

API docs: **http://localhost:8000/docs**

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/v1/search/similar` | Find similar cases |
| POST | `/api/v1/search/citations` | Citation recommendations |
| POST | `/api/v1/search/precedents` | Winning precedents |
| GET | `/api/v1/search/judges` | List all judges |
| GET | `/api/v1/search/judges/{name}` | Judge profile |
| POST | `/api/v1/strategy/analyze` | Argument strength analysis |
| GET | `/health` | Health check |

---

## Disclaimer

All output from this platform is a **research aid based on historical judgment data**. It does not constitute legal advice. Always consult a qualified advocate before relying on any analysis produced here.

---

## Roadmap

- **Phase 1 (current):** Similar Case Finder + Strategy Assistant
- **Phase 2 (after first paying client):** Litigation Outcome Predictor — XGBoost classifier on InLegalBERT embeddings + structured features + SHAP explainability
