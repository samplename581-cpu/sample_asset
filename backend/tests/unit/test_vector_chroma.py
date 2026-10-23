"""Unit and local integration tests for ChromaVectorStore."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import chromadb
import numpy as np
import pytest
from chromadb.config import Settings as ChromaSettings
from helpdesk.adapters.vector_chroma import ChromaVectorStore
from helpdesk.domain.errors import ValidationError


@pytest.fixture()
def store(tmp_path: Path) -> Iterator[ChromaVectorStore]:
    client = chromadb.PersistentClient(
        path=str(tmp_path / "chroma"),
        settings=ChromaSettings(anonymized_telemetry=False),
    )
    collection = client.create_collection(
        name="knowledge",
        embedding_function=None,
        metadata={"hnsw:space": "cosine"},
    )
    collection.add(
        ids=["chunk-1", "chunk-2", "chunk-3"],
        embeddings=[[1.0, 0.0], [0.8, 0.2], [-1.0, 0.0]],
        documents=["VPN再接続手順", "パスワード変更手順", "無効な旧手順"],
        metadatas=[
            {
                "document_id": "doc-1",
                "title": "VPN",
                "source": "vpn.md",
                "document_type": "faq",
                "access_scope": "default",
                "is_active": True,
            },
            {
                "document_id": "doc-2",
                "title": "Password",
                "source": "password.md",
                "document_type": "manual",
                "access_scope": "staff",
                "is_active": True,
            },
            {
                "document_id": "doc-3",
                "title": "Old",
                "source": "old.md",
                "document_type": "faq",
                "access_scope": "default",
                "is_active": False,
            },
        ],
    )
    store = ChromaVectorStore(client, collection)
    try:
        yield store
    finally:
        store.close()


def test_search_filters_scope_type_and_inactive_records(store: ChromaVectorStore) -> None:
    results = store.search(
        np.array([1.0, 0.0], dtype=np.float32),
        top_k=3,
        document_types=["faq"],
        access_scope="default",
        min_score=0.0,
    )

    assert [result.chunk_id for result in results] == ["chunk-1"]
    assert results[0].score == pytest.approx(1.0)
    assert results[0].source == "vpn.md"
    assert store.count() == 3


def test_search_rejects_untrusted_filter_values(store: ChromaVectorStore) -> None:
    with pytest.raises(ValidationError, match="Invalid access_scope"):
        store.search(np.array([1.0, 0.0]), access_scope='default" or true')

    with pytest.raises(ValidationError, match="Invalid document type"):
        store.search(np.array([1.0, 0.0]), document_types=["faq OR true"])


def test_close_releases_chroma_client() -> None:
    class ClosableClient:
        closed = False

        def close(self) -> None:
            self.closed = True

    client = ClosableClient()
    store = ChromaVectorStore(client, object())

    store.close()

    assert client.closed is True
