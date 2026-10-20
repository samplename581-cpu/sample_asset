from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np

from helpdesk.domain.errors import ConfigurationError, ProviderError, ValidationError
from helpdesk.ports.vector_store import SearchResult

if TYPE_CHECKING:
    from helpdesk.config import Settings

_ACCESS_SCOPE = re.compile(r"^[a-zA-Z0-9_-]{1,80}$")
_DOCUMENT_TYPE = re.compile(r"^[a-zA-Z0-9_-]{1,40}$")


class ChromaVectorStore:
    """Local persistent Chroma implementation of VectorStorePort."""

    def __init__(self, client: Any, collection: Any) -> None:
        self._client = client
        self._collection = collection

    @classmethod
    def from_settings(cls, settings: Settings) -> ChromaVectorStore:
        try:
            import chromadb
            from chromadb.config import Settings as ChromaSettings
        except ImportError as exc:
            raise ConfigurationError("chromadb is not installed. Run 'uv sync'.") from exc

        persist_dir = Path(settings.INDEX_DIR) / "chroma"
        if not persist_dir.exists():
            raise ConfigurationError(
                f"Chroma index does not exist at '{persist_dir}'. Run the index build first."
            )

        try:
            client = chromadb.PersistentClient(
                path=str(persist_dir),
                settings=ChromaSettings(anonymized_telemetry=False),
            )
            collection = client.get_collection(
                name=settings.CHROMA_COLLECTION,
                embedding_function=None,
            )
        except Exception as exc:
            raise ConfigurationError("Unable to open the local Chroma collection") from exc

        return cls(client=client, collection=collection)

    def search(
        self,
        query_vector: np.ndarray,
        top_k: int = 5,
        document_types: list[str] | None = None,
        min_score: float = 0.0,
        access_scope: str | None = None,
    ) -> list[SearchResult]:
        if access_scope is not None and not _ACCESS_SCOPE.fullmatch(access_scope):
            raise ValidationError("Invalid access_scope value")
        if document_types and any(
            not _DOCUMENT_TYPE.fullmatch(value) for value in document_types
        ):
            raise ValidationError("Invalid document type filter")

        clauses: list[dict[str, object]] = [{"is_active": {"$eq": True}}]
        if access_scope is not None:
            clauses.append({"access_scope": {"$eq": access_scope}})
        if document_types:
            clauses.append({"document_type": {"$in": document_types}})
        where: dict[str, object] = clauses[0] if len(clauses) == 1 else {"$and": clauses}

        try:
            count = int(self._collection.count())
            if count == 0:
                return []
            response = self._collection.query(
                query_embeddings=[query_vector.astype(np.float32).tolist()],
                n_results=min(top_k, count),
                where=where,
                include=["documents", "metadatas", "distances"],
            )
        except (ValidationError, ConfigurationError):
            raise
        except Exception as exc:
            raise ProviderError("Chroma vector search failed") from exc

        ids = response.get("ids") or [[]]
        documents = response.get("documents") or [[]]
        metadatas = response.get("metadatas") or [[]]
        distances = response.get("distances") or [[]]

        results: list[SearchResult] = []
        for chunk_id, document, metadata, distance in zip(
            ids[0], documents[0], metadatas[0], distances[0], strict=True
        ):
            # cosine distance is 1 - cosine similarity.
            score = max(-1.0, min(1.0, 1.0 - float(distance)))
            if score < min_score:
                continue
            item = metadata or {}
            results.append(
                SearchResult(
                    chunk_id=str(chunk_id),
                    document_id=str(item.get("document_id", "")),
                    title=str(item.get("title", "")),
                    snippet=str(document or "")[:300],
                    score=score,
                    source=str(item.get("source", "")),
                )
            )
        return results

    def count(self) -> int:
        try:
            return int(self._collection.count())
        except Exception as exc:
            raise ProviderError("Unable to read Chroma collection statistics") from exc

    def close(self) -> None:
        # PersistentClient flushes writes automatically and exposes no close operation.
        return None
