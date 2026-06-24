"""
Judge History Analysis — Phase 1, Step 4.

Reads precomputed stats from the judge_stats table (never computes on request).
Also fetches the judge's 5 most recent judgments from the cases table.

Usage (CLI):
    python -m search.judge_stats "m_singh"
    python -m search.judge_stats "manmohan singh" --case-type IPR
    python -m search.judge_stats --list        # show all judges in DB
"""

import argparse
import logging
import os

from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

DISCLAIMER = (
    "Judge analytics are based on scraped historical data and may be incomplete. "
    "Do not use as the sole basis for legal strategy."
)

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
# Name resolution
# ---------------------------------------------------------------------------

def resolve_judge_name(raw: str) -> str | None:
    """
    Accept either a normalized key ('m_singh') or a display-name fragment
    ('manmohan singh'). Returns the canonical DB key or None if not found.
    """
    client = _get_client()
    normalized = raw.strip().lower().replace(" ", "_")

    # Try exact match first
    result = (
        client.table("judge_stats")
        .select("judge_name")
        .eq("judge_name", normalized)
        .eq("case_type", "all")
        .limit(1)
        .execute()
    )
    if result.data:
        return result.data[0]["judge_name"]

    # Fuzzy: judge_name contains each word of the query
    words = normalized.replace("_", " ").split()
    query = client.table("judge_stats").select("judge_name").eq("case_type", "all")
    for w in words:
        query = query.ilike("judge_name", f"%{w}%")

    result = query.limit(5).execute()
    if result.data:
        return result.data[0]["judge_name"]

    return None


# ---------------------------------------------------------------------------
# Profile builder
# ---------------------------------------------------------------------------

def get_judge_profile(judge_name: str, case_type: str | None = None) -> dict | None:
    """
    Returns the judge's precomputed profile.

    judge_name: normalized DB key (e.g. 'm_singh') or display fragment
    case_type:  optional filter ('IPR', 'civil', etc.)

    Returns None if judge not found.
    """
    client = _get_client()

    # Resolve display name → DB key
    db_key = resolve_judge_name(judge_name)
    if not db_key:
        return None

    # Fetch all stat rows for this judge
    result = (
        client.table("judge_stats")
        .select("*")
        .eq("judge_name", db_key)
        .execute()
    )
    stat_rows = result.data or []

    overall = next((r for r in stat_rows if r["case_type"] == "all"), None)
    if not overall:
        return None

    # by_case_type breakdown (exclude the 'all' row)
    by_type = {}
    for r in stat_rows:
        if r["case_type"] == "all":
            continue
        if case_type and r["case_type"] != case_type:
            continue
        by_type[r["case_type"]] = {
            "allow_rate":  round(r["allow_rate"] or 0, 4),
            "total":       r["total_cases"],
            "allowed":     r["allowed"],
            "dismissed":   r["dismissed"],
            "partially_allowed": r["partially_allowed"],
        }

    # Recent judgments (last 5 with known outcome)
    recent_q = (
        client.table("cases")
        .select("case_id, judgment_date, outcome, indian_kanoon_url, summary, judge_name")
        .eq("judge_name", db_key)
        .neq("outcome", "unknown")
        .order("judgment_date", desc=True)
        .limit(5)
    )
    if case_type:
        recent_q = recent_q.eq("case_type", case_type)

    recent_result = recent_q.execute()
    recent = [
        {
            "case_id":  r["case_id"],
            "title":    (r.get("summary") or "")[:80],
            "date":     str(r.get("judgment_date") or ""),
            "outcome":  r.get("outcome", "unknown"),
            "url":      r.get("indian_kanoon_url", ""),
        }
        for r in (recent_result.data or [])
    ]

    display_name = db_key.replace("_", " ").title()

    return {
        "judge_name":                db_key,
        "display_name":              display_name,
        "total_cases":               overall["total_cases"],
        "overall_allow_rate":        round(overall["allow_rate"] or 0, 4),
        "overall_dismiss_rate":      round(
            (overall["dismissed"] / overall["total_cases"])
            if overall["total_cases"] else 0, 4
        ),
        "avg_hearings_before_judgment": float(overall["avg_hearing_count"] or 0),
        "by_case_type":              by_type,
        "recent_judgments":          recent,
        "disclaimer":                DISCLAIMER,
    }


def list_judges() -> list[dict]:
    """Return all judges in the DB with their overall stats."""
    client = _get_client()
    result = (
        client.table("judge_stats")
        .select("judge_name, total_cases, allow_rate, avg_hearing_count")
        .eq("case_type", "all")
        .order("total_cases", desc=True)
        .execute()
    )
    return result.data or []


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _print_profile(profile: dict) -> None:
    p = profile
    print(f"\nJudge: {p['display_name']}")
    print(f"Total cases (known outcome): {p['total_cases']}")
    print(f"Allow rate:   {p['overall_allow_rate']*100:.1f}%")
    print(f"Dismiss rate: {p['overall_dismiss_rate']*100:.1f}%")
    print(f"Avg hearings: {p['avg_hearings_before_judgment']:.1f}")

    if p["by_case_type"]:
        print("\nBy case type:")
        for ctype, stats in p["by_case_type"].items():
            print(f"  {ctype:<15} allow={stats['allow_rate']*100:.0f}%  "
                  f"n={stats['total']}")

    if p["recent_judgments"]:
        print("\nRecent judgments:")
        for r in p["recent_judgments"]:
            print(f"  [{r['outcome'].upper():<18}] {r['date']}  {r['title']}")
            print(f"    {r['url']}")

    print(f"\n--- {p['disclaimer']} ---")


def main() -> None:
    parser = argparse.ArgumentParser(description="Judge history analytics")
    parser.add_argument("judge", nargs="?", help="Judge name or normalized key")
    parser.add_argument("--case-type", help="Filter by case type")
    parser.add_argument("--list", action="store_true", help="List all judges")
    args = parser.parse_args()

    if args.list:
        judges = list_judges()
        print(f"\n{'Judge':<30} {'Cases':>6}  {'Allow%':>7}  {'Avg Hearings':>12}")
        print("-" * 60)
        for j in judges:
            rate = (j.get("allow_rate") or 0) * 100
            print(f"{j['judge_name']:<30} {j['total_cases']:>6}  {rate:>6.1f}%  "
                  f"{j.get('avg_hearing_count') or 0:>12.1f}")
        return

    if not args.judge:
        parser.print_help()
        return

    profile = get_judge_profile(args.judge, args.case_type)
    if not profile:
        print(f"Judge '{args.judge}' not found in database.")
        print("Run: python -m search.judge_stats --list")
        return

    _print_profile(profile)


if __name__ == "__main__":
    main()
