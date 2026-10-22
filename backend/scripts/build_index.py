"""build_index.py — Build the vector index from seed documents.

Usage (from sample_asset/ directory):
    python backend/scripts/build_index.py

Environment variables:
    EMBEDDING_PROVIDER  mock (default) | local | watsonx
    EMBEDDING_MODEL_ID  model name for local provider
"""
from __future__ import annotations

import hashlib
import json
import logging
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

# ---------------------------------------------------------------------------
# Path setup – allow running from sample_asset/ without installing the package
# ---------------------------------------------------------------------------
_SCRIPT_DIR = Path(__file__).resolve().parent
_BACKEND_SRC = _SCRIPT_DIR.parent / "src"
if str(_BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(_BACKEND_SRC))

from helpdesk.adapters.embedding_mock import MockEmbeddingAdapter
from helpdesk.config import Settings
from helpdesk.ports.vector_store import ChunkRecord

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("build_index")


# ---------------------------------------------------------------------------
# Chunking helpers
# ---------------------------------------------------------------------------

def _chunk_document(doc: dict[str, Any]) -> list[ChunkRecord]:
    """Convert a document dict into ChunkRecord objects.

    FAQ・分類基準は1文書=1チャンクにする（質問と回答、基準と例を分割しない）。
    """
    doc_id: str = doc["document_id"]
    title: str = doc["title"]
    body: str = doc["body"]
    doc_type: str = doc["document_type"]
    return [
        ChunkRecord(
            chunk_id=f"{doc_id}:0001",
            document_id=doc_id,
            text=f"{title}\n{body}",
            title=title,
            source=doc["source"],
            document_type=doc_type,
            category=doc.get("category"),
            position=0,
            access_scope=str(doc.get("access_scope", "default")),
            is_active=bool(doc.get("is_active", True)),
            faq_id=doc.get("faq_id"),
            completion_policy=doc.get("completion_policy"),
        )
    ]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    # Resolve paths relative to sample_asset/ (cwd) or script location
    sample_asset_dir = _SCRIPT_DIR.parent.parent  # sample_asset/
    documents_path = sample_asset_dir / "data" / "seed" / "documents.json"
    index_dir = sample_asset_dir / "data" / "index"

    if not documents_path.exists():
        logger.error("documents.json not found at %s", documents_path)
        sys.exit(1)

    # Load documents
    raw = documents_path.read_bytes()
    source_hash = "sha256:" + hashlib.sha256(raw).hexdigest()
    documents: list[dict[str, Any]] = json.loads(raw)
    active_docs = [d for d in documents if d.get("is_active", True)]
    logger.info("Loaded %d active documents (total %d)", len(active_docs), len(documents))

    # Chunk
    all_chunks: list[ChunkRecord] = []
    for doc in active_docs:
        all_chunks.extend(_chunk_document(doc))
    logger.info("Generated %d chunks", len(all_chunks))

    # Select embedding adapter
    settings = Settings()
    provider = settings.EMBEDDING_PROVIDER
    if provider == "local":
        model_id = settings.EMBEDDING_MODEL_ID
        try:
            from helpdesk.adapters.embedding_local import LocalEmbeddingAdapter
            embedding = LocalEmbeddingAdapter(model_id)
        except Exception as exc:
            logger.error("Failed to load local embedding: %s", exc)
            sys.exit(1)
    elif provider == "watsonx":
        try:
            from helpdesk.adapters.embedding_watsonx import WatsonxEmbeddingAdapter

            embedding = WatsonxEmbeddingAdapter.from_settings(settings)
        except Exception as exc:
            logger.error("Failed to initialize watsonx.ai embedding: %s", exc)
            sys.exit(1)
    elif provider == "mock":
        embedding = MockEmbeddingAdapter()
    else:
        logger.error("Unsupported EMBEDDING_PROVIDER: %s", provider)
        sys.exit(1)

    logger.info(
        "Embedding provider=%s model=%s dim=%d",
        embedding.provider_name,
        embedding.model_name,
        embedding.dimension,
    )

    # Encode
    texts = [c.text for c in all_chunks]
    logger.info("Encoding %d passages …", len(texts))
    vectors = embedding.encode_passages(texts)  # (n, dim)
    logger.info("Vectors shape: %s dtype: %s", vectors.shape, vectors.dtype)

    # Write to tmp directory, then atomically replace entire index directory.
    # Strategy: write to <index_dir>.new/, then rename into place.
    parent = index_dir.parent
    parent.mkdir(parents=True, exist_ok=True)
    new_dir = parent / f"{index_dir.name}.new"
    old_dir = parent / f"{index_dir.name}.old"

    # Clean up any leftover temp dirs from a previous failed run
    shutil.rmtree(new_dir, ignore_errors=True)
    shutil.rmtree(old_dir, ignore_errors=True)

    new_dir.mkdir(parents=True)

    try:
        # chunks.json
        chunks_data = [
            {
                "chunk_id": c.chunk_id,
                "document_id": c.document_id,
                "text": c.text,
                "title": c.title,
                "source": c.source,
                "document_type": c.document_type,
                "category": c.category,
                "position": c.position,
                "access_scope": c.access_scope,
                "is_active": c.is_active,
                "faq_id": c.faq_id,
                "completion_policy": c.completion_policy,
            }
            for c in all_chunks
        ]
        (new_dir / "chunks.json").write_text(
            json.dumps(chunks_data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        # vectors.npy
        np.save(str(new_dir / "vectors.npy"), vectors)

        # manifest.json
        created_at = datetime.now(tz=UTC).astimezone().isoformat()
        manifest = {
            "schema_version": 1,
            "created_at": created_at,
            "embedding_provider": embedding.provider_name,
            "embedding_model": embedding.model_name,
            "dimension": embedding.dimension,
            "distance": "cosine",
            "chunk_count": len(all_chunks),
            "source_hash": source_hash,
        }
        (new_dir / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        # Chroma is the standard local vector DB. It stores the same precomputed
        # embeddings as the NumPy fallback, so no additional embedding call occurs.
        try:
            import chromadb
            from chromadb.config import Settings as ChromaSettings
        except ImportError as exc:
            raise RuntimeError("chromadb is not installed. Run 'uv sync'.") from exc

        chroma_client = chromadb.PersistentClient(
            path=str(new_dir / "chroma"),
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        collection_name = settings.CHROMA_COLLECTION
        collection = chroma_client.create_collection(
            name=collection_name,
            embedding_function=None,
            metadata={"hnsw:space": "cosine"},
        )
        collection.add(
            ids=[c.chunk_id for c in all_chunks],
            embeddings=vectors.astype(np.float32).tolist(),
            documents=[c.text for c in all_chunks],
            metadatas=[
                {
                    "document_id": c.document_id,
                    "title": c.title,
                    "source": c.source,
                    "document_type": c.document_type,
                    "access_scope": c.access_scope,
                    "is_active": c.is_active,
                    "position": c.position,
                    **({"category": c.category} if c.category is not None else {}),
                    **({"faq_id": c.faq_id} if c.faq_id is not None else {}),
                    **(
                        {"completion_policy": c.completion_policy}
                        if c.completion_policy is not None
                        else {}
                    ),
                }
                for c in all_chunks
            ],
        )

        # Atomic directory swap: rename current -> old, new -> current, remove old
        if index_dir.exists():
            index_dir.rename(old_dir)
        new_dir.rename(index_dir)
        shutil.rmtree(old_dir, ignore_errors=True)

        logger.info("Index written to %s", index_dir)
        logger.info("  chunks   : %d", len(all_chunks))
        logger.info("  dimension: %d", embedding.dimension)
        logger.info("  provider : %s / %s", embedding.provider_name, embedding.model_name)

    except Exception:
        shutil.rmtree(new_dir, ignore_errors=True)
        raise


if __name__ == "__main__":
    main()
