"""
InLegalBERT batch embedder — Phase 1, Step 2.

Reads structured records from data/processed/, generates 768-dim embeddings
(last 512 tokens, CLS token), caches as .npy files in data/embeddings/,
and builds a local FAISS index for fast similarity search.

Why last 512 tokens: Indian judgments place the operative conclusion at the
end, not the beginning — truncating from the front loses the holding.

Usage:
    python -m pipeline.embedder           # embed all processed records
    python -m pipeline.embedder --limit 5 # embed first N (for testing)
"""

import argparse
import json
import logging
import os
from pathlib import Path

import faiss
import numpy as np
import torch
from transformers import AutoModel, AutoTokenizer
from tqdm import tqdm

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

MODEL_NAME = "law-ai/InLegalBERT"
EMBEDDING_DIM = 768
FAISS_INDEX_PATH = Path("data/embeddings/faiss.index")
CASE_ID_MAP_PATH = Path("data/embeddings/case_id_map.json")  # index position → case_id

# ---------------------------------------------------------------------------
# Model (loaded once, reused across all calls)
# ---------------------------------------------------------------------------

_tokenizer = None
_model = None


def _load_model():
    global _tokenizer, _model
    if _tokenizer is None:
        log.info("Loading InLegalBERT from HuggingFace (first run downloads ~400 MB)...")
        _tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
        _model = AutoModel.from_pretrained(MODEL_NAME)
        _model.eval()
        if torch.cuda.is_available():
            _model = _model.cuda()
            log.info("Using GPU")
        else:
            log.info("Using CPU")


# ---------------------------------------------------------------------------
# Core embedding function
# ---------------------------------------------------------------------------

def embed_text(text: str) -> np.ndarray:
    """
    Returns a L2-normalised 768-dim vector for `text`.
    Encodes the LAST 512 tokens — the operative conclusion of Indian judgments
    sits at the end, not the beginning.
    """
    _load_model()

    # Tokenize without truncation first, then take the last 512 tokens
    tokens = _tokenizer(
        text,
        add_special_tokens=False,
        return_tensors="pt",
        truncation=False,
    )
    input_ids = tokens["input_ids"][0]

    # Keep last 510 tokens + [CLS] at front and [SEP] at back
    max_body = 510
    if len(input_ids) > max_body:
        input_ids = input_ids[-max_body:]

    cls_id = _tokenizer.cls_token_id
    sep_id = _tokenizer.sep_token_id
    input_ids = torch.cat([
        torch.tensor([cls_id]),
        input_ids,
        torch.tensor([sep_id]),
    ]).unsqueeze(0)

    attention_mask = torch.ones_like(input_ids)

    if torch.cuda.is_available():
        input_ids = input_ids.cuda()
        attention_mask = attention_mask.cuda()

    with torch.no_grad():
        output = _model(input_ids=input_ids, attention_mask=attention_mask)

    vec = output.last_hidden_state[:, 0, :].squeeze().cpu().numpy().astype(np.float32)

    # L2-normalise so inner product == cosine similarity
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec = vec / norm
    return vec


# ---------------------------------------------------------------------------
# Batch embedding
# ---------------------------------------------------------------------------

def embed_all(
    processed_dir: Path = Path("data/processed"),
    embeddings_dir: Path = Path("data/embeddings"),
    limit: int = 0,
) -> dict[str, np.ndarray]:
    """
    Embed every processed record that doesn't already have a cached .npy file.
    Returns {case_id: embedding_vector}.
    """
    embeddings_dir.mkdir(parents=True, exist_ok=True)
    paths = sorted(processed_dir.glob("*.json"))
    if limit:
        paths = paths[:limit]

    results: dict[str, np.ndarray] = {}

    for path in tqdm(paths, desc="Embedding"):
        record = json.loads(path.read_text(encoding="utf-8"))
        case_id = record["case_id"]
        npy_path = embeddings_dir / f"{case_id}.npy"

        if npy_path.exists():
            results[case_id] = np.load(str(npy_path))
            continue

        text = record.get("judgment_text", "")
        if not text.strip():
            log.warning("Skipping %s — empty judgment text", case_id)
            continue

        vec = embed_text(text)
        np.save(str(npy_path), vec)
        results[case_id] = vec
        log.info("Embedded %s", case_id)

    return results


# ---------------------------------------------------------------------------
# FAISS index
# ---------------------------------------------------------------------------

def build_faiss_index(
    embeddings: dict[str, np.ndarray],
    index_path: Path = FAISS_INDEX_PATH,
    map_path: Path = CASE_ID_MAP_PATH,
) -> faiss.Index:
    """
    Build an IndexFlatIP (exact inner-product search).
    Saves index + case_id position map to disk.
    """
    if not embeddings:
        raise ValueError("No embeddings to index")

    case_ids = list(embeddings.keys())
    matrix = np.stack([embeddings[c] for c in case_ids]).astype(np.float32)

    index = faiss.IndexFlatIP(EMBEDDING_DIM)
    index.add(matrix)

    index_path.parent.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(index_path))
    map_path.write_text(json.dumps(case_ids), encoding="utf-8")

    log.info("FAISS index built: %d vectors → %s", index.ntotal, index_path)
    return index


def load_faiss_index() -> tuple[faiss.Index, list[str]]:
    """Load the saved FAISS index and its case_id position map."""
    index = faiss.read_index(str(FAISS_INDEX_PATH))
    case_ids = json.loads(CASE_ID_MAP_PATH.read_text(encoding="utf-8"))
    return index, case_ids


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Embed processed judgments with InLegalBERT")
    parser.add_argument("--limit", type=int, default=0, help="Only embed first N records (0 = all)")
    parser.add_argument("--processed-dir", type=Path, default=Path("data/processed"))
    parser.add_argument("--embeddings-dir", type=Path, default=Path("data/embeddings"))
    args = parser.parse_args()

    embeddings = embed_all(args.processed_dir, args.embeddings_dir, args.limit)
    log.info("Generated %d embeddings", len(embeddings))

    if embeddings:
        build_faiss_index(embeddings)


if __name__ == "__main__":
    main()
