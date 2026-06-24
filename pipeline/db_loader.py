"""
Supabase loader — upserts processed case records + embeddings into the
`cases` table using the supabase-py client (HTTPS, no direct TCP needed).

Usage:
    python -m pipeline.db_loader            # upsert all processed + embedded records
    python -m pipeline.db_loader --dry-run  # print rows without uploading
"""

import argparse
import json
import logging
import os
from pathlib import Path

import numpy as np
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def _get_client() -> Client:
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not url or not key:
        raise SystemExit(
            "SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in .env\n"
            "Get them from: Supabase dashboard → Project Settings → API"
        )
    return create_client(url, key)


def load_records(
    processed_dir: Path = Path("data/processed"),
    embeddings_dir: Path = Path("data/embeddings"),
) -> list[dict]:
    """
    Return list of row dicts ready for Supabase upsert.
    Only includes records that have a cached embedding .npy file.
    """
    rows = []
    for path in sorted(processed_dir.glob("*.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        case_id = record["case_id"]

        npy_path = embeddings_dir / f"{case_id}.npy"
        if not npy_path.exists():
            log.debug("Skipping %s — no embedding cached", case_id)
            continue

        vec = np.load(str(npy_path)).tolist()  # supabase-py sends as JSON array

        judgment_date = record.get("judgment_date") or None
        if judgment_date == "":
            judgment_date = None

        rows.append({
            "case_id":           case_id,
            "court":             record.get("court", ""),
            "judge_name":        record.get("judge_name", "unknown"),
            "case_type":         record.get("case_type", "unknown"),
            "petitioner_type":   record.get("petitioner_type", "unknown"),
            "respondent_type":   record.get("respondent_type", "unknown"),
            "acts_cited":        record.get("acts_cited", []),
            "hearing_count":     record.get("hearing_count", 0),
            "judgment_date":     judgment_date,
            "outcome":           record.get("outcome", "unknown"),
            "judgment_text":     record.get("judgment_text", ""),
            "indian_kanoon_url": record.get("indian_kanoon_url", ""),
            "embedding":         vec,
        })

    return rows


def upsert(rows: list[dict], dry_run: bool = False) -> int:
    """Upsert rows into Supabase cases table. Returns number of rows upserted."""
    if not rows:
        log.info("No rows to upsert")
        return 0

    if dry_run:
        log.info("[dry-run] Would upsert %d rows", len(rows))
        for r in rows[:3]:
            log.info("  %s | %s | %s | vec_dim=%d",
                     r["case_id"], r["outcome"], r["court"], len(r["embedding"]))
        return 0

    client = _get_client()

    # Supabase upsert in batches of 10 (large judgment_text + 768-dim vectors = big payloads)
    batch_size = 10
    total = 0
    for i in range(0, len(rows), batch_size):
        batch = rows[i : i + batch_size]
        result = (
            client.table("cases")
            .upsert(batch, on_conflict="case_id")
            .execute()
        )
        total += len(result.data)
        log.info("Upserted batch %d/%d (%d rows)", i // batch_size + 1,
                 (len(rows) - 1) // batch_size + 1, len(result.data))

    log.info("Done — %d rows upserted into cases table", total)
    return total


def main() -> None:
    parser = argparse.ArgumentParser(description="Load processed cases + embeddings into Supabase")
    parser.add_argument("--processed-dir", type=Path, default=Path("data/processed"))
    parser.add_argument("--embeddings-dir", type=Path, default=Path("data/embeddings"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    rows = load_records(args.processed_dir, args.embeddings_dir)
    log.info("Found %d records with embeddings", len(rows))
    upsert(rows, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
