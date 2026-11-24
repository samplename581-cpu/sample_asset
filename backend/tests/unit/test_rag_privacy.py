"""個人情報がQuery・Prompt・Log・Citationへ含まれないことの検証。"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

import numpy as np
import pytest
from helpdesk.adapters.embedding_mock import MockEmbeddingAdapter
from helpdesk.adapters.vector_numpy import NumpyVectorStore
from helpdesk.config import Settings
from helpdesk.domain.models import Ticket
from helpdesk.ports.llm import ChatMessage, LLMResult
from helpdesk.ports.vector_store import ChunkRecord
from helpdesk.services.rag_service import RagService, build_ticket_facts, build_ticket_query

NAME = "秘密 太郎"
EMAIL = "secret.taro@example.com"
ORDER = "MK-99999"


def _ticket() -> Ticket:
    return Ticket(
        ticket_id="Q1020-99",
        title="t",
        description="配送予定日を10/25に変更したい",
        created_at=datetime.now(UTC),
        customer_name=NAME,
        customer_email=EMAIL,
        order_number=ORDER,
        product_name="3人掛けソファ「モリ」",
        inquiry_type="配送について",
        notes="備考に個人情報っぽい内容",
        status="未対応",
        has_attachment=True,
    )


def test_build_ticket_query_allows_only_whitelisted_fields() -> None:
    q = build_ticket_query(_ticket())
    assert "配送について" in q
    assert "3人掛けソファ「モリ」" in q
    assert "配送予定日を10/25に変更したい" in q
    for secret in (NAME, EMAIL, ORDER, "備考に個人情報", "Q1020-99"):
        assert secret not in q


def test_build_ticket_query_without_optional_fields() -> None:
    t = _ticket().model_copy(update={"inquiry_type": None, "product_name": None})
    assert build_ticket_query(t) == "問い合わせ内容: 配送予定日を10/25に変更したい"


class _CapturingLLM:
    provider = "fake"
    model = "fake"

    def __init__(self, text: str) -> None:
        self.text = text
        self.messages: list[ChatMessage] = []

    async def generate(self, messages: list[ChatMessage]) -> LLMResult:
        self.messages = messages
        return LLMResult(text=self.text, model="fake", provider="fake", input_tokens=None, output_tokens=None)


class _FixedEmbedding(MockEmbeddingAdapter):
    """全チャンクとQueryを同一方向にして、検索結果が必ず全件返るようにする。"""

    def encode_passages(self, texts: list[str]) -> np.ndarray:
        return np.tile(self.encode_query("q"), (len(texts), 1))

    def encode_query(self, text: str) -> np.ndarray:
        v = np.zeros(self.dimension, dtype=np.float32)
        v[0] = 1.0
        return v


def _rag() -> RagService:
    emb = _FixedEmbedding()
    texts = ["faq text", "category text", "priority text"]
    chunks = [
        ChunkRecord("c1", "faq:FAQ-04", texts[0], "配送日を変更したい", "faq.xlsx#1", "faq", "配送関連", 0, faq_id="FAQ-04"),
        ChunkRecord("c2", "classification:category:01", texts[1], "分類基準（カテゴリ）: 配送関連", "cls.xlsx#1", "classification_rule", "配送関連", 0),
        ChunkRecord("c3", "classification:priority:01", texts[2], "分類基準（緊急度）: 高", "cls.xlsx#2", "priority_rule", None, 0),
    ]
    return RagService(embedding=emb, store=NumpyVectorStore(chunks=chunks, vectors=emb.encode_passages(texts)))


def _settings() -> Settings:
    return Settings(LLM_PROVIDER="mock", EMBEDDING_PROVIDER="mock", VECTOR_MIN_SCORE=-1.0)


@pytest.mark.asyncio
async def test_prompt_and_logs_contain_no_personal_data(caplog: pytest.LogCaptureFixture) -> None:
    llm = _CapturingLLM('{"draft_answer": "ok", "citation_ids": ["S1"]}')
    query = build_ticket_query(_ticket())
    with caplog.at_level(logging.DEBUG):
        res = await _rag().draft_answer(llm, query, 3, "rid", _settings())  # type: ignore[arg-type]

    prompt = "\n".join(m.content for m in llm.messages)
    for secret in (NAME, EMAIL, ORDER, "備考に個人情報"):
        assert secret not in prompt
        assert secret not in caplog.text
        assert secret not in res.model_dump_json()


@pytest.mark.asyncio
async def test_ticket_facts_reach_prompt_without_values() -> None:
    t = _ticket()
    facts = build_ticket_facts(t)
    assert ORDER not in facts
    assert "注文番号: 登録済み" in facts and "写真の添付: あり" in facts
    assert "未登録" in build_ticket_facts(t.model_copy(update={"order_number": None}))

    llm = _CapturingLLM('{"draft_answer": "ok", "citation_ids": ["S1"]}')
    await _rag().draft_answer(  # type: ignore[arg-type]
        llm, build_ticket_query(t), 3, "rid", _settings(), ticket_facts=facts
    )
    prompt = llm.messages[-1].content
    assert "<ticket_facts>" in prompt and ORDER not in prompt


@pytest.mark.asyncio
async def test_internal_notes_are_stripped_from_draft() -> None:
    text = (
        '{"draft_answer": "ご注文どおりの色でございます（S1）。\\n\\n※[S1]を参照しました。\\n'
        'よろしくお願いいたします[S2、S3]。", "citation_ids": ["S1"]}'
    )
    res = await _rag().draft_answer(_CapturingLLM(text), "色が違う", 3, "rid", _settings())  # type: ignore[arg-type]
    assert res.draft_answer == "ご注文どおりの色でございます。\n\nよろしくお願いいたします。"
    assert [c.citation_id for c in res.citations] == ["S1"]  # 参照元の表示は残す


@pytest.mark.asyncio
async def test_order_number_requests_removed_when_registered() -> None:
    text = (
        '{"draft_answer": "色について確認いたします。注文番号をお知らせいただけますでしょうか。'
        'また、商品の写真をお送りください。", "missing_information": ["注文番号", "商品の写真"]}'
    )
    res = await _rag().draft_answer(  # type: ignore[arg-type]
        _CapturingLLM(text), "色が違う", 3, "rid", _settings(), order_registered=True
    )
    assert res.draft_answer == "色について確認いたします。また、商品の写真をお送りください。"
    assert res.missing_information == ["商品の写真"]

    res = await _rag().draft_answer(_CapturingLLM(text), "色が違う", 3, "rid", _settings())  # type: ignore[arg-type]
    assert "注文番号をお知らせ" in res.draft_answer  # 未登録なら聞いてよい


@pytest.mark.asyncio
async def test_suggestion_limited_to_master_choices() -> None:
    text = (
        '{"draft_answer": "ok", "classification_suggestion": {"category": "商品の不具合・不良", '
        '"priority": "高", "assigned_team": "カスタマーサポート"}}'
    )
    allowed = {"category": ["商品不良・破損"], "priority": ["高", "中", "低"], "assigned_team": ["窓口担当"]}
    llm = _CapturingLLM(text)
    res = await _rag().draft_answer(  # type: ignore[arg-type]
        llm, "脚が割れた", 3, "rid", _settings(), allowed_values=allowed
    )
    assert "- category: 商品不良・破損" in llm.messages[-1].content
    assert res.classification_suggestion is not None
    assert res.classification_suggestion.category is None
    assert res.classification_suggestion.priority == "高"
    assert res.classification_suggestion.assigned_team is None


@pytest.mark.asyncio
async def test_prompt_is_sectioned_with_citation_ids() -> None:
    llm = _CapturingLLM('{"draft_answer": "ok", "citation_ids": ["S1"]}')
    await _rag().draft_answer(llm, "配送日", 3, "rid", _settings())  # type: ignore[arg-type]
    prompt = llm.messages[-1].content
    assert "## FAQ回答" in prompt
    assert "## カテゴリ分類基準" in prompt
    assert "## 緊急度基準" in prompt
    assert prompt.index("## FAQ回答") < prompt.index("## カテゴリ分類基準") < prompt.index("## 緊急度基準")
    for cid in ("[S1]", "[S2]", "[S3]"):
        assert cid in prompt


@pytest.mark.asyncio
async def test_classification_suggestion_is_validated() -> None:
    text = (
        '{"draft_answer": "ok", "citation_ids": ["S1"], "classification_suggestion": '
        '{"category": "配送関連", "priority": "高", "handling_type": "専門部署へ引き継ぎ", '
        '"assigned_team": "配送センター担当", "faq_id": "FAQ-04"}}'
    )
    res = await _rag().draft_answer(_CapturingLLM(text), "配送日", 3, "rid", _settings())  # type: ignore[arg-type]
    assert res.needs_human_confirmation is True
    assert res.classification_suggestion is not None
    assert res.classification_suggestion.category == "配送関連"
    assert res.classification_suggestion.faq_id == "FAQ-04"


@pytest.mark.asyncio
async def test_suggestion_drops_faq_not_in_citations_and_bad_values() -> None:
    text = (
        '{"draft_answer": "ok", "classification_suggestion": '
        '{"category": 123, "faq_id": "FAQ-99", "priority": ""}}'
    )
    res = await _rag().draft_answer(_CapturingLLM(text), "配送日", 3, "rid", _settings())  # type: ignore[arg-type]
    assert res.classification_suggestion is None  # 全て無効なら提案なし


@pytest.mark.asyncio
async def test_missing_suggestion_is_none() -> None:
    res = await _rag().draft_answer(_CapturingLLM('{"draft_answer": "ok"}'), "配送日", 3, "rid", _settings())  # type: ignore[arg-type]
    assert res.classification_suggestion is None


