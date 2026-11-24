"""ExcelSheetExporter — openpyxl を使ったシート書き出しアダプター。

書き込みルール（excel-auto-transfer-plan.md より）:
- 見出し行は「受付番号」というセル値を持つ行として検出する
- 列の特定は見出し名で行う（列記号ではなく）
- 空き行の最初の行（「受付番号」列が空の行）に追記する
- 重複チェック：同じ ticket_id があればスキップ
- 出力ファイルがない場合はテンプレートをコピーして初期化
- 一時ファイル経由の保存（アトミック）＋スレッドロック
- ログには ticket_id とエラー種別のみ（個人情報は出さない）
"""

from __future__ import annotations

import logging
import os
import tempfile
import threading
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import openpyxl

from helpdesk.domain.models import Ticket

logger = logging.getLogger(__name__)

_JST = ZoneInfo("Asia/Tokyo")

# フィールド対応表（見出し名 → Ticket属性 or 特殊処理キー）
# 値が None の列は「手動入力列」であり自動では書き込まない
_HEADER_TO_FIELD: dict[str, str | None] = {
    "受付番号": "ticket_id",
    "受付日時": "_received_at",   # 特殊処理（日本時間変換）
    "お客様名": "customer_name",
    "メールアドレス": "customer_email",  # 見出しがある場合のみ
    "注文番号": "_order_number",   # None → "—"
    "商品名": "_product_name",    # None → "—"
    "問い合わせ内容（要約）": "description",
    "カテゴリ": None,
    "緊急度": None,
    "対応区分": None,
    "担当": None,
    "ステータス": "status",
    "FAQ番号": None,
    "備考": "_notes",             # has_attachment 考慮
}


def _get_cell_value(ticket: Ticket, field_key: str) -> Any:
    """見出しキーに対応する書き込み値を返す。"""
    if field_key == "_received_at":
        jst_dt = ticket.created_at.astimezone(_JST)
        return jst_dt.strftime("%Y/%m/%d %H:%M")
    if field_key == "_order_number":
        return ticket.order_number if ticket.order_number is not None else "—"
    if field_key == "_product_name":
        return ticket.product_name if ticket.product_name is not None else "—"
    if field_key == "_notes":
        if ticket.notes is not None:
            return ticket.notes
        if ticket.has_attachment:
            return "写真あり"
        return None
    # 通常フィールド
    return getattr(ticket, field_key, None)


