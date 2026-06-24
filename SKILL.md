---
name: legal-case-intelligence
description: >
  Full project skill for building a Legal Case Intelligence platform — starting with
  a Similar Case Finder & Strategy Assistant (Phase 1, MVP) and expanding to a
  Litigation Outcome Predictor (Phase 2, upsell). Use this skill whenever working on
  this project: data pipeline, embeddings, similarity search, judge analytics, argument
  strength analysis, citation recommendations, FastAPI backend, or React frontend.
  Triggers on any task related to Indian court data, InLegalBERT, legal search,
  precedent research, or the FastAPI / React / PostgreSQL stack for this project.
---

# Legal Case Intelligence — Project Skill

A two-phase legal intelligence platform for lawyers and legal ops teams.

| Phase | Product | Sell as | Timeline |
|---|---|---|---|
| **Phase 1** | Similar Case Finder + Strategy Assistant | "AI Research Assistant for Lawyers" | Weeks 1–4 |
| **Phase 2** | Litigation Outcome Predictor | "Case Strategy Intelligence" | Weeks 5–10 |

**Always build Phase 1 first.** It delivers client value fast, builds your dataset,
and creates the upsell path to Phase 2.

---

## Project Structure

```
legal-case-intelligence/
├── data/
│   ├── raw/                  # Raw scraped judgments (JSON)
│   ├── processed/            # Cleaned, structured records
│   └── embeddings/           # Precomputed InLegalBERT vectors (.npy)
├── pipeline/
│   ├── scraper.py            # Indian Kanoon + eCourts scraper
│   ├── extractor.py          # Judgment parser & metadata extractor
│   └── embedder.py           # InLegalBERT embedding generator
├── search/
│   ├── similarity.py         # Cosine similarity + FAISS index
│   ├── judge_stats.py        # Judge analytics aggregator
│   └── citation_ranker.py    # Winning precedent ranker
├── strategy/
│   └── analyzer.py           # Claude API — argument strength analysis
├── model/                    # Phase 2 only
│   ├── train.py
│   ├── evaluate.py
│   └── artifacts/
├── api/
│   ├── main.py               # FastAPI app (all endpoints)
│   ├── schemas.py            # Pydantic models
│   └── routers/
│       ├── search.py         # Phase 1 endpoints
│       └── predict.py        # Phase 2 endpoints
├── frontend/
│   └── src/
├── requirements.txt
├── docker-compose.yml
└── .env.example
```

---

## PHASE 1 — Similar Case Finder + Strategy Assistant

### Overview of 5 Features

| Feature | Technical approach |
|---|---|
| Similar Case Finder | Cosine similarity on InLegalBERT embeddings via FAISS |
| Judge History Analysis | Precomputed stats per judge × case type from DB |
| Argument Strength Analysis | Claude API call scoring petitioner args vs winning patterns |
| Citation Recommendations | Top-K similar cases filtered by section cited |
| Winning Precedent Search | Similar cases filtered where outcome = allowed, ranked by relevance |

---

### Step 1 — Data Pipeline

#### 1.1 Data Sources

| Source | What to get | Access |
|---|---|---|
| Indian Kanoon API | Full judgment text, court, date, acts cited | Free API key at indiankanoon.org |
| eCourts API | Case status, judge name, hearing count | ecourts.gov.in developer portal |
| Supreme Court website | SC judgments PDF scrape | Public |

#### 1.2 Scraper (`pipeline/scraper.py`)

```python
REQUIRED_FIELDS = [
    "case_id",          # Unique identifier from source
    "court",            # e.g. "Delhi High Court"
    "judge_name",       # Normalized — see normalization note below
    "case_type",        # civil / criminal / IPR / labour / tax / constitutional
    "acts_cited",       # ["TM Act 29", "Copyright Act 51"] — list
    "petitioner_type",  # individual / corporation / government / NGO
    "respondent_type",
    "hearing_count",    # Number of hearings before judgment
    "judgment_date",    # ISO format
    "judgment_text",    # Full raw text
    "outcome",          # allowed / dismissed / partially_allowed (extract via regex)
    "indian_kanoon_url" # Direct link — shown to user in results
]
```

