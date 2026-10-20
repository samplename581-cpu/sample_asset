from __future__ import annotations

import json

from helpdesk.ports.llm import ChatMessage, LLMPort, LLMResult


class MockLLMAdapter(LLMPort):
    def __init__(self, model: str = "mock-helpdesk-v1") -> None:
        self.model = model

    async def generate(self, messages: list[ChatMessage]) -> LLMResult:
        user_content = ""
        for msg in reversed(messages):
            if msg.role == "user":
                user_content = msg.content
                break

        quoted = user_content[:100]
        payload = {
            "draft_answer": f"[MOCK] この回答はモック応答です。実際のLLMに置き換えてください。参照情報をもとに確認してください。（質問要約: {quoted}）"
            if quoted
            else "[MOCK] この回答はモック応答です。実際のLLMに置き換えてください。参照情報をもとに確認してください。",
            "citation_ids": ["S1"],
            "needs_human_confirmation": True,
            "missing_information": [],
        }

        return LLMResult(
            text=json.dumps(payload, ensure_ascii=False),
            model=self.model,
            provider="mock",
            input_tokens=None,
            output_tokens=None,
        )
