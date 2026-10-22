"""Test configuration: force mock providers and use temporary data directories."""

from __future__ import annotations

import json
import os
from collections.abc import Generator
from pathlib import Path

import numpy as np
import pytest

# ── 環境変数を最初に設定 ────────────────────────────────────────────────────
# helpdesk モジュールのインポート前に設定する必要があるため、モジュールレベルで記述
os.environ["EMBEDDING_PROVIDER"] = "mock"
os.environ["EMBEDDING_DIMENSION"] = "64"
os.environ["LLM_PROVIDER"] = "mock"
os.environ["VECTOR_STORE_PROVIDER"] = "numpy"


@pytest.fixture(autouse=True)
def reset_settings_cache() -> Generator[None]:
    """Clear the lru_cache on get_settings so env overrides take effect per test."""
    from helpdesk.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture()
def tmp_seed_dir(tmp_path: Path) -> Path:
    """テスト用 seed ディレクトリ（最小限のチケットデータ付き）。"""
    seed_dir = tmp_path / "seed"
    seed_dir.mkdir()

    tickets = [
        {
            "ticket_id": "TKT-00000001",
            "title": "テストチケット1",
            "description": "テスト用の説明文です",
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
    (seed_dir / "tickets.json").write_text(
        json.dumps(tickets, ensure_ascii=False), encoding="utf-8"
    )
    return seed_dir


@pytest.fixture()
def tmp_runtime_dir(tmp_path: Path) -> Path:
    """テスト用 runtime ディレクトリ。"""
    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir()
    return runtime_dir


@pytest.fixture()
def tmp_index_dir(tmp_path: Path) -> Path:
    """テスト用 index ディレクトリ（64次元 mock ベクトル付き）。"""
    index_dir = tmp_path / "index"
    index_dir.mkdir()

    dim = 64
    chunks = [
        {
            "chunk_id": "c1",
            "document_id": "doc1",
            "text": "テスト用のドキュメントテキストです。",
            "title": "テストドキュメント",
            "source": "test-manual",
            "document_type": "manual",
            "category": "general",
            "position": 0,
        }
    ]
    (index_dir / "chunks.json").write_text(json.dumps(chunks, ensure_ascii=False), encoding="utf-8")
    (index_dir / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "created_at": "2025-01-01T00:00:00+09:00",
                "embedding_provider": "mock",
                "embedding_model": "mock-embedding-v1",
                "dimension": dim,
                "distance": "cosine",
                "chunk_count": 1,
                "source_hash": "sha256:test",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    v = np.zeros((1, dim), dtype=np.float32)
    v[0, 0] = 1.0
    np.save(str(index_dir / "vectors.npy"), v)

    return index_dir
