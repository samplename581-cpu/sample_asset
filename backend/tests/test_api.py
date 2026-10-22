"""Basic API smoke tests – use temporary directories so tests are self-contained."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """TestClient with isolated seed/runtime/index directories."""
    seed_dir = tmp_path / "seed"
    seed_dir.mkdir()
    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir()
    index_dir = tmp_path / "index"
    index_dir.mkdir()

    # Minimal seed data
    tickets = [
        {
            "ticket_id": f"OBS-{i:03d}",
            "title": f"チケット{i}",
            "description": "テスト用説明",
            "created_at": f"2025-04-10T0{i % 10}:00:00+09:00",
            "customer_name": f"顧客{i}",
            "category": "配送関連",
            "priority": "中",
            "status": "完了",
            "assigned_team": "窓口担当",
            "resolution": "解決済み",
            "version": 1,
        }
        for i in range(1, 11)
    ]
    (seed_dir / "tickets_student.json").write_text(
        json.dumps(tickets, ensure_ascii=False), encoding="utf-8"
    )
    (seed_dir / "masters.json").write_text(
        json.dumps(
            {
                "categories": [{"category_id": "CAT01", "category_name": "配送関連"}],
                "priorities": [{"priority_id": "P01", "priority_name": "高"}],
                "support-teams": [{"team_id": "T01", "team_name": "窓口担当"}],
                "statuses": [{"status_id": "ST01", "status_name": "未対応"}],
                "handling-types": [{"handling_type_id": "H01", "handling_type_name": "FAQで回答"}],
                "inquiry-types": [
                    {"inquiry_type_id": "IT01", "inquiry_type_name": "配送について"}
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    # Minimal index (64-dim mock)
    dim = 64
    chunks = [
        {
            "chunk_id": "c1",
            "document_id": "doc1",
            "text": "配送日を変更したい",
            "title": "配送日を変更したい",
            "source": "test",
            "document_type": "faq",
            "category": "配送関連",
            "position": 0,
        }
    ]
    (index_dir / "chunks.json").write_text(json.dumps(chunks, ensure_ascii=False), encoding="utf-8")
    manifest = {
        "schema_version": 1,
        "created_at": "2025-01-01T00:00:00+09:00",
        "embedding_provider": "mock",
        "embedding_model": "mock-embedding-v1",
        "dimension": dim,
        "distance": "cosine",
        "chunk_count": 1,
        "source_hash": "sha256:test",
    }
    (index_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
    )
    v = np.zeros((1, dim), dtype=np.float32)
    v[0, 0] = 1.0
    np.save(str(index_dir / "vectors.npy"), v)

    monkeypatch.setenv("SEED_DATA_DIR", str(seed_dir))
    monkeypatch.setenv("RUNTIME_DATA_DIR", str(runtime_dir))
    monkeypatch.setenv("INDEX_DIR", str(index_dir))
    monkeypatch.setenv("EMBEDDING_DIMENSION", str(dim))

    # Re-import app after env overrides
    from helpdesk.config import get_settings

    get_settings.cache_clear()
    from helpdesk.main import app  # noqa: PLC0415

    with TestClient(app) as c:
        yield c

    get_settings.cache_clear()


def test_live(client: TestClient) -> None:
    res = client.get("/api/v1/health/live")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}
    assert "X-Request-ID" in res.headers


def test_ready(client: TestClient) -> None:
    res = client.get("/api/v1/health/ready")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ready"
    assert data["checks"]["seed_tickets"] == "ok"


def test_masters(client: TestClient) -> None:
    res = client.get("/api/v1/masters/categories")
    assert res.status_code == 200
    data = res.json()
    assert data["name"] == "categories"
    assert len(data["items"]) > 0


def test_tickets_crud(client: TestClient) -> None:
    # 1. List tickets (10件あり, limit=5 なので next_cursor が返る)
    res = client.get("/api/v1/tickets?limit=5")
    assert res.status_code == 200
    page = res.json()
    assert "items" in page
    assert len(page["items"]) == 5
    assert page["next_cursor"] is not None

    # 2. Create ticket
    new_ticket = {
        "customer_name": "佐藤 美咲",
        "customer_email": "misaki@example.com",
        "order_number": "MK-24581",
        "product_name": "3人掛けソファ「モリ」",
        "inquiry_type": "配送について",
        "description": "配送日を変更したい",
    }
    res = client.post("/api/v1/tickets", json=new_ticket)
    assert res.status_code == 201
    created = res.json()
    ticket_id = created["ticket_id"]
    assert ticket_id.startswith("TKT-")
    assert created["title"].startswith("3人掛けソファ「モリ」")
    assert created["customer_name"] == "佐藤 美咲"
    assert created["status"] == "未対応"
    assert created["version"] == 1
    assert "Location" in res.headers

    # 3. Get ticket
    res = client.get(f"/api/v1/tickets/{ticket_id}")
    assert res.status_code == 200
    assert res.json()["ticket_id"] == ticket_id

    # 4. Update ticket - success
    update_payload = {"version": 1, "category": "配送関連", "status": "対応中"}
    res = client.patch(f"/api/v1/tickets/{ticket_id}", json=update_payload)
    assert res.status_code == 200
    updated = res.json()
    assert updated["category"] == "配送関連"
    assert updated["status"] == "対応中"
    assert updated["version"] == 2

    # 5. Update ticket - version conflict (409)
    res = client.patch(f"/api/v1/tickets/{ticket_id}", json=update_payload)
    assert res.status_code == 409
    assert res.headers["content-type"].startswith("application/problem+json")
    assert res.json()["status"] == 409

    # 6. Get not found (404)
    res = client.get("/api/v1/tickets/TKT-99999999")
    assert res.status_code == 404
    assert res.headers["content-type"].startswith("application/problem+json")
