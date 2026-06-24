"""
Scraper for Indian Kanoon API (primary) and eCourts (supplementary).

MVP scope: Delhi HC + IPR cases only.
Rate limit: 1 req/s to Indian Kanoon (enforced by ratelimit decorator).
Raw JSON is always persisted before parsing — never lose source data.

Usage:
    python -m pipeline.scraper --query "trademark infringement Delhi High Court" \
                               --max 1000 --out data/raw
"""

import argparse
import json
import logging
import os
import time
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

IK_BASE_URL = "https://api.indiankanoon.org"
ECOURTS_BASE_URL = "https://services.ecourts.gov.in/ecourtindia_v6"

# MVP scope: only these courts in Phase 1
ALLOWED_COURTS = {"Delhi High Court"}

# MVP case type filter
IPR_KEYWORDS = {
    "trademark", "copyright", "patent", "intellectual property",
    "ipr", "passing off", "infringement", "trade mark",
}

REQUIRED_FIELDS = [
    "case_id",
    "court",
    "judge_name",
    "case_type",
    "acts_cited",
    "petitioner_type",
    "respondent_type",
    "hearing_count",
    "judgment_date",
    "judgment_text",
    "outcome",
    "indian_kanoon_url",
]


# ---------------------------------------------------------------------------
# Indian Kanoon API client
# ---------------------------------------------------------------------------