**Scraping rules:**
- MVP scope: **Delhi HC + IPR cases only** (well-structured, good density)
- Rate limit: 1 request/second max to Indian Kanoon
- Store raw JSON always — parse in a separate step, never lose source data
- Target: **1,000 judgments** to launch Phase 1 (vs 10,000 needed for Phase 2)

#### 1.3 Judge Name Normalization

Build this early — judge names are inconsistent across sources.

```python
# pipeline/judge_normalizer.py
JUDGE_ALIASES = {
    "hon'ble mr. justice rajiv shakdher": "rajiv_shakdher",
    "justice r. shakdher": "rajiv_shakdher",
    # build this map as you scrape
}

def normalize_judge(raw_name: str) -> str:
    key = raw_name.lower().strip()
    return JUDGE_ALIASES.get(key, key.replace(" ", "_"))
```

#### 1.4 Outcome Extraction (`pipeline/extractor.py`)

```python
OUTCOME_PATTERNS = {
    "allowed": [
        r"petition\s+is\s+(hereby\s+)?allowed",
        r"appeal\s+is\s+(hereby\s+)?allowed",
        r"rule\s+is\s+made\s+absolute",
    ],
    "dismissed": [
        r"petition\s+is\s+(hereby\s+)?dismissed",
        r"appeal\s+is\s+(hereby\s+)?dismissed",
        r"no\s+merit",
    ],
    "partially_allowed": [
        r"allowed\s+in\s+part",
        r"partially\s+allowed",
        r"partly\s+allowed",
    ]
}
```

For ambiguous cases use Claude API fallback — send last 500 words of judgment,
ask for outcome classification. Budget ~₹2 per 1,000 ambiguous cases.

---

### Step 2 — Embeddings (`pipeline/embedder.py`)

Use **InLegalBERT** — fine-tuned on Indian legal corpus.
HuggingFace: `law-ai/InLegalBERT`

```python
from transformers import AutoTokenizer, AutoModel
import torch, numpy as np

MODEL_NAME = "law-ai/InLegalBERT"

def embed_judgment(text: str) -> np.ndarray:
    """
    Always embed the LAST 512 tokens — the operative part.
    The conclusion is at the end of Indian judgments, not the beginning.
    """
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoModel.from_pretrained(MODEL_NAME)

    inputs = tokenizer(
        text, return_tensors="pt",
        max_length=512, truncation=True, padding=True
    )
    with torch.no_grad():
        output = model(**inputs)
    return output.last_hidden_state[:, 0, :].squeeze().numpy()  # CLS token
```

**Critical:** Precompute all embeddings in batch. Cache as `.npy` files in
`data/embeddings/{case_id}.npy`. Never recompute at inference time.

Build a FAISS index for fast similarity search:

```python
import faiss, numpy as np

def build_faiss_index(embeddings: np.ndarray) -> faiss.Index:
    dim = embeddings.shape[1]  # 768 for InLegalBERT
    index = faiss.IndexFlatIP(dim)  # Inner product = cosine sim (normalize first)
    faiss.normalize_L2(embeddings)
    index.add(embeddings)
    return index

# Save index
faiss.write_index(index, "data/embeddings/faiss.index")
```

---

### Step 3 — Feature 1: Similar Case Finder (`search/similarity.py`)

```python
def find_similar_cases(
    query_text: str,
    top_k: int = 10,
    filters: dict = None   # {"case_type": "IPR", "court": "Delhi HC"}
) -> list[dict]:
    """
    1. Embed query_text with InLegalBERT
    2. Search FAISS index for top_k nearest
    3. Apply metadata filters
    4. Return ranked list with similarity scores + Indian Kanoon links
    """
```

