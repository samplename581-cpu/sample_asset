"""Unit tests for domain models."""

from __future__ import annotations

from datetime import UTC

import pytest
from helpdesk.domain.models import (
    DraftAnswerRequest,
    SearchItem,
    Ticket,
    TicketUpdate,
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
            requester_department="開発部",
            status="新規",
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
                requester_department="開発部",
                status="新規",
            )

    def test_title_empty(self) -> None:
        from datetime import datetime

        with pytest.raises(ValidationError):
            Ticket(
                ticket_id="TKT-00000001",
                title="",  # min_length=1
                description="説明",
                created_at=datetime.now(UTC),
                requester_department="開発部",
                status="新規",
            )

    def test_title_too_long(self) -> None:
        from datetime import datetime

        with pytest.raises(ValidationError):
            Ticket(
                ticket_id="TKT-00000001",
                title="x" * 201,  # max_length=200
                description="説明",
                created_at=datetime.now(UTC),
                requester_department="開発部",
                status="新規",
            )

    def test_description_too_long(self) -> None:
        from datetime import datetime

        with pytest.raises(ValidationError):
            Ticket(
                ticket_id="TKT-00000001",
                title="テスト",
                description="x" * 10001,  # max_length=10000
                created_at=datetime.now(UTC),
                requester_department="開発部",
                status="新規",
            )


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
