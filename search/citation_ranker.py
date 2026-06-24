"""
Citation Recommendations + Winning Precedents — Phase 1, Step 6.

Thin filters on top of find_similar_cases():
  - get_citation_recommendations: cases that cite the same Acts as the query
  - get_winning_precedents:        cases with outcome=allowed, ranked by similarity

Usage (CLI):
    python -m search.citation_ranker "phonetically identical trademark consumer confusion"
    python -m search.citation_ranker "patent drug formulation" --acts "Patents Act" --top-k 5
    python -m search.citation_ranker "..." --precedents
"""

import argparse
import logging

from dotenv import load_dotenv

from search.similarity import find_similar_cases

load_dotenv()

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

DISCLAIMER = (
    "Citation suggestions are based on semantic similarity to historical judgments "
    "and do not guarantee legal relevance. Verify each citation independently."
)


# ---------------------------------------------------------------------------
# Citation recommendations
# ---------------------------------------------------------------------------

def get_citation_recommendations(
    query_text: str,
    acts_cited: list[str] | None = None,
    case_type: str = "IPR",
    court: str | None = None,
    top_k: int = 5,
) -> list[dict]:
    """
    Return cases most semantically similar to query_text.

    If acts_cited is provided, boost cases that share at least one act by
    placing them first (stable sort — similarity order preserved within group).

    Returns list of dicts with citation metadata + disclaimer.
    """
    filters: dict = {"case_type": case_type}
    if court:
        filters["court"] = court

    candidates = find_similar_cases(query_text, top_k=top_k * 3, filters=filters)

    if not candidates and court:
        # retry without court filter when corpus is small
        candidates = find_similar_cases(query_text, top_k=top_k * 3, filters={"case_type": case_type})

    if not candidates:
        candidates = find_similar_cases(query_text, top_k=top_k * 3)

    normalized_acts = {a.lower().strip() for a in (acts_cited or [])}

    def _act_overlap(case: dict) -> bool:
        if not normalized_acts:
            return False
        case_acts = {a.lower().strip() for a in case.get("acts_cited", [])}
        return bool(normalized_acts & case_acts)

    if normalized_acts:
        # stable-sort: act-overlap cases first, then the rest
        overlapping = [c for c in candidates if _act_overlap(c)]
        others = [c for c in candidates if not _act_overlap(c)]
        ranked = (overlapping + others)[:top_k]
    else:
        ranked = candidates[:top_k]

    results = []
    for case in ranked:
        shared = [
            a for a in case.get("acts_cited", [])
            if a.lower().strip() in normalized_acts
        ] if normalized_acts else []

        results.append({
            "case_id":         case["case_id"],
            "title":           case["title"],
            "court":           case["court"],
            "date":            case["date"],
            "judge":           case["judge"],
            "outcome":         case["outcome"],
            "similarity_score": case["similarity_score"],
            "acts_cited":      case["acts_cited"],
            "shared_acts":     shared,
            "summary":         case["summary"],
            "url":             case["url"],
            "disclaimer":      DISCLAIMER,
        })

    return results


# ---------------------------------------------------------------------------
# Winning precedents
# ---------------------------------------------------------------------------

def get_winning_precedents(
    query_text: str,
    case_type: str = "IPR",
    court: str | None = None,
    top_k: int = 5,
) -> list[dict]:
    """
    Return the top_k cases most similar to query_text that were allowed (won).

    Falls back to unfiltered search if the court+outcome combination yields
    too few results (fewer than top_k // 2).
    """
    filters: dict = {"case_type": case_type, "outcome": "allowed"}
    if court:
        filters["court"] = court

    results = find_similar_cases(query_text, top_k=top_k * 2, filters=filters)

    if len(results) < max(1, top_k // 2) and court:
        # retry without court filter
        results = find_similar_cases(
            query_text,
            top_k=top_k * 2,
            filters={"case_type": case_type, "outcome": "allowed"},
        )

    precedents = []
    for case in results[:top_k]:
        precedents.append({
            "case_id":         case["case_id"],
            "title":           case["title"],
            "court":           case["court"],
            "date":            case["date"],
            "judge":           case["judge"],
            "similarity_score": case["similarity_score"],
            "acts_cited":      case["acts_cited"],
            "summary":         case["summary"],
            "url":             case["url"],
            "disclaimer":      DISCLAIMER,
        })

    return precedents


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _print_citations(results: list[dict]) -> None:
    if not results:
        print("No citation recommendations found.")
        return
    print(f"\nTop {len(results)} citation recommendations:\n")
    for i, r in enumerate(results, 1):
        shared = f"  [Shared acts: {', '.join(r['shared_acts'])}]" if r.get("shared_acts") else ""
        print(f"[{i}] Score: {r['similarity_score']:.3f} | {r['outcome'].upper():<18}{shared}")
        print(f"    {r['title']}")
        print(f"    {r['court']} | {r['date']} | {r['judge']}")
        if r["acts_cited"]:
            print(f"    Acts: {', '.join(r['acts_cited'][:4])}")
        print(f"    {r['url']}")
        print()
    print(f"--- {DISCLAIMER} ---")


def _print_precedents(results: list[dict]) -> None:
    if not results:
        print("No winning precedents found.")
        return
    print(f"\nTop {len(results)} winning precedents:\n")
    for i, r in enumerate(results, 1):
        print(f"[{i}] Score: {r['similarity_score']:.3f} | ALLOWED")
        print(f"    {r['title']}")
        print(f"    {r['court']} | {r['date']} | {r['judge']}")
        if r["acts_cited"]:
            print(f"    Acts: {', '.join(r['acts_cited'][:4])}")
        print(f"    {r['url']}")
        print()
    print(f"--- {DISCLAIMER} ---")


def main() -> None:
    parser = argparse.ArgumentParser(description="Citation recommendations and winning precedents")
    parser.add_argument("query", help="Case facts or argument summary")
    parser.add_argument("--acts", nargs="*", default=[], metavar="ACT",
                        help="Acts cited (e.g. 'Trade Marks Act' 'Patents Act')")
    parser.add_argument("--case-type", default="IPR")
    parser.add_argument("--court", default=None)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--precedents", action="store_true",
                        help="Show winning precedents instead of general citations")
    args = parser.parse_args()

    if args.precedents:
        results = get_winning_precedents(
            args.query, args.case_type, args.court, args.top_k
        )
        _print_precedents(results)
    else:
        results = get_citation_recommendations(
            args.query, args.acts, args.case_type, args.court, args.top_k
        )
        _print_citations(results)


if __name__ == "__main__":
    main()