Response shape per result:
```python
{
    "case_id": "...",
    "title": "...",
    "court": "Delhi High Court",
    "date": "2023-04-12",
    "judge": "Justice X",
    "outcome": "allowed",
    "similarity_score": 0.91,
    "acts_cited": ["TM Act 29", "Copyright Act 51"],
    "summary": "...",           # First 300 chars of judgment
    "url": "https://indiankanoon.org/doc/..."
}
```

---

### Step 4 — Feature 2: Judge History Analysis (`search/judge_stats.py`)

Precompute nightly and store in PostgreSQL. Never compute on request.

```python
# DB table: judge_stats
# Columns: judge_name, case_type, total_cases, allowed, dismissed,
#          partially_allowed, avg_hearing_count, last_updated

def get_judge_profile(judge_name: str, case_type: str = None) -> dict:
    """Returns judge stats optionally filtered by case type"""
    return {
        "judge_name": "Justice X",
        "total_cases": 312,
        "overall_allow_rate": 0.43,
        "by_case_type": {
            "IPR": {"allow_rate": 0.29, "total": 87},
            "civil": {"allow_rate": 0.51, "total": 140},
        },
        "avg_hearings_before_judgment": 6.2,
        "recent_judgments": [...]   # Last 5
    }
```

---

### Step 5 — Feature 3: Argument Strength Analysis (`strategy/analyzer.py`)

Use Claude API. This is the highest-value feature for the lawyer.

```python
import anthropic

client = anthropic.Anthropic()

SYSTEM_PROMPT = """You are a legal strategy analyst specializing in Indian courts.
Given a lawyer's argument summary and similar winning/losing cases, analyze the
strength of the argument. Be specific, cite patterns from the similar cases provided.
Never give legal advice — frame as analytical observations only."""

def analyze_argument_strength(
    argument_summary: str,
    similar_cases: list[dict],
    case_type: str,
    court: str
) -> dict:
    winning = [c for c in similar_cases if c["outcome"] == "allowed"]
    losing  = [c for c in similar_cases if c["outcome"] == "dismissed"]

    prompt = f"""
Case Type: {case_type} | Court: {court}

Lawyer's Argument:
{argument_summary}

Similar Winning Cases ({len(winning)}):
{format_cases(winning)}

Similar Losing Cases ({len(losing)}):
{format_cases(losing)}

Analyze:
1. Argument strengths (what aligns with winning patterns)
2. Argument weaknesses (what aligns with losing patterns)
3. Missing elements (what winning cases had that this argument lacks)
4. Suggested citations from the cases above
5. Overall strength score: Weak / Moderate / Strong
"""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}]
    )
    return {"analysis": response.content[0].text}
```

---

### Step 6 — Feature 4 & 5: Citations + Winning Precedents (`search/citation_ranker.py`)

These are filters on top of the similarity search — not separate ML models.

```python
def get_citation_recommendations(
    query_text: str,
    acts_cited: list[str],
    top_k: int = 5
) -> list[dict]:
    """Similar cases that cite the SAME acts — best for citation."""
    results = find_similar_cases(query_text, top_k=50)
    filtered = [r for r in results if any(a in r["acts_cited"] for a in acts_cited)]
    return filtered[:top_k]

def get_winning_precedents(
    query_text: str,
    top_k: int = 5
) -> list[dict]:
    """Similar cases where outcome = allowed — ranked by similarity."""
    results = find_similar_cases(query_text, top_k=50)
    winning = [r for r in results if r["outcome"] == "allowed"]
    return winning[:top_k]
```

---

### Step 7 — API Phase 1 Endpoints (`api/routers/search.py`)

