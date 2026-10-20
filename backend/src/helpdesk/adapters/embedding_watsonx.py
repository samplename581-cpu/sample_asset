from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np

from helpdesk.domain.errors import ConfigurationError, ProviderError

if TYPE_CHECKING:
    from helpdesk.config import Settings


class WatsonxEmbeddingAdapter:
    """watsonx.ai embedding adapter isolated behind EmbeddingPort."""

    def __init__(self, embeddings: Any, model_name: str, dimension: int) -> None:
        self._embeddings = embeddings
        self._model_name = model_name
        self._dimension = dimension

    @classmethod
    def from_settings(cls, settings: Settings) -> WatsonxEmbeddingAdapter:
        try:
            from ibm_watsonx_ai import Credentials
            from ibm_watsonx_ai.foundation_models import Embeddings
        except ImportError as exc:
            raise ConfigurationError(
                "ibm_watsonx_ai is not installed. Install the 'watsonx' extra."
            ) from exc

        model_id = settings.WATSONX_EMBEDDING_MODEL_ID
        if not model_id or not settings.WATSONX_URL or not settings.WATSONX_API_KEY:
            raise ConfigurationError("watsonx.ai embedding settings are incomplete")

        embeddings = Embeddings(
            model_id=model_id,
            credentials=Credentials(
                url=settings.WATSONX_URL,
                api_key=settings.WATSONX_API_KEY,
            ),
            project_id=settings.WATSONX_PROJECT_ID,
        )
        return cls(embeddings, model_id, settings.EMBEDDING_DIMENSION)

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def provider_name(self) -> str:
        return "watsonx"

    @property
    def model_name(self) -> str:
        return self._model_name

    def encode_passages(self, texts: list[str]) -> np.ndarray:
        try:
            return np.asarray(self._embeddings.embed_documents(texts=texts), dtype=np.float32)
        except Exception as exc:
            raise ProviderError("watsonx.ai embedding request failed") from exc

    def encode_query(self, text: str) -> np.ndarray:
        try:
            return np.asarray(self._embeddings.embed_query(text=text), dtype=np.float32)
        except Exception as exc:
            raise ProviderError("watsonx.ai embedding request failed") from exc

    def close(self) -> None:
        close = getattr(self._embeddings, "close_persistent_connection", None)
        if callable(close):
            close()
