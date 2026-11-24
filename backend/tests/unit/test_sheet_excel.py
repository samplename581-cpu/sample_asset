"""Unit tests for ExcelSheetExporter.

受け入れ条件（excel-auto-transfer-plan.md）:
  1. 1件送信すると行が1行増え、集計シートの「未判定」と「未対応」がそれぞれ1増える
  2. 同じチケットを2回書き出しても、行は1行のまま
  3. 追記してもテンプレートのプルダウンと黄色セルの書式が残っている（書式破壊がない）
  4. 14列テンプレートでは「メールアドレス」列に書き込み、13列テンプレートでは書き込まない
  5. 受付日時が日本時間で表示される
  6. 出力ファイルを開いたまま送信しても、ログに個人情報が出ていない
  7. 空き行がない状態で送信しても例外が起きない
  8. rebuild を2回実行しても同じ結果になる
  9. テンプレートファイルの中身が変わっていない
"""

from __future__ import annotations

import logging
import shutil
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import openpyxl
import pytest
from helpdesk.adapters.sheet_excel import ExcelSheetExporter
from helpdesk.domain.models import Ticket

# プロジェクトルートからの絶対パスでテンプレートを参照
# __file__ = backend/tests/unit/test_sheet_excel.py
# parents[0] = backend/tests/unit
# parents[1] = backend/tests
# parents[2] = backend
# parents[3] = <workspace_root> (sample_asset)
_TEMPLATE_PATH = (
    Path(__file__).parents[3] / "assets" / "source" / "business_tools" / "inquiry_management.xlsx"
)


def _make_ticket(
    ticket_id: str = "TKT-00000001",
    customer_name: str = "テスト顧客",
    customer_email: str | None = "test@example.com",
    order_number: str | None = None,
    product_name: str | None = None,
    description: str = "テスト問い合わせ内容",
    status: str = "未対応",
    has_attachment: bool = False,
    notes: str | None = None,
    created_at: datetime | None = None,
) -> Ticket:
    """テスト用 Ticket を生成するファクトリー。"""
    if created_at is None:
        created_at = datetime(2026, 10, 20, 1, 5, tzinfo=UTC)  # JST 10:05
    return Ticket(
        ticket_id=ticket_id,
        title="テストタイトル",
        description=description,
        created_at=created_at,
        customer_name=customer_name,
        customer_email=customer_email,
        order_number=order_number,
        product_name=product_name,
        status=status,
        has_attachment=has_attachment,
        notes=notes,
        version=1,
    )


@pytest.fixture()
def exporter(tmp_path: Path) -> ExcelSheetExporter:
    """テンプレートを使い、出力先を tmp_path に向けた ExcelSheetExporter。"""
    output_path = tmp_path / "output" / "inquiry_management.xlsx"
    return ExcelSheetExporter(
        template_path=str(_TEMPLATE_PATH),
        output_path=str(output_path),
    )


def _count_data_rows(wb: openpyxl.Workbook) -> int:
    """見出し行より下で「受付番号」列に値がある行を数える。"""
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
# 条件 1: 1件書き込むと行が1行増える
# ---------------------------------------------------------------------------

def test_append_adds_one_row(exporter: ExcelSheetExporter, tmp_path: Path) -> None:
    """受け入れ条件1: 1件送信すると出力ファイルの行が1行増える。"""
    ticket = _make_ticket()
    exporter.append_ticket(ticket)

    output_path = Path(str(exporter._output_path))
    assert output_path.exists()
    wb = openpyxl.load_workbook(output_path)
    assert _count_data_rows(wb) == 1


def test_append_writes_correct_fields(exporter: ExcelSheetExporter) -> None:
    """受け入れ条件1: 書き込まれた値がチケットの値と一致する。"""
    ticket = _make_ticket(
        ticket_id="TKT-00000001",
        customer_name="山田 太郎",
        order_number="MK-12345",
        product_name="テスト商品",
        description="商品に傷があります",
        status="未対応",
    )
    exporter.append_ticket(ticket)

    wb = openpyxl.load_workbook(str(exporter._output_path))
    ws = wb.worksheets[0]

    # 見出し行を検出してフィールド確認
    col_map: dict[str, int] = {}
    header_row_num = None
    for row in ws.iter_rows():
        for cell in row:
            if cell.value == "受付番号":
                header_row_num = cell.row
                for c in ws[cell.row]:
                    if c.value is not None:
                        col_map[str(c.value)] = c.column
                break
        if header_row_num:
            break

    assert header_row_num is not None
    data_row = header_row_num + 1

    assert ws.cell(data_row, col_map["受付番号"]).value == "TKT-00000001"
    assert ws.cell(data_row, col_map["お客様名"]).value == "山田 太郎"
    assert ws.cell(data_row, col_map["注文番号"]).value == "MK-12345"
    assert ws.cell(data_row, col_map["商品名"]).value == "テスト商品"
    assert ws.cell(data_row, col_map["問い合わせ内容（要約）"]).value == "商品に傷があります"
    assert ws.cell(data_row, col_map["ステータス"]).value == "未対応"


