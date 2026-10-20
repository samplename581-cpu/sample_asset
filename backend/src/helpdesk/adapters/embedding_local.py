from __future__ import annotations

import numpy as np

from helpdesk.domain.errors import ConfigurationError


class LocalEmbeddingAdapter:
    """Sentence-Transformers based embedding adapter."""

    def __init__(self, model_name: str = "intfloat/multilingual-e5-small") -> None:
        try:
            from sentence_transformers import (  # type: ignore[import-not-found,import-untyped,unused-ignore]
                SentenceTransformer,
            )

            self._ST = SentenceTransformer
        except ImportError as exc:
            raise ConfigurationError(
                "sentence_transformers is not installed. "
                "Install it with: pip install sentence-transformers"
            ) from exc

        self._model_name = model_name
        self._model = self._ST(model_name)

    @property
    def dimension(self) -> int:
        dim = self._model.get_sentence_embedding_dimension()
        return int(dim) if dim is not None else 384

    @property
    def provider_name(self) -> str:
        return "local"

    @property
    def model_name(self) -> str:
        return self._model_name

    def encode_passages(self, texts: list[str]) -> np.ndarray:
        """passages を (n, dim) float32 行列に変換する"""
        prefixed = [f"passage: {t}" for t in texts]
        result = self._model.encode(
            prefixed,
            normalize_embeddings=True,
            convert_to_numpy=True,
        )
        return np.asarray(result, dtype=np.float32)

    def encode_query(self, text: str) -> np.ndarray:
        """query を (dim,) float32 ベクトルに変換する"""
        result = self._model.encode(
            f"query: {text}",
            normalize_embeddings=True,
            convert_to_numpy=True,
        )
        return np.asarray(result, dtype=np.float32)
