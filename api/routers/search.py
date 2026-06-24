"""
Search router — similar cases, citations, precedents, judge profiles.

All endpoints are synchronous (run_in_executor wraps CPU-bound embedding).
"""

import logging
from functools import partial

from fastapi import APIRouter, HTTPException

from api.schemas import (
    CitationResult,
    CitationsRequest,
    CitationsResponse,
    CaseResult,
    JudgeListItem,
    JudgeListResponse,
    JudgeProfileResponse,
    JudgeStatsByType,
    PrecedentResult,
    PrecedentsRequest,
    PrecedentsResponse,
    RecentJudgment,
    SimilarCasesRequest,
    SimilarCasesResponse,
)
from search.citation_ranker import get_citation_recommendations, get_winning_precedents
from search.judge_stats import get_judge_profile, list_judges
from search.similarity import find_similar_cases

log = logging.getLogger(__name__)

router = APIRouter(prefix="/search", tags=["search"])


# ---------------------------------------------------------------------------
# Similar cases
# ---------------------------------------------------------------------------

@router.post("/similar", response_model=SimilarCasesResponse)
def similar_cases(req: SimilarCasesRequest) -> SimilarCasesResponse:
    filters = {}
    if req.case_type:
        filters["case_type"] = req.case_type
    if req.court:
        filters["court"] = req.court
    if req.outcome:
        filters["outcome"] = req.outcome

    try:
        raw = find_similar_cases(req.query, top_k=req.top_k, filters=filters or None)
    except Exception as exc:
        log.exception("similar_cases failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    results = [CaseResult(**{k: v for k, v in r.items() if k != "disclaimer"}) for r in raw]
    return SimilarCasesResponse(results=results, total=len(results))


# ---------------------------------------------------------------------------
# Citations
# ---------------------------------------------------------------------------

@router.post("/citations", response_model=CitationsResponse)
def citations(req: CitationsRequest) -> CitationsResponse:
    try:
        raw = get_citation_recommendations(
            query_text=req.query,
            acts_cited=req.acts_cited,
            case_type=req.case_type,
            court=req.court,
            top_k=req.top_k,
        )
    except Exception as exc:
        log.exception("citations failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    results = [CitationResult(**{k: v for k, v in r.items() if k != "disclaimer"}) for r in raw]
    return CitationsResponse(results=results, total=len(results))


# ---------------------------------------------------------------------------
# Winning precedents
# ---------------------------------------------------------------------------

@router.post("/precedents", response_model=PrecedentsResponse)
def precedents(req: PrecedentsRequest) -> PrecedentsResponse:
    try:
        raw = get_winning_precedents(
            query_text=req.query,
            case_type=req.case_type,
            court=req.court,
            top_k=req.top_k,
        )
    except Exception as exc:
        log.exception("precedents failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    results = [PrecedentResult(**{k: v for k, v in r.items() if k != "disclaimer"}) for r in raw]
    return PrecedentsResponse(results=results, total=len(results))


# ---------------------------------------------------------------------------
# Judge profiles
# ---------------------------------------------------------------------------

@router.get("/judges", response_model=JudgeListResponse)
def judges_list() -> JudgeListResponse:
    try:
        raw = list_judges()
    except Exception as exc:
        log.exception("judges_list failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    items = [
        JudgeListItem(
            judge_name=j["judge_name"],
            total_cases=j["total_cases"],
            allow_rate=round(j.get("allow_rate") or 0.0, 4),
            avg_hearing_count=float(j.get("avg_hearing_count") or 0),
        )
        for j in raw
    ]
    return JudgeListResponse(judges=items, total=len(items))


@router.get("/judges/{judge_name}", response_model=JudgeProfileResponse)
def judge_profile(judge_name: str, case_type: str | None = None) -> JudgeProfileResponse:
    try:
        profile = get_judge_profile(judge_name, case_type)
    except Exception as exc:
        log.exception("judge_profile failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if not profile:
        raise HTTPException(
            status_code=404,
            detail=f"Judge '{judge_name}' not found. Use GET /search/judges to list all.",
        )

    by_case_type = {
        ct: JudgeStatsByType(**stats)
        for ct, stats in profile.get("by_case_type", {}).items()
    }

    recent = [
        RecentJudgment(**j)
        for j in profile.get("recent_judgments", [])
    ]

    return JudgeProfileResponse(
        judge_name=profile["judge_name"],
        display_name=profile["display_name"],
        total_cases=profile["total_cases"],
        overall_allow_rate=profile["overall_allow_rate"],
        overall_dismiss_rate=profile["overall_dismiss_rate"],
        avg_hearings_before_judgment=profile["avg_hearings_before_judgment"],
        by_case_type=by_case_type,
        recent_judgments=recent,
    )