```python
from fastapi import APIRouter
router = APIRouter(prefix="/v1", tags=["Phase 1 - Case Intelligence"])

@router.post("/similar-cases")
async def similar_cases(case_summary: str, filters: dict = {}):
    """Find similar judgments"""

@router.get("/judge/{judge_name}")
async def judge_profile(judge_name: str, case_type: str = None):
    """Judge history and analytics"""

@router.post("/analyze-argument")
async def analyze_argument(argument: str, case_type: str, court: str):
    """Argument strength analysis via Claude"""

@router.post("/citations")
async def citation_recommendations(case_summary: str, acts_cited: list[str]):
    """Recommend citations from similar cases"""

@router.post("/winning-precedents")
async def winning_precedents(case_summary: str):
    """Find winning precedents most similar to this case"""
```

Always include in every response:
```python
DISCLAIMER = (
    "This is a research aid based on historical judgments. "
    "It does not constitute legal advice. Consult a qualified advocate."
)
```

---

### Step 8 — Frontend Phase 1 (`frontend/src/`)

**Tech stack:** React + Vite + TailwindCSS + Recharts + React Query

**Pages:**

| Route | Feature |
|---|---|
| `/search` | Case input → similar cases list |
| `/judge/:name` | Judge profile with allow-rate charts |
| `/analyze` | Argument input → strength report |
| `/precedents` | Winning precedent search |
| `/history` | Saved searches for the firm |

**Similar Case Card UI:**
```
┌──────────────────────────────────────────┐
│ 🟢 ALLOWED  •  Delhi HC  •  Apr 2023     │
│ Parle vs. ITC — Trademark Infringement   │
│ Similarity: 91%  •  Judge: Justice X     │
│ Acts: TM Act 29, 30                      │
│ "Court held that phonetic similarity..." │
│                          [View Full Case]│
└──────────────────────────────────────────┘
```

---

### Phase 1 MVP Checklist

- [ ] Scrape 1,000+ Delhi HC IPR judgments
- [ ] Normalize judge names
- [ ] Extract outcomes (verify 100 manually)
- [ ] Generate + cache InLegalBERT embeddings
- [ ] Build FAISS index
- [ ] Precompute judge stats into PostgreSQL
- [ ] Build FastAPI with all 5 endpoints
- [ ] Build React frontend (search + judge pages minimum)
- [ ] Deploy on Docker

**Timeline: 3–4 weeks**

---

## PHASE 2 — Litigation Outcome Predictor

Build this AFTER Phase 1 is deployed and you have a paying client.
Phase 1 data collection naturally creates the labeled dataset Phase 2 needs.

### Architecture

```
[InLegalBERT embedding (768-dim)]  ──┐
[Structured features (15-dim)]     ──┤──► XGBoost Classifier ──► Outcome + Probability
[Judge stats (5-dim)]              ──┘
                                           │
                                      SHAP Explainer
                                           │
                                    Top 3 drivers (human-readable)
```

### Structured Features for Training

```python
STRUCTURED_FEATURES = {
    "judge_allow_rate":          # Historical % allowed by this judge
    "judge_allow_rate_by_type":  # Rate filtered to this case_type
    "judge_case_count":          # Data confidence signal
    "case_type_encoded":         # One-hot
    "petitioner_type_encoded":
    "respondent_type_encoded":
    "hearing_count":             # More hearings → complex / contested
    "month_filed":               # Seasonality
    "section_success_rate":      # Historical win rate for primary section
    "num_acts_cited":            # Complexity proxy
    "govt_as_respondent":        # Boolean — shifts odds significantly
}
```

### Training

```python
import xgboost as xgb
from sklearn.model_selection import StratifiedKFold
import shap

X = np.hstack([embeddings, structured_features, judge_features])
y = label_encoder.transform(outcomes)  # 0=dismissed, 1=allowed, 2=partial

model = xgb.XGBClassifier(
    n_estimators=500, max_depth=6,
    learning_rate=0.05, subsample=0.8,
    eval_metric="mlogloss", early_stopping_rounds=20,
)
model.fit(X_train, y_train, eval_set=[(X_val, y_val)])

# SHAP for explainability
explainer = shap.TreeExplainer(model)
shap_values = explainer.shap_values(X_sample)
```

