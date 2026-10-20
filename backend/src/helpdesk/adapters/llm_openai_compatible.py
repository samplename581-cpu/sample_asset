from __future__ import annotations

import asyncio
import logging
import random
from typing import TYPE_CHECKING, Any

from helpdesk.domain.errors import ConfigurationError, ProviderError
from helpdesk.ports.llm import ChatMessage, LLMPort, LLMResult

if TYPE_CHECKING:
    from helpdesk.config import Settings

logger = logging.getLogger("helpdesk.adapters.llm_openai_compatible")


class OpenAICompatibleLLMAdapter(LLMPort):
    def __init__(
        self,
        client: Any,
        base_url: str,
        model_id: str,
        api_key: str | None = None,
        max_tokens: int = 500,
        temperature: float = 0.1,
        timeout_seconds: int = 30,
    ) -> None:
        self._client = client
        self._base_url = base_url.rstrip("/")
        self._model_id = model_id
        self._api_key = api_key
        self._max_tokens = max_tokens
        self._temperature = temperature
        self._timeout_seconds = timeout_seconds

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()

    @classmethod
    def from_settings(cls, settings: Settings) -> OpenAICompatibleLLMAdapter:
        try:
            import httpx
        except ImportError as e:
            raise ConfigurationError(
                "httpx is not installed. Please install httpx to use OpenAI compatible LLM provider."
            ) from e

        base_url = settings.OPENAI_COMPATIBLE_BASE_URL or "http://127.0.0.1:11434/v1"
        model_id = settings.OPENAI_COMPATIBLE_MODEL_ID or settings.LLM_MODEL_ID

        client = httpx.AsyncClient(timeout=float(settings.LLM_TIMEOUT_SECONDS))
        return cls(
            client=client,
            base_url=base_url,
            model_id=model_id,
            api_key=settings.OPENAI_COMPATIBLE_API_KEY,
            max_tokens=settings.LLM_MAX_OUTPUT_TOKENS,
            temperature=settings.LLM_TEMPERATURE,
            timeout_seconds=settings.LLM_TIMEOUT_SECONDS,
        )

    async def generate(self, messages: list[ChatMessage]) -> LLMResult:
        url = f"{self._base_url}/chat/completions"
        headers: dict[str, str] = {
            "Content-Type": "application/json",
        }
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        payload = {
            "model": self._model_id,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "max_tokens": self._max_tokens,
            "temperature": self._temperature,
        }

        max_retries = 2
        for attempt in range(max_retries + 1):
            try:
                response = await self._client.post(
                    url,
                    json=payload,
                    headers=headers,
                    timeout=float(self._timeout_seconds),
                )

                if response.status_code in (401, 403):
                    logger.error(
                        "OpenAI Compatible API authentication failed (status %d)",
                        response.status_code,
                    )
                    raise ProviderError(
                        "Authentication error with OpenAI compatible provider",
                        detail=f"OpenAI compatible API returned {response.status_code}",
                    )

                if response.status_code in (429, 503) and attempt < max_retries:
                    delay = (2**attempt) + random.uniform(0.1, 0.5)
                    logger.warning(
                        "OpenAI Compatible API returned %d (attempt %d/%d). Retrying in %.2fs",
                        response.status_code,
                        attempt + 1,
                        max_retries,
                        delay,
                    )
                    await asyncio.sleep(delay)
                    continue

                response.raise_for_status()
                data = response.json()
                text = data["choices"][0]["message"]["content"]
                usage = data.get("usage", {})
                input_tokens = usage.get("prompt_tokens")
                output_tokens = usage.get("completion_tokens")

                return LLMResult(
                    text=text,
                    model=self._model_id,
                    provider="openai_compatible",
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                )
            except ProviderError:
                raise
            except Exception as exc:
                if attempt < max_retries and "timeout" in str(exc).lower():
                    delay = (2**attempt) + random.uniform(0.1, 0.5)
                    logger.warning(
                        "OpenAI Compatible request timed out (attempt %d/%d). Retrying in %.2fs",
                        attempt + 1,
                        max_retries,
                        delay,
                    )
                    await asyncio.sleep(delay)
                    continue

                logger.error("OpenAI Compatible LLM request failed: %s", exc.__class__.__name__)
                raise ProviderError(
                    "OpenAI compatible provider error",
                    detail=f"Failed to generate response: {exc.__class__.__name__}",
                ) from exc
        raise ProviderError("OpenAI compatible provider error", detail="Max retries exceeded")
