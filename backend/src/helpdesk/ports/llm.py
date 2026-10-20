from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ChatMessage:
    role: str  # "system" | "user" | "assistant"
    content: str


@dataclass(frozen=True)
class LLMResult:
    text: str
    model: str
    provider: str
    input_tokens: int | None = None
    output_tokens: int | None = None


class LLMPort(Protocol):
    async def generate(self, messages: list[ChatMessage]) -> LLMResult: ...
