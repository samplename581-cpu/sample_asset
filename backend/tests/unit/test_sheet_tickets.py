from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pytest
from helpdesk.adapters.sheet_tickets import rows_to_tickets
from helpdesk.adapters.ticket_json import JsonTicketRepository
from helpdesk.config import Settings


def _row(**over: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "受付番号": "Q1124-01",
        "受付日時": "2026-11-24T05:05:00.000Z",
        "お客様名": "秘密 花子",
        "メールアドレス": "hanako@example.com",
        "注文番号": "MK-24631",
        "商品名": "デスク「ブナ」",
        "問い合わせ内容（要約）": "先日届いたデスクですが、\n注文した色と違うように思います。",
        "カテゴリ": "",
        "ステータス": "未対応",
        "添付画像": "desk.jpg",
        "メールID": "abc",
    }
    row.update(over)
    return row


def test_row_is_mapped_to_ticket() -> None:
    tickets, skipped = rows_to_tickets([_row()])
    assert skipped == 0
    t = tickets[0]
    assert t.ticket_id == "Q1124-01"
    assert t.created_at.isoformat() == "2026-11-24T05:05:00+00:00"
    assert t.description.startswith("先日届いたデスク")
    assert t.title.startswith("デスク「ブナ」: ")
    assert t.order_number == "MK-24631"
    assert t.has_attachment is True
    assert t.category is None


def test_empty_cells_become_none_and_no_photo() -> None:
    tickets, _ = rows_to_tickets([_row(注文番号="", 商品名="", 添付画像="", ステータス="")])
    t = tickets[0]
    assert (t.order_number, t.product_name, t.has_attachment, t.status) == (
        None, None, False, "未対応",
    )  # fmt: skip


def test_invalid_rows_are_skipped_without_logging_values(caplog: pytest.LogCaptureFixture) -> None:
    rows = [_row(), _row(受付番号="Q1124-02", メールアドレス="bad"), {"受付番号": ""}, "x"]
    with caplog.at_level(logging.WARNING):
        tickets, skipped = rows_to_tickets(rows)
    assert [t.ticket_id for t in tickets] == ["Q1124-01"]
    assert skipped == 1
    assert "row 3" in caplog.text
    assert "bad" not in caplog.text and "秘密" not in caplog.text


def test_add_new_tickets_never_overwrites(tmp_seed_dir: Path, tmp_runtime_dir: Path) -> None:
    repo = JsonTicketRepository(str(tmp_seed_dir), str(tmp_runtime_dir))
    tickets, _ = rows_to_tickets([_row()])
    assert repo.add_new_tickets(tickets) == 1
    changed, _ = rows_to_tickets([_row(商品名="別の商品")])
    assert repo.add_new_tickets(changed) == 0
    assert repo.get_ticket("Q1124-01").product_name == "デスク「ブナ」"
    reloaded = JsonTicketRepository(str(tmp_seed_dir), str(tmp_runtime_dir))
    assert reloaded.get_ticket("Q1124-01").has_attachment is True


@pytest.mark.parametrize(
    ("url", "token"), [("http://example.com/exec", "t"), ("https://example.com/exec", None)]
)
def test_sheet_sync_settings_are_validated(url: str, token: str | None) -> None:
    with pytest.raises(ValueError):
        Settings(SHEET_SYNC_URL=url, SHEET_SYNC_TOKEN=token)
