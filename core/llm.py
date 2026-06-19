"""
LLM: Anthropic Claude API 래퍼.
tool_use 루프를 처리하고 스트리밍을 지원합니다.
"""
from __future__ import annotations
import anthropic
from typing import Optional, Iterator


class LLMClient:
    def __init__(self, model: str, max_tokens: int = 8192):
        self.client = anthropic.Anthropic()
        self.model = model
        self.max_tokens = max_tokens

    def chat(
        self,
        messages: list[dict],
        tools: Optional[list[dict]] = None,
        system: str = "",
    ) -> anthropic.types.Message:
        """단일 API 호출. tool_use 블록 포함 가능."""
        kwargs: dict = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": messages,
        }
        if system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = tools
        return self.client.messages.create(**kwargs)

    def stream_text(
        self,
        messages: list[dict],
        system: str = "",
    ) -> Iterator[str]:
        """최종 답변을 스트리밍으로 반환."""
        with self.client.messages.stream(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system,
            messages=messages,
        ) as stream:
            for text in stream.text_stream:
                yield text
