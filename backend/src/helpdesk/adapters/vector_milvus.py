from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any

import numpy as np

from helpdesk.domain.errors import ConfigurationError, ProviderError, ValidationError
from helpdesk.ports.vector_store import SearchResult

if TYPE_CHECKING:
    from helpdesk.config import Settings

# access_scope は呼出元サーバーが決定した値だけを許可する（1~80文字の識別子）
_ACCESS_SCOPE = re.compile(r"^[a-zA-Z0-9_-]{1,80}$")
_DOCUMENT_TYPE = re.compile(r"^[a-zA-Z0-9_-]{1,40}$")


class MilvusVectorStore:
    """watsonx.data Milvus implementation of VectorStorePort."""

    def __init__(self, client: Any, collection_name: str) -> None:
        self._client = client
        self._collection_name = collection_name

    @property
    def provider_name(self) -> str:
        return "milvus"

    @classmethod
    def from_settings(cls, settings: Settings) -> MilvusVectorStore:
        try:
            from pymilvus import MilvusClient
        except ImportError as exc:
            raise ConfigurationError(
                "pymilvus is not installed. Install the 'milvus' extra."
            ) from exc

        if not settings.MILVUS_URI or not settings.MILVUS_USERNAME or not settings.MILVUS_PASSWORD:
            raise ConfigurationError("watsonx.data Milvus settings are incomplete")

        client = MilvusClient(
            uri=settings.MILVUS_URI,
            user=settings.MILVUS_USERNAME,
            password=settings.MILVUS_PASSWORD,
            db_name=settings.MILVUS_DATABASE,
            secure=settings.MILVUS_TLS,
        )
        if not client.has_collection(collection_name=settings.MILVUS_COLLECTION):
            raise ConfigurationError(
                f"Milvus collection '{settings.MILVUS_COLLECTION}' does not exist"
            )
        return cls(client, settings.MILVUS_COLLECTION)

    def search(
        self,
        query_vector: np.ndarray,
        top_k: int = 5,
        document_types: list[str] | None = None,
        min_score: float = 0.0,
        access_scope: str | None = None,
    ) -> list[SearchResult]:
        # access_scope はサーバー側で決定した値のみ受け付ける。
        # Client request の値をそのまま渡さない（設計書 10.1 節）。
        if access_scope is not None and not _ACCESS_SCOPE.fullmatch(access_scope):
            raise ValidationError("Invalid access_scope value")

        # is_active=true は必ず含める（設計書 FR-10）
        filter_parts = ["is_active == true"]

        if access_scope is not None:
            filter_parts.append(f"access_scope == {json.dumps(access_scope)}")

        if document_types:
            if any(not _DOCUMENT_TYPE.fullmatch(value) for value in document_types):
                raise ValidationError("Invalid document type filter")
            values = ", ".join(json.dumps(value) for value in document_types)
            filter_parts.append(f"document_type in [{values}]")

        filter_expression = " and ".join(filter_parts)

        try:
            response = self._client.search(
                collection_name=self._collection_name,
                data=[query_vector.astype(np.float32).tolist()],
                anns_field="vector",
                limit=top_k,
                filter=filter_expression,
                output_fields=[
                    "chunk_id",
                    "document_id",
                    "title",
                    "text",
                    "source",
                    "document_type",
                    "access_scope",
                    "is_active",
                ],
                search_params={"metric_type": "COSINE", "params": {}},
            )
        except (ConfigurationError, ValidationError):
            raise
        except Exception as exc:
            raise ProviderError("Milvus vector search failed") from exc

        hits = response[0] if response else []
        results: list[SearchResult] = []
        for hit in hits:
            entity = hit.get("entity", {})
            score = float(hit.get("distance", 0.0))
            if score < min_score:
                continue
            results.append(
                SearchResult(
                    chunk_id=str(entity.get("chunk_id") or hit.get("id", "")),
                    document_id=str(entity.get("document_id", "")),
                    title=str(entity.get("title", "")),
                    snippet=str(entity.get("text", ""))[:300],
                    score=max(-1.0, min(1.0, score)),
                    source=str(entity.get("source", "")),
                )
            )
        return results

    def count(self) -> int:
        try:
            stats = self._client.get_collection_stats(collection_name=self._collection_name)
            return int(stats.get("row_count", 0))
        except Exception as exc:
            raise ProviderError("Unable to read Milvus collection statistics") from exc

    def close(self) -> None:
        self._client.close()
