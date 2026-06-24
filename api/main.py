"""
Legal Case Intelligence Platform — FastAPI application.

Run locally:
    uvicorn api.main:app --reload --port 8000

Swagger UI:  http://localhost:8000/docs
ReDoc:       http://localhost:8000/redoc
"""

import logging
import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import search, strategy
from api.schemas import HealthResponse

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)

VERSION = "0.1.0"

app = FastAPI(
    title="Legal Case Intelligence Platform",
    description=(
        "AI-powered research assistant for Indian court cases. "
        "Find similar cases, analyse argument strength, discover winning precedents, "
        "and explore judge history.\n\n"
        "**All responses include a `disclaimer` field that must be shown to the user.**"
    ),
    version=VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ---------------------------------------------------------------------------
# CORS — allow the React frontend (dev: 3000, prod: same origin)
# ---------------------------------------------------------------------------

_origins = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
]
extra_origin = os.environ.get("FRONTEND_ORIGIN")
if extra_origin:
    _origins.append(extra_origin)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(search.router, prefix="/api/v1")
app.include_router(strategy.router, prefix="/api/v1")


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/health", response_model=HealthResponse, tags=["health"])
def health() -> HealthResponse:
    return HealthResponse(status="ok", version=VERSION)


@app.get("/", include_in_schema=False)
def root():
    return {"message": "Legal Case Intelligence API", "docs": "/docs"}
