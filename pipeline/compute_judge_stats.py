"""
Judge stats aggregation job — runs nightly (or on demand after a new scrape).
Reads all cases from Supabase, computes per-judge stats, upserts into judge_stats.

Never compute judge stats at request time — always read from the precomputed table.

Usage:
    python -m pipeline.compute_judge_stats
"""

import logging
import os
from collections import defaultdict

from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

_client: Client | None = None


def _get_client() -> Client:
    global _client
    if _client is None:
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_SERVICE_KEY")
        if not url or not key:
            raise SystemExit("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in .env")
        _client = create_client(url, key)
    return _client


# ---------------------------------------------------------------------------
# Fetch cases from Supabase
# ---------------------------------------------------------------------------

def _fetch_cases() -> list[dict]:
    """Fetch all cases with a known outcome from Supabase (paginated)."""
    client = _get_client()
    all_rows = []
    page_size = 1000
    offset = 0

    while True:
        result = (
            client.table("cases")
            .select("judge_name, case_type, outcome, hearing_count")
            .neq("outcome", "unknown")
            .range(offset, offset + page_size - 1)
            .execute()
        )
        rows = result.data or []
        all_rows.extend(rows)
        if len(rows) < page_size:
            break
        offset += page_size

    log.info("Fetched %d cases with known outcomes", len(all_rows))
    return all_rows


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

def _aggregate(cases: list[dict]) -> list[dict]:
    """
    Compute judge stats by (judge_name, case_type) and (judge_name, 'all').
    Returns list of row dicts ready to upsert into judge_stats.
    """
    # key → {total, allowed, dismissed, partially_allowed, hearing_sum}
    buckets: dict[tuple, dict] = defaultdict(lambda: {
        "total": 0, "allowed": 0, "dismissed": 0,
        "partially_allowed": 0, "hearing_sum": 0,
    })

    for case in cases:
        judge = case.get("judge_name", "unknown")
        ctype = case.get("case_type", "unknown")
        outcome = case.get("outcome", "unknown")
        hearings = case.get("hearing_count", 0) or 0

        for key in [(judge, ctype), (judge, "all")]:
            b = buckets[key]
            b["total"] += 1
            b["hearing_sum"] += hearings
            if outcome in ("allowed", "dismissed", "partially_allowed"):
                b[outcome] += 1

    rows = []
    for (judge_name, case_type), b in buckets.items():
        total = b["total"]
        rows.append({
            "judge_name":       judge_name,
            "case_type":        case_type,
            "total_cases":      total,
            "allowed":          b["allowed"],
            "dismissed":        b["dismissed"],
            "partially_allowed": b["partially_allowed"],
            "avg_hearing_count": round(b["hearing_sum"] / total, 2) if total else 0,
        })

    return rows


# ---------------------------------------------------------------------------
# Upsert
# ---------------------------------------------------------------------------

def compute_and_upsert() -> int:
    """Aggregate cases → judge_stats. Returns number of rows upserted."""
    cases = _fetch_cases()
    if not cases:
        log.warning("No cases with known outcomes found — nothing to aggregate")
        return 0

    rows = _aggregate(cases)
    log.info("Aggregated %d judge × case_type buckets", len(rows))

    client = _get_client()
    batch_size = 100
    total = 0
    for i in range(0, len(rows), batch_size):
        batch = rows[i : i + batch_size]
        result = (
            client.table("judge_stats")
            .upsert(batch, on_conflict="judge_name,case_type")
            .execute()
        )
        total += len(result.data)

    log.info("Upserted %d rows into judge_stats", total)
    return total


def main() -> None:
    compute_and_upsert()


if __name__ == "__main__":
    main()
