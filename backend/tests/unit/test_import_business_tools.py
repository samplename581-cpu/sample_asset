"""Unit tests for backend/scripts/import_business_tools.py."""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from datetime import date, datetime
from pathlib import Path

import openpyxl
import pytest

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "import_business_tools.py"
_SOURCE = Path(__file__).resolve().parents[3] / "assets" / "source" / "business_tools"

_spec = importlib.util.spec_from_file_location("import_business_tools", _SCRIPT)
assert _spec is not None and _spec.loader is not None
ibt = importlib.util.module_from_spec(_spec)
sys.modules["import_business_tools"] = ibt
_spec.loader.exec_module(ibt)


@pytest.fixture()
def source_dir(tmp_path: Path) -> Path:
    dst = tmp_path / "src"
    shutil.copytree(_SOURCE, dst)
    return dst


def _issues(source: Path) -> list[object]:
    with pytest.raises(ibt.ImportValidationError) as exc:
        ibt.build_seed(source)
    return exc.value.issues


def _edit(source: Path, file: str, sheet: str, fn) -> None:  # type: ignore[no-untyped-def]
    path = source / file
    wb = openpyxl.load_workbook(path)
    fn(wb[sheet])
    wb.save(path)


# ── 正規化 ──────────────────────────────────────────────────────────────────


def test_normalize_text() -> None:
    assert ibt.normalize_text("  a\u3000") == "a"
    assert ibt.normalize_text("\u3000") is None
    assert ibt.normalize_text("—") is None
    assert ibt.normalize_text(None) is None
    assert ibt.normalize_text("a\r\nb") == "a\nb"


def test_normalize_date_and_datetime() -> None:
    assert ibt.normalize_date(datetime(2026, 10, 1)) == "2026-10-01"
    assert ibt.normalize_date(date(2026, 10, 1)) == "2026-10-01"
    assert ibt.normalize_date("2026-10-01") == "2026-10-01"
    assert ibt.normalize_date(None) is None
    with pytest.raises(ValueError):
        ibt.normalize_date("not-a-date")
    dt = ibt.normalize_datetime_jst(datetime(2026, 10, 20, 9, 5))
    assert dt.isoformat() == "2026-10-20T09:05:00+09:00"


# ── 変換 ────────────────────────────────────────────────────────────────────


def test_build_seed_counts_and_ids() -> None:
    bundle = ibt.build_seed(_SOURCE)
    types = [d["document_type"] for d in bundle.documents]
    assert types.count("faq") == 15
    assert types.count("classification_rule") == 5
    assert types.count("priority_rule") == 3
    assert len(bundle.tickets) == 20
    ids = [d["document_id"] for d in bundle.documents]
    assert len(ids) == len(set(ids))
    assert "faq:FAQ-04" in ids
    assert "classification:category:01" in ids
    assert "classification:priority:03" in ids
    assert set(bundle.masters) == {
        "categories", "priorities", "support-teams", "statuses", "handling-types", "inquiry-types",
    }  # fmt: skip
    assert len(bundle.masters["inquiry-types"]) == 6


def test_faq_document_keeps_source_and_policy() -> None:
    doc = next(d for d in ibt.build_seed(_SOURCE).documents if d["document_id"] == "faq:FAQ-04")
    assert doc["source"] == "FAQ回答集.xlsx#FAQ回答集!8"
    assert doc["updated_at"] == "2026-10-01"
    assert doc["faq_id"] == "FAQ-04"
    assert doc["completion_policy"].startswith("いいえ")
    assert "窓口対応:" in doc["body"]


def test_ticket_mapping_and_null_normalization() -> None:
    tickets = {t["ticket_id"]: t for t in ibt.build_seed(_SOURCE).tickets}
    t1 = tickets["Q1020-01"]
    assert t1["created_at"] == "2026-10-20T09:05:00+09:00"
    assert t1["faq_id"] == "FAQ-04"
    assert t1["order_number"] == "MK-24581"
    t4 = tickets["Q1020-04"]
    assert t4["order_number"] is None  # "—" は null
    assert t4["product_name"] is None
    t15 = tickets["Q1020-15"]
    assert t15["category"] is None and t15["priority"] is None and t15["assigned_team"] is None
    assert t15["status"] == "未対応"


def test_student_tickets_hide_all_answer_fields() -> None:
    bundle = ibt.build_seed(_SOURCE)
    assert len(bundle.tickets_student) == 20
    for t in bundle.tickets_student:
        for f in ("category", "priority", "handling_type", "assigned_team", "faq_id", "notes"):
            assert t[f] is None, f
    gold = {g["ticket_id"]: g for g in bundle.ticket_gold}
    assert gold["Q1020-01"]["category"] == "配送関連"
    assert gold["Q1020-15"]["category"] is None  # 未判定6件はgoldも未判定
    assert sum(1 for g in gold.values() if g["category"] is None) == 6


def test_documents_contain_no_personal_data() -> None:
    bundle = ibt.build_seed(_SOURCE)
    blob = json.dumps(bundle.documents, ensure_ascii=False)
    for t in bundle.tickets:
        assert t["customer_name"] not in blob
        if t["order_number"]:
            assert t["order_number"] not in blob


# ── Validation ──────────────────────────────────────────────────────────────


def test_missing_file_reports_file_only(tmp_path: Path) -> None:
    issues = _issues(tmp_path)
    assert {i.error_code for i in issues} == {"FILE_NOT_FOUND"}


def test_missing_sheet(source_dir: Path) -> None:
    def rename(ws):  # type: ignore[no-untyped-def]
        ws.title = "別名"

    _edit(source_dir, "faq_answers.xlsx", "FAQ回答集", rename)
    issues = _issues(source_dir)
    assert any(i.error_code == "SHEET_NOT_FOUND" and i.file == "faq_answers.xlsx" for i in issues)


