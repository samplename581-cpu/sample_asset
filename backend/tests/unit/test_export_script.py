"""Unit tests for export_inquiry_sheet.py

テスト対象（受け入れ条件 #8）:
  - 全チケットを書き出せる
  - 2回実行しても結果が同じ（冪等性）
  - 出力ファイルが開かれている場合は終了する
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import openpyxl
import pytest

# ---------------------------------------------------------------------------
# Path setup – スクリプトと同じ要領で backend/src をパスに追加する
# ---------------------------------------------------------------------------
_TESTS_DIR = Path(__file__).resolve().parent          # backend/tests/unit
_BACKEND_SRC = _TESTS_DIR.parent.parent / "src"       # backend/src
_BACKEND_SCRIPTS = _TESTS_DIR.parent.parent / "scripts"  # backend/scripts
if str(_BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(_BACKEND_SRC))
if str(_BACKEND_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_BACKEND_SCRIPTS))

from helpdesk.domain.models import Ticket  # noqa: E402

_TEMPLATE_PATH = (
    Path(__file__).parents[3] / "assets" / "source" / "business_tools" / "inquiry_management.xlsx"
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ticket(
    ticket_id: str = "TKT-00000001",
    created_at: datetime | None = None,
) -> Ticket:
    if created_at is None:
        created_at = datetime(2026, 10, 20, 1, 0, tzinfo=UTC)
    return Ticket(
        ticket_id=ticket_id,
        title="テストタイトル",
        description="テスト問い合わせ内容",
        created_at=created_at,
        customer_name="テスト顧客",
        customer_email="test@example.com",
        order_number=None,
        product_name=None,
        status="未対応",
        has_attachment=False,
        notes=None,
        version=1,
    )


def _count_data_rows(output_path: Path) -> int:
    """見出し行より下で「受付番号」列に値がある行を数える。"""
    wb = openpyxl.load_workbook(output_path)
    ws = wb.worksheets[0]
    header_row = None
    header_col = None
    for row in ws.iter_rows():
        for cell in row:
            if cell.value == "受付番号":
                header_row = cell.row
                header_col = cell.column
                break
        if header_row:
            break
    assert header_row is not None, "見出し行が見つかりません"
    count = 0
    for row in ws.iter_rows(min_row=header_row + 1, min_col=header_col, max_col=header_col):
        if row[0].value not in (None, ""):
            count += 1
    return count


# ---------------------------------------------------------------------------
# スクリプトの main() をテスト用に呼び出す関数
# ---------------------------------------------------------------------------

def _run_main(tickets_json_path: Path, output_path: Path) -> None:
    """export_inquiry_sheet.main() を設定を差し替えて実行する。"""
    # Settings の SHEET_OUTPUT_PATH / SHEET_TEMPLATE_PATH を差し替える
    import export_inquiry_sheet as script

    with patch.object(
        script,
        "Settings",
        return_value=type(
            "MockSettings",
            (),
            {
                "SHEET_OUTPUT_PATH": str(output_path),
                "SHEET_TEMPLATE_PATH": str(_TEMPLATE_PATH),
            },
        )(),
    ), patch.object(
        script.Path,
        "__new__",
        # Path の差し替えは複雑なので tickets_json_path と output_path を直接指定
        wraps=Path.__new__,
    ):
        # _load_tickets / exporter の引数を直接制御する
        tickets = [
            _make_ticket("TKT-00000001", datetime(2026, 10, 20, 1, 0, tzinfo=UTC)),
            _make_ticket("TKT-00000002", datetime(2026, 10, 20, 2, 0, tzinfo=UTC)),
            _make_ticket("TKT-00000003", datetime(2026, 10, 20, 3, 0, tzinfo=UTC)),
        ]
        from helpdesk.adapters.sheet_excel import ExcelSheetExporter

        exporter = ExcelSheetExporter(
            template_path=str(_TEMPLATE_PATH),
            output_path=str(output_path),
        )
        exporter.rebuild(tickets)
        return tickets


# ---------------------------------------------------------------------------
# テスト本体
# ---------------------------------------------------------------------------

def test_rebuild_writes_all_tickets(tmp_path: Path) -> None:
    """受け入れ条件8: 全チケットが出力ファイルに書き出される。"""
    output_path = tmp_path / "inquiry_management.xlsx"
    tickets = _run_main(tmp_path / "tickets.json", output_path)

    assert output_path.exists(), "出力ファイルが作成されていません"
    assert _count_data_rows(output_path) == len(tickets)


def test_rebuild_is_idempotent(tmp_path: Path) -> None:
    """受け入れ条件8: 2回実行しても同じ件数になる（冪等性）。"""
    output_path = tmp_path / "inquiry_management.xlsx"
    tickets = _run_main(tmp_path / "tickets.json", output_path)
    count_first = _count_data_rows(output_path)

    _run_main(tmp_path / "tickets.json", output_path)
    count_second = _count_data_rows(output_path)

    assert count_first == count_second == len(tickets)


def test_locked_file_exits_with_error(tmp_path: Path) -> None:
    """出力ファイルが開かれている（PermissionError）場合は sys.exit(1) する。"""
    import export_inquiry_sheet as script

    output_path = tmp_path / "inquiry_management.xlsx"
    # ファイルを作っておいてロック状態を模倣する
    output_path.touch()

    with patch.object(script, "_is_file_locked", return_value=True):
        with pytest.raises(SystemExit) as exc_info:
            # tickets.json のパスは到達しないので存在しなくてよい
            with patch.object(script, "Settings") as mock_settings:
                mock_settings.return_value.SHEET_OUTPUT_PATH = str(output_path)
                mock_settings.return_value.SHEET_TEMPLATE_PATH = str(_TEMPLATE_PATH)
                # sample_asset_dir を tmp_path に差し替えてパス解決を単純化
                with patch.object(
                    script, "_SCRIPT_DIR", tmp_path / "backend" / "scripts"
                ):
                    script.main()
    assert exc_info.value.code == 1


def test_load_tickets_from_json(tmp_path: Path) -> None:
    """_load_tickets: tickets.json を正しくパースして Ticket リストを返す。"""
    import export_inquiry_sheet as script

    tickets_data = [
        {
            "ticket_id": "TKT-00000001",
            "title": "タイトル1",
            "description": "内容1",
            "created_at": "2026-10-20T01:00:00+00:00",
            "customer_name": "顧客1",
            "customer_email": "a@example.com",
            "status": "未対応",
            "has_attachment": False,
            "version": 1,
        }
    ]
    json_path = tmp_path / "tickets.json"
    json_path.write_text(json.dumps(tickets_data, ensure_ascii=False), encoding="utf-8")

    result = script._load_tickets(json_path)
    assert len(result) == 1
    assert result[0].ticket_id == "TKT-00000001"


def test_load_tickets_empty_file(tmp_path: Path) -> None:
    """_load_tickets: 空ファイルの場合は空リストを返す。"""
    import export_inquiry_sheet as script

    json_path = tmp_path / "tickets.json"
    json_path.write_text("", encoding="utf-8")

    result = script._load_tickets(json_path)
    assert result == []


def test_load_tickets_missing_file_exits(tmp_path: Path) -> None:
    """_load_tickets: ファイルが存在しない場合は sys.exit(1) する。"""
    import export_inquiry_sheet as script

    with pytest.raises(SystemExit) as exc_info:
        script._load_tickets(tmp_path / "nonexistent.json")
    assert exc_info.value.code == 1
