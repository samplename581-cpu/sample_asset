"""Unit tests for domain models."""

from __future__ import annotations

from datetime import UTC

import pytest
from helpdesk.domain.models import (
    DraftAnswerRequest,
    SearchItem,
    Ticket,
    TicketCreate,
    TicketUpdate,
    build_ticket_title,
)
from pydantic import ValidationError


class TestTicket:
    """Tests for Ticket model validation."""

    def test_valid_ticket(self) -> None:
        from datetime import datetime

        t = Ticket(
            ticket_id="TKT-00000001",
            title="テストタイトル",
            description="テスト説明文です。",
            created_at=datetime.now(UTC),
            customer_name="テスト 太郎",
            status="未対応",
        )
        assert t.ticket_id == "TKT-00000001"

    def test_ticket_id_too_short(self) -> None:
        from datetime import datetime

        with pytest.raises(ValidationError):
            Ticket(
                ticket_id="AB",  # 3文字未満
                title="テスト",
                description="説明",
                created_at=datetime.now(UTC),
                customer_name="テスト 太郎",
                status="未対応",
            )

    def test_title_empty(self) -> None:
        from datetime import datetime

        with pytest.raises(ValidationError):
            Ticket(
                ticket_id="TKT-00000001",
                title="",  # min_length=1
                description="説明",
                created_at=datetime.now(UTC),
                customer_name="テスト 太郎",
                status="未対応",
            )

    def test_title_too_long(self) -> None:
        from datetime import datetime

        with pytest.raises(ValidationError):
            Ticket(
                ticket_id="TKT-00000001",
                title="x" * 201,  # max_length=200
                description="説明",
                created_at=datetime.now(UTC),
                customer_name="テスト 太郎",
                status="未対応",
            )

    def test_description_too_long(self) -> None:
        from datetime import datetime

        with pytest.raises(ValidationError):
            Ticket(
                ticket_id="TKT-00000001",
                title="テスト",
                description="x" * 4001,  # max_length=4000
                created_at=datetime.now(UTC),
                customer_name="テスト 太郎",
                status="未対応",
            )


class TestTicketBusinessFields:
    """業務ツール取込で追加した項目のValidation。"""

    def _base(self, **overrides: object) -> dict[str, object]:
        from datetime import datetime

        base: dict[str, object] = {
            "ticket_id": "Q1020-01",
            "title": "t",
            "description": "説明",
            "created_at": datetime.now(UTC),
            "customer_name": "佐藤 美咲",
            "status": "未対応",
        }
        base.update(overrides)
        return base

    def test_valid_business_ticket(self) -> None:
        t = Ticket.model_validate(
            self._base(order_number="MK-24581", faq_id="FAQ-04", customer_email="a@example.com")
        )
        assert t.has_attachment is False
        assert t.requester_department is None

    @pytest.mark.parametrize("value", ["mk-24581", "MK 24581", "MK_1", "A" * 41])
    def test_invalid_order_number(self, value: str) -> None:
        with pytest.raises(ValidationError):
            Ticket.model_validate(self._base(order_number=value))

    @pytest.mark.parametrize("value", ["FAQ-1", "faq-01", "FAQ-12345", "XYZ-01"])
    def test_invalid_faq_id(self, value: str) -> None:
        with pytest.raises(ValidationError):
            Ticket.model_validate(self._base(faq_id=value))

    def test_invalid_email(self) -> None:
        with pytest.raises(ValidationError):
            Ticket.model_validate(self._base(customer_email="not-an-email"))

    def test_customer_name_too_long(self) -> None:
        with pytest.raises(ValidationError):
            Ticket.model_validate(self._base(customer_name="x" * 101))


class TestTicketCreate:
    def _payload(self, **overrides: object) -> dict[str, object]:
        payload: dict[str, object] = {
            "customer_name": "佐藤 美咲",
            "customer_email": "misaki@example.com",
            "inquiry_type": "配送について",
            "description": "配送日を変更したい",
        }
        payload.update(overrides)
        return payload

    def test_valid(self) -> None:
        c = TicketCreate.model_validate(self._payload(order_number="MK-1"))
        assert c.order_number == "MK-1"

    @pytest.mark.parametrize("field", ["ticket_id", "status", "version", "created_at", "title"])
    def test_backend_generated_fields_are_rejected(self, field: str) -> None:
        with pytest.raises(ValidationError):
            TicketCreate.model_validate(self._payload(**{field: "x"}))

    def test_extra_field_rejected(self) -> None:
        with pytest.raises(ValidationError):
            TicketCreate.model_validate(self._payload(requester_department="営業部"))

    @pytest.mark.parametrize("field", ["customer_name", "customer_email", "inquiry_type", "description"])
    def test_required_fields(self, field: str) -> None:
        payload = self._payload()
        del payload[field]
        with pytest.raises(ValidationError):
            TicketCreate.model_validate(payload)

    def test_description_max_length(self) -> None:
        with pytest.raises(ValidationError):
            TicketCreate.model_validate(self._payload(description="x" * 4001))


def test_build_ticket_title() -> None:
    assert build_ticket_title("ソファ", "配送日を変更したい") == "ソファ: 配送日を変更したい"
    assert build_ticket_title(None, "a\n b") == "a b"
    assert len(build_ticket_title("p" * 200, "x" * 100)) <= 200


class TestTicketUpdate:
    """Tests for TicketUpdate model validation."""

    def test_valid_ticket_update(self) -> None:
        u = TicketUpdate(version=1, status="対応中")
        assert u.version == 1

    def test_version_required(self) -> None:
        with pytest.raises(ValidationError):
            TicketUpdate(status="対応中")  # version なし

    def test_version_must_be_ge_1(self) -> None:
        with pytest.raises(ValidationError):
            TicketUpdate(version=0)  # ge=1 に違反


class TestDraftAnswerRequest:
    """Tests for DraftAnswerRequest model validation."""

    def test_both_none_raises(self) -> None:
        with pytest.raises(ValidationError):
            DraftAnswerRequest(ticket_id=None, question=None)

    def test_ticket_id_only_valid(self) -> None:
        r = DraftAnswerRequest(ticket_id="TKT-00000001")
        assert r.ticket_id == "TKT-00000001"
        assert r.question is None

    def test_question_only_valid(self) -> None:
        r = DraftAnswerRequest(question="VPNに接続できません")
        assert r.question == "VPNに接続できません"
        assert r.ticket_id is None


class TestSearchItem:
    """Tests for SearchItem model validation."""

    def test_score_within_range(self) -> None:
        item = SearchItem(
            chunk_id="c1",
            document_id="d1",
            title="タイトル",
            snippet="スニペット",
            score=0.85,
            source="manual",
        )
        assert item.score == 0.85

    def test_score_minus_1(self) -> None:
        item = SearchItem(
            chunk_id="c1",
            document_id="d1",
            title="タイトル",
            snippet="スニペット",
            score=-1.0,
            source="manual",
        )
        assert item.score == -1.0

    def test_score_out_of_range_high(self) -> None:
        with pytest.raises(ValidationError):
            SearchItem(
                chunk_id="c1",
                document_id="d1",
                title="タイトル",
                snippet="スニペット",
                score=1.1,  # ge=-1, le=1 に違反
                source="manual",
            )

    def test_score_out_of_range_low(self) -> None:
        with pytest.raises(ValidationError):
            SearchItem(
                chunk_id="c1",
                document_id="d1",
                title="タイトル",
                snippet="スニペット",
                score=-1.1,  # ge=-1 に違反
                source="manual",
            )