# ---------------------------------------------------------------------------
# 条件 2: 同じチケットを2回送っても行は1行のまま（冪等性）
# ---------------------------------------------------------------------------

def test_append_is_idempotent(exporter: ExcelSheetExporter) -> None:
    """受け入れ条件2: 同じチケットを2回書き出しても行は1行のまま。"""
    ticket = _make_ticket()
    exporter.append_ticket(ticket)
    exporter.append_ticket(ticket)

    wb = openpyxl.load_workbook(str(exporter._output_path))
    assert _count_data_rows(wb) == 1


# ---------------------------------------------------------------------------
# 条件 3: 書式破壊がない（集計シートの数式が壊れていない）
# ---------------------------------------------------------------------------

def test_aggregate_sheet_formulas_intact(exporter: ExcelSheetExporter) -> None:
    """受け入れ条件3: 追記後も集計シートの数式が残っている。"""
    ticket = _make_ticket()
    exporter.append_ticket(ticket)

    wb = openpyxl.load_workbook(str(exporter._output_path), data_only=False)
    # 集計シートが存在することを確認
    sheet_names = [ws.title for ws in wb.worksheets]
    assert len(wb.worksheets) >= 2, f"集計シートがありません。シート: {sheet_names}"

    agg_ws = wb.worksheets[1]
    # 数式セルが少なくとも1つ存在することを確認
    formula_count = 0
    for row in agg_ws.iter_rows():
        for cell in row:
            if isinstance(cell.value, str) and cell.value.startswith("="):
                formula_count += 1
    assert formula_count > 0, "集計シートに数式がありません"


# ---------------------------------------------------------------------------
# 条件 4: 13列テンプレートではメールアドレスを書かない
# ---------------------------------------------------------------------------

def test_no_email_column_in_13col_template(exporter: ExcelSheetExporter) -> None:
    """受け入れ条件4: 13列テンプレートには「メールアドレス」列がなく、正常終了する。"""
    ticket = _make_ticket(customer_email="secret@example.com")
    exporter.append_ticket(ticket)  # 例外なく終了すること

    wb = openpyxl.load_workbook(str(exporter._output_path))
    ws = wb.worksheets[0]

    # 「メールアドレス」見出しがないことを確認
    headers = [
        str(cell.value)
        for row in ws.iter_rows(max_row=10)
        for cell in row
        if cell.value is not None
    ]
    assert "メールアドレス" not in headers


def test_email_written_in_14col_template(tmp_path: Path) -> None:
    """受け入れ条件4: 14列テンプレート（「メールアドレス」あり）では該当列に書き込む。"""
    # 13列テンプレートを元に「メールアドレス」列を追加した疑似テンプレートを作成
    src = str(_TEMPLATE_PATH)
    tpl = tmp_path / "template_14col.xlsx"
    shutil.copy(src, tpl)

    wb = openpyxl.load_workbook(str(tpl))
    ws = wb.worksheets[0]

    # 見出し行を見つけてメールアドレス列（14列目相当）を追加
    for row in ws.iter_rows(max_row=10):
        for cell in row:
            if cell.value == "受付番号":
                header_row = cell.row
                # 現在の最終列の隣に追加
                last_col = ws.max_column
                ws.cell(header_row, last_col + 1).value = "メールアドレス"
                wb.save(str(tpl))
                break

    output_path = tmp_path / "output_14col.xlsx"
    exporter14 = ExcelSheetExporter(template_path=str(tpl), output_path=str(output_path))

    ticket = _make_ticket(customer_email="user@example.com")
    exporter14.append_ticket(ticket)

    wb_out = openpyxl.load_workbook(str(output_path))
    ws_out = wb_out.worksheets[0]

    # メールアドレスが書かれているか確認
    email_col = None
    for row in ws_out.iter_rows(max_row=10):
        for cell in row:
            if cell.value == "メールアドレス":
                email_col = cell.column
                break

    assert email_col is not None
    # データ行のメールアドレスを確認
    for row in ws_out.iter_rows():
        for cell in row:
            if cell.value == "受付番号":
                data_row = cell.row + 1
                assert ws_out.cell(data_row, email_col).value == "user@example.com"
                return
    pytest.fail("データ行が見つかりません")


# ---------------------------------------------------------------------------
# 条件 5: 受付日時が日本時間で書き込まれる
# ---------------------------------------------------------------------------

