"""Unit tests for RagService."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest
from helpdesk.adapters.embedding_mock import MockEmbeddingAdapter
from helpdesk.adapters.llm_mock import MockLLMAdapter
from helpdesk.adapters.vector_numpy import NumpyVectorStore
from helpdesk.ports.vector_store import ChunkRecord
from helpdesk.services.rag_service import RagService

if TYPE_CHECKING:
    from helpdesk.config import Settings


def _make_settings(min_score: float = 0.45) -> Settings:
    from helpdesk.config import Settings

    return Settings(
        LLM_PROVIDER="mock",
        EMBEDDING_PROVIDER="mock",
        EMBEDDING_DIMENSION=64,
        VECTOR_MIN_SCORE=min_score,
    )


def _make_store_with_chunks(n: int, dim: int = 64, score_value: float = 1.0) -> NumpyVectorStore:
    """n 個の同一ベクトルを持つベクトルストアを作る。"""
    chunks = [
        ChunkRecord(
            chunk_id=f"c{i}",
            document_id=f"doc{i}",
            text=f"text {i}",
            title=f"Title {i}",
            source="manual",
            document_type="manual",
            category=None,
            position=i,
        )
        for i in range(n)
    ]
    # 全ベクトルをクエリ方向に揃えて高スコアを保証
    v = np.zeros(dim, dtype=np.float32)
    v[0] = score_value
    vectors = np.stack([v] * n)
    return NumpyVectorStore(chunks=chunks, vectors=vectors)


@pytest.mark.asyncio
async def test_no_evidence_skips_llm() -> None:
    """根拠 0 件（min_score 未満）のとき LLM を呼ばず insufficient_context 応答を返すこと。"""
    embedding = MockEmbeddingAdapter()
    # 空のベクトルストア（0チャンク）
    store = NumpyVectorStore(chunks=[], vectors=np.zeros((0, 64), dtype=np.float32))
    rag = RagService(embedding=embedding, store=store)

    llm = MockLLMAdapter()
    settings = _make_settings(min_score=0.45)

    response = await rag.draft_answer(
        llm=llm,
        query="VPNに接続できません",
        top_k=5,
        request_id="test-req-1",
        settings=settings,
    )

    assert "insufficient" in response.draft_answer.lower() or "確認" in response.draft_answer
    assert response.citations == []
    assert response.needs_human_confirmation is True


@pytest.mark.asyncio
async def test_citation_allowlist_filters_unknown_ids() -> None:
    """citation allow-list に含まれない ID が除外されること。"""
    embedding = MockEmbeddingAdapter()
    # クエリと同じテキストをチャンクに使う → スコア=1.0で store.search の min_score=0.0 をクリア
    query_text = "テストクエリ"
    texts = [query_text, query_text + "A", query_text + "B"]
    vecs = embedding.encode_passages(texts)
    chunks = [
        ChunkRecord(
            chunk_id=f"c{i}",
            document_id=f"doc{i}",
            text=texts[i],
            title=f"Title {i}",
            source="manual",
            document_type="manual",
            category=None,
            position=i,
        )
        for i in range(3)
    ]
    store = NumpyVectorStore(chunks=chunks, vectors=vecs)
    rag = RagService(embedding=embedding, store=store)

    # LLM が allow-list 外の citation_ids を返すモック
    import json as _json

    from helpdesk.ports.llm import LLMResult

    bad_payload = _json.dumps(
        {
            "draft_answer": "テスト回答",
            "citation_ids": ["S99", "S100"],  # allow-list は S1〜S3 のはず
            "needs_human_confirmation": True,
            "missing_information": [],
        }
    )

    mock_llm = MagicMock()
    mock_llm.provider = "test"
    mock_llm.model = "test-model"
    mock_llm.generate = AsyncMock(
        return_value=LLMResult(
            text=bad_payload,
            model="test",
            provider="test",
            input_tokens=None,
            output_tokens=None,
        )
    )

    settings = _make_settings(min_score=0.0)
    response = await rag.draft_answer(
        llm=mock_llm,
        query="テストクエリ",
        top_k=3,
        request_id="test-req-2",
        settings=settings,
    )

    # S99, S100 は allow-list 外なので citations は空
    assert response.citations == []


@pytest.mark.asyncio
async def test_citation_contains_chunk_id_and_score() -> None:
    """Citation に server-side の chunk_id と score が含まれること（FR-11）。"""
    embedding = MockEmbeddingAdapter()
    query_text = "テストクエリ"
    texts = [query_text]
    vecs = embedding.encode_passages(texts)
    chunks = [
        ChunkRecord(
            chunk_id="chunk-abc",
            document_id="doc1",
            text=query_text,
            title="テストドキュメント",
            source="manual.md",
            document_type="manual",
            category=None,
            position=0,
        )
    ]
    store = NumpyVectorStore(chunks=chunks, vectors=vecs)
    rag = RagService(embedding=embedding, store=store)

    import json as _json

    from helpdesk.ports.llm import LLMResult

    payload = _json.dumps(
        {
            "draft_answer": "回答テキスト",
            "citation_ids": ["S1"],
            "needs_human_confirmation": True,
            "missing_information": [],
        }
    )
    mock_llm = MagicMock()
    mock_llm.provider = "test"
    mock_llm.model = "test-model"
    mock_llm.generate = AsyncMock(
        return_value=LLMResult(text=payload, model="test", provider="test")
    )

    settings = _make_settings(min_score=0.0)
    response = await rag.draft_answer(
        llm=mock_llm,
        query=query_text,
        top_k=1,
        request_id="test-req-4",
        settings=settings,
    )

    assert len(response.citations) == 1
    citation = response.citations[0]
    assert citation.chunk_id == "chunk-abc"
    assert -1.0 <= citation.score <= 1.0


@pytest.mark.asyncio
async def test_mock_llm_response_contains_mock_marker() -> None:
    """Mock LLM が `[MOCK]` を含む応答を返すこと。"""
    embedding = MockEmbeddingAdapter()
    # クエリと同じテキストをチャンクに使う → cosine similarity = 1.0（確実にヒット）
    query_text = "テストクエリ"
    texts = [query_text, query_text + "2"]  # 1つはクエリと完全一致でスコア=1.0
    vecs = embedding.encode_passages(texts)
    chunks = [
        ChunkRecord(
            chunk_id=f"c{i}",
            document_id=f"doc{i}",
            text=texts[i],
            title=f"Title {i}",
            source="manual",
            document_type="manual",
            category=None,
            position=i,
        )
        for i in range(2)
    ]
    store = NumpyVectorStore(chunks=chunks, vectors=vecs)
    rag = RagService(embedding=embedding, store=store)

    llm = MockLLMAdapter()
    # store.search のデフォルト min_score=0.0 以上になるよう、クエリ一致テキストを使う
    settings = _make_settings(min_score=0.0)

    response = await rag.draft_answer(
        llm=llm,
        query=query_text,
        top_k=2,
        request_id="test-req-3",
        settings=settings,
    )

    assert "[MOCK]" in response.draft_answer
