from __future__ import annotations

from helpdesk.adapters.llm_mock import MockLLMAdapter
from helpdesk.adapters.llm_openai_compatible import OpenAICompatibleLLMAdapter
from helpdesk.adapters.llm_watsonx import WatsonxLLMAdapter
from helpdesk.config import Settings
from helpdesk.domain.errors import ConfigurationError
from helpdesk.ports.llm import LLMPort


def create_llm(settings: Settings) -> LLMPort:
    match settings.LLM_PROVIDER:
        case "mock":
            return MockLLMAdapter(model=settings.LLM_MODEL_ID)
        case "watsonx":
            return WatsonxLLMAdapter.from_settings(settings)
        case "local" | "openai_compatible":
            return OpenAICompatibleLLMAdapter.from_settings(settings)
        case _:
            raise ConfigurationError(f"Unsupported LLM provider: {settings.LLM_PROVIDER}")


__all__ = [
    "MockLLMAdapter",
    "OpenAICompatibleLLMAdapter",
    "WatsonxLLMAdapter",
    "create_llm",
]
