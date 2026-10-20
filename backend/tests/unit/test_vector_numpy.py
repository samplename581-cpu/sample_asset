"""Unit tests for NumpyVectorStore."""

from __future__ import annotations

import numpy as np
import pytest
from helpdesk.adapters.vector_numpy import NumpyVectorStore
from helpdesk.ports.vector_store import ChunkRecord


def _make_chunk(chunk_id: str, document_type: str = "manual") -> ChunkRecord:
    return ChunkRecord(
        chunk_id=chunk_id,
        document_id=f"doc-{chunk_id}",
        text=f"Text for {chunk_id}",
        title=f"Title {chunk_id}",
        source="test",
        document_type=document_type,
        category=None,
        position=0,
    )


def _normalized(v: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(v)
    return (v / norm).astype(np.float32) if norm > 0 else v.astype(np.float32)


@pytest.fixture()
def store() -> NumpyVectorStore:
    """3 チャンクのベクトルストア。c0 がクエリに最も近い。"""
    dim = 8
    rng = np.random.default_rng(42)

    # c0: クエリ方向に近いベクトル
    v0 = _normalized(np.array([1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0], dtype=np.float32))
    # c1: 中間
    v1 = _normalized(rng.standard_normal(dim))
    # c2: クエリから遠い（逆方向）
    v2 = _normalized(np.array([-1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0], dtype=np.float32))

    chunks = [_make_chunk("c0"), _make_chunk("c1"), _make_chunk("c2")]
    vectors = np.stack([v0, v1, v2])
    return NumpyVectorStore(chunks=chunks, vectors=vectors)


def test_cosine_ranking(store: NumpyVectorStore) -> None:
    """cosine 検索の順位が期待通りであること (c0 が最上位、c2 が最下位)。"""
    query = _normalized(np.array([1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0], dtype=np.float32))
    results = store.search(query_vector=query, top_k=3, min_score=-1.0)
    assert len(results) == 3
    assert results[0].chunk_id == "c0"
    assert results[-1].chunk_id == "c2"


def test_top_k_exceeds_chunks(store: NumpyVectorStore) -> None:
    """`top_k` が chunk 数を超えても安全であること。"""
    query = _normalized(np.array([1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0], dtype=np.float32))
    results = store.search(query_vector=query, top_k=100, min_score=-1.0)
    # 3 chunks しかないので最大 3 件
    assert len(results) == 3


def test_min_score_filter(store: NumpyVectorStore) -> None:
    """`min_score` フィルタが機能すること。"""
    query = _normalized(np.array([1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0], dtype=np.float32))
    # c2 は score=-1.0 なので min_score=0.0 で除外される
    results = store.search(query_vector=query, top_k=3, min_score=0.0)
    chunk_ids = {r.chunk_id for r in results}
    assert "c2" not in chunk_ids


def test_document_types_filter() -> None:
    """`document_types` フィルタが機能すること。"""
    dim = 4
    v = _normalized(np.ones(dim, dtype=np.float32))

    chunks = [
        _make_chunk("c0", document_type="manual"),
        _make_chunk("c1", document_type="faq"),
        _make_chunk("c2", document_type="manual"),
    ]
    vectors = np.stack([v, v, v])
    store = NumpyVectorStore(chunks=chunks, vectors=vectors)

    query = _normalized(np.ones(dim, dtype=np.float32))
    results = store.search(query_vector=query, top_k=10, document_types=["faq"], min_score=-1.0)

    assert all(r.document_id == "doc-c1" for r in results)


def test_empty_query_no_exception(store: NumpyVectorStore) -> None:
    """空クエリ（all-zero ベクトル）で例外が出ないこと。"""
    zero_query = np.zeros(8, dtype=np.float32)
    # all-zero クエリは全スコアが 0.0 になる
    results = store.search(query_vector=zero_query, top_k=3, min_score=-1.0)
    assert isinstance(results, list)
