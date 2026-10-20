"""Unit tests for the watsonx.ai embedding adapter."""

from __future__ import annotations

import numpy as np
import pytest
from helpdesk.adapters.embedding_watsonx import WatsonxEmbeddingAdapter
from helpdesk.domain.errors import ProviderError


class _FakeEmbeddings:
    def __init__(self) -> None:
        self.closed = False

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[float(index), 1.0] for index, _ in enumerate(texts)]

    def embed_query(self, text: str) -> list[float]:
        return [float(len(text)), 1.0]

    def close_persistent_connection(self) -> None:
        self.closed = True


def test_encode_and_close() -> None:
    client = _FakeEmbeddings()
    adapter = WatsonxEmbeddingAdapter(client, "embedding-model", 2)

    passages = adapter.encode_passages(["a", "b"])
    query = adapter.encode_query("abc")
    adapter.close()

    assert passages.dtype == np.float32
    assert passages.shape == (2, 2)
    assert query.tolist() == [3.0, 1.0]
    assert client.closed is True


def test_provider_failure_is_wrapped() -> None:
    class _FailingEmbeddings:
        def embed_query(self, text: str) -> list[float]:
            raise RuntimeError("secret provider detail")

    adapter = WatsonxEmbeddingAdapter(_FailingEmbeddings(), "embedding-model", 2)

    with pytest.raises(ProviderError, match="embedding request failed"):
        adapter.encode_query("query")
