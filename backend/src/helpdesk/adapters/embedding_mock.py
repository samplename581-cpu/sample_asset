from __future__ import annotations

import hashlib
import struct

import numpy as np


class MockEmbeddingAdapter:
    """Deterministic mock embedding adapter for testing and development.

    Uses hashlib.sha256 as seed source so vectors are stable across
    Python processes (unlike the built-in hash() which changes per process).
    """

    @property
    def dimension(self) -> int:
        return 64

    @property
    def provider_name(self) -> str:
        return "mock"

    @property
    def model_name(self) -> str:
        return "mock-embedding-v1"

    def _embed(self, text: str) -> np.ndarray:
        # Derive a stable 32-bit integer seed from SHA-256 of the text.
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        seed = struct.unpack("<I", digest[:4])[0]
        vec = np.random.default_rng(seed).standard_normal(self.dimension).astype(np.float32)
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec

    def encode_passages(self, texts: list[str]) -> np.ndarray:
        """passages を (n, dim) float32 行列に変換する"""
        return np.stack([self._embed(t) for t in texts], axis=0)

    def encode_query(self, text: str) -> np.ndarray:
        """query を (dim,) float32 ベクトルに変換する"""
        return self._embed(text)
