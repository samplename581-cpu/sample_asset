"""GET /health/providers が、実際に動作中の provider 名を返すことの確認。

watsonx.ai には接続しない。アダプタを app.state に差し替えて、返却値だけを検証する。
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from helpdesk.adapters.llm_mock import MockLLMAdapter
from helpdesk.adapters.llm_openai_compatible import OpenAICompatibleLLMAdapter
from helpdesk.adapters.llm_watsonx import WatsonxLLMAdapter
from helpdesk.main import app
from helpdesk.services.rag_service import RagService

URL = "/api/v1/health/providers"


class _FakeHttpClient:
    async def aclose(self) -> None:
        return None


class _FakeEmbedding:
    def __init__(self, provider: str, model: str) -> None:
        self.provider_name = provider
        self.model_name = model
        self.dimension = 64


@pytest.fixture()
def client() -> TestClient:
    with TestClient(app) as c:
        yield c


def _rag(provider: str, model: str, vector_store: str = "test-vector") -> RagService:
    store = SimpleNamespace(provider_name=vector_store)
    return RagService(embedding=_FakeEmbedding(provider, model), store=store)  # type: ignore[arg-type]


def test_mock_providers(client: TestClient) -> None:
    app.state.llm = MockLLMAdapter(model="mock-helpdesk-v1")
    app.state.rag_service = _rag("mock", "mock-embedding-v1")

    body = client.get(URL).json()

    assert body["llm"] == {"provider": "mock", "model": "mock-helpdesk-v1"}
    assert body["embedding"] == {"provider": "mock", "model": "mock-embedding-v1"}
    assert body["vector_store"] == {"provider": "test-vector", "model": None}


def test_watsonx_providers(client: TestClient) -> None:
    app.state.llm = WatsonxLLMAdapter(model_inference=object(), model_id="ibm/granite-test")
    app.state.rag_service = _rag("watsonx", "ibm/slate-test")

    body = client.get(URL).json()

    assert body["llm"] == {"provider": "watsonx", "model": "ibm/granite-test"}
    assert body["embedding"] == {"provider": "watsonx", "model": "ibm/slate-test"}
    assert body["vector_store"] == {"provider": "test-vector", "model": None}


def test_openai_compatible_llm_reports_its_own_name(client: TestClient) -> None:
    llm = OpenAICompatibleLLMAdapter(
        client=_FakeHttpClient(), base_url="http://x/v1", model_id="local-model"
    )
    app.state.llm = llm
    app.state.rag_service = _rag("local", "local-embed")

    body = client.get(URL).json()

    assert body["llm"] == {"provider": "openai_compatible", "model": "local-model"}
    assert body["embedding"]["provider"] == "local"


def test_mixed_providers_are_reported_separately(client: TestClient) -> None:
    """LLM と Embedding の provider が異なる場合、それぞれを正しく返す。"""
    app.state.llm = WatsonxLLMAdapter(model_inference=object(), model_id="m")
    app.state.rag_service = _rag("mock", "mock-embedding-v1")

    body = client.get(URL).json()

    assert body["llm"]["provider"] == "watsonx"
    assert body["embedding"]["provider"] == "mock"


def test_unavailable_when_rag_service_missing(client: TestClient) -> None:
    app.state.llm = MockLLMAdapter()
    app.state.rag_service = None

    body = client.get(URL).json()

    assert body["embedding"] == {"provider": "unavailable", "model": None}
    assert body["vector_store"] == {"provider": "unavailable", "model": None}


def test_response_has_no_connection_secrets(client: TestClient) -> None:
    """URL・Project ID・API Key に当たる項目を返さない。"""
    app.state.llm = WatsonxLLMAdapter(model_inference=object(), model_id="m")
    app.state.rag_service = _rag("watsonx", "e")

    text = client.get(URL).text.lower()

    for word in ("api_key", "apikey", "project", "url", "http"):
        assert word not in text
