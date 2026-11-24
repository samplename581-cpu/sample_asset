"""結合テスト: POST /api/v1/tickets → tickets.json 保存 → Excel 自動追記。

シナリオ:
  - フォーム送信（POST /api/v1/tickets）が成功し、tickets.json にチケットが保存される
  - 出力 Excel ファイルに 1 行追記される
  - Excel 書き込みが失敗しても API は 201 を返し、チケットも保存される
  - テンプレートファイルが書き換えられない
"""

from __future__ import annotations

import logging
from pathlib import Path

import openpyxl
import pytest
from fastapi.testclient import TestClient

# プロジェクトルートからのテンプレートパス
# __file__ = backend/tests/integration/test_ticket_excel_integration.py
# parents[0] = backend/tests/integration
# parents[1] = backend/tests
# parents[2] = backend
# parents[3] = <workspace_root> (sample_asset)
_TEMPLATE_PATH = (
    Path(__file__).parents[3] / "assets" / "source" / "business_tools" / "inquiry_management.xlsx"
)

_VALID_PAYLOAD: dict[str, object] = {
    "customer_name": "統合テスト 太郎",
    "customer_email": "integration@example.com",
    "order_number": "MK-99999",
    "product_name": "テスト商品",
    "inquiry_type": "配送について",
    "description": "配送予定日を変更したい（結合テスト）",
    "has_attachment": False,
}


def _count_data_rows(xlsx_path: Path) -> int:
    """見出し行より下の「受付番号」列に値がある行数を返す。"""
    wb = openpyxl.load_workbook(str(xlsx_path))
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


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> TestClient:
    """一時ディレクトリを向けた TestClient。sheet_exporter も tmp_path に出力する。"""
    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir()
    seed_dir = tmp_path / "seed"
    seed_dir.mkdir()

    # 最小限のシードデータを作成（inquiry-types マスターが必要）
    import shutil

    # seed ディレクトリのデータをコピー
    src_seed = Path(__file__).parents[3] / "data" / "seed"
    for f in src_seed.iterdir():
        shutil.copy(f, seed_dir / f.name)

    output_path = str(runtime_dir / "inquiry_management.xlsx")

    monkeypatch.setenv("SEED_DATA_DIR", str(seed_dir))
    monkeypatch.setenv("RUNTIME_DATA_DIR", str(runtime_dir))
    monkeypatch.setenv("SHEET_TEMPLATE_PATH", str(_TEMPLATE_PATH))
    monkeypatch.setenv("SHEET_OUTPUT_PATH", output_path)
    monkeypatch.setenv("VECTOR_STORE_PROVIDER", "numpy")

    from helpdesk.config import get_settings

    get_settings.cache_clear()

    # app を再インポートして lifespan を新設定で動かす
    import importlib

    import helpdesk.main as main_mod

    importlib.reload(main_mod)
    app = main_mod.app

    with TestClient(app) as c:
        yield c

    get_settings.cache_clear()


# ---------------------------------------------------------------------------
# メインシナリオ: POST → JSON 保存 → Excel 1行追記
# ---------------------------------------------------------------------------


def test_create_ticket_saves_to_json_and_excel(client: TestClient, tmp_path: Path) -> None:
    """POST /api/v1/tickets で tickets.json と Excel に1行追記される。"""
    output_path = Path(str(client.app.state.sheet_exporter._output_path))  # type: ignore[attr-defined]

    res = client.post("/api/v1/tickets", json=_VALID_PAYLOAD)
    assert res.status_code == 201
    created = res.json()
    assert created["ticket_id"].startswith("TKT-")

    # Excel に1行追記されている
    assert output_path.exists(), "出力 Excel ファイルが作成されていません"
    assert _count_data_rows(output_path) == 1


def test_create_two_tickets_adds_two_rows(client: TestClient) -> None:
    """2件送信すると Excel に2行追記される。"""
    output_path = Path(str(client.app.state.sheet_exporter._output_path))  # type: ignore[attr-defined]

    client.post("/api/v1/tickets", json=_VALID_PAYLOAD)
    second_payload = dict(_VALID_PAYLOAD)
    second_payload["description"] = "2件目の問い合わせ"
    client.post("/api/v1/tickets", json=second_payload)

    assert _count_data_rows(output_path) == 2


# ---------------------------------------------------------------------------
# ベストエフォート: Excel 書き込み失敗でも 201 が返る
# ---------------------------------------------------------------------------


def test_excel_failure_still_returns_201(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Excel 書き込みが例外を起こしてもチケット作成は 201 を返す。"""
    from unittest.mock import patch

    with patch.object(
        client.app.state.sheet_exporter,
        "append_ticket",
        side_effect=RuntimeError("disk full"),
    ):
        with caplog.at_level(logging.ERROR):
            res = client.post("/api/v1/tickets", json=_VALID_PAYLOAD)

    assert res.status_code == 201
    # エラーがログに記録されている
    assert any("append_ticket" in r.message for r in caplog.records)
    # ログに個人情報が含まれない
    for record in caplog.records:
        assert "統合テスト 太郎" not in record.getMessage()
        assert "integration@example.com" not in record.getMessage()


# ---------------------------------------------------------------------------
# テンプレート汚染チェック
# ---------------------------------------------------------------------------


def test_template_not_modified(client: TestClient) -> None:
    """POST 後にテンプレートファイルが書き換えられていない。"""
    before = _TEMPLATE_PATH.read_bytes()
    client.post("/api/v1/tickets", json=_VALID_PAYLOAD)
    after = _TEMPLATE_PATH.read_bytes()
    assert before == after, "テンプレートファイルが書き換えられました"
