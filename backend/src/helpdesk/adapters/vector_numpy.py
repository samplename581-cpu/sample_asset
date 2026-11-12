from __future__ import annotations

import numpy as np

from helpdesk.ports.vector_store import ChunkRecord, SearchResult


class NumpyVectorStore:
    """In-memory vector store backed by NumPy cosine similarity search."""

    def __init__(self, chunks: list[ChunkRecord], vectors: np.ndarray) -> None:
        # vectors shape: (n, dim), expected to be L2-normalized float32
        self._chunks = chunks
        self._vectors = vectors.astype(np.float32)

    @property
    def provider_name(self) -> str:
        return "numpy"

    def search(
        self,
        query_vector: np.ndarray,
        top_k: int = 5,
        document_types: list[str] | None = None,
        min_score: float = 0.0,
        access_scope: str | None = None,  # NumPy store はスコープ制御を持たない（Mock/テスト用）
    ) -> list[SearchResult]:
        if len(self._chunks) == 0:
            return []

        # cosine similarity (vectors are pre-normalized); clip to [-1, 1] for float32 precision
        scores: np.ndarray = np.clip(self._vectors @ query_vector.astype(np.float32), -1.0, 1.0)

        # Build candidate mask
        if document_types is not None:
            dt_set = set(document_types)
            mask = np.array([c.document_type in dt_set for c in self._chunks], dtype=bool)
            scores = np.where(mask, scores, -np.inf)

        # Filter by min_score via mask
        score_mask = scores >= min_score
        candidate_indices = np.nonzero(score_mask)[0]

        if len(candidate_indices) == 0:
            return []

        k = min(top_k, len(candidate_indices))
        candidate_scores = scores[candidate_indices]

        # Use argpartition for efficiency, then sort top-k
        if k < len(candidate_scores):
            part = np.argpartition(candidate_scores, -k)[-k:]
        else:
            part = np.arange(len(candidate_scores))

        top_local = part[np.argsort(candidate_scores[part])[::-1]]
        top_indices = candidate_indices[top_local]

        results: list[SearchResult] = []
        for idx in top_indices:
            chunk = self._chunks[idx]
            results.append(
                SearchResult(
                    chunk_id=chunk.chunk_id,
                    document_id=chunk.document_id,
                    title=chunk.title,
                    snippet=chunk.text[:300],
                    score=float(scores[idx]),
                    source=chunk.source,
                )
            )
        return results

    def count(self) -> int:
        return len(self._chunks)
