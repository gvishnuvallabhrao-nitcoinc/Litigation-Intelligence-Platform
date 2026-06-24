"""
Argument Strength Analysis — Phase 1, Step 5.

Uses Cohere command-r-plus-08-2024 to score a lawyer's argument against
winning and losing patterns found in similar cases.

Never give legal advice — frame output as analytical observations only.

Usage (CLI):
    python -m strategy.analyzer \
        --argument "The defendant used a phonetically identical mark causing consumer confusion" \
        --case-type IPR --court "Delhi High Court"
"""

import argparse
import logging
import os

import cohere
from dotenv import load_dotenv

from search.similarity import find_similar_cases

load_dotenv()

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

DISCLAIMER = (
    "This analysis is a research aid based on historical judgment patterns. "
    "It does not constitute legal advice. Consult a qualified advocate before "
    "relying on any observation made here."
)

SYSTEM_PROMPT = (
    "You are a legal strategy analyst specialising in Indian courts. "
    "Given a lawyer's argument summary and similar winning/losing cases, "
    "analyse the strength of the argument. Be specific — cite patterns from "
    "the similar cases provided. Never give legal advice; frame everything as "
    "analytical observations only."
)

_cohere_client: cohere.ClientV2 | None = None


def _get_cohere() -> cohere.ClientV2:
    global _cohere_client
    if _cohere_client is None:
        key = os.environ.get("COHERE_API_KEY")
        if not key:
            raise SystemExit("COHERE_API_KEY must be set in .env")
        _cohere_client = cohere.ClientV2(api_key=key)
    return _cohere_client


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _format_cases(cases: list[dict], max_cases: int = 5) -> str:
    if not cases:
        return "None found."
    lines = []
    for c in cases[:max_cases]:
        acts = ", ".join(c.get("acts_cited", [])[:3]) or "—"
        lines.append(
            f"- {c['title'][:80]} ({c['date'][:4]}) | "
            f"Score: {c['similarity_score']:.2f} | Acts: {acts}\n"
            f"  Summary: {c['summary'][:200]}"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Core analysis
# ---------------------------------------------------------------------------

def analyze_argument_strength(
    argument_summary: str,
    case_type: str,
    court: str,
    top_k: int = 10,
) -> dict:
    """
    Analyse how strong argument_summary is based on similar case patterns.

    Returns:
        strengths        — what aligns with winning patterns
        weaknesses       — what aligns with losing patterns
        missing_elements — what winning cases had that this argument lacks
        suggested_citations — cases from the similar set to cite
        overall_score    — Weak / Moderate / Strong
        disclaimer
    """
    filters = {"case_type": case_type, "court": court}
    similar = find_similar_cases(argument_summary, top_k=top_k, filters=filters)

    if not similar:
        # fall back to no filters if the corpus is too small
        similar = find_similar_cases(argument_summary, top_k=top_k)

    winning = [c for c in similar if c["outcome"] == "allowed"]
    losing  = [c for c in similar if c["outcome"] == "dismissed"]

    prompt = f"""Case Type: {case_type} | Court: {court}

Lawyer's Argument:
{argument_summary}

Similar Winning Cases ({len(winning)}):
{_format_cases(winning)}

Similar Losing Cases ({len(losing)}):
{_format_cases(losing)}

Analyse the following and respond in exactly this format:

STRENGTHS:
[bullet points — what aligns with winning patterns]

WEAKNESSES:
[bullet points — what aligns with losing patterns]

MISSING ELEMENTS:
[bullet points — what winning cases had that this argument lacks]

SUGGESTED CITATIONS:
[bullet points — specific cases from above worth citing]

OVERALL SCORE: [Weak / Moderate / Strong]
[one sentence justification]"""

    response = _get_cohere().chat(
        model="command-r-plus-08-2024",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": prompt},
        ],
    )

    raw = response.message.content[0].text.strip()
    parsed = _parse_response(raw)
    parsed["similar_cases_used"] = len(similar)
    parsed["disclaimer"] = DISCLAIMER
    return parsed


def _parse_response(text: str) -> dict:
    """Extract sections from the structured response."""
    sections = {
        "strengths":           [],
        "weaknesses":          [],
        "missing_elements":    [],
        "suggested_citations": [],
        "overall_score":       "Unknown",
        "raw_analysis":        text,
    }

    current = None
    score_next = False

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue

        upper = stripped.upper()
        if upper.startswith("STRENGTHS"):
            current = "strengths"; continue
        if upper.startswith("WEAKNESSES"):
            current = "weaknesses"; continue
        if upper.startswith("MISSING ELEMENTS"):
            current = "missing_elements"; continue
        if upper.startswith("SUGGESTED CITATIONS"):
            current = "suggested_citations"; continue
        if upper.startswith("OVERALL SCORE"):
            score_part = stripped.split(":", 1)[-1].strip()
            for level in ("Strong", "Moderate", "Weak"):
                if level.lower() in score_part.lower():
                    sections["overall_score"] = level
                    break
            current = None
            score_next = True
            continue

        if current and stripped.startswith(("-", "•", "*")):
            sections[current].append(stripped.lstrip("-•* ").strip())

    return sections


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Analyse argument strength against similar cases")
    parser.add_argument("--argument", required=True, help="Lawyer's argument summary")
    parser.add_argument("--case-type", default="IPR", help="IPR / civil / criminal / etc.")
    parser.add_argument("--court", default="Delhi High Court")
    parser.add_argument("--top-k", type=int, default=10)
    args = parser.parse_args()

    result = analyze_argument_strength(
        args.argument, args.case_type, args.court, args.top_k
    )

    print(f"\nArgument Strength: {result['overall_score'].upper()}")
    print(f"Based on {result['similar_cases_used']} similar cases\n")

    for section, key in [
        ("Strengths",           "strengths"),
        ("Weaknesses",          "weaknesses"),
        ("Missing Elements",    "missing_elements"),
        ("Suggested Citations", "suggested_citations"),
    ]:
        items = result.get(key, [])
        if items:
            print(f"{section}:")
            for item in items:
                print(f"  • {item}")
            print()

    print(f"--- {result['disclaimer']} ---")


if __name__ == "__main__":
    main()
