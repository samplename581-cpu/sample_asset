"""Unit tests for Settings (config.py)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError


def test_watsonx_missing_api_key() -> None:
    """`LLM_PROVIDER=watsonx` のとき `WATSONX_API_KEY` が空なら ValidationError になること。"""
    with pytest.raises((ValidationError, Exception)) as exc_info:
        from helpdesk.config import Settings

        Settings(
            LLM_PROVIDER="watsonx",
            WATSONX_API_KEY=None,
            WATSONX_PROJECT_ID=None,
            WATSONX_MODEL_ID=None,
        )
    # pydantic ValidationError か helpdesk ConfigurationError のいずれか
    assert exc_info.value is not None


def test_mock_provider_without_watsonx() -> None:
    """`LLM_PROVIDER=mock` のとき watsonx 変数が空でも起動できること。"""
    from helpdesk.config import Settings

    settings = Settings(
        _env_file=None,
        LLM_PROVIDER="mock",
        WATSONX_API_KEY=None,
        WATSONX_PROJECT_ID=None,
        WATSONX_MODEL_ID=None,
    )
    assert settings.LLM_PROVIDER == "mock"


def test_llm_timeout_zero_fails() -> None:
    """`LLM_TIMEOUT_SECONDS` が 0 のとき失敗すること。"""
    with pytest.raises(ValidationError):
        from helpdesk.config import Settings

        Settings(LLM_TIMEOUT_SECONDS=0)


def test_llm_temperature_too_high_fails() -> None:
    """`LLM_TEMPERATURE` が 3.0 のとき失敗すること（le=2.0）。"""
    with pytest.raises(ValidationError):
        from helpdesk.config import Settings

        Settings(LLM_TEMPERATURE=3.0)


def test_watsonx_embedding_requires_model_id() -> None:
    """watsonx.ai Embedding選択時はEmbedding model IDを必須にすること。"""
    from helpdesk.config import Settings

    with pytest.raises(ValidationError, match="WATSONX_EMBEDDING_MODEL_ID"):
        Settings(
            EMBEDDING_PROVIDER="watsonx",
            WATSONX_API_KEY="dummy-key",
            WATSONX_PROJECT_ID="dummy-project",
            WATSONX_EMBEDDING_MODEL_ID=None,
        )