class ExcelSheetExporter:
    """Excelシートへの追記・再構築を担うアダプター。"""

    def __init__(self, template_path: str, output_path: str) -> None:
        self._template_path = Path(template_path)
        self._output_path = Path(output_path)
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def append_ticket(self, ticket: Ticket) -> None:
        """チケット1件を出力ファイルの最初の空き行に追記する（冪等）。"""
        with self._lock:
            try:
                self._ensure_output_exists()
                wb = openpyxl.load_workbook(self._output_path)
                ws = wb.worksheets[0]

                header_row, col_map = self._detect_header(ws)
                if header_row is None:
                    logger.warning(
                        "sheet_exporter: 見出し行が見つかりません。ticket_id=%s", ticket.ticket_id
                    )
                    return

                # 重複チェック
                ticket_id_col = col_map.get("受付番号")
                if ticket_id_col is None:
                    logger.warning(
                        "sheet_exporter: 「受付番号」列が見つかりません。ticket_id=%s",
                        ticket.ticket_id,
                    )
                    return

                for row in ws.iter_rows(min_row=header_row + 1, max_col=ticket_id_col):
                    cell = row[ticket_id_col - 1]
                    if cell.value == ticket.ticket_id:
                        logger.debug(
                            "sheet_exporter: 重複スキップ。ticket_id=%s", ticket.ticket_id
                        )
                        return

                # 空き行の検出
                empty_row = self._find_empty_row(ws, header_row, ticket_id_col)
                if empty_row is None:
                    logger.error(
                        "sheet_exporter: 空き行がありません。ticket_id=%s", ticket.ticket_id
                    )
                    return

                self._write_row(ws, empty_row, col_map, ticket)
                self._save_atomic(wb)

            except PermissionError:
                logger.error(
                    "sheet_exporter: ファイルが開かれていて保存できません。ticket_id=%s",
                    ticket.ticket_id,
                )
            except Exception as exc:  # noqa: BLE001
                logger.error(
                    "sheet_exporter: 書き込みエラー (%s)。ticket_id=%s",
                    type(exc).__name__,
                    ticket.ticket_id,
                )

    def rebuild(self, tickets: list[Ticket]) -> None:
        """テンプレートから出力ファイルを作り直し、全チケットを古い順に書き込む。"""
        with self._lock:
            try:
                # テンプレートをコピーしてワークブックを開く
                wb = openpyxl.load_workbook(self._template_path)
                ws = wb.worksheets[0]

                header_row, col_map = self._detect_header(ws)
                if header_row is None:
                    logger.warning("sheet_exporter: rebuild: 見出し行が見つかりません。")
                    return

                # データ行をクリア（書式・入力規則は残す）
                ticket_id_col = col_map.get("受付番号")
                if ticket_id_col is None:
                    logger.warning("sheet_exporter: rebuild: 「受付番号」列がありません。")
                    return

                for row in ws.iter_rows(min_row=header_row + 1):
                    for cell in row:
                        cell.value = None

                # 古い順にソートして書き込む
                sorted_tickets = sorted(tickets, key=lambda t: t.created_at)
                empty_row = header_row + 1
                for ticket in sorted_tickets:
                    self._write_row(ws, empty_row, col_map, ticket)
                    empty_row += 1

                self._output_path.parent.mkdir(parents=True, exist_ok=True)
                self._save_atomic(wb)

            except Exception as exc:  # noqa: BLE001
                logger.error(
                    "sheet_exporter: rebuild エラー (%s)。", type(exc).__name__
                )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _ensure_output_exists(self) -> None:
        """出力ファイルがなければテンプレートをコピーして初期化する。"""
        if not self._output_path.exists():
            self._output_path.parent.mkdir(parents=True, exist_ok=True)
            wb = openpyxl.load_workbook(self._template_path)
            ws = wb.worksheets[0]
            header_row, col_map = self._detect_header(ws)
            if header_row is not None:
                # テンプレートに入っている既存データ行をすべて空にする
                for row in ws.iter_rows(min_row=header_row + 1):
                    for cell in row:
                        cell.value = None
            self._output_path.parent.mkdir(parents=True, exist_ok=True)
            wb.save(self._output_path)

    def _detect_header(
        self, ws: Any
    ) -> tuple[int | None, dict[str, int]]:
        """見出し行の行番号と「見出し名 → 列番号（1始まり）」の対応表を返す。"""
        for row in ws.iter_rows():
            for cell in row:
                if cell.value == "受付番号":
                    header_row_num = cell.row
                    col_map: dict[str, int] = {}
                    for c in ws[header_row_num]:
                        if c.value is not None:
                            col_map[str(c.value)] = c.column
                    return header_row_num, col_map
        return None, {}

    def _find_empty_row(
        self, ws: Any, header_row: int, ticket_id_col: int
    ) -> int | None:
        """「受付番号」列が空の最初のデータ行番号を返す。"""
        for row in ws.iter_rows(min_row=header_row + 1, min_col=ticket_id_col, max_col=ticket_id_col):
            cell = row[0]
            if cell.value is None or str(cell.value).strip() == "":
                return int(cell.row)
        return None

    def _write_row(
        self, ws: Any, row_num: int, col_map: dict[str, int], ticket: Ticket
    ) -> None:
        """指定行にチケットの各フィールドを書き込む。"""
        for header_name, field_key in _HEADER_TO_FIELD.items():
            if field_key is None:
                continue  # 手動列はスキップ
            col = col_map.get(header_name)
            if col is None:
                continue  # テンプレートにない見出しはスキップ
            value = _get_cell_value(ticket, field_key)
            if value is not None:
                ws.cell(row=row_num, column=col).value = value

    def _save_atomic(self, wb: Any) -> None:
        """一時ファイルに保存してからアトミックに置き換える。"""
        self._output_path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            suffix=".xlsx", dir=self._output_path.parent, delete=False
        ) as tf:
            temp_name = tf.name

        try:
            wb.save(temp_name)
            os.replace(temp_name, self._output_path)
        except Exception:
            # クリーンアップしてから再スロー
            try:
                os.unlink(temp_name)
            except OSError:
                pass
            raise
