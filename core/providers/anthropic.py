"""
Anthropic Claude 프로바이더.
"""
from __future__ import annotations
import anthropic
from typing import Iterator, Optional

from core.llm import BaseLLMClient, LLMResponse, TextBlock, ToolUseBlock


class AnthropicClient(BaseLLMClient):
    def __init__(self, model: str, max_tokens: int = 8192):
        self.client = anthropic.Anthropic()
        self.model = model
        self.max_tokens = max_tokens

    def chat(
        self,
        messages: list[dict],
        tools: Optional[list[dict]] = None,
        system: str = "",
    ) -> LLMResponse:
        kwargs: dict = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": _to_anthropic_messages(messages),
        }
        if system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = tools
        response = self.client.messages.create(**kwargs)
        return _from_anthropic_response(response)

    def stream_text(
        self,
        messages: list[dict],
        system: str = "",
    ) -> Iterator[str]:
        with self.client.messages.stream(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system,
            messages=_to_anthropic_messages(messages),
        ) as stream:
            for text in stream.text_stream:
                yield text


def _to_anthropic_messages(messages: list[dict]) -> list[dict]:
    result = []
    for msg in messages:
        content = msg["content"]
        if isinstance(content, str):
            result.append({"role": msg["role"], "content": content})
        elif isinstance(content, list):
            blocks = []
            for block in content:
                if isinstance(block, TextBlock):
                    blocks.append({"type": "text", "text": block.text})
                elif isinstance(block, ToolUseBlock):
                    blocks.append({
                        "type": "tool_use",
                        "id": block.id,
                        "name": block.name,
                        "input": block.input,
                    })
                elif isinstance(block, dict):
                    blocks.append(block)
            result.append({"role": msg["role"], "content": blocks})
    return result


def _from_anthropic_response(response) -> LLMResponse:
    content = []
    for block in response.content:
        if block.type == "text":
            content.append(TextBlock(text=block.text))
        elif block.type == "tool_use":
            content.append(ToolUseBlock(id=block.id, name=block.name, input=block.input))
    return LLMResponse(stop_reason=response.stop_reason, content=content)
