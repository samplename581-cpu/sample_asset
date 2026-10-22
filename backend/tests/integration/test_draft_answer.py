"""Integration tests for draft answer endpoint."""

from __future__ import annotations

import json

import numpy as np
import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client_with_rag(tmp_path_factory: pytest.TempPathFactory) -> TestClient:
    """Mock provider + mock RAG index を持つ TestClient を返す。"""
    import os

    tmp_path = tmp_path_factory.mktemp("integration")
    seed_dir = tmp_path / "seed"
    runtime_dir = tmp_path / "runtime"
    index_dir = tmp_path / "index"
    seed_dir.mkdir()
    runtime_dir.mkdir()
    index_dir.mkdir()

    # Seed tickets
    tickets = [
        {
            "ticket_id": "TKT-00000001",
            "title": "VPN接続障害",
            "description": "VPNに接続できない",
            "created_at": "2025-01-01T00:00:00+00:00",
            "customer_name": "テスト 太郎",
            "category": "配送関連",
            "priority": "中",
            "status": "未対応",
            "assigned_team": None,
            "resolution": None,
            "version": 1,
        }
    ]
    (seed_dir / "tickets_student.json").write_text(
        json.dumps(tickets, ensure_ascii=False), encoding="utf-8"
    )

    # Minimal RAG index (1 chunk, dim=64)
    # MockEmbeddingAdapter は hash ベースのため、クエリテキストと同一のテキストを
    # チャンクに使うことで cosine=1.0（確実にスコア>0.0）を保証する
    from helpdesk.adapters.embedding_mock import MockEmbeddingAdapter as _MockEmb

    _emb = _MockEmb()
    # 各テストで使うクエリをすべてカバーするチャンクを作成
    chunk_texts = [
        "VPNに接続できません",
        "パスワードを忘れました",
    ]
    chunk_vecs = _emb.encode_passages(chunk_texts)

    chunks = [
        {
            "chunk_id": f"c{i + 1}",
            "document_id": f"doc{i + 1}",
            "text": chunk_texts[i],
            "title": f"チャンク{i + 1}",
            "source": "internal-manual",
            "document_type": "manual",
            "category": "general",
            "position": i,
        }
        for i in range(len(chunk_texts))
    ]
    (index_dir / "chunks.json").write_text(json.dumps(chunks, ensure_ascii=False), encoding="utf-8")
    (index_dir / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "created_at": "2025-01-01T00:00:00+09:00",
                "embedding_provider": "mock",
                "embedding_model": "mock-embedding-v1",
                "dimension": 64,
                "distance": "cosine",
                "chunk_count": len(chunks),
                "source_hash": "sha256:test",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    np.save(str(index_dir / "vectors.npy"), chunk_vecs)

    # 環境変数でパスを上書き
    env_overrides = {
        "LLM_PROVIDER": "mock",
        "EMBEDDING_PROVIDER": "mock",
        "EMBEDDING_DIMENSION": "64",
        "SEED_DATA_DIR": str(seed_dir),
        "RUNTIME_DATA_DIR": str(runtime_dir),
        "INDEX_DIR": str(index_dir),
        "VECTOR_MIN_SCORE": "0.0",
    }
    original_env = {k: os.environ.get(k) for k in env_overrides}
    for k, v_str in env_overrides.items():
        os.environ[k] = v_str

    from helpdesk.config import get_settings

    get_settings.cache_clear()

    from helpdesk.main import app

    with TestClient(app) as c:
        yield c

    # 環境変数を元に戻す
    for k, v_orig in original_env.items():
        if v_orig is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v_orig
    get_settings.cache_clear()


def test_draft_answer_success(client_with_rag: TestClient) -> None:
    """Mock provider で Ticket 選択から Draft 生成まで成功すること。"""
    res = client_with_rag.post(
        "/api/v1/answers/draft",
        json={"ticket_id": "TKT-00000001", "top_k": 1},
    )
    assert res.status_code == 200
    data = res.json()
    assert "draft_answer" in data


def test_draft_answer_contains_mock_marker(client_with_rag: TestClient) -> None:
    """`draft_answer` に `[MOCK]` が含まれること。"""
    res = client_with_rag.post(
        "/api/v1/answers/draft",
        json={"question": "VPNに接続できません", "top_k": 1},
    )
    assert res.status_code == 200
    data = res.json()
    assert "[MOCK]" in data["draft_answer"]


def test_draft_answer_needs_human_confirmation(client_with_rag: TestClient) -> None:
    """`needs_human_confirmation` が `true` であること。"""
    res = client_with_rag.post(
        "/api/v1/answers/draft",
        json={"question": "パスワードを忘れました", "top_k": 1},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["needs_human_confirmation"] is True


def test_draft_answer_both_none_returns_422(client_with_rag: TestClient) -> None:
    """`ticket_id` も `question` も None で 422 になること。"""
    res = client_with_rag.post(
        "/api/v1/answers/draft",
        json={},
    )
    assert res.status_code == 422


def test_draft_answer_both_specified_returns_422(client_with_rag: TestClient) -> None:
    """`ticket_id` と `question` の両方を指定したとき 422 になること（oneOf 制約）。"""
    res = client_with_rag.post(
        "/api/v1/answers/draft",
        json={"ticket_id": "TKT-00000001", "question": "パスワードを忘れました"},
    )
    assert res.status_code == 422


def test_draft_answer_unknown_ticket_id_returns_404(client_with_rag: TestClient) -> None:
    """存在しない `ticket_id` で 404 になること。"""
    res = client_with_rag.post(
        "/api/v1/answers/draft",
        json={"ticket_id": "TKT-99999999"},
    )
    assert res.status_code == 404


def test_draft_answer_citation_has_chunk_id_and_score(client_with_rag: TestClient) -> None:
    """Citation に chunk_id と score が含まれること（FR-11）。"""
    res = client_with_rag.post(
        "/api/v1/answers/draft",
        json={"question": "VPNに接続できません", "top_k": 1},
    )
    assert res.status_code == 200
    data = res.json()
    # citations が 1 件以上あるときだけ chunk_id/score を検証する
    for citation in data.get("citations", []):
        assert "chunk_id" in citation
        assert "score" in citation
        assert isinstance(citation["score"], float)
        assert -1.0 <= citation["score"] <= 1.0
