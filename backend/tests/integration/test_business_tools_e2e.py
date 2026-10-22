"""業務ツール取込 -> Index構築 -> 検索 -> 回答案生成 の統合テスト（Mock Embedding）。"""

from __future__ import annotations

import importlib.util
import json
import logging
import shutil
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

_ROOT = Path(__file__).resolve().parents[3]
_SOURCE = _ROOT / "assets" / "source" / "business_tools"


def _load(name: str) -> object:
    spec = importlib.util.spec_from_file_location(name, _ROOT / "backend" / "scripts" / f"{name}.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """tmp に data/ を生成し、build_index.py の main を tmp 向けに実行する。"""
    root = tmp_path_factory.mktemp("e2e")
    shutil.copytree(_ROOT / "backend", root / "backend", ignore=shutil.ignore_patterns("tests", "__pycache__"))
    ibt = _load("import_business_tools")
    assert ibt.run("export", _SOURCE, root / "data") == 0  # type: ignore[attr-defined]

    spec = importlib.util.spec_from_file_location("build_index_tmp", root / "backend" / "scripts" / "build_index.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.main()
    return root


def test_index_contains_all_documents(built: Path) -> None:
    chunks = json.loads((built / "data" / "index" / "chunks.json").read_text(encoding="utf-8"))
    types = [c["document_type"] for c in chunks]
    assert types.count("faq") == 15
    assert types.count("classification_rule") == 5
    assert types.count("priority_rule") == 3
    faq4 = next(c for c in chunks if c["document_id"] == "faq:FAQ-04")
    assert faq4["faq_id"] == "FAQ-04"
    assert faq4["completion_policy"].startswith("いいえ")


def test_index_has_no_personal_data(built: Path) -> None:
    blob = (built / "data" / "index" / "chunks.json").read_text(encoding="utf-8")
    for t in json.loads((built / "data" / "seed" / "tickets.json").read_text(encoding="utf-8")):
        assert t["customer_name"] not in blob
        if t["order_number"]:
            assert t["order_number"] not in blob


@pytest.fixture()
def client(built: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> TestClient:
    monkeypatch.setenv("SEED_DATA_DIR", str(built / "data" / "seed"))
    monkeypatch.setenv("INDEX_DIR", str(built / "data" / "index"))
    monkeypatch.setenv("RUNTIME_DATA_DIR", str(tmp_path / "runtime"))
    monkeypatch.setenv("VECTOR_STORE_PROVIDER", "chroma")
    monkeypatch.setenv("VECTOR_MIN_SCORE", "-1.0")
    from helpdesk.config import get_settings

    get_settings.cache_clear()
    from helpdesk.main import app

    with TestClient(app) as c:
        yield c
    get_settings.cache_clear()


def test_search_after_restart_returns_chroma_hits(client: TestClient) -> None:
    query = "質問: 配送日を変更したい\n回答: 配送予定日の3日前までであれば、こちらで変更を承ります。それ以降のご変更は、配送センターの担当者から改めてご連絡いたします。\n窓口対応: いいえ（配送センター担当）"
    q = "配送日を変更したい\n" + query
    res = client.post("/api/v1/search", json={"query": q, "top_k": 3})
    assert res.status_code == 200
    ids = [i["document_id"] for i in res.json()["items"]]
    assert ids[0] == "faq:FAQ-04"  # Mock Embeddingは同一文で完全一致する
    assert all(i["source"] for i in res.json()["items"])


def test_student_tickets_are_served_without_labels(client: TestClient) -> None:
    res = client.get("/api/v1/tickets?limit=100")
    items = res.json()["items"]
    assert len(items) == 20
    assert all(t["category"] is None and t["faq_id"] is None and t["notes"] is None for t in items)


def test_unlabeled_ticket_can_draft_answer_without_pii(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    ticket = client.get("/api/v1/tickets/Q1020-15").json()
    with caplog.at_level(logging.DEBUG):
        res = client.post("/api/v1/answers/draft", json={"ticket_id": "Q1020-15", "top_k": 3})
    assert res.status_code == 200
    body = res.json()
    assert body["needs_human_confirmation"] is True
    for secret in (ticket["customer_name"], ticket["order_number"]):
        assert secret not in res.text
        assert secret not in caplog.text


def test_masters_endpoints(client: TestClient) -> None:
    for name, n in (("categories", 5), ("priorities", 3), ("inquiry-types", 6), ("statuses", 3)):
        res = client.get(f"/api/v1/masters/{name}")
        assert res.status_code == 200, name
        assert len(res.json()["items"]) == n
    assert client.get("/api/v1/masters/services").status_code == 422


def test_create_ticket_via_form_fields(client: TestClient) -> None:
    payload = {
        "customer_name": "佐藤 美咲",
        "customer_email": "misaki@example.com",
        "order_number": "MK-24581",
        "product_name": "3人掛けソファ「モリ」",
        "inquiry_type": "配送について",
        "description": "配送予定日を変更したい",
        "has_attachment": True,
    }
    res = client.post("/api/v1/tickets", json=payload)
    assert res.status_code == 201
    created = res.json()
    assert created["ticket_id"].startswith("TKT-")
    assert created["status"] == "未対応"
    assert created["has_attachment"] is True
    second = client.post("/api/v1/tickets", json=payload).json()
    assert second["ticket_id"] != created["ticket_id"]


@pytest.mark.parametrize(
    "override",
    [
        {"inquiry_type": "存在しない種類"},
        {"customer_email": "invalid"},
        {"order_number": "bad number"},
        {"customer_name": ""},
        {"description": "x" * 4001},
        {"ticket_id": "TKT-HACK"},
        {"status": "完了"},
        {"requester_department": "営業部"},
    ],
)
def test_create_ticket_rejects_invalid(client: TestClient, override: dict[str, object]) -> None:
    payload = {
        "customer_name": "佐藤 美咲",
        "customer_email": "misaki@example.com",
        "inquiry_type": "配送について",
        "description": "配送予定日を変更したい",
        **override,
    }
    res = client.post("/api/v1/tickets", json=payload)
    assert res.status_code == 422
    assert res.headers["content-type"].startswith("application/problem+json")
