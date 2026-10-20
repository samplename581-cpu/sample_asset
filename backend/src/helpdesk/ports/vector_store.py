from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    import numpy as np


@dataclass(frozen=True)
class ChunkRecord:
    chunk_id: str
    document_id: str
    text: str
    title: str
    source: str
    document_type: str
    category: str | None
    position: int
    access_scope: str = "student"
    is_active: bool = True


@dataclass(frozen=True)
class SearchResult:
    chunk_id: str
    document_id: str
    title: str
    snippet: str
    score: float
    source: str


class VectorStorePort(Protocol):
    def search(
        self,
        query_vector: np.ndarray,
        top_k: int = 5,
        document_types: list[str] | None = None,
        min_score: float = 0.0,
        access_scope: str | None = None,
    ) -> list[SearchResult]: ...

    def count(self) -> int: ...
