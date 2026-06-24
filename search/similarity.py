"""
Similar Case Finder — Phase 1, Step 3.

Primary path:  embed query → call match_cases() pgvector RPC on Supabase
Fallback path: embed query → search local FAISS index (offline / testing)

Usage (CLI):
    python -m search.similarity "trademark infringement phonetic similarity"
    python -m search.similarity "patent drug formulation" --top-k 5 --case-type IPR
    python -m search.similarity "..." --local   # use local FAISS index
"""

import argparse
import json
import logging
import os
from pathlib import Path

import numpy as np
from dotenv import load_dotenv
from supabase import create_client, Client

from pipeline.embedder import embed_text, load_faiss_index

load_dotenv()

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

DISCLAIMER = (
    "This is a research aid based on historical judgments. "
    "It does not constitute legal advice. Consult a qualified advocate."
)

_supabase_client: Client | None = None


def _get_client() -> Client:
    global _supabase_client
    if _supabase_client is None:
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_SERVICE_KEY")
        if not url or not key:
            raise SystemExit("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in .env")
        _supabase_client = create_client(url, key)
    return _supabase_client


# ---------------------------------------------------------------------------
# Result formatting
# ---------------------------------------------------------------------------

def _extract_title(row: dict) -> str:
    """Derive a case title from the first non-empty line of the summary."""
    text = row.get("summary") or row.get("judgment_text", "")
    for line in text.splitlines():
        line = line.strip()
        if len(line) > 10:
            return line[:120]
    return row.get("case_id", "")


def _format_result(row: dict, similarity: float) -> dict:
    return {
        "case_id":        row["case_id"],
        "title":          _extract_title(row),
        "court":          row.get("court", ""),
        "date":           str(row.get("judgment_date") or ""),
        "judge":          row.get("judge_name", "").replace("_", " ").title(),
        "outcome":        row.get("outcome", "unknown"),
        "similarity_score": round(similarity, 4),
        "acts_cited":     row.get("acts_cited", []),
        "summary":        (row.get("summary") or row.get("judgment_text", ""))[:300],
        "url":            row.get("indian_kanoon_url", ""),
        "disclaimer":     DISCLAIMER,
    }


# ---------------------------------------------------------------------------
# Primary: Supabase pgvector search
# ---------------------------------------------------------------------------

def find_similar_cases(
    query_text: str,
    top_k: int = 10,
    filters: dict | None = None,
) -> list[dict]:
    """
    Find the top_k cases most similar to query_text.

    filters (optional):
        {"case_type": "IPR", "court": "Delhi High Court", "outcome": "allowed"}

    Returns a list of result dicts ordered by descending similarity score.
    """
    vec = embed_text(query_text).tolist()

    filters = filters or {}
    result = _get_client().rpc(
        "match_cases",
        {
            "query_embedding": vec,
            "match_count":     top_k,
            "filter_court":     filters.get("court"),
            "filter_case_type": filters.get("case_type"),
            "filter_outcome":   filters.get("outcome"),
        },
    ).execute()

    rows = result.data or []
    return [_format_result(row, row.get("similarity", 0.0)) for row in rows]


# ---------------------------------------------------------------------------
# Fallback: local FAISS search
# ---------------------------------------------------------------------------

def find_similar_cases_local(
    query_text: str,
    top_k: int = 10,
    processed_dir: Path = Path("data/processed"),
) -> list[dict]:
    """
    Offline similarity search using the local FAISS index.
    No Supabase connection required.
    """
    index, case_ids = load_faiss_index()
    vec = embed_text(query_text).reshape(1, -1).astype(np.float32)

    k = min(top_k, index.ntotal)
    scores, indices = index.search(vec, k)

    results = []
    for score, idx in zip(scores[0], indices[0]):
        if idx < 0:
            continue
        case_id = case_ids[idx]
        path = processed_dir / f"{case_id}.json"
        if not path.exists():
            continue
        row = json.loads(path.read_text(encoding="utf-8"))
        results.append(_format_result(row, float(score)))

    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _print_results(results: list[dict]) -> None:
    if not results:
        print("No results found.")
        return
    print(f"\nFound {len(results)} similar cases:\n")
    for i, r in enumerate(results, 1):
        print(f"[{i}] {r['outcome'].upper():<18} | Score: {r['similarity_score']:.3f}")
        print(f"    {r['title']}")
        print(f"    {r['court']} | {r['date']} | {r['judge']}")
        if r["acts_cited"]:
            print(f"    Acts: {', '.join(r['acts_cited'][:3])}")
        print(f"    {r['url']}")
        print()
    print(f"--- {DISCLAIMER} ---")


def main() -> None:
    parser = argparse.ArgumentParser(description="Find similar Indian court cases")
    parser.add_argument("query", help="Case facts or argument summary to search with")
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--case-type", help="Filter: IPR / civil / criminal / labour / tax")
    parser.add_argument("--court", help="Filter: e.g. 'Delhi High Court'")
    parser.add_argument("--outcome", help="Filter: allowed / dismissed / partially_allowed")
    parser.add_argument("--local", action="store_true", help="Use local FAISS index (offline)")
    args = parser.parse_args()

    if args.local:
        results = find_similar_cases_local(args.query, args.top_k)
    else:
        filters = {}
        if args.case_type:
            filters["case_type"] = args.case_type
        if args.court:
            filters["court"] = args.court
        if args.outcome:
            filters["outcome"] = args.outcome
        results = find_similar_cases(args.query, args.top_k, filters)

    _print_results(results)


if __name__ == "__main__":
    main()
