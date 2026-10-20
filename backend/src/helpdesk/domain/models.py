from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

TICKET_ID_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9_-]{2,39}$")


class Ticket(BaseModel):
    ticket_id: str = Field(max_length=40)
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=10000)
    created_at: datetime
    requester_department: str = Field(max_length=100)
    category: str | None = Field(None, max_length=40)
    priority: str | None = Field(None, max_length=40)
    status: str = Field(max_length=40)
    assigned_team: str | None = Field(None, max_length=80)
    resolution: str | None = Field(None, max_length=10000)
    version: int = Field(ge=1, default=1)

    @field_validator("ticket_id")
    @classmethod
    def validate_ticket_id(cls, v: str) -> str:
        if not TICKET_ID_PATTERN.match(v):
            raise ValueError(f"Invalid ticket_id pattern: {v}")
        return v


class TicketCreate(BaseModel):
    model_config = {"extra": "forbid"}

    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=10000)
    requester_department: str = Field(min_length=1, max_length=100)


class TicketUpdate(BaseModel):
    model_config = {"extra": "forbid"}

    version: int = Field(ge=1)
    category: str | None = Field(None, max_length=40)
    priority: str | None = Field(None, max_length=40)
    status: str | None = Field(None, max_length=40)
    assigned_team: str | None = Field(None, max_length=80)
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


class DraftAnswerResponse(BaseModel):
    draft_answer: str
    citations: list[Citation]
    needs_human_confirmation: bool = True
    missing_information: list[str]
    metadata: DraftAnswerResponseMeta