def test_received_at_is_jst(exporter: ExcelSheetExporter) -> None:
    """受け入れ条件5: 受付日時が Asia/Tokyo で YYYY/MM/DD HH:MM 形式で書かれる。"""
    # UTC 2026-10-20 00:05 → JST 2026-10-20 09:05
    utc_dt = datetime(2026, 10, 20, 0, 5, tzinfo=UTC)
    ticket = _make_ticket(created_at=utc_dt)
    exporter.append_ticket(ticket)

    wb = openpyxl.load_workbook(str(exporter._output_path))
    ws = wb.worksheets[0]

    col_map: dict[str, int] = {}
    header_row_num = None
    for row in ws.iter_rows():
        for cell in row:
            if cell.value == "受付番号":
                header_row_num = cell.row
                for c in ws[cell.row]:
                    if c.value is not None:
                        col_map[str(c.value)] = c.column
                break
        if header_row_num:
            break

    assert header_row_num is not None
    data_row = header_row_num + 1
    received_at_val = ws.cell(data_row, col_map["受付日時"]).value
    assert received_at_val == "2026/10/20 09:05"


# ---------------------------------------------------------------------------
# 条件 6: PermissionError が起きてもログに個人情報が出ない
# ---------------------------------------------------------------------------

def test_permission_error_does_not_log_pii(
    exporter: ExcelSheetExporter, caplog: pytest.LogCaptureFixture
) -> None:
    """受け入れ条件6: PermissionError 時にログに個人情報が出ない。"""
    ticket = _make_ticket(
        customer_name="田中 花子",
        customer_email="hana@example.com",
        description="個人情報を含む問い合わせ内容",
    )

    with patch("helpdesk.adapters.sheet_excel.openpyxl.load_workbook", side_effect=PermissionError("file locked")):
        with caplog.at_level(logging.ERROR, logger="helpdesk.adapters.sheet_excel"):
            exporter.append_ticket(ticket)

    pii_values = ["田中 花子", "hana@example.com", "個人情報を含む問い合わせ内容"]
    for pii in pii_values:
        for record in caplog.records:
            assert pii not in record.getMessage(), f"ログにPIIが含まれています: {pii}"


# ---------------------------------------------------------------------------
# 条件 7: 空き行がなくても例外が起きない
# ---------------------------------------------------------------------------

def test_no_empty_row_does_not_raise(exporter: ExcelSheetExporter) -> None:
    """受け入れ条件7: 空き行がない状態で append_ticket しても例外が起きない。"""
    # 出力ファイルを初期化してから全データ行を埋める
    exporter._ensure_output_exists()
    wb = openpyxl.load_workbook(str(exporter._output_path))
    ws = wb.worksheets[0]

    # 見出し行を検出
    header_row_num = None
    for row in ws.iter_rows():
        for cell in row:
            if cell.value == "受付番号":
                header_row_num = cell.row
                break
        if header_row_num:
            break

    assert header_row_num is not None
    # 全データ行の「受付番号」列に値を入れて空き行をなくす
    ticket_id_col = None
    for c in ws[header_row_num]:
        if c.value == "受付番号":
            ticket_id_col = c.column
            break

    assert ticket_id_col is not None
    for i, row in enumerate(ws.iter_rows(min_row=header_row_num + 1)):
        ws.cell(row[0].row, ticket_id_col).value = f"DUMMY-{i:04d}"

    wb.save(str(exporter._output_path))

    # 新しいチケットを追記しても例外にならないことを確認
    new_ticket = _make_ticket(ticket_id="TKT-99999999")
    exporter.append_ticket(new_ticket)  # raises してはいけない


# ---------------------------------------------------------------------------
# 条件 8: rebuild を2回実行しても同じ結果になる（冪等性）
# ---------------------------------------------------------------------------

def test_rebuild_is_idempotent(exporter: ExcelSheetExporter) -> None:
    """受け入れ条件8: rebuild を2回実行しても同じ結果になる。"""
    tickets = [
        _make_ticket(
            ticket_id=f"TKT-{i:08d}",
            created_at=datetime(2026, 10, 20, i, 0, tzinfo=UTC),
        )
        for i in range(1, 4)
    ]

    exporter.rebuild(tickets)
    wb1 = openpyxl.load_workbook(str(exporter._output_path))
    rows_first = _count_data_rows(wb1)

    exporter.rebuild(tickets)
    wb2 = openpyxl.load_workbook(str(exporter._output_path))
    rows_second = _count_data_rows(wb2)

    assert rows_first == rows_second == 3


