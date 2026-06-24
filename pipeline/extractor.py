"""
Judgment parser and metadata extractor.
Parses raw JSON records produced by scraper.py into structured records.
Outcome is extracted by regex first; ambiguous cases fall back to Cohere API.
"""

import os
import re
import json
import logging
from pathlib import Path
from typing import Optional

import cohere

from pipeline.judge_normalizer import normalize_judge

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Outcome patterns — order matters: more specific patterns first
# ---------------------------------------------------------------------------

OUTCOME_PATTERNS: dict[str, list[str]] = {
    "partially_allowed": [
        r"allowed\s+in\s+part",
        r"partially\s+allowed",
        r"partly\s+allowed",
        r"allowed\s+to\s+the\s+extent",
        r"decree\s+is\s+modified",
        r"modified\s+to\s+the\s+extent",
        r"suit\s+is\s+(hereby\s+)?decreed\s+in\s+part",
    ],
    "allowed": [
        r"petition\s+is\s+(hereby\s+)?allowed",
        r"appeal\s+is\s+(hereby\s+)?allowed",
        r"writ\s+petition\s+is\s+(hereby\s+)?allowed",
        r"application\s+is\s+(hereby\s+)?allowed",
        r"rule\s+is\s+made\s+absolute",
        r"suit\s+is\s+(hereby\s+)?decreed",
        r"decree\s+be\s+drawn",
        r"decree\s+is\s+(hereby\s+)?passed",
        r"decree\s+accordingly",
        r"allowed\s+with\s+costs",
        r"allowed\s+without\s+costs",
        r"injunction\s+is\s+(hereby\s+)?granted",
        r"permanent\s+injunction.*?granted",
        r"plaintiff\s+is\s+entitled\s+to\s+(a\s+)?decree",
        r"I\.A\.\s*(?:No\.)?\s*\d+.*?allowed",
        r"restrained.*?by\s+(an\s+)?interim\s+injunction",
        r"interim\s+injunction.*?restrain",
        r"order\s+accordingly",
    ],
    "dismissed": [
        r"petition\s+is\s+(hereby\s+)?dismissed",
        r"appeal\s+is\s+(hereby\s+)?dismissed",
        r"writ\s+petition\s+is\s+(hereby\s+)?dismissed",
        r"application\s+is\s+(hereby\s+)?dismissed",
        r"suit\s+is\s+(hereby\s+)?dismissed",
        r"no\s+merit",
        r"dismissed\s+with\s+costs",
        r"dismissed\s+as\s+withdrawn",
        r"dismissed\s+as\s+infructuous",
        r"dismissed\s+as\s+not\s+maintainable",
        r"no\s+case\s+is\s+made\s+out",
        r"plaintiff\s+has\s+failed\s+to\s+prove",
    ],
}

_COMPILED: dict[str, list[re.Pattern]] = {
    outcome: [re.compile(p, re.IGNORECASE) for p in patterns]
    for outcome, patterns in OUTCOME_PATTERNS.items()
}

ACTS_PATTERN = re.compile(
    r"(section\s+\d+[\w\s,]*?(?:of\s+the\s+)?(?:[A-Z][A-Za-z\s]+?Act(?:,\s*\d{4})?))",
    re.IGNORECASE,
)

_cohere_client: Optional[cohere.ClientV2] = None


def _get_cohere() -> cohere.ClientV2:
    global _cohere_client
    if _cohere_client is None:
        _cohere_client = cohere.ClientV2(api_key=os.environ["COHERE_API_KEY"])
    return _cohere_client


# ---------------------------------------------------------------------------
# Outcome extraction
# ---------------------------------------------------------------------------

def extract_outcome_regex(text: str) -> Optional[str]:
    """
    Search the last 1,500 characters of the judgment (operative portion).
    Returns outcome key or None when inconclusive.
    """
    tail = text[-2500:]
    for outcome in ("partially_allowed", "allowed", "dismissed"):
        for pattern in _COMPILED[outcome]:
            if pattern.search(tail):
                return outcome
    return None


def extract_outcome_cohere(text: str) -> str:
    """
    Fallback for regex-ambiguous cases.
    Sends last 500 words to Cohere command-r for classification (free tier).
    """
    words = text.split()
    snippet = " ".join(words[-500:])

    response = _get_cohere().chat(
        model="command-r-08-2024",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a legal text classifier. Reply with EXACTLY one word: "
                    "allowed, dismissed, or partially_allowed. No punctuation, no explanation."
                ),
            },
            {
                "role": "user",
                "content": f"Classify the outcome of this Indian court judgment excerpt:\n\n{snippet}",
            },
        ],
    )
    raw = response.message.content[0].text.strip().lower().replace(" ", "_").rstrip(".")
    if raw in ("allowed", "dismissed", "partially_allowed"):
        return raw
    log.warning("Cohere returned unexpected outcome '%s'; defaulting to 'dismissed'", raw)
    return "dismissed"


def extract_outcome(text: str, use_cohere_fallback: bool = False) -> str:
    outcome = extract_outcome_regex(text)
    if outcome:
        return outcome
    if use_cohere_fallback:
        return extract_outcome_cohere(text)
    return "unknown"


# ---------------------------------------------------------------------------
# Acts extraction
# ---------------------------------------------------------------------------

def extract_acts_cited(text: str) -> list[str]:
    """Return deduplicated list of acts/sections cited in the judgment."""
    matches = ACTS_PATTERN.findall(text)
    seen: set[str] = set()
    result: list[str] = []
    for m in matches:
        clean = re.sub(r"\s+", " ", m).strip()
        if clean not in seen:
            seen.add(clean)
            result.append(clean)
    return result[:20]  # cap at 20 to avoid noise


# ---------------------------------------------------------------------------
# Full record extraction
# ---------------------------------------------------------------------------

def extract_record(raw: dict) -> dict:
    """
    Transform a raw scraped record into a structured record ready for the DB
    and embedding pipeline.

    raw must contain at minimum: case_id, judgment_text, court, judgment_date.
    All other fields are extracted or defaulted.
    """
    text = raw.get("judgment_text", "")

    return {
        "case_id": raw["case_id"],
        "court": raw.get("court", ""),
        "judge_name": normalize_judge(raw.get("judge_name", "")),
        "case_type": raw.get("case_type", "unknown"),
        "acts_cited": raw.get("acts_cited") or extract_acts_cited(text),
        "petitioner_type": raw.get("petitioner_type", "unknown"),
        "respondent_type": raw.get("respondent_type", "unknown"),
        "hearing_count": raw.get("hearing_count", 0),
        "judgment_date": raw.get("judgment_date", ""),
        "judgment_text": text,
        "outcome": extract_outcome(text),
        "indian_kanoon_url": raw.get("indian_kanoon_url", ""),
    }


# ---------------------------------------------------------------------------
# Batch processing
# ---------------------------------------------------------------------------

def process_raw_dir(
    raw_dir: Path = Path("data/raw"),
    out_dir: Path = Path("data/processed"),
) -> int:
    """
    Process all .json files in raw_dir, write structured records to out_dir.
    Returns number of records processed.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    count = 0

    for path in sorted(raw_dir.glob("*.json")):
        out_path = out_dir / path.name
        if out_path.exists():
            continue
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            record = extract_record(raw)
            out_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
            count += 1
        except Exception:
            log.exception("Failed to process %s", path)

    log.info("Processed %d new records", count)
    return count
