"""
Google Gemini 프로바이더.
의존성: pip install google-generativeai
"""
from __future__ import annotations
import uuid
from typing import Iterator, Optional

from core.llm import BaseLLMClient, LLMResponse, TextBlock, ToolUseBlock

try:
    import google.generativeai as genai
    import google.generativeai.types as genai_types
except ImportError:
    genai = None
    genai_types = None


class GeminiClient(BaseLLMClient):
    def __init__(self, model: str = "gemini-1.5-pro", max_tokens: int = 8192, api_key: str = ""):
        if genai is None:
            raise ImportError(
                "google-generativeai 패키지가 필요합니다: pip install google-generativeai"
            )
        if api_key:
            genai.configure(api_key=api_key)
        self.model_name = model
        self.max_tokens = max_tokens

    def chat(
        self,
        messages: list[dict],
        tools: Optional[list[dict]] = None,
        system: str = "",
    ) -> LLMResponse:
        model = genai.GenerativeModel(
            model_name=self.model_name,
            tools=_to_gemini_tools(tools) if tools else None,
            system_instruction=system or None,
            generation_config=genai_types.GenerationConfig(max_output_tokens=self.max_tokens),
        )
        response = model.generate_content(_to_gemini_messages(messages))
        return _from_gemini_response(response)

    def stream_text(
        self,
        messages: list[dict],
        system: str = "",
    ) -> Iterator[str]:
        model = genai.GenerativeModel(
            model_name=self.model_name,
            system_instruction=system or None,
            generation_config=genai_types.GenerationConfig(max_output_tokens=self.max_tokens),
        )
        for chunk in model.generate_content(_to_gemini_messages(messages), stream=True):
            if chunk.text:
                yield chunk.text


# ── 변환 헬퍼 ────────────────────────────────────────────


_UNSUPPORTED_SCHEMA_FIELDS = {"default", "title", "examples", "$schema", "additionalProperties"}


def _strip_schema(schema: dict) -> dict:
    """Gemini가 지원하지 않는 JSON Schema 필드를 재귀적으로 제거."""
    result = {k: v for k, v in schema.items() if k not in _UNSUPPORTED_SCHEMA_FIELDS}
    if "properties" in result:
        result["properties"] = {k: _strip_schema(v) for k, v in result["properties"].items()}
    if "items" in result:
        items = result["items"]
        result["items"] = _strip_schema(items) if isinstance(items, dict) and items else {"type": "string"}
    return result


def _to_gemini_tools(tools: list[dict]) -> list:
    """Anthropic input_schema 형식 → Gemini function_declarations."""
    declarations = []
    for t in tools:
        fd: dict = {"name": t["name"], "description": t.get("description", "")}
        if "input_schema" in t:
            fd["parameters"] = _strip_schema(t["input_schema"])
        declarations.append(fd)
    return [{"function_declarations": declarations}]


def _build_id_name_map(messages: list[dict]) -> dict[str, str]:
    """tool_use_id → function name 매핑 (function_response 변환용)."""
    mapping: dict[str, str] = {}
    for msg in messages:
        content = msg.get("content", [])
        if isinstance(content, list):
            for block in content:
                if isinstance(block, ToolUseBlock):
                    mapping[block.id] = block.name
    return mapping


def _to_gemini_messages(messages: list[dict]) -> list[dict]:
    """정규화된 메시지 → Gemini contents 형식."""
    id_to_name = _build_id_name_map(messages)
    result = []
    for msg in messages:
        role = "model" if msg["role"] == "assistant" else "user"
        content = msg["content"]

        if isinstance(content, str):
            result.append({"role": role, "parts": [{"text": content}]})
            continue

        parts = []
        for block in content:
            if isinstance(block, TextBlock):
                if block.text:
                    parts.append({"text": block.text})
            elif isinstance(block, ToolUseBlock):
                parts.append({"function_call": {"name": block.name, "args": block.input}})
            elif isinstance(block, dict) and block.get("type") == "tool_result":
                name = id_to_name.get(block["tool_use_id"], "unknown_function")
                parts.append({
                    "function_response": {
                        "name": name,
                        "response": {"result": block["content"]},
                    }
                })
        if parts:
            result.append({"role": role, "parts": parts})

    return result


def _proto_to_python(val):
    """proto composite 타입(MapComposite, RepeatedComposite)을 Python 기본 타입으로 재귀 변환."""
    if val is None or isinstance(val, (bool, int, float, str)):
        return val
    if hasattr(val, "items"):
        return {k: _proto_to_python(v) for k, v in val.items()}
    if hasattr(val, "__iter__"):
        return [_proto_to_python(v) for v in val]
    return val


def _from_gemini_response(response) -> LLMResponse:
    """Gemini 응답 → 정규화된 LLMResponse."""
    content = []
    has_tool_call = False

    candidate = response.candidates[0]
    for part in candidate.content.parts:
        fc = getattr(part, "function_call", None)
        if fc and getattr(fc, "name", None):
            has_tool_call = True
            content.append(ToolUseBlock(
                id=str(uuid.uuid4()),
                name=fc.name,
                input=_proto_to_python(fc.args),
            ))
        elif getattr(part, "text", None):
            content.append(TextBlock(text=part.text))

    return LLMResponse(
        stop_reason="tool_use" if has_tool_call else "end_turn",
        content=content,
    )
