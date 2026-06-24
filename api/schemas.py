"""
Pydantic request / response schemas for the Legal Case Intelligence API.

All response models include a `disclaimer` field that must be surfaced to
the end user — never omit it in the frontend.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Shared
# ---------------------------------------------------------------------------

DISCLAIMER_RESEARCH = (
    "This is a research aid based on historical judgments. "
    "It does not constitute legal advice. Consult a qualified advocate."
)

DISCLAIMER_ANALYSIS = (
    "This analysis is a research aid based on historical judgment patterns. "
    "It does not constitute legal advice. Consult a qualified advocate before "
    "relying on any observation made here."
)

DISCLAIMER_CITATIONS = (
    "Citation suggestions are based on semantic similarity to historical judgments "
    "and do not guarantee legal relevance. Verify each citation independently."
)

DISCLAIMER_JUDGES = (
    "Judge analytics are based on scraped historical data and may be incomplete. "
    "Do not use as the sole basis for legal strategy."
)


# ---------------------------------------------------------------------------
# /search/similar
# ---------------------------------------------------------------------------

class SimilarCasesRequest(BaseModel):
    query: str = Field(..., min_length=10, description="Case facts or argument summary")
    top_k: int = Field(10, ge=1, le=50)
    case_type: str | None = Field(None, description="IPR / civil / criminal / labour / tax")
    court: str | None = Field(None, description="e.g. 'Delhi High Court'")
    outcome: str | None = Field(None, description="allowed / dismissed / partially_allowed")


class CaseResult(BaseModel):
    case_id: str
    title: str
    court: str
    date: str
    judge: str
    outcome: str
    similarity_score: float
    acts_cited: list[str]
    summary: str
    url: str


class SimilarCasesResponse(BaseModel):
    results: list[CaseResult]
    total: int
    disclaimer: str = DISCLAIMER_RESEARCH


# ---------------------------------------------------------------------------
# /search/citations
# ---------------------------------------------------------------------------

class CitationsRequest(BaseModel):
    query: str = Field(..., min_length=10)
    acts_cited: list[str] = Field(default_factory=list, description="Acts relevant to the case")
    case_type: str = Field("IPR")
    court: str | None = None
    top_k: int = Field(5, ge=1, le=20)


class CitationResult(BaseModel):
    case_id: str
    title: str
    court: str
    date: str
    judge: str
    outcome: str
    similarity_score: float
    acts_cited: list[str]
    shared_acts: list[str]
    summary: str
    url: str


class CitationsResponse(BaseModel):
    results: list[CitationResult]
    total: int
    disclaimer: str = DISCLAIMER_CITATIONS


# ---------------------------------------------------------------------------
# /search/precedents
# ---------------------------------------------------------------------------

class PrecedentsRequest(BaseModel):
    query: str = Field(..., min_length=10)
    case_type: str = Field("IPR")
    court: str | None = None
    top_k: int = Field(5, ge=1, le=20)


class PrecedentResult(BaseModel):
    case_id: str
    title: str
    court: str
    date: str
    judge: str
    similarity_score: float
    acts_cited: list[str]
    summary: str
    url: str


class PrecedentsResponse(BaseModel):
    results: list[PrecedentResult]
    total: int
    disclaimer: str = DISCLAIMER_CITATIONS


# ---------------------------------------------------------------------------
# /judges
# ---------------------------------------------------------------------------

class JudgeStatsByType(BaseModel):
    allow_rate: float
    total: int
    allowed: int
    dismissed: int
    partially_allowed: int


class RecentJudgment(BaseModel):
    case_id: str
    title: str
    date: str
    outcome: str
    url: str


class JudgeProfileResponse(BaseModel):
    judge_name: str
    display_name: str
    total_cases: int
    overall_allow_rate: float
    overall_dismiss_rate: float
    avg_hearings_before_judgment: float
    by_case_type: dict[str, JudgeStatsByType]
    recent_judgments: list[RecentJudgment]
    disclaimer: str = DISCLAIMER_JUDGES


class JudgeListItem(BaseModel):
    judge_name: str
    total_cases: int
    allow_rate: float
    avg_hearing_count: float


class JudgeListResponse(BaseModel):
    judges: list[JudgeListItem]
    total: int


# ---------------------------------------------------------------------------
# /strategy/analyze
# ---------------------------------------------------------------------------

class AnalyzeRequest(BaseModel):
    argument: str = Field(..., min_length=20, description="Lawyer's argument summary")
    case_type: str = Field("IPR")
    court: str = Field("Delhi High Court")
    top_k: int = Field(10, ge=1, le=30)


class AnalysisResponse(BaseModel):
    overall_score: str
    strengths: list[str]
    weaknesses: list[str]
    missing_elements: list[str]
    suggested_citations: list[str]
    similar_cases_used: int
    raw_analysis: str
    disclaimer: str = DISCLAIMER_ANALYSIS


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    status: str
    version: str
