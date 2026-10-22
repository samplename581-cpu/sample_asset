"""Unit tests for JsonTicketRepository."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from helpdesk.adapters.ticket_json import JsonTicketRepository
from helpdesk.domain.errors import ConflictError
from helpdesk.domain.models import TicketCreate, TicketUpdate


@pytest.fixture()
def tmp_repo(tmp_path: Path) -> JsonTicketRepository:
    """Create a fresh repository backed by a temporary directory."""
    seed_dir = tmp_path / "seed"
    runtime_dir = tmp_path / "runtime"
    seed_dir.mkdir()

    # Write minimal seed tickets
    tickets = [
        {
            "ticket_id": "TKT-00000001",
            "title": "VPN接続障害",
            "description": "VPNに接続できない",
            "created_at": "2025-01-01T00:00:00+00:00",
            "customer_name": "顧客A",
            "category": "配送関連",
            "priority": "中",
            "status": "未対応",
            "assigned_team": None,
            "resolution": None,
            "version": 1,
        },
        {
            "ticket_id": "TKT-00000002",
            "title": "パスワードリセット",
            "description": "パスワードを忘れた",
            "created_at": "2025-01-02T00:00:00+00:00",
            "customer_name": "顧客B",
            "category": "組み立て・使い方",
            "priority": "低",
            "status": "完了",
            "assigned_team": "窓口担当",
            "resolution": "リセット済み",
            "version": 1,
        },
    ]
    (seed_dir / "tickets.json").write_text(
        json.dumps(tickets, ensure_ascii=False), encoding="utf-8"
    )
    return JsonTicketRepository(
        seed_data_dir=str(seed_dir),
        runtime_data_dir=str(runtime_dir),
    )


def test_seed_init(tmp_repo: JsonTicketRepository) -> None:
    """seed JSON を一時ディレクトリで初期化できること。"""
    page = tmp_repo.list_tickets()
    assert len(page.items) == 2


def test_list_cursor_pagination_no_overlap_no_gap(tmp_path: Path) -> None:
    """カーソルページネーションが重複・欠落なく機能すること。"""
    seed_dir = tmp_path / "seed"
    runtime_dir = tmp_path / "runtime"
    seed_dir.mkdir()

    # 5 tickets
    tickets = [
        {
            "ticket_id": f"TKT-{i:08d}",
            "title": f"Ticket {i}",
            "description": "desc",
            "created_at": f"2025-01-0{i}T00:00:00+00:00",
            "customer_name": "顧客",
            "category": None,
            "priority": None,
            "status": "新規",
            "assigned_team": None,
            "resolution": None,
            "version": 1,
        }
        for i in range(1, 6)
    ]
    (seed_dir / "tickets.json").write_text(
        json.dumps(tickets, ensure_ascii=False), encoding="utf-8"
    )
    repo = JsonTicketRepository(
        seed_data_dir=str(seed_dir),
        runtime_data_dir=str(runtime_dir),
    )

    # 2 items per page
    collected: list[str] = []
    cursor = None
    while True:
        page = repo.list_tickets(limit=2, cursor=cursor)
        collected.extend(t.ticket_id for t in page.items)
        if page.next_cursor is None:
            break
        cursor = page.next_cursor

    assert len(collected) == 5, "重複または欠落がある"
    assert len(set(collected)) == 5, "重複チケットが存在する"


def test_list_status_filter(tmp_repo: JsonTicketRepository) -> None:
    """status フィルタが機能すること。"""
    page_new = tmp_repo.list_tickets(status="未対応")
    assert len(page_new.items) == 1
    assert all(t.status == "未対応" for t in page_new.items)

    page_done = tmp_repo.list_tickets(status="完了")
    assert all(t.status == "完了" for t in page_done.items)


def test_create_ticket_id_prefix(tmp_repo: JsonTicketRepository) -> None:
    """`create_ticket` で `ticket_id` が `TKT-` プレフィックスであること。"""
    new_ticket = TicketCreate(
        customer_name="新規 顧客",
        customer_email="new@example.com",
        inquiry_type="配送について",
        description="説明文です",
    )
    created = tmp_repo.create_ticket(new_ticket)
    assert created.ticket_id.startswith("TKT-")
    assert created.status == "未対応"
    assert created.created_at.tzinfo is not None


def test_create_ticket_ids_are_sequential_and_unique(tmp_repo: JsonTicketRepository) -> None:
    """受付番号はBackendが排他的に採番し、重複しないこと。"""
    ids = [
        tmp_repo.create_ticket(
            TicketCreate(
                customer_name=f"顧客{i}",
                customer_email="a@example.com",
                inquiry_type="その他",
                description="問い合わせ",
            )
        ).ticket_id
        for i in range(5)
    ]
    assert len(set(ids)) == 5
    assert ids == sorted(ids)


def test_seed_file_name_is_configurable(tmp_path: Path) -> None:
    """seed_file_name で Student用Ticketを選択できること。"""
    seed_dir = tmp_path / "seed"
    seed_dir.mkdir()
    base = {
        "title": "t",
        "description": "d",
        "created_at": "2025-01-01T00:00:00+00:00",
        "customer_name": "顧客",
        "status": "未対応",
    }
    (seed_dir / "tickets.json").write_text(
        json.dumps([{**base, "ticket_id": "TKT-GOLD01", "category": "配送関連"}]), encoding="utf-8"
    )
    (seed_dir / "tickets_student.json").write_text(
        json.dumps([{**base, "ticket_id": "TKT-STUDENT1"}]), encoding="utf-8"
    )
    repo = JsonTicketRepository(
        seed_data_dir=str(seed_dir),
        runtime_data_dir=str(tmp_path / "runtime"),
        seed_file_name="tickets_student.json",
    )
    page = repo.list_tickets()
    assert [t.ticket_id for t in page.items] == ["TKT-STUDENT1"]
    assert page.items[0].category is None


def test_update_ticket_version_conflict(tmp_repo: JsonTicketRepository) -> None:
    """`update_ticket` で version 不一致が `ConflictError` になること。"""
    update = TicketUpdate(version=99, status="対応中")
    with pytest.raises(ConflictError):
        tmp_repo.update_ticket("TKT-00000001", update)


def test_update_ticket_version_incremented(tmp_repo: JsonTicketRepository) -> None:
    """`update_ticket` で version がインクリメントされること。"""
    update = TicketUpdate(version=1, status="対応中")
    updated = tmp_repo.update_ticket("TKT-00000001", update)
    assert updated.version == 2


def test_atomic_file_save(tmp_repo: JsonTicketRepository, tmp_path: Path) -> None:
    """atomic ファイル保存（一時ファイル経由）が機能すること。"""
    runtime_dir = tmp_path / "runtime"
    runtime_file = runtime_dir / "tickets.json"

    # Update to trigger a save
    tmp_repo.update_ticket("TKT-00000001", TicketUpdate(version=1, status="対応中"))

    # Verify file exists and is valid JSON
    assert runtime_file.exists()
    content = runtime_file.read_text(encoding="utf-8")
    loaded = json.loads(content)
    assert isinstance(loaded, list)

    # Verify no temp files remain
    temp_files = [f for f in runtime_dir.iterdir() if f.name != "tickets.json"]
    assert len(temp_files) == 0, "一時ファイルが残っている"