def test_missing_column_reports_header_not_found(source_dir: Path) -> None:
    _edit(source_dir, "faq_answers.xlsx", "FAQ回答集", lambda ws: ws.cell(4, 3).__setattr__("value", "x"))
    issues = _issues(source_dir)
    assert any(i.error_code == "HEADER_NOT_FOUND" for i in issues)


def test_header_row_shift_is_tolerated(source_dir: Path) -> None:
    _edit(source_dir, "faq_answers.xlsx", "FAQ回答集", lambda ws: ws.insert_rows(3, amount=2))
    bundle = ibt.build_seed(source_dir)
    faq = next(d for d in bundle.documents if d["document_id"] == "faq:FAQ-04")
    assert faq["source"].endswith("!10")  # 行番号は実際の位置を指す


def test_unknown_category_in_faq_has_location(source_dir: Path) -> None:
    _edit(source_dir, "faq_answers.xlsx", "FAQ回答集", lambda ws: ws.cell(8, 2).__setattr__("value", "未知"))
    issues = _issues(source_dir)
    hit = [i for i in issues if i.error_code == "UNKNOWN_CATEGORY"]
    assert hit and (hit[0].sheet, hit[0].row, hit[0].column) == ("FAQ回答集", 8, "カテゴリ")


def test_duplicate_id_rejected(source_dir: Path) -> None:
    _edit(source_dir, "faq_answers.xlsx", "FAQ回答集", lambda ws: ws.cell(6, 1).__setattr__("value", "FAQ-01"))
    assert any(i.error_code == "DUPLICATE_ID" and i.row == 6 for i in _issues(source_dir))


def test_unknown_faq_reference_rejected(source_dir: Path) -> None:
    _edit(source_dir, "inquiry_management.xlsx", "問い合わせ一覧", lambda ws: ws.cell(5, 12).__setattr__("value", "FAQ-99"))
    assert any(i.error_code == "UNKNOWN_FAQ_REFERENCE" and i.row == 5 for i in _issues(source_dir))


@pytest.mark.parametrize(
    ("col", "value", "code"),
    [
        (7, "未知カテゴリ", "UNKNOWN_CATEGORY"),
        (8, "最高", "UNKNOWN_PRIORITY"),
        (9, "未知区分", "UNKNOWN_HANDLING_TYPE"),
        (10, "未知担当", "UNKNOWN_TEAM"),
        (11, "保留", "UNKNOWN_STATUS"),
        (2, "not-a-date", "INVALID_DATE"),
        (4, "bad number!", "INVALID_VALUE"),
    ],
)
def test_ticket_validation_codes(source_dir: Path, col: int, value: str, code: str) -> None:
    _edit(source_dir, "inquiry_management.xlsx", "問い合わせ一覧", lambda ws: ws.cell(5, col).__setattr__("value", value))
    assert code in {i.error_code for i in _issues(source_dir)}


def test_issue_never_contains_cell_values(source_dir: Path) -> None:
    leaked_value = "秘密の氏名XYZ"
    _edit(source_dir, "inquiry_management.xlsx", "問い合わせ一覧", lambda ws: (ws.cell(5, 3).__setattr__("value", leaked_value), ws.cell(5, 7).__setattr__("value", leaked_value)))
    issues = _issues(source_dir)
    assert leaked_value not in json.dumps([i.__dict__ for i in issues], ensure_ascii=False)


def test_unknown_inquiry_type_in_form(source_dir: Path) -> None:
    html = source_dir / "inquiry_form.html"
    html.write_text(html.read_text(encoding="utf-8").replace('value="その他"', 'value="未知の種類"'), encoding="utf-8")
    assert any(i.error_code == "UNKNOWN_INQUIRY_TYPE" for i in _issues(source_dir))


def test_macro_workbook_rejected(source_dir: Path) -> None:
    import zipfile

    path = source_dir / "faq_answers.xlsx"
    with zipfile.ZipFile(path, "a") as zf:
        zf.writestr("xl/vbaProject.bin", b"x")
    assert any(i.error_code == "UNSAFE_CONTENT" for i in _issues(source_dir))


# ── Export ──────────────────────────────────────────────────────────────────


def test_validate_does_not_write(tmp_path: Path) -> None:
    assert ibt.run("validate", _SOURCE, tmp_path / "out") == 0
    assert not (tmp_path / "out").exists()


def test_export_writes_all_files_and_leaves_no_temp(tmp_path: Path) -> None:
    out = tmp_path / "data"
    assert ibt.run("export", _SOURCE, out) == 0
    for rel in (
        "seed/documents.json", "seed/masters.json", "seed/tickets.json",
        "seed/tickets_student.json", "evaluation/ticket_gold.json",
    ):  # fmt: skip
        assert json.loads((out / rel).read_text(encoding="utf-8")) is not None
    assert [p.name for p in out.iterdir() if p.name.startswith(".")] == []


def test_failed_export_keeps_existing_seed(source_dir: Path, tmp_path: Path) -> None:
    out = tmp_path / "data"
    (out / "seed").mkdir(parents=True)
    existing = out / "seed" / "documents.json"
    existing.write_text('["keep"]', encoding="utf-8")
    _edit(source_dir, "faq_answers.xlsx", "FAQ回答集", lambda ws: ws.cell(8, 2).__setattr__("value", "未知"))
    assert ibt.run("export", source_dir, out) == 1
    assert existing.read_text(encoding="utf-8") == '["keep"]'
