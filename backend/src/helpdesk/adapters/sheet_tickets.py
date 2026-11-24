"""メール転記スプシ（GAS の doGet が返す JSON）からチケットを取り込む。

スプシは読むだけで、アプリでの分類・ステータス変更は書き戻さない。
"""

from __future__ import annotations

import asyncio
import json
import logging
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from typing import Any

import pydantic

from helpdesk.domain.models import Ticket, build_ticket_title
from helpdesk.ports.ticket_repository import TicketRepository

logger = logging.getLogger("helpdesk.adapters.sheet_tickets")

_MAX_DESCRIPTION = 4000
_TIMEOUT_SECONDS = 15


def _text(row: dict[str, Any], key: str) -> str | None:
    value = row.get(key)
    text = "" if value is None else str(value).strip()
    return text or None


def row_to_ticket(row: dict[str, Any]) -> Ticket:
    """スプシ1行をTicketに変換する。不正な行は pydantic.ValidationError / ValueError を送出する。"""
    description = _text(row, "問い合わせ内容（要約）") or ""
    # shortcut: 4000字を超える本文は切り詰める。長文メールが多ければ要約を検討する
    description = description[:_MAX_DESCRIPTION]
    product_name = _text(row, "商品名")
    created_raw = _text(row, "受付日時")
    created_at = (
        datetime.fromisoformat(created_raw.replace("Z", "+00:00"))
        if created_raw
        else datetime.now(UTC)
    )
    return Ticket.model_validate(
        {
            "ticket_id": _text(row, "受付番号"),
            "title": build_ticket_title(product_name, description),
            "description": description,
            "created_at": created_at,
            "customer_name": _text(row, "お客様名"),
            "customer_email": _text(row, "メールアドレス"),
            "order_number": _text(row, "注文番号"),
            "product_name": product_name,
            "status": _text(row, "ステータス") or "未対応",
            "has_attachment": _text(row, "添付画像") is not None,
            "version": 1,
        }
    )


def rows_to_tickets(rows: list[Any]) -> tuple[list[Ticket], int]:
    """変換できた行と、飛ばした行数を返す。ログには行番号だけを出す（値は個人情報を含むため出さない）。"""
    tickets: list[Ticket] = []
    skipped = 0
    for idx, row in enumerate(rows, start=2):  # スプシの2行目からデータ
        if not isinstance(row, dict) or not _text(row, "受付番号"):
            continue  # 空行
        try:
            tickets.append(row_to_ticket(row))
        except (pydantic.ValidationError, ValueError) as exc:
            skipped += 1
            logger.warning("Skipped sheet row %d: error_type=%s", idx, exc.__class__.__name__)
    return tickets, skipped


def fetch_rows(url: str, token: str) -> list[Any]:
    """doGet を呼んで行の配列を返す。URL に合言葉が含まれるので、URL はログに出さない。"""
    full_url = f"{url}{'&' if '?' in url else '?'}{urllib.parse.urlencode({'token': token})}"
    # https 以外は Settings で拒否済み
    with urllib.request.urlopen(full_url, timeout=_TIMEOUT_SECONDS) as res:  # noqa: S310
        payload = json.loads(res.read().decode("utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("rows"), list):
        raise ValueError("Unexpected sheet response")
    rows: list[Any] = payload["rows"]
    return rows


async def run_sheet_sync(
    repository: TicketRepository, url: str, token: str, interval: int
) -> None:
    """interval 秒ごとにスプシを読み、まだ無い受付番号のチケットだけを追加し続ける。"""
    while True:
        try:
            rows = await asyncio.to_thread(fetch_rows, url, token)
            tickets, skipped = rows_to_tickets(rows)
            added = repository.add_new_tickets(tickets)
            if added or skipped:
                logger.info("Sheet sync: added=%d skipped=%d", added, skipped)
        except Exception as exc:
            logger.error("Sheet sync failed: error_type=%s", exc.__class__.__name__)
        await asyncio.sleep(interval)
