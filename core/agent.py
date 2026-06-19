"""
Agent: 핵심 에이전트 루프.
Claude의 native tool_use를 이용해 Tool을 자동으로 호출하고
최종 답변을 합성합니다.
"""
from __future__ import annotations
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import anthropic

from core.config import Config
from core.llm import LLMClient
from tools.registry import registry


# ─────────────────────────────────────────────
# 출력 형식 템플릿
# ─────────────────────────────────────────────

OUTPUT_FORMAT_INSTRUCTIONS = {
    "markdown": (
        "응답은 Markdown 형식으로 작성하세요. "
        "헤딩, 표, 코드 블록, 목록을 적절히 활용하세요."
    ),
    "plain": (
        "응답은 순수 텍스트로 작성하세요. "
        "특수 마크업 없이 명확하고 간결하게 서술하세요."
    ),
    "json": (
        "응답은 JSON 형식으로만 작성하세요. "
        '{"answer": "...", "summary": "...", "sources": [...]} 구조를 권장합니다.'
    ),
}


# ─────────────────────────────────────────────
# Agent 클래스
# ─────────────────────────────────────────────

class Agent:
    def __init__(self, config: Config):
        self.config = config
        self.llm = LLMClient(model=config.model, max_tokens=config.max_tokens)
        self.system_prompt = self._load_system_prompt()
        self.conversation: list[dict] = []
        self._session_log: list[str] = []

    # ── 시스템 프롬프트 ──────────────────────

    def _load_system_prompt(self) -> str:
        path = Path(self.config.system_prompt_path)
        if path.exists():
            return path.read_text(encoding="utf-8")
        return self._default_system_prompt()

    def _default_system_prompt(self) -> str:
        tool_names = ", ".join(registry.names())
        fmt_instruction = OUTPUT_FORMAT_INSTRUCTIONS.get(
            self.config.output_format,
            OUTPUT_FORMAT_INSTRUCTIONS["markdown"],
        )
        return f"""당신은 유능한 AI 에이전트입니다.
사용 가능한 Tool: {tool_names}

작업 방침:
- 사용자 질문을 분석하고, 필요한 Tool을 순서대로 호출해 정보를 수집하세요.
- 불필요한 Tool 호출은 자제하고 효율적으로 작업하세요.
- Tool 결과를 종합하여 사용자의 질문 의도에 맞게 답변하세요.
- 충분한 정보가 모이면 바로 최종 답변을 작성하세요.

출력 형식:
{fmt_instruction}

현재 날짜/시간: {datetime.now().strftime('%Y-%m-%d %H:%M')}
작업 폴더: {self.config.work_dir}
"""

    # ── 에이전트 루프 ────────────────────────

    def run(self, user_input: str) -> str:
        """
        단일 사용자 입력에 대해 에이전트 루프를 실행합니다.
        tool_use → tool_result → ... → 최종 text 응답
        """
        self.conversation.append({"role": "user", "content": user_input})
        self._log(f"\n[USER] {user_input}")

        iteration = 0
        tools_def = registry.api_definitions()

        while iteration < self.config.max_iterations:
            iteration += 1
            if self.config.verbose:
                print(f"\n  [루프 {iteration}] LLM 호출 중...")

            response = self.llm.chat(
                messages=self.conversation,
                tools=tools_def if tools_def else None,
                system=self.system_prompt,
            )

            # 응답 메시지를 대화 히스토리에 추가
            assistant_msg = {"role": "assistant", "content": response.content}
            self.conversation.append(assistant_msg)

            # 종료 조건 확인
            if response.stop_reason == "end_turn":
                # 최종 텍스트 답변 추출
                final = self._extract_text(response.content)
                self._log(f"[AGENT] {final}")
                return final

            if response.stop_reason != "tool_use":
                break

            # Tool 호출 처리
            tool_results = self._process_tool_calls(response.content)
            self.conversation.append({
                "role": "user",
                "content": tool_results,
            })

        # 루프 한계 도달
        fallback = self._extract_text(response.content) if response else "응답을 생성하지 못했습니다."
        return fallback

    def _process_tool_calls(self, content_blocks: list) -> list[dict]:
        """tool_use 블록들을 실행하고 tool_result 목록 반환."""
        results = []
        for block in content_blocks:
            if block.type != "tool_use":
                continue

            tool_name = block.name
            tool_input = block.input
            tool_id = block.id

            if self.config.verbose:
                print(
                    f"  [Tool] {tool_name}({json.dumps(tool_input, ensure_ascii=False)[:120]})",
                )
            self._log(f"[TOOL] {tool_name} ← {json.dumps(tool_input, ensure_ascii=False)}")

            start = time.perf_counter()
            result = registry.run(tool_name, tool_id, **tool_input)
            elapsed = time.perf_counter() - start

            if self.config.verbose:
                preview = result["content"][:200].replace("\n", " ")
                print(f"         → {preview}... ({elapsed:.2f}s)")
            self._log(f"[RESULT] {result['content'][:500]}")

            results.append(result)

        return results

    @staticmethod
    def _extract_text(content_blocks) -> str:
        """assistant 메시지에서 텍스트 블록만 추출."""
        parts = []
        for block in content_blocks:
            if hasattr(block, "type") and block.type == "text":
                parts.append(block.text)
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(block["text"])
        return "\n".join(parts).strip()

    # ── 대화 관리 ────────────────────────────

    def reset(self) -> None:
        """대화 히스토리를 초기화합니다."""
        self.conversation.clear()
        self._session_log.clear()

    def set_output_format(self, fmt: str) -> None:
        """출력 형식을 변경하고 시스템 프롬프트를 갱신합니다."""
        self.config.output_format = fmt
        self.system_prompt = self._load_system_prompt()

    # ── 세션 로깅 ────────────────────────────

    def _log(self, message: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        self._session_log.append(f"[{ts}] {message}")

    def save_session(self) -> Optional[Path]:
        if not self.config.log_session or not self._session_log:
            return None
        log_dir = Path(self.config.log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = log_dir / f"session_{ts}.log"
        path.write_text("\n".join(self._session_log), encoding="utf-8")
        return path
