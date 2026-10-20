from __future__ import annotations

import asyncio
import logging
import random
from typing import TYPE_CHECKING, Any

from helpdesk.domain.errors import ConfigurationError, ProviderError
from helpdesk.ports.llm import ChatMessage, LLMPort, LLMResult

if TYPE_CHECKING:
    from helpdesk.config import Settings

logger = logging.getLogger("helpdesk.adapters.llm_watsonx")


class WatsonxLLMAdapter(LLMPort):
    def __init__(self, model_inference: Any, model_id: str) -> None:
        self._model = model_inference
        self._model_id = model_id

    @classmethod
    def from_settings(cls, settings: Settings) -> WatsonxLLMAdapter:
        try:
            from ibm_watsonx_ai import Credentials
            from ibm_watsonx_ai.foundation_models import ModelInference
        except ImportError as e:
            raise ConfigurationError(
                "ibm_watsonx_ai is not installed. Please install it to use the watsonx LLM provider."
            ) from e

        if (
            not settings.WATSONX_URL
            or not settings.WATSONX_API_KEY
            or not settings.WATSONX_PROJECT_ID
            or not settings.WATSONX_MODEL_ID
        ):
            raise ConfigurationError("Watsonx credentials and model settings are incomplete.")

        credentials = Credentials(
            url=settings.WATSONX_URL,
            api_key=settings.WATSONX_API_KEY,
        )
        model = ModelInference(
            model_id=settings.WATSONX_MODEL_ID,
            credentials=credentials,
            project_id=settings.WATSONX_PROJECT_ID,
            params={
                "max_new_tokens": settings.LLM_MAX_OUTPUT_TOKENS,
                "temperature": settings.LLM_TEMPERATURE,
            },
        )
        return cls(model_inference=model, model_id=settings.WATSONX_MODEL_ID)

    async def generate(self, messages: list[ChatMessage]) -> LLMResult:
        # Prompt 構築: system + user メッセージ等を結合
        prompt_parts: list[str] = []
        for msg in messages:
            if msg.role == "system":
                prompt_parts.append(f"[System]\n{msg.content}")
            elif msg.role == "user":
                prompt_parts.append(f"[User]\n{msg.content}")
            elif msg.role == "assistant":
                prompt_parts.append(f"[Assistant]\n{msg.content}")
            else:
                prompt_parts.append(f"[{msg.role}]\n{msg.content}")
        prompt = "\n\n".join(prompt_parts) + "\n\n[Assistant]\n"

        max_retries = 2
        for attempt in range(max_retries + 1):
            try:
                # generate_text は同期呼び出しのため asyncio.to_thread で実行
                response = await asyncio.to_thread(self._model.generate_text, prompt=prompt)
                return LLMResult(
                    text=response,
                    model=self._model_id,
                    provider="watsonx",
                    input_tokens=None,
                    output_tokens=None,
                )
            except Exception as exc:
                exc_str = str(exc)
                status_code = getattr(exc, "status_code", None) or getattr(exc, "code", None)

                # 401/403 認証・認可エラーはリトライしない
                if status_code in (401, 403) or "401" in exc_str or "403" in exc_str:
                    logger.error("Watsonx authentication/authorization failed. Not retrying.")
                    raise ProviderError(
                        "Watsonx provider authentication error",
                        detail="Authentication failed with Watsonx API",
                    ) from exc

                # 429/503 はリトライ（最大2回、指数バックオフ + jitter）
                is_retryable = (
                    status_code in (429, 503)
                    or "429" in exc_str
                    or "503" in exc_str
                    or "rate limit" in exc_str.lower()
                )
                if is_retryable and attempt < max_retries:
                    delay = (2**attempt) + random.uniform(0.1, 0.5)
                    logger.warning(
                        "Watsonx API returned retryable error (attempt %d/%d). Retrying in %.2fs: %s",
                        attempt + 1,
                        max_retries,
                        delay,
                        exc.__class__.__name__,
                    )
                    await asyncio.sleep(delay)
                    continue

                logger.error("Watsonx generation failed: %s", exc.__class__.__name__)
                raise ProviderError(
                    "Watsonx provider error", detail="Failed to generate response from Watsonx"
                ) from exc
        raise ProviderError("Watsonx provider error", detail="Max retries exceeded")
