"""
Strategy router — argument strength analysis via Cohere.
"""

import logging

from fastapi import APIRouter, HTTPException

from api.schemas import AnalyzeRequest, AnalysisResponse
from strategy.analyzer import analyze_argument_strength

log = logging.getLogger(__name__)

router = APIRouter(prefix="/strategy", tags=["strategy"])


@router.post("/analyze", response_model=AnalysisResponse)
def analyze(req: AnalyzeRequest) -> AnalysisResponse:
    try:
        result = analyze_argument_strength(
            argument_summary=req.argument,
            case_type=req.case_type,
            court=req.court,
            top_k=req.top_k,
        )
    except Exception as exc:
        log.exception("analyze failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return AnalysisResponse(
        overall_score=result.get("overall_score", "Unknown"),
        strengths=result.get("strengths", []),
        weaknesses=result.get("weaknesses", []),
        missing_elements=result.get("missing_elements", []),
        suggested_citations=result.get("suggested_citations", []),
        similar_cases_used=result.get("similar_cases_used", 0),
        raw_analysis=result.get("raw_analysis", ""),
    )