def test_rebuild_sorts_by_created_at(exporter: ExcelSheetExporter) -> None:
    """受け入れ条件8: rebuild 後に古い順で並んでいる。"""
    tickets = [
        _make_ticket(
            ticket_id="TKT-00000003",
            created_at=datetime(2026, 10, 20, 3, 0, tzinfo=UTC),
        ),
        _make_ticket(
            ticket_id="TKT-00000001",
            created_at=datetime(2026, 10, 20, 1, 0, tzinfo=UTC),
        ),
        _make_ticket(
            ticket_id="TKT-00000002",
            created_at=datetime(2026, 10, 20, 2, 0, tzinfo=UTC),
        ),
    ]
    exporter.rebuild(tickets)

    wb = openpyxl.load_workbook(str(exporter._output_path))
    ws = wb.worksheets[0]

    header_row_num = None
    ticket_id_col = None
    for row in ws.iter_rows():
        for cell in row:
            if cell.value == "受付番号":
                header_row_num = cell.row
                ticket_id_col = cell.column
                break
        if header_row_num:
            break

    assert header_row_num is not None and ticket_id_col is not None
    written_ids = []
    for row in ws.iter_rows(min_row=header_row_num + 1, min_col=ticket_id_col, max_col=ticket_id_col):
        val = row[0].value
        if val:
            written_ids.append(val)

    assert written_ids == ["TKT-00000001", "TKT-00000002", "TKT-00000003"]


# ---------------------------------------------------------------------------
# 条件 9: テンプレートファイルが書き換えられていない
# ---------------------------------------------------------------------------

def test_template_is_not_modified(exporter: ExcelSheetExporter) -> None:
    """受け入れ条件9: append_ticket 後にテンプレートの内容が変わっていない。"""
    before = _TEMPLATE_PATH.read_bytes()
    ticket = _make_ticket()
    exporter.append_ticket(ticket)
    after = _TEMPLATE_PATH.read_bytes()
    assert before == after, "テンプレートファイルが書き換えられました"


def test_rebuild_does_not_modify_template(exporter: ExcelSheetExporter) -> None:
    """受け入れ条件9: rebuild 後にもテンプレートの内容が変わっていない。"""
    before = _TEMPLATE_PATH.read_bytes()
    tickets = [_make_ticket()]
    exporter.rebuild(tickets)
    after = _TEMPLATE_PATH.read_bytes()
    assert before == after, "テンプレートファイルが書き換えられました（rebuild）"


# ---------------------------------------------------------------------------
# 追加: None フィールドのデフォルト値確認
# ---------------------------------------------------------------------------

def test_none_order_and_product_written_as_dash(exporter: ExcelSheetExporter) -> None:
    """注文番号・商品名が None のとき「—」が書き込まれる。"""
    ticket = _make_ticket(order_number=None, product_name=None)
    exporter.append_ticket(ticket)

    wb = openpyxl.load_workbook(str(exporter._output_path))
    ws = wb.worksheets[0]

    col_map: dict[str, int] = {}
    header_row_num = None
    for row in ws.iter_rows():
        for cell in row:
            if cell.value == "受付番号":
                header_row_num = cell.row
                for c in ws[cell.row]:
                    if c.value is not None:
                        col_map[str(c.value)] = c.column
                break
        if header_row_num:
            break

    assert header_row_num is not None
    data_row = header_row_num + 1
    assert ws.cell(data_row, col_map["注文番号"]).value == "—"
    assert ws.cell(data_row, col_map["商品名"]).value == "—"


def test_has_attachment_writes_photo_note(exporter: ExcelSheetExporter) -> None:
    """has_attachment=True かつ notes=None のとき「写真あり」が書き込まれる。"""
    ticket = _make_ticket(has_attachment=True, notes=None)
    exporter.append_ticket(ticket)

    wb = openpyxl.load_workbook(str(exporter._output_path))
    ws = wb.worksheets[0]

    col_map: dict[str, int] = {}
    header_row_num = None
    for row in ws.iter_rows():
        for cell in row:
            if cell.value == "受付番号":
                header_row_num = cell.row
                for c in ws[cell.row]:
                    if c.value is not None:
                        col_map[str(c.value)] = c.column
                break
        if header_row_num:
            break

    assert header_row_num is not None
    data_row = header_row_num + 1
    assert ws.cell(data_row, col_map["備考"]).value == "写真あり"


def test_notes_takes_priority_over_attachment(exporter: ExcelSheetExporter) -> None:
    """notes が既にある場合は has_attachment より notes が優先される。"""
    ticket = _make_ticket(has_attachment=True, notes="既存のメモ")
    exporter.append_ticket(ticket)

    wb = openpyxl.load_workbook(str(exporter._output_path))
    ws = wb.worksheets[0]

    col_map: dict[str, int] = {}
    header_row_num = None
    for row in ws.iter_rows():
        for cell in row:
            if cell.value == "受付番号":
                header_row_num = cell.row
                for c in ws[cell.row]:
                    if c.value is not None:
                        col_map[str(c.value)] = c.column
                break
        if header_row_num:
            break

    assert header_row_num is not None
    data_row = header_row_num + 1
    assert ws.cell(data_row, col_map["備考"]).value == "既存のメモ"