**Minimum data before training: 5,000 labeled judgments**

### Target Metrics

| Metric | Target |
|---|---|
| Accuracy | > 68% |
| F1 (macro) | > 0.62 |
| Brier score | < 0.20 |

If accuracy < 65%: check label extraction quality first, then feature leakage.

### Phase 2 API Endpoint (`api/routers/predict.py`)

```python
@router.post("/predict")
async def predict_outcome(
    court: str, case_type: str, judge_name: str,
    petitioner_type: str, respondent_type: str,
    acts_cited: list[str], case_summary: str
) -> dict:
    return {
        "predicted_outcome": "dismissed",
        "confidence": 0.68,
        "top_drivers": [
            {"factor": "Judge X: 71% dismiss rate for IPR", "direction": "negative"},
            {"factor": "Section 29 TM Act: historically weak", "direction": "negative"},
            {"factor": "Corporate petitioner: slight positive", "direction": "positive"},
        ],
        "similar_cases": [...],   # Reuse Phase 1 similarity search
        "judge_stats": {...},     # Reuse Phase 1 judge analytics
        "disclaimer": DISCLAIMER
    }
```

### Phase 2 Pitfalls

| Problem | Fix |
|---|---|
| Label extraction errors | Manually verify 200 samples before training |
| Feature leakage | Never use outcome-revealing fields from judgment text |
| Judge name inconsistency | Reuse Phase 1 normalizer map |
| Class imbalance | Use `scale_pos_weight` in XGBoost or SMOTE |
| Overfit on judge names | Use judge stats (rates), not raw judge ID |
| Slow inference | Cache all judge stats nightly in Redis |

---

## Infrastructure (Both Phases)

### docker-compose.yml

```yaml
services:
  api:
    build: ./api
    ports: ["8000:8000"]
    volumes: ["./data:/app/data", "./model/artifacts:/app/artifacts"]
    env_file: .env

  frontend:
    build: ./frontend
    ports: ["3000:3000"]

  db:
    image: postgres:15
    environment:
      POSTGRES_DB: legal_intelligence_db
      POSTGRES_USER: admin
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes: ["pgdata:/var/lib/postgresql/data"]

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
```

### Hosting

| Component | Service | Cost |
|---|---|---|
| API | AWS EC2 t3.medium | ~$30/mo |
| Embeddings (batch) | AWS EC2 g4dn.xlarge | ~$0.50/hr only for batch |
| DB | AWS RDS PostgreSQL | ~$25/mo |
| Frontend | Vercel | Free |

### .env.example

```
INDIAN_KANOON_API_KEY=
DB_PASSWORD=
JWT_SECRET=
ANTHROPIC_API_KEY=
REDIS_URL=redis://redis:6379
ENVIRONMENT=development
```

---

## Client Pitch

**Phase 1 pitch:** "How many hours does your team spend on precedent research per case? We cut that to 5 minutes."

**Phase 2 upsell:** "Now that you're using the research tool, want to see how judges have historically ruled on cases like yours?"

**Pricing:**
- Phase 1: ₹15K–₹25K/month per firm
- Phase 1 + 2 bundle: ₹35K–₹50K/month

**Target clients:** Litigation boutiques, corporate legal ops, insurance legal teams, PE/VC legal advisors

**Never say** "predict outcomes" — say "judicial analytics" or "case strategy intelligence"

---

## References

- InLegalBERT: https://huggingface.co/law-ai/InLegalBERT
- Indian Kanoon API: https://api.indiankanoon.org
- eCourts portal: https://ecourts.gov.in
- FAISS docs: https://faiss.ai
- SHAP docs: https://shap.readthedocs.io
- XGBoost docs: https://xgboost.readthedocs.io
- Anthropic API: https://docs.anthropic.com
