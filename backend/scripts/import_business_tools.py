"""import_business_tools.py — 業務ツール4ファイルをSeed JSONへ変換する。

Usage (from sample_asset/ directory):
    uv run python backend/scripts/import_business_tools.py validate
    uv run python backend/scripts/import_business_tools.py export
    uv run python backend/scripts/import_business_tools.py export --source-dir ./assets/source/business_tools

- validate: 読み取りとValidationのみ。出力ファイルを変更しない。
- export  : 一時ディレクトリに全JSONを生成し、全検証成功後に一括置換する。

エラーとLogには file / sheet / row / column / error_code だけを出力し、
セル本文・氏名・メール・注文番号は出力しない。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import shutil
import sys
import tempfile
import time
import zipfile
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

import openpyxl
import pydantic

_SCRIPT_DIR = Path(__file__).resolve().parent
_BASE_DIR = _SCRIPT_DIR.parent.parent  # sample_asset/
_BACKEND_SRC = _SCRIPT_DIR.parent / "src"
if str(_BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(_BACKEND_SRC))

from helpdesk.domain.models import Ticket, build_ticket_title

logger = logging.getLogger("import_business_tools")

JST = timezone(timedelta(hours=9))
DEFAULT_SOURCE_DIR = _BASE_DIR / "assets" / "source" / "business_tools"
DEFAULT_DATA_DIR = _BASE_DIR / "data"
HEADER_SEARCH_ROWS = 10
MAX_CELL_LENGTH = 4000
EMPTY_MARK = "—"

# repository内のファイル名 -> 原本名
SOURCE_FILES = {
    "faq_answers.xlsx": "FAQ回答集.xlsx",
    "inquiry_classification.xlsx": "問い合わせ分類基準表.xlsx",
    "inquiry_management.xlsx": "問い合わせ管理シート.xlsx",
    "inquiry_form.html": "問い合わせフォーム.html",
}
F_FAQ, F_CLS, F_MGMT, F_FORM = SOURCE_FILES

# IDは表示名から都度生成せず、明示的な対応表で割り当てる。
# 未知の表示値はValidation Errorとし、ここへの追加を要求する。
CATEGORY_IDS = {
    "配送関連": "CAT01",
    "商品不良・破損": "CAT02",
    "組み立て・使い方": "CAT03",
    "注文変更・キャンセル": "CAT04",
    "店舗・在庫・その他": "CAT05",
}
PRIORITY_IDS = {"高": "P01", "中": "P02", "低": "P03"}
TEAM_IDS = {"配送センター担当": "T01", "修理・アフターサービス担当": "T02", "窓口担当": "T03"}
TEAM_ALIASES = {"窓口担当（FAQで回答）": "窓口担当"}
STATUS_IDS = {"未対応": "ST01", "対応中": "ST02", "完了": "ST03"}
HANDLING_TYPE_IDS = {"FAQで回答": "H01", "専門部署へ引き継ぎ": "H02"}
INQUIRY_TYPE_IDS = {
    "配送について": "IT01",
    "商品の傷・不具合": "IT02",
    "組み立て・使い方": "IT03",
    "注文の変更・キャンセル": "IT04",
    "店舗・在庫": "IT05",
    "その他": "IT06",
}

FAQ_COLUMNS = ("FAQ番号", "カテゴリ", "よくある質問", "回答文（ひな形）", "窓口で完結", "最終更新日")
CATEGORY_COLUMNS = ("カテゴリ", "問い合わせの例", "見分けるキーワード", "対応先", "補足")
PRIORITY_COLUMNS = ("緊急度", "判断の目安", "例", "着手の目安")
TICKET_COLUMNS = (
    "受付番号", "受付日時", "お客様名", "注文番号", "商品名", "問い合わせ内容（要約）",
    "カテゴリ", "緊急度", "対応区分", "担当", "ステータス", "FAQ番号", "備考",
)  # fmt: skip

# Ticket field名 -> Excel列名（pydanticのエラー位置を列名へ戻すために使う）
_TICKET_FIELD_COLUMNS = {
    "ticket_id": "受付番号",
    "created_at": "受付日時",
    "customer_name": "お客様名",
    "order_number": "注文番号",
    "product_name": "商品名",
    "description": "問い合わせ内容（要約）",
    "category": "カテゴリ",
    "priority": "緊急度",
    "handling_type": "対応区分",
    "assigned_team": "担当",
    "status": "ステータス",
    "faq_id": "FAQ番号",
    "notes": "備考",
}

# アプリケーションの初期表示では未判定として扱うfield
_APP_HIDDEN_FIELDS = (
    "category",
    "priority",
    "handling_type",
    "assigned_team",
    "faq_id",
    "notes",
)

# (file, sheet, row)
Location = tuple[str, str, int]


@dataclass(frozen=True)
class ImportIssue:
    file: str
    sheet: str | None
    row: int | None
    column: str | None
    error_code: str


class ImportValidationError(Exception):
    def __init__(self, issues: list[ImportIssue]) -> None:
        super().__init__(f"{len(issues)} validation issue(s)")
        self.issues = issues


@dataclass(frozen=True)
class SeedBundle:
    documents: list[dict[str, Any]]
    masters: dict[str, list[dict[str, Any]]]
    tickets: list[dict[str, Any]]
    tickets_app: list[dict[str, Any]]


# ---------------------------------------------------------------------------
# 正規化
# ---------------------------------------------------------------------------


def normalize_text(value: Any) -> str | None:
    """前後空白（全角含む）を除去し、空文字と`—`をNoneへ正規化する。"""
    if value is None:
        return None
    text = str(value).replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text or text == EMPTY_MARK:
        return None
    return text


def normalize_date(value: Any) -> str | None:
    """日付のみの値を`YYYY-MM-DD`へ変換する。変換できなければValueError。"""
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return date.fromisoformat(str(value).strip()[:10]).isoformat()


def normalize_datetime_jst(value: Any) -> datetime:
    """日時をtimezone付きdatetimeへ変換する。timezoneなしはJSTとして扱う。"""
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        text = value.strip()
        try:
            parsed = datetime.strptime(text, "%Y-%m-%d %H:%M")
        except ValueError:
            parsed = datetime.fromisoformat(text)
    else:
        raise ValueError("unsupported datetime value")
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=JST)


# ---------------------------------------------------------------------------
# 読み取り
# ---------------------------------------------------------------------------


class _RadioParser(HTMLParser):
    """`<input type="radio" name="type">`のvalueを収集する。"""

    def __init__(self) -> None:
        super().__init__()
        self.values: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = dict(attrs)
        if tag == "input" and a.get("type") == "radio" and a.get("name") == "type":
            value = normalize_text(a.get("value"))
            if value:
                self.values.append(value)


class _Reader:
    """Issueを蓄積しながら4ファイルを読み取る。"""

    def __init__(self, source_dir: Path) -> None:
        self.source_dir = source_dir
        self.issues: list[ImportIssue] = []

    def add(
        self, file: str, sheet: str | None, row: int | None, column: str | None, code: str
    ) -> None:
        self.issues.append(ImportIssue(file, sheet, row, column, code))

    def _check_workbook_safety(self, path: Path, file: str) -> bool:
        """Macro・外部Link・埋め込みObjectを含むBookは読み込まない（実行もしない）。"""
        try:
            with zipfile.ZipFile(path) as zf:
                names = zf.namelist()
        except zipfile.BadZipFile:
            self.add(file, None, None, None, "INVALID_WORKBOOK")
            return False
        unsafe = any(
            n.lower().endswith("vbaproject.bin")
            or n.startswith("xl/externalLinks/")
            or n.startswith("xl/embeddings/")
            for n in names
        )
        if unsafe:
            self.add(file, None, None, None, "UNSAFE_CONTENT")
        return not unsafe

    def read_table(
        self,
        file: str,
        sheet: str,
        columns: Sequence[str],
        key_column: str,
    ) -> list[tuple[int, dict[str, Any]]]:
        """Header行を先頭10行から検出し、(行番号, {列名: 値})を返す。"""
        path = self.source_dir / file
        if not path.is_file():
            self.add(file, None, None, None, "FILE_NOT_FOUND")
            return []
        if not self._check_workbook_safety(path, file):
            return []

        # data_only=True: Excel数式は計算せず保存済みの結果を読む
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        try:
            if sheet not in wb.sheetnames:
                self.add(file, sheet, None, None, "SHEET_NOT_FOUND")
                return []
            rows = list(wb[sheet].iter_rows(values_only=True))
        finally:
            wb.close()

        header_row: int | None = None
        index: dict[str, int] = {}
        for row_no, row in enumerate(rows[:HEADER_SEARCH_ROWS], start=1):
            labels = {
                normalize_text(cell): pos for pos, cell in enumerate(row) if normalize_text(cell)
            }
            if all(col in labels for col in columns):
                header_row = row_no
                index = {col: labels[col] for col in columns}
                break
        if header_row is None:
            self.add(file, sheet, None, None, "HEADER_NOT_FOUND")
            return []

        result: list[tuple[int, dict[str, Any]]] = []
        seen: set[str] = set()
        for row_no, row in enumerate(rows[header_row:], start=header_row + 1):
            record = {col: (row[pos] if pos < len(row) else None) for col, pos in index.items()}
            key = normalize_text(record[key_column])
            if key is None:  # 主キー列が空の行はData終了後の空行として無視する
                continue
            if key in seen:
                self.add(file, sheet, row_no, key_column, "DUPLICATE_ID")
                continue
            seen.add(key)
            for col, val in record.items():
                if isinstance(val, str) and len(val) > MAX_CELL_LENGTH:
                    self.add(file, sheet, row_no, col, "VALUE_TOO_LONG")
            result.append((row_no, record))
        return result

    def read_inquiry_types(self, file: str) -> list[str]:
        """HTMLフォームのradio値（name=type）を読み取る。HTMLは実行しない。"""
        path = self.source_dir / file
        if not path.is_file():
            self.add(file, None, None, None, "FILE_NOT_FOUND")
            return []
        parser = _RadioParser()
        parser.feed(path.read_text(encoding="utf-8"))
        if not parser.values:
            self.add(file, None, None, "お問い合わせの種類", "RADIO_NOT_FOUND")
        return parser.values

    def lookup(
        self,
        table: dict[str, str],
        value: str | None,
        loc: Location,
        column: str,
        code: str,
        aliases: dict[str, str] | None = None,
    ) -> str | None:
        """表示値を対応表で確認し、未知の値はIssueへ記録する。"""
        if value is None:
            return None
        normalized = (aliases or {}).get(value, value)
        if normalized not in table:
            self.add(loc[0], loc[1], loc[2], column, code)
            return None
        return normalized


# ---------------------------------------------------------------------------
# 変換
# ---------------------------------------------------------------------------


def _document(
    document_id: str,
    title: str,
    body: str,
    document_type: str,
    source: str,
    category: str | None,
    updated_at: str | None,
    *,
    faq_id: str | None = None,
    completion_policy: str | None = None,
) -> dict[str, Any]:
    doc: dict[str, Any] = {
        "document_id": document_id,
        "title": title,
        "body": body,
        "document_type": document_type,
        "source": source,
        "category": category,
        "updated_at": updated_at,
        "access_scope": "default",
        "is_active": True,
    }
    if faq_id is not None:
        doc["faq_id"] = faq_id
        doc["completion_policy"] = completion_policy
    return doc


def _ordered(table: dict[str, str], used: set[str], prefix: str) -> list[dict[str, Any]]:
    return [
        {f"{prefix}_id": table[name], f"{prefix}_name": name}
        for name in sorted(used, key=lambda n: table[n])
    ]


def _category_documents(
    reader: _Reader, rows: list[tuple[int, dict[str, Any]]], teams: set[str]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    documents: list[dict[str, Any]] = []
    items: list[dict[str, Any]] = []
    for seq, (row_no, rec) in enumerate(rows, start=1):
        name = normalize_text(rec["カテゴリ"]) or ""
        loc = (F_CLS, "カテゴリ", row_no)
        if name not in CATEGORY_IDS:
            reader.add(F_CLS, "カテゴリ", row_no, "カテゴリ", "UNKNOWN_CATEGORY")
            continue
        examples = normalize_text(rec["問い合わせの例"])
        keywords = normalize_text(rec["見分けるキーワード"])
        team_raw = normalize_text(rec["対応先"])
        note = normalize_text(rec["補足"])
        team = reader.lookup(TEAM_IDS, team_raw, loc, "対応先", "UNKNOWN_TEAM", TEAM_ALIASES)
        if team:
            teams.add(team)
        items.append(
            {
                "category_id": CATEGORY_IDS[name],
                "category_name": name,
                "description": examples,
                "example_keywords": keywords,
                "support_team": team,
                "note": note,
            }
        )
        body = "\n".join(
            [
                f"カテゴリ: {name}",
                f"問い合わせの例: {examples or ''}",
                f"見分けるキーワード: {keywords or ''}",
                f"対応先: {team_raw or ''}",
                f"補足: {note or ''}",
            ]
        )
        documents.append(
            _document(
                f"classification:category:{seq:02d}",
                f"分類基準（カテゴリ）: {name}",
                body,
                "classification_rule",
                f"{SOURCE_FILES[F_CLS]}#カテゴリ!{row_no}",
                name,
                None,
            )
        )
    return documents, items


def _priority_documents(
    reader: _Reader, rows: list[tuple[int, dict[str, Any]]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    documents: list[dict[str, Any]] = []
    items: list[dict[str, Any]] = []
    for seq, (row_no, rec) in enumerate(rows, start=1):
        name = normalize_text(rec["緊急度"]) or ""
        if name not in PRIORITY_IDS:
            reader.add(F_CLS, "緊急度", row_no, "緊急度", "UNKNOWN_PRIORITY")
            continue
        criteria = normalize_text(rec["判断の目安"])
        examples = normalize_text(rec["例"])
        target = normalize_text(rec["着手の目安"])
        items.append(
            {
                "priority_id": PRIORITY_IDS[name],
                "priority_name": name,
                "description": criteria,
                "examples": examples,
                "response_target": target,
            }
        )
        body = "\n".join(
            [
                f"緊急度: {name}",
                f"判断の目安: {criteria or ''}",
                f"例: {examples or ''}",
                f"着手の目安: {target or ''}",
            ]
        )
        documents.append(
            _document(
                f"classification:priority:{seq:02d}",
                f"分類基準（緊急度）: {name}",
                body,
                "priority_rule",
                f"{SOURCE_FILES[F_CLS]}#緊急度!{row_no}",
                None,
                None,
            )
        )
    return documents, items


def _faq_documents(
    reader: _Reader, rows: list[tuple[int, dict[str, Any]]]
) -> tuple[list[dict[str, Any]], set[str]]:
    documents: list[dict[str, Any]] = []
    faq_ids: set[str] = set()
    for row_no, rec in rows:
        faq_id = normalize_text(rec["FAQ番号"]) or ""
        faq_ids.add(faq_id)
        category = normalize_text(rec["カテゴリ"])
        if category not in CATEGORY_IDS:  # FAQのカテゴリはカテゴリMasterに存在すること
            reader.add(F_FAQ, "FAQ回答集", row_no, "カテゴリ", "UNKNOWN_CATEGORY")
        question = normalize_text(rec["よくある質問"])
        answer = normalize_text(rec["回答文（ひな形）"])
        completion = normalize_text(rec["窓口で完結"])
        for col, val in (("よくある質問", question), ("回答文（ひな形）", answer)):
            if val is None:
                reader.add(F_FAQ, "FAQ回答集", row_no, col, "MISSING_REQUIRED")
        try:
            updated_at = normalize_date(rec["最終更新日"])
        except ValueError:
            reader.add(F_FAQ, "FAQ回答集", row_no, "最終更新日", "INVALID_DATE")
            updated_at = None
        body = f"質問: {question or ''}\n回答: {answer or ''}\n窓口対応: {completion or ''}"
        documents.append(
            _document(
                f"faq:{faq_id}",
                question or faq_id,
                body,
                "faq",
                f"{SOURCE_FILES[F_FAQ]}#FAQ回答集!{row_no}",
                category,
                updated_at,
                faq_id=faq_id,
                completion_policy=completion,
            )
        )
    return documents, faq_ids


def _ticket_error_code(err_type: str) -> str:
    if err_type in ("missing", "string_too_short"):
        return "MISSING_REQUIRED"
    if "too_long" in err_type:
        return "VALUE_TOO_LONG"
    return "INVALID_VALUE"


def _tickets(
    reader: _Reader,
    rows: list[tuple[int, dict[str, Any]]],
    faq_ids: set[str],
    teams: set[str],
    statuses: set[str],
    handlings: set[str],
) -> list[dict[str, Any]]:
    tickets: list[dict[str, Any]] = []
    for row_no, rec in rows:
        loc = (F_MGMT, "問い合わせ一覧", row_no)
        category = reader.lookup(
            CATEGORY_IDS, normalize_text(rec["カテゴリ"]), loc, "カテゴリ", "UNKNOWN_CATEGORY"
        )
        priority = reader.lookup(
            PRIORITY_IDS, normalize_text(rec["緊急度"]), loc, "緊急度", "UNKNOWN_PRIORITY"
        )
        handling = reader.lookup(
            HANDLING_TYPE_IDS,
            normalize_text(rec["対応区分"]),
            loc,
            "対応区分",
            "UNKNOWN_HANDLING_TYPE",
        )
        team = reader.lookup(
            TEAM_IDS, normalize_text(rec["担当"]), loc, "担当", "UNKNOWN_TEAM", TEAM_ALIASES
        )
        status = reader.lookup(
            STATUS_IDS, normalize_text(rec["ステータス"]), loc, "ステータス", "UNKNOWN_STATUS"
        )
        faq_id = normalize_text(rec["FAQ番号"])
        if faq_id is not None and faq_id not in faq_ids:
            reader.add(F_MGMT, "問い合わせ一覧", row_no, "FAQ番号", "UNKNOWN_FAQ_REFERENCE")
        if team:
            teams.add(team)
        if status:
            statuses.add(status)
        if handling:
            handlings.add(handling)

        try:
            created_at = normalize_datetime_jst(rec["受付日時"])
        except (ValueError, TypeError):
            reader.add(F_MGMT, "問い合わせ一覧", row_no, "受付日時", "INVALID_DATE")
            continue
        description = normalize_text(rec["問い合わせ内容（要約）"]) or ""
        product = normalize_text(rec["商品名"])
        try:
            ticket = Ticket.model_validate(
                {
                    "ticket_id": normalize_text(rec["受付番号"]) or "",
                    "title": build_ticket_title(product, description) or "-",
                    "description": description,
                    "created_at": created_at,
                    "customer_name": normalize_text(rec["お客様名"]) or "",
                    "order_number": normalize_text(rec["注文番号"]),
                    "product_name": product,
                    "category": category,
                    "priority": priority,
                    "handling_type": handling,
                    "assigned_team": team,
                    "status": status or "",
                    "faq_id": faq_id,
                    "notes": normalize_text(rec["備考"]),
                }
            )
        except pydantic.ValidationError as exc:
            for err in exc.errors():
                field = str(err["loc"][0]) if err["loc"] else ""
                column = _TICKET_FIELD_COLUMNS.get(field)
                reader.add(F_MGMT, "問い合わせ一覧", row_no, column, _ticket_error_code(err["type"]))
            continue
        tickets.append(ticket.model_dump(mode="json"))
    return tickets


def build_seed(source_dir: Path) -> SeedBundle:
    """4ファイルを読み取り、全Seedを生成する。Issueがあれば例外を送出する。"""
    reader = _Reader(source_dir)

    category_rows = reader.read_table(F_CLS, "カテゴリ", CATEGORY_COLUMNS, "カテゴリ")
    priority_rows = reader.read_table(F_CLS, "緊急度", PRIORITY_COLUMNS, "緊急度")
    faq_rows = reader.read_table(F_FAQ, "FAQ回答集", FAQ_COLUMNS, "FAQ番号")
    ticket_rows = reader.read_table(F_MGMT, "問い合わせ一覧", TICKET_COLUMNS, "受付番号")
    form_types = reader.read_inquiry_types(F_FORM)

    teams: set[str] = set()
    statuses: set[str] = set()
    handlings: set[str] = set()

    category_docs, category_items = _category_documents(reader, category_rows, teams)
    priority_docs, priority_items = _priority_documents(reader, priority_rows)
    faq_docs, faq_ids = _faq_documents(reader, faq_rows)
    tickets = _tickets(reader, ticket_rows, faq_ids, teams, statuses, handlings)

    inquiry_type_items: list[dict[str, Any]] = []
    for value in form_types:
        if value not in INQUIRY_TYPE_IDS:
            reader.add(F_FORM, None, None, "お問い合わせの種類", "UNKNOWN_INQUIRY_TYPE")
            continue
        inquiry_type_items.append(
            {"inquiry_type_id": INQUIRY_TYPE_IDS[value], "inquiry_type_name": value}
        )

    if reader.issues:
        raise ImportValidationError(reader.issues)

    masters = {
        "categories": category_items,
        "priorities": priority_items,
        "support-teams": _ordered(TEAM_IDS, teams, "team"),
        "statuses": _ordered(STATUS_IDS, statuses, "status"),
        "handling-types": _ordered(HANDLING_TYPE_IDS, handlings, "handling_type"),
        "inquiry-types": inquiry_type_items,
    }
    tickets_app = [
        {k: (None if k in _APP_HIDDEN_FIELDS else v) for k, v in t.items()} for t in tickets
    ]
    return SeedBundle(faq_docs + category_docs + priority_docs, masters, tickets, tickets_app)


# ---------------------------------------------------------------------------
# 出力
# ---------------------------------------------------------------------------


def _outputs(bundle: SeedBundle) -> dict[str, Any]:
    """出力先(data_dirからの相対パス) -> JSON値"""
    return {
        "seed/documents.json": bundle.documents,
        "seed/masters.json": bundle.masters,
        "seed/tickets.json": bundle.tickets,
        "seed/tickets_app.json": bundle.tickets_app,
    }


def write_seed(bundle: SeedBundle, data_dir: Path) -> None:
    """同一filesystem上の一時Directoryへ全JSONを生成してから、`os.replace`で置換する。"""
    data_dir.mkdir(parents=True, exist_ok=True)
    tmp_dir = Path(tempfile.mkdtemp(prefix=".import_tmp_", dir=data_dir))
    try:
        staged: list[tuple[Path, Path]] = []
        for rel, payload in _outputs(bundle).items():
            staged_path = tmp_dir / rel.replace("/", "__")
            staged_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            staged.append((staged_path, data_dir / rel))
        for staged_path, final_path in staged:
            final_path.parent.mkdir(parents=True, exist_ok=True)
            os.replace(staged_path, final_path)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _source_hashes(source_dir: Path) -> dict[str, str]:
    return {
        name: "sha256:" + hashlib.sha256((source_dir / name).read_bytes()).hexdigest()
        for name in SOURCE_FILES
        if (source_dir / name).is_file()
    }


def _log_issues(issues: list[ImportIssue]) -> None:
    for issue in issues:
        logger.error(
            json.dumps({"event": "business_tools_import_failed", **asdict(issue)}, ensure_ascii=False)
        )


def run(command: str, source_dir: Path, data_dir: Path) -> int:
    started = time.perf_counter()
    try:
        bundle = build_seed(source_dir)
    except ImportValidationError as exc:
        _log_issues(exc.issues)
        return 1

    if command == "export":
        write_seed(bundle, data_dir)

    # Log には件数・所要時間・出力先・Source Hash だけを記録する
    logger.info(
        json.dumps(
            {
                "event": f"business_tools_{command}_succeeded",
                "documents": len(bundle.documents),
                "tickets": len(bundle.tickets),
                "output_dir": str(data_dir) if command == "export" else None,
                "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                "source_hash": _source_hashes(source_dir),
            },
            ensure_ascii=False,
        )
    )
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stderr)
    parser = argparse.ArgumentParser(description="業務ツール4ファイルをSeed JSONへ変換する")
    parser.add_argument("command", choices=["validate", "export"])
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE_DIR)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    return run(args.command, args.source_dir, args.data_dir)


if __name__ == "__main__":
    raise SystemExit(main())
