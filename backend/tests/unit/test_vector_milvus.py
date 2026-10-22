"""Unit tests for the Milvus vector-store adapter."""

from __future__ import annotations

import numpy as np
import pytest
from helpdesk.adapters.vector_milvus import MilvusVectorStore
from helpdesk.domain.errors import ProviderError, ValidationError


class _FakeMilvusClient:
    def __init__(self) -> None:
        self.search_kwargs: dict[str, object] = {}
        self.closed = False

    def search(self, **kwargs: object) -> list[list[dict[str, object]]]:
        self.search_kwargs = kwargs
        return [
            [
                {
                    "id": "fallback-id",
                    "distance": 0.91,
                    "entity": {
                        "chunk_id": "chunk-1",
                        "document_id": "doc-1",
                        "title": "VPN",
                        "text": "VPN再接続手順",
                        "source": "vpn.md",
                    },
                },
                {
                    "id": "chunk-2",
                    "distance": 0.2,
                    "entity": {"document_id": "doc-2", "text": "low score"},
                },
            ]
        ]

    def get_collection_stats(self, **kwargs: object) -> dict[str, str]:
        return {"row_count": "12"}

    def close(self) -> None:
        self.closed = True


def test_search_maps_metadata_and_applies_score() -> None:
    client = _FakeMilvusClient()
    store = MilvusVectorStore(client, "knowledge")

    results = store.search(
        np.array([0.1, 0.2], dtype=np.float64),
        top_k=3,
        document_types=["faq", "rule"],
        min_score=0.5,
    )

    assert [result.chunk_id for result in results] == ["chunk-1"]
    assert results[0].source == "vpn.md"
    # is_active=true は必ず先頭に付く（設計書 FR-10）
    assert client.search_kwargs["filter"] == 'is_active == true and document_type in ["faq", "rule"]'
    assert client.search_kwargs["data"] == [[0.10000000149011612, 0.20000000298023224]]
    assert store.count() == 12


def test_search_includes_is_active_filter_without_document_types() -> None:
    """document_types 未指定でも is_active=true フィルタが含まれること。"""
    client = _FakeMilvusClient()
    store = MilvusVectorStore(client, "knowledge")

    store.search(np.array([0.1], dtype=np.float32), min_score=0.0)

    assert client.search_kwargs["filter"] == "is_active == true"


def test_search_includes_access_scope_filter() -> None:
    """access_scope を指定したとき is_active=true と access_scope フィルタが含まれること。"""
    client = _FakeMilvusClient()
    store = MilvusVectorStore(client, "knowledge")

    store.search(np.array([0.1], dtype=np.float32), min_score=0.0, access_scope="default")

    assert client.search_kwargs["filter"] == 'is_active == true and access_scope == "default"'


def test_search_rejects_invalid_access_scope() -> None:
    """不正な access_scope はプロバイダ呼び出し前に ValidationError を返すこと。"""
    client = _FakeMilvusClient()
    store = MilvusVectorStore(client, "knowledge")

    with pytest.raises(ValidationError, match="Invalid access_scope"):
        store.search(np.array([0.1], dtype=np.float32), access_scope='default" or true')

    assert client.search_kwargs == {}


def test_search_rejects_invalid_document_type_before_provider_call() -> None:
    client = _FakeMilvusClient()
    store = MilvusVectorStore(client, "knowledge")

    with pytest.raises(ValidationError, match="Invalid document type"):
        store.search(np.array([0.1], dtype=np.float32), document_types=['faq"] or true'])

    assert client.search_kwargs == {}


def test_provider_failure_is_wrapped() -> None:
    class _FailingClient:
        def search(self, **kwargs: object) -> list[object]:
            raise RuntimeError("secret provider detail")

    store = MilvusVectorStore(_FailingClient(), "knowledge")

    with pytest.raises(ProviderError, match="vector search failed"):
        store.search(np.array([0.1], dtype=np.float32))
