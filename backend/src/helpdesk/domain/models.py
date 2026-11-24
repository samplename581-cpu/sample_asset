from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

TICKET_ID_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9_-]{2,39}$")
DRIVE_FILE_ID_PATTERN = re.compile(r"[A-Za-z0-9_-]{10,100}")

_EMAIL_PATTERN = r"^[^\s@]+@[^\s@]+\.[^\s@]+$"
_ORDER_NUMBER_PATTERN = r"^[A-Z0-9-]{1,40}$"
_FAQ_ID_PATTERN = r"^FAQ-[0-9]{2,4}$"


def build_ticket_title(product_name: str | None, description: str) -> str:
    """商品名と問い合わせ内容の先頭部分から互換用 title を生成する。"""
    text = " ".join(description.split())
    # メール本文全体が入る場合に備え、最初の1文を使い、それでも長ければ「…」で切る
    first = text.split("。", 1)[0]
    head = first if len(first) <= 40 else first[:39] + "…"
    title = f"{product_name}: {head}" if product_name else head
    return title[:200]


class Ticket(BaseModel):
    ticket_id: str = Field(max_length=40)
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=4000)
    created_at: datetime
    # Deprecated: 業務ツール取込後の新規データでは使用しない（将来削除候補）
    requester_department: str | None = Field(
        None, max_length=100, description="Deprecated. 新規データでは使用しない"
    )
    # Sensitive: Embedding / Chroma / LLM Prompt / Log へ渡さない
    customer_name: str = Field(min_length=1, max_length=100)
    customer_email: str | None = Field(None, max_length=254, pattern=_EMAIL_PATTERN)
    order_number: str | None = Field(None, pattern=_ORDER_NUMBER_PATTERN)
    product_name: str | None = Field(None, max_length=200)
    inquiry_type: str | None = Field(None, max_length=40)
    category: str | None = Field(None, max_length=40)
    priority: str | None = Field(None, max_length=40)
    handling_type: str | None = Field(None, max_length=40)
    status: str = Field(max_length=40)
    assigned_team: str | None = Field(None, max_length=80)
    faq_id: str | None = Field(None, pattern=_FAQ_ID_PATTERN)
    notes: str | None = Field(None, max_length=4000)
    resolution: str | None = Field(None, max_length=10000)
    has_attachment: bool = False
    # 添付写真の Google ドライブのファイルID（画面表示のみ。LLM・検索には渡さない）
    attachment_file_ids: list[str] = Field(default_factory=list, max_length=10)
    version: int = Field(ge=1, default=1)

    @field_validator("attachment_file_ids")
    @classmethod
    def _check_file_ids(cls, v: list[str]) -> list[str]:
        if not all(DRIVE_FILE_ID_PATTERN.fullmatch(x) for x in v):
            raise ValueError("invalid attachment file id")
        return v

    @field_validator("ticket_id")
    @classmethod
    def validate_ticket_id(cls, v: str) -> str:
        if not TICKET_ID_PATTERN.match(v):
            raise ValueError(f"Invalid ticket_id pattern: {v}")
        return v


class TicketCreate(BaseModel):
    """問い合わせフォーム項目。受付番号・作成日時・ステータス・versionは Backend が生成する。"""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    customer_name: str = Field(min_length=1, max_length=100)
    customer_email: str = Field(max_length=254, pattern=_EMAIL_PATTERN)
    order_number: str | None = Field(None, pattern=_ORDER_NUMBER_PATTERN)
    product_name: str | None = Field(None, max_length=200)
    inquiry_type: str = Field(min_length=1, max_length=40)
    description: str = Field(min_length=1, max_length=4000)
    has_attachment: bool = False


class TicketUpdate(BaseModel):
    model_config = {"extra": "forbid"}

    version: int = Field(ge=1)
    category: str | None = Field(None, max_length=40)
    priority: str | None = Field(None, max_length=40)
    handling_type: str | None = Field(None, max_length=40)
    status: str | None = Field(None, max_length=40)
    assigned_team: str | None = Field(None, max_length=80)
    faq_id: str | None = Field(None, pattern=_FAQ_ID_PATTERN)
    resolution: str | None = Field(None, max_length=10000)

    @model_validator(mode="after")
    def require_at_least_one_field(self) -> TicketUpdate:
        updatable = {k: v for k, v in self.model_dump(exclude={"version"}).items() if v is not None}
        if not updatable:
            raise ValueError("version 以外に更新するフィールドが必要です")
        return self


class TicketPage(BaseModel):
    items: list[Ticket]
    next_cursor: str | None


class MasterResponse(BaseModel):
    name: str
    items: list[dict[str, Any]]


class SearchItem(BaseModel):
    chunk_id: str
    document_id: str
    title: str
    snippet: str = Field(max_length=1000)
    score: float = Field(ge=-1, le=1)
    source: str


class SearchResponse(BaseModel):
    query: str
    items: list[SearchItem]


class Citation(BaseModel):
    citation_id: str = Field(pattern=r"^S[1-9][0-9]*$")
    chunk_id: str
    document_id: str
    title: str
    source: str
    snippet: str = Field(max_length=1000)
    score: float = Field(ge=-1, le=1)


class DraftAnswerRequest(BaseModel):
    model_config = {"extra": "forbid"}

    ticket_id: str | None = Field(None, max_length=40)
    question: str | None = Field(None, min_length=1, max_length=4000)
    top_k: int = Field(default=5, ge=1, le=10)

    @model_validator(mode="after")
    def check_ticket_or_question(self) -> DraftAnswerRequest:
        has_ticket_id = self.ticket_id is not None
        has_question = self.question is not None
        if has_ticket_id == has_question:
            # 両方 None または両方指定はいずれも不正
            raise ValueError("ticket_id と question のどちらか一方だけを指定してください")
        return self


class DraftAnswerResponseMeta(BaseModel):
    provider: str
    model: str
    request_id: str


class ClassificationSuggestion(BaseModel):
    """LLMによる分類提案。確定値ではなく、必ず担当者が確認する。"""

    category: str | None = Field(None, max_length=40)
    priority: str | None = Field(None, max_length=40)
    handling_type: str | None = Field(None, max_length=40)
    assigned_team: str | None = Field(None, max_length=80)
    faq_id: str | None = Field(None, pattern=_FAQ_ID_PATTERN)
    priority_reason: str | None = Field(None, max_length=200)


class DraftAnswerResponse(BaseModel):
    draft_answer: str
    # 専門部署へ引き継ぐ場合の社内向け転送文。引き継がない場合は None
    forward_draft: str | None = None
    citations: list[Citation]
    classification_suggestion: ClassificationSuggestion | None = None
    needs_human_confirmation: bool = True
    missing_information: list[str]
    metadata: DraftAnswerResponseMeta
