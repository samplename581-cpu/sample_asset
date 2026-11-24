"""export_inquiry_sheet.py — tickets.json の全件から出力ファイルを作り直す復旧スクリプト。

Usage (from sample_asset/ directory):
    uv run python backend/scripts/export_inquiry_sheet.py

出力ファイルが開かれている場合はメッセージを表示して終了します。
書き込みに失敗した場合はこのスクリプトで復旧してください。
"""
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup – allow running from sample_asset/ without installing the package
# ---------------------------------------------------------------------------
_SCRIPT_DIR = Path(__file__).resolve().parent
_BACKEND_SRC = _SCRIPT_DIR.parent / "src"
if str(_BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(_BACKEND_SRC))

from helpdesk.adapters.sheet_excel import ExcelSheetExporter
from helpdesk.config import Settings
from helpdesk.domain.models import Ticket

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("export_inquiry_sheet")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_file_locked(path: Path) -> bool:
    """出力ファイルが開かれているか（書き込みロックがかかっているか）を確認する。

    Windows では開かれている xlsx は排他ロックされるため open で検出できる。
    macOS / Linux では常に False を返す（ベストエフォート）。
    """
    if not path.exists():
        return False
    try:
        with open(path, "r+b"):
            return False
    except PermissionError:
        return True


def _load_tickets(tickets_json_path: Path) -> list[Ticket]:
    """tickets.json を読み込み Ticket のリストを返す。"""
    if not tickets_json_path.exists():
        logger.error("tickets.json が見つかりません: %s", tickets_json_path)
        sys.exit(1)
    content = tickets_json_path.read_text(encoding="utf-8").strip()
    if not content:
        return []
    raw_items: list[dict] = json.loads(content)
    return [Ticket.model_validate(item) for item in raw_items]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    sample_asset_dir = _SCRIPT_DIR.parent.parent  # sample_asset/
    settings = Settings()

    tickets_json_path = sample_asset_dir / "data" / "runtime" / "tickets.json"
    output_path = Path(settings.SHEET_OUTPUT_PATH)
    # 相対パスの場合は sample_asset/ を基準に解決する
    if not output_path.is_absolute():
        output_path = sample_asset_dir / output_path
    template_path = Path(settings.SHEET_TEMPLATE_PATH)
    if not template_path.is_absolute():
        template_path = sample_asset_dir / template_path

    # 出力ファイルが開かれているか確認
    if _is_file_locked(output_path):
        print(
            f"エラー: 出力ファイルが開かれています。\n"
            f"  {output_path}\n"
            "Excelを閉じてから再実行してください。",
            file=sys.stderr,
        )
        sys.exit(1)

    # チケット全件を読み込む
    tickets = _load_tickets(tickets_json_path)
    logger.info("tickets.json から %d 件を読み込みました。", len(tickets))

    # 出力ファイルを作り直す
    exporter = ExcelSheetExporter(
        template_path=str(template_path),
        output_path=str(output_path),
    )
    exporter.rebuild(tickets)

    logger.info("出力ファイルを作り直しました: %s", output_path)
    logger.info("書き出し件数: %d 件", len(tickets))


if __name__ == "__main__":
    main()
