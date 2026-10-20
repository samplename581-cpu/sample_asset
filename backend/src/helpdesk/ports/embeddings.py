from typing import Protocol

import numpy as np


class EmbeddingPort(Protocol):
    @property
    def dimension(self) -> int: ...

    @property
    def provider_name(self) -> str: ...

    @property
    def model_name(self) -> str: ...

    def encode_passages(self, texts: list[str]) -> np.ndarray:
        """passages を (n, dim) float32 行列に変換する"""
        ...

    def encode_query(self, text: str) -> np.ndarray:
        """query を (dim,) float32 ベクトルに変換する"""
        ...