class IndianKanoonClient:
    def __init__(self, api_key: str) -> None:
        self._session = requests.Session()
        self._session.headers.update({"Authorization": f"Token {api_key}"})

    def _request(self, method: str, path: str, params: dict) -> dict:
        time.sleep(1)  # enforce 1 req/s to Indian Kanoon
        url = f"{IK_BASE_URL}/{path.lstrip('/')}"
        if method == "POST":
            resp = self._session.post(url, data=params, timeout=30)
        else:
            resp = self._session.get(url, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def search(
        self,
        query: str,
        page: int = 0,
        doc_types: str = "judgments",
    ) -> dict:
        """IK search requires POST with form-encoded body."""
        return self._request(
            "POST", "/search/",
            {"formInput": query, "pagenum": page, "doctype": doc_types},
        )

    def get_doc(self, doc_id: int) -> dict:
        """Fetch full judgment document by IK doc ID."""
        return self._request("POST", f"/doc/{doc_id}/", {})

    def get_doc_meta(self, doc_id: int) -> dict:
        return self._request("POST", f"/docmeta/{doc_id}/", {})


# ---------------------------------------------------------------------------
# Case type inference
# ---------------------------------------------------------------------------

def infer_case_type(title: str, text: str) -> str:
    combined = (title + " " + text[:500]).lower()
    if any(k in combined for k in IPR_KEYWORDS):
        return "IPR"
    if any(k in combined for k in {"tax", "income tax", "gst", "customs", "excise"}):
        return "tax"
    if any(k in combined for k in {"criminal", "culpable", "murder", "theft", "accused"}):
        return "criminal"
    if any(k in combined for k in {"labour", "workman", "industrial dispute", "dismissal"}):
        return "labour"
    return "civil"


def infer_party_type(name: str) -> str:
    name_l = name.lower()
    if any(k in name_l for k in {"union of india", "government", "state of", "ministry", "collector"}):
        return "government"
    if any(k in name_l for k in {"ltd", "limited", "pvt", "private", "corp", "inc", "llp"}):
        return "corporation"
    if any(k in name_l for k in {"trust", "ngo", "society", "foundation", "association"}):
        return "NGO"
    return "individual"


# ---------------------------------------------------------------------------
# Raw record builder
# ---------------------------------------------------------------------------

def _strip_html(html: str) -> str:
    """Convert IK HTML judgment to plain text."""
    return BeautifulSoup(html, "lxml").get_text(separator="\n")


def build_raw_record(doc: dict, search_item: dict) -> Optional[dict]:
    """
    Map IK API response to our REQUIRED_FIELDS schema.
    doc       — from POST /doc/<tid>/
    search_item — the matching entry from the /search/ results page
    Returns None if the document should be skipped (wrong court, no text, etc.).
    """
    doc_id = str(doc.get("tid", ""))
    title = doc.get("title") or search_item.get("title", "")

    # docsource is the court name field in the IK API
    court = (doc.get("docsource") or search_item.get("docsource") or "").strip()

    # MVP scope gate
    if court not in ALLOWED_COURTS:
        log.debug("Skipping %s — court '%s' not in scope", doc_id, court)
        return None

    html = doc.get("doc", "")
    if not html:
        log.debug("Skipping %s — no judgment text", doc_id)
        return None
    text = _strip_html(html)

    # judge name: prefer search_item.author (cleaner), fall back to extracting from HTML
    judge_name = search_item.get("author") or doc.get("author") or ""

    # publishdate is already ISO (YYYY-MM-DD) from the API
    judgment_date = doc.get("publishdate") or search_item.get("publishdate") or ""

    case_type = infer_case_type(title, text)
    title_lower = title.lower()
    sep = " vs " if " vs " in title_lower else " v. " if " v. " in title_lower else None
    petitioner = title.split(sep)[0].strip() if sep else title
    respondent = title.split(sep)[-1].strip() if sep else ""

    return {
        "case_id": f"ik_{doc_id}",
        "court": court,
        "judge_name": judge_name,
        "case_type": case_type,
        "acts_cited": [],           # populated by extractor.py
        "petitioner_type": infer_party_type(petitioner),
        "respondent_type": infer_party_type(respondent),
        "hearing_count": 0,
        "judgment_date": judgment_date,
        "judgment_text": text,
        "outcome": "",              # populated by extractor.py
        "indian_kanoon_url": f"https://indiankanoon.org/doc/{doc_id}/",
        "_title": title,
    }


# ---------------------------------------------------------------------------
# Main scrape loop
# ---------------------------------------------------------------------------

def scrape_delhi_hc_ipr(
    api_key: str,
    max_docs: int = 1000,
    out_dir: Path = Path("data/raw"),
) -> int:
    """
    Scrape Delhi HC IPR judgments from Indian Kanoon.
    Persists one JSON file per judgment in out_dir.
    Returns number of new documents saved.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    client = IndianKanoonClient(api_key)

    query = (
        "trademark infringement Delhi High Court "
        "OR copyright infringement Delhi High Court "
        "OR patent infringement Delhi High Court"
    )

    saved = 0
    page = 0

    while saved < max_docs:
        log.info("Fetching page %d (saved %d / %d)", page, saved, max_docs)

        try:
            results = client.search(query, page=page)
        except requests.HTTPError as e:
            log.error("Search page %d failed: %s", page, e)
            break

        docs = results.get("docs", [])
        if not docs:
            log.info("No more results at page %d", page)
            break

        for item in docs:
            if saved >= max_docs:
                break

            doc_id = item.get("tid")
            if not doc_id:
                continue

            out_path = out_dir / f"ik_{doc_id}.json"
            if out_path.exists():
                saved += 1
                continue

            try:
                doc = client.get_doc(doc_id)
            except requests.HTTPError as e:
                log.warning("Failed to fetch doc %s: %s", doc_id, e)
                continue

            record = build_raw_record(doc, item)
            if record is None:
                continue

            out_path.write_text(
                json.dumps(record, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            saved += 1
            log.info("[%d] Saved %s — %s", saved, record["case_id"], record.get("_title", "")[:60])

        page += 1
        # defensive sleep between pages beyond the per-call rate limit
        time.sleep(0.5)

    log.info("Scrape complete. Total saved: %d", saved)
    return saved


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape Indian Kanoon judgments")
    parser.add_argument("--max", type=int, default=1000, help="Max docs to fetch")
    parser.add_argument("--out", type=Path, default=Path("data/raw"), help="Output directory")
    args = parser.parse_args()

    api_key = os.environ.get("INDIAN_KANOON_API_KEY")
    if not api_key:
        raise SystemExit("INDIAN_KANOON_API_KEY environment variable not set")

    scrape_delhi_hc_ipr(api_key=api_key, max_docs=args.max, out_dir=args.out)


if __name__ == "__main__":
    main()
