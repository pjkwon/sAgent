"""
LLM: 프로바이더 공통 타입 + 클라이언트 팩토리.
"""
from __future__ import annotations
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Iterator, Optional


@dataclass
class TextBlock:
    text: str
    type: str = "text"


@dataclass
class ToolUseBlock:
    id: str
    name: str
    input: dict
    type: str = "tool_use"


@dataclass
class LLMResponse:
    stop_reason: str  # "end_turn" | "tool_use"
    content: list     # list[TextBlock | ToolUseBlock]


class BaseLLMClient(ABC):
    @abstractmethod
    def chat(
        self,
        messages: list[dict],
        tools: Optional[list[dict]] = None,
        system: str = "",
    ) -> LLMResponse: ...

    @abstractmethod
    def stream_text(
        self,
        messages: list[dict],
        system: str = "",
    ) -> Iterator[str]: ...


def create_llm_client(config) -> BaseLLMClient:
    provider = getattr(config, "provider", "anthropic").lower()

    if provider == "anthropic":
        from core.providers.anthropic import AnthropicClient
        return AnthropicClient(model=config.model, max_tokens=config.max_tokens)

    elif provider == "gemini":
        from core.providers.gemini import GeminiClient
        api_key = getattr(config, "gemini_api_key", "") or os.environ.get("GOOGLE_API_KEY", "")
        return GeminiClient(model=config.model, max_tokens=config.max_tokens, api_key=api_key)

    raise ValueError(f"지원하지 않는 LLM 프로바이더: {provider!r}. (anthropic | gemini)")
