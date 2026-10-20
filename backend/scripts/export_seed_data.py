import json
from datetime import datetime
from pathlib import Path
from typing import Any

import openpyxl


def format_iso8601_jst(val: Any) -> str:
    """Format datetime or string representation into ISO 8601 with +09:00 timezone."""
    if isinstance(val, datetime):
        # Treat as JST (+09:00)
        dt = val
    elif isinstance(val, str):
        # try parsing YYYY-MM-DD HH:MM or ISO
        val = val.strip()
        try:
            dt = datetime.strptime(val, "%Y-%m-%d %H:%M")
        except ValueError:
            dt = datetime.fromisoformat(val)
    else:
        dt = datetime.now()

    # If naive, assume +09:00
    if dt.tzinfo is None:
        return f"{dt.strftime('%Y-%m-%dT%H:%M:%S')}+09:00"
    return dt.isoformat()


def export_tickets(excel_path: Path, out_path: Path) -> list[dict[str, Any]]:
    wb = openpyxl.load_workbook(excel_path, data_only=True)
    tickets = []

    for sheet_name in ["tickets_observation", "tickets_dev"]:
        if sheet_name not in wb.sheetnames:
            continue
        ws = wb[sheet_name]
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            continue
        headers = [str(h).strip() if h is not None else "" for h in rows[0]]

        for r_idx, row in enumerate(rows[1:], start=2):
            if not any(row):
                continue
            row_dict = dict(zip(headers, row))
            ticket_id = str(row_dict.get("ticket_id") or "").strip()
            if not ticket_id:
                continue

            created_at_raw = row_dict.get("created_at")
            created_at_iso = format_iso8601_jst(created_at_raw)

            ticket = {
                "ticket_id": ticket_id,
                "title": str(row_dict.get("title") or "").strip(),
                "description": str(row_dict.get("description") or "").strip(),
                "created_at": created_at_iso,
                "requester_department": str(row_dict.get("requester_department") or "").strip(),
                "category": str(row_dict.get("category")).strip() if row_dict.get("category") else None,
                "priority": str(row_dict.get("priority")).strip() if row_dict.get("priority") else None,
                "status": str(row_dict.get("status") or "新規").strip(),
                "assigned_team": str(row_dict.get("assigned_team")).strip() if row_dict.get("assigned_team") else None,
                "resolution": str(row_dict.get("resolution")).strip() if row_dict.get("resolution") else None,
                "version": 1,
            }
            tickets.append(ticket)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(tickets, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Exported {len(tickets)} tickets to {out_path}")
    return tickets


# Fields removed from student-facing tickets to preserve classification labels
_STUDENT_HIDDEN_FIELDS = ("category", "priority", "assigned_team", "resolution")


def strip_labels(tickets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return a copy of tickets with answer-label fields removed (for student distribution)."""
    result = []
    for t in tickets:
        t_copy = dict(t)
        for field in _STUDENT_HIDDEN_FIELDS:
            t_copy.pop(field, None)
        result.append(t_copy)
    return result


def export_masters(excel_path: Path, out_path: Path) -> dict[str, Any]:
    wb = openpyxl.load_workbook(excel_path, data_only=True)
    masters: dict[str, Any] = {
        "categories": [],
        "priorities": [],
        "support-teams": [],
        "services": [],
    }

    sheet_mapping = {
        "category_master": "categories",
        "priority_master": "priorities",
        "support_team_master": "support-teams",
        "service_catalog": "services",
    }

    for sheet_name, master_key in sheet_mapping.items():
        if sheet_name not in wb.sheetnames:
            continue
        ws = wb[sheet_name]
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            continue
        headers = [str(h).strip() if h is not None else "" for h in rows[0]]

        items = []
        for row in rows[1:]:
            if not any(row):
                continue
            item = {}
            for h, v in zip(headers, row):
                if h:
                    item[h] = v if v is not None else ""
            items.append(item)
        masters[master_key] = items

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(masters, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Exported masters to {out_path}")
    return masters


def export_documents(excel_path: Path, out_path: Path) -> list[dict[str, Any]]:
    wb = openpyxl.load_workbook(excel_path, data_only=True)
    documents = []

    # 1. triage_rule
    if "triage_rule" in wb.sheetnames:
        ws = wb["triage_rule"]
        rows = list(ws.iter_rows(values_only=True))
        current_section = ""
        rule_idx = 1
        for r_idx, row in enumerate(rows, start=1):
            if not any(row):
                continue
            col1 = str(row[0]).strip() if row[0] is not None else ""
            col2 = str(row[1]).strip() if len(row) > 1 and row[1] is not None else ""

            if col1 and not col2:
                current_section = col1
            elif col1 and col2:
                doc_id = f"triage_rule:{rule_idx:02d}"
                title = f"{current_section} - {col1}" if current_section else col1
                body = col2
                documents.append({
                    "document_id": doc_id,
                    "title": title,
                    "body": body,
                    "document_type": "triage_rule",
                    "source": f"helpdesk_documents.xlsx#triage_rule!{r_idx}",
                    "category": None,
                    "updated_at": None,
                    "access_scope": "student",
                    "is_active": True,
                })
                rule_idx += 1

    # 2. routing_rule
    if "routing_rule" in wb.sheetnames:
        ws = wb["routing_rule"]
        rows = list(ws.iter_rows(values_only=True))
        if rows:
            headers = [str(h).strip() if h is not None else "" for h in rows[0]]
            for r_idx, row in enumerate(rows[1:], start=2):
                if not any(row):
                    continue
                row_dict = dict(zip(headers, row))
                cond = str(row_dict.get("条件キーワード・状況") or "").strip()
                primary = str(row_dict.get("優先ルーティング先") or "").strip()
                secondary = str(row_dict.get("副担当") or "").strip()
                notes = str(row_dict.get("補足・条件") or "").strip()

                body_lines = [f"優先ルーティング先: {primary}"]
                if secondary:
                    body_lines.append(f"副担当: {secondary}")
                if notes:
                    body_lines.append(f"補足・条件: {notes}")
                body = "\n".join(body_lines)

                doc_id = f"routing_rule:{r_idx - 1:02d}"
                documents.append({
                    "document_id": doc_id,
                    "title": f"ルーティング規則: {cond}",
                    "body": body,
                    "document_type": "routing_rule",
                    "source": f"helpdesk_documents.xlsx#routing_rule!{r_idx}",
                    "category": None,
                    "updated_at": None,
                    "access_scope": "student",
                    "is_active": True,
                })

    # 3. escalation_rule
    if "escalation_rule" in wb.sheetnames:
        ws = wb["escalation_rule"]
        rows = list(ws.iter_rows(values_only=True))
        if rows:
            headers = [str(h).strip() if h is not None else "" for h in rows[0]]
            for r_idx, row in enumerate(rows[1:], start=2):
                if not any(row):
                    continue
                row_dict = dict(zip(headers, row))
                cond_id = str(row_dict.get("条件ID") or f"ESC{r_idx-1:02d}").strip()
                cond_name = str(row_dict.get("エスカレーション条件") or "").strip()
                criteria = str(row_dict.get("判断基準・具体例") or "").strip()
                target = str(row_dict.get("エスカレーション先") or "").strip()
                action = str(row_dict.get("アクション") or "").strip()

                body = f"エスカレーション条件: {cond_name}\n判断基準: {criteria}\nエスカレーション先: {target}\nアクション: {action}"
                doc_id = f"escalation_rule:{cond_id}"
                documents.append({
                    "document_id": doc_id,
                    "title": f"エスカレーション基準: {cond_name}",
                    "body": body,
                    "document_type": "escalation_rule",
                    "source": f"helpdesk_documents.xlsx#escalation_rule!{r_idx}",
                    "category": None,
                    "updated_at": None,
                    "access_scope": "student",
                    "is_active": True,
                })

    # 4. FAQ
    if "FAQ" in wb.sheetnames:
        ws = wb["FAQ"]
        rows = list(ws.iter_rows(values_only=True))
        if rows:
            headers = [str(h).strip() if h is not None else "" for h in rows[0]]
            for r_idx, row in enumerate(rows[1:], start=2):
                if not any(row):
                    continue
                row_dict = dict(zip(headers, row))
                faq_id = str(row_dict.get("faq_id") or f"F{r_idx-1:02d}").strip()
                question = str(row_dict.get("question") or "").strip()
                answer = str(row_dict.get("answer") or "").strip()
                category = str(row_dict.get("category") or "").strip() or None

                doc_id = f"faq:{faq_id}"
                documents.append({
                    "document_id": doc_id,
                    "title": question,
                    "body": answer,
                    "document_type": "faq",
                    "source": f"helpdesk_documents.xlsx#FAQ!{r_idx}",
                    "category": category,
                    "updated_at": None,
                    "access_scope": "student",
                    "is_active": True,
                })

    # 5. troubleshooting_guide
    if "troubleshooting_guide" in wb.sheetnames:
        ws = wb["troubleshooting_guide"]
        rows = list(ws.iter_rows(values_only=True))
        if rows:
            headers = [str(h).strip() if h is not None else "" for h in rows[0]]
            for r_idx, row in enumerate(rows[1:], start=2):
                if not any(row):
                    continue
                row_dict = dict(zip(headers, row))
                doc_code = str(row_dict.get("doc_id") or f"DOC{r_idx-1:02d}").strip()
                doc_name = str(row_dict.get("document_name") or "").strip()
                service = str(row_dict.get("対象サービス") or "").strip()
                team = str(row_dict.get("主担当チーム") or "").strip()
                summary = str(row_dict.get("概要") or "").strip()
                updated_at_val = row_dict.get("最終更新日")
                updated_at_str = str(updated_at_val).strip() if updated_at_val else None

                body = f"対象サービス: {service}\n主担当チーム: {team}\n概要: {summary}"
                doc_id = f"guide:{doc_code}"
                documents.append({
                    "document_id": doc_id,
                    "title": f"トラブルシューティングガイド: {doc_name}",
                    "body": body,
                    "document_type": "troubleshooting_guide",
                    "source": f"helpdesk_documents.xlsx#troubleshooting_guide!{r_idx}",
                    "category": None,
                    "updated_at": updated_at_str,
                    "access_scope": "student",
                    "is_active": True,
                })

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(documents, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Exported {len(documents)} documents to {out_path}")
    return documents


def main() -> None:
    # Resolve relative to backend/scripts/
    script_dir = Path(__file__).resolve().parent
    base_dir = script_dir.parent.parent  # sample_asset directory

    # Keep source workbooks inside this repository so a standalone clone can
    # reproduce every generated JSON file without relying on a parent directory.
    source_dir = base_dir / "assets" / "source"

    seed_dir = base_dir / "data" / "seed"

    tickets_excel = source_dir / "helpdesk_tickets.xlsx"
    masters_excel = source_dir / "helpdesk_master.xlsx"
    docs_excel = source_dir / "helpdesk_documents.xlsx"

    missing = [
        str(path.relative_to(base_dir))
        for path in (tickets_excel, masters_excel, docs_excel)
        if not path.is_file()
    ]
    if missing:
        raise SystemExit("Missing source workbook(s): " + ", ".join(missing))

    seed_dir.mkdir(parents=True, exist_ok=True)

    # Export full tickets (with labels) – used internally and for evaluation
    all_tickets = export_tickets(tickets_excel, seed_dir / "tickets.json")

    # Export student-facing tickets (labels stripped) to data/seed/tickets_student.json
    student_tickets = strip_labels(all_tickets)
    student_path = seed_dir / "tickets_student.json"
    student_path.write_text(json.dumps(student_tickets, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Exported {len(student_tickets)} student tickets (labels stripped) to {student_path}")

    # Export evaluation gold labels to data/evaluation/ (not served by API)
    eval_dir = base_dir / "data" / "evaluation"
    eval_dir.mkdir(parents=True, exist_ok=True)
    gold = [
        {
            "ticket_id": t["ticket_id"],
            "category": t.get("category"),
            "priority": t.get("priority"),
            "assigned_team": t.get("assigned_team"),
        }
        for t in all_tickets
    ]
    gold_path = eval_dir / "ticket_gold.json"
    gold_path.write_text(json.dumps(gold, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Exported {len(gold)} gold labels to {gold_path} (DO NOT distribute to students)")

    export_masters(masters_excel, seed_dir / "masters.json")
    export_documents(docs_excel, seed_dir / "documents.json")
    print("Seed data export completed successfully.")


if __name__ == "__main__":
    main()
