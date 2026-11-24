from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from helpdesk.api.masters import read_master
from helpdesk.config import Settings, get_settings
from helpdesk.domain.errors import HelpdeskError
from helpdesk.domain.models import (
    DraftAnswerRequest,
    DraftAnswerResponse,
    SearchResponse,
)
from helpdesk.ports.llm import ChatMessage, LLMPort
from helpdesk.services.rag_service import RagService, build_ticket_facts, build_ticket_query
from helpdesk.services.ticket_service import TicketService

router = APIRouter(tags=["rag"])


class SearchRequest(BaseModel):
    model_config = {"extra": "forbid"}

    query: str = Field(min_length=1, max_length=4000)
    top_k: int = Field(default=5, ge=1, le=20)
    document_types: list[str] | None = Field(None, max_length=10)


def get_rag_service(request: Request) -> RagService:
    rag_service: RagService | None = getattr(request.app.state, "rag_service", None)
    if rag_service is None:
        raise _ServiceUnavailable()
    return rag_service


class _ServiceUnavailable(Exception):
    pass


def get_llm(request: Request) -> LLMPort:
    llm: LLMPort | None = getattr(request.app.state, "llm", None)
    if llm is None:
        raise _ServiceUnavailable()
    return llm


def get_ticket_service(request: Request) -> TicketService:
    repo = request.app.state.ticket_repository
    return TicketService(repo)


class GenerateRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=4000)


class GenerateResponse(BaseModel):
    text: str
    provider: str
    model: str


@router.post("/search", response_model=SearchResponse)
async def search_knowledge(
    request: SearchRequest,
    rag: RagService = Depends(get_rag_service),
) -> SearchResponse:
    return rag.search(
        query=request.query,
        top_k=request.top_k,
        document_types=request.document_types,
    )


@router.post("/answers/draft", response_model=DraftAnswerResponse)
async def create_draft_answer(
    request: DraftAnswerRequest,
    req: Request,
    rag: RagService = Depends(get_rag_service),
    llm: LLMPort = Depends(get_llm),
    ticket_service: TicketService = Depends(get_ticket_service),
    settings: Settings = Depends(get_settings),
) -> DraftAnswerResponse:
    facts: str | None = None
    order_registered = False
    if request.ticket_id:
        ticket = ticket_service.get_ticket(request.ticket_id)
        query = build_ticket_query(ticket)
        facts = build_ticket_facts(ticket)
        order_registered = ticket.order_number is not None
    else:
        query = request.question or ""

    request_id = getattr(req.state, "request_id", "")
    return await rag.draft_answer(
        llm=llm,
        query=query,
        top_k=request.top_k,
        request_id=request_id,
        settings=settings,
        ticket_facts=facts,
        order_registered=order_registered,
        allowed_values=_suggestion_choices(settings),
    )


# 分類提案の項目 -> マスタ名
_SUGGESTION_MASTERS = {
    "category": "categories",
    "priority": "priorities",
    "handling_type": "handling-types",
    "assigned_team": "support-teams",
}


def _suggestion_choices(settings: Settings) -> dict[str, list[str]] | None:
    """マスタから分類提案の選択肢を作る。マスタが読めなければ None（選択肢の制約なし）。"""
    try:
        return {
            key: [
                str(v) for item in read_master(settings, master)
                for k, v in item.items() if k.endswith("_name")
            ]
            for key, master in _SUGGESTION_MASTERS.items()
        }
    except HelpdeskError:
        return None


@router.post("/llm/generate", response_model=GenerateResponse)
async def generate_once(
    request: GenerateRequest,
    llm: LLMPort = Depends(get_llm),
) -> GenerateResponse:
    result = await llm.generate(
        [
            ChatMessage(
                role="system",
                content="あなたはヘルプデスク担当者の下書き作成を支援します。",
            ),
            ChatMessage(role="user", content=request.prompt),
        ]
    )
    return GenerateResponse(
        text=result.text,
        provider=result.provider,
        model=result.model,
    )
