"""
Tool Registry: 데코레이터 기반으로 Tool을 등록하고 실행합니다.
Claude API tool_use 형식(input_schema)으로 변환합니다.
"""
from __future__ import annotations
import traceback
from typing import Any, Callable, Optional


class Tool:
    def __init__(
        self,
        name: str,
        description: str,
        parameters: dict,
        func: Callable,
    ):
        self.name = name
        self.description = description
        self.parameters = parameters
        self.func = func

    def to_api_format(self) -> dict:
        """Anthropic tool_use 정의 형식으로 변환."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.parameters,
        }

    def execute(self, **kwargs) -> Any:
        return self.func(**kwargs)


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(
        self,
        name: str,
        description: str,
        parameters: dict,
    ) -> Callable:
        """Tool 등록 데코레이터."""
        def decorator(func: Callable) -> Callable:
            self._tools[name] = Tool(name, description, parameters, func)
            return func
        return decorator

    def get(self, name: str) -> Optional[Tool]:
        return self._tools.get(name)

    def names(self) -> list[str]:
        return list(self._tools.keys())

    def api_definitions(self) -> list[dict]:
        """Claude API에 전달할 tool 정의 목록."""
        return [t.to_api_format() for t in self._tools.values()]

    def run(self, name: str, tool_use_id: str, **kwargs) -> dict:
        """
        Tool을 실행하고 Claude API tool_result 형식으로 반환.
        성공/실패 모두 tool_result로 래핑해서 대화 흐름을 유지합니다.
        """
        tool = self.get(name)
        if not tool:
            return self._result(tool_use_id, f"[오류] 존재하지 않는 Tool: {name}", is_error=True)
        try:
            result = tool.execute(**kwargs)
            content = result if isinstance(result, str) else str(result)
            return self._result(tool_use_id, content)
        except Exception as e:
            msg = f"[오류] {name} 실행 실패: {e}\n{traceback.format_exc()}"
            return self._result(tool_use_id, msg, is_error=True)

    @staticmethod
    def _result(tool_use_id: str, content: str, is_error: bool = False) -> dict:
        return {
            "type": "tool_result",
            "tool_use_id": tool_use_id,
            "content": content,
            **({"is_error": True} if is_error else {}),
        }


# 전역 싱글턴 레지스트리
registry = ToolRegistry()
