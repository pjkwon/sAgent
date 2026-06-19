"""
File Tools: 작업 폴더 내 파일 검색, 읽기, 목록 조회 Tool 모음.
"""
from __future__ import annotations
import os
import re
import json
from pathlib import Path
from typing import Optional

from tools.registry import registry

# ─────────────────────────────────────────────
# 공통 헬퍼
# ─────────────────────────────────────────────

_work_dir: Path = Path("workspace")


def set_work_dir(path: str | Path) -> None:
    global _work_dir
    _work_dir = Path(path).resolve()


def _safe_path(relative: str) -> Path:
    """작업 폴더 외부 경로 접근을 차단합니다."""
    target = (_work_dir / relative).resolve()
    if not str(target).startswith(str(_work_dir)):
        raise PermissionError(f"작업 폴더 외부 접근 불가: {relative}")
    return target


# ─────────────────────────────────────────────
# Tool: list_files
# ─────────────────────────────────────────────

@registry.register(
    name="list_files",
    description=(
        "작업 폴더 내 파일/디렉터리 목록을 조회합니다. "
        "확장자 필터와 재귀 탐색을 지원합니다."
    ),
    parameters={
        "type": "object",
        "properties": {
            "subdir": {
                "type": "string",
                "description": "조회할 하위 디렉터리 (기본: 루트)",
                "default": "",
            },
            "extensions": {
                "type": "array",
                "items": {"type": "string"},
                "description": "확장자 필터 목록 (예: ['.txt', '.md']). 빈 배열이면 전체.",
                "default": [],
            },
            "recursive": {
                "type": "boolean",
                "description": "하위 폴더 재귀 탐색 여부",
                "default": True,
            },
        },
        "required": [],
    },
)
def list_files(
    subdir: str = "",
    extensions: list[str] = [],
    recursive: bool = True,
) -> str:
    base = _safe_path(subdir) if subdir else _work_dir
    if not base.exists():
        return f"폴더가 존재하지 않습니다: {base}"

    exts = {e.lower() if e.startswith(".") else f".{e.lower()}" for e in extensions}
    results: list[str] = []

    pattern = "**/*" if recursive else "*"
    for p in sorted(base.glob(pattern)):
        if p.is_file():
            if not exts or p.suffix.lower() in exts:
                results.append(str(p.relative_to(_work_dir)))

    if not results:
        return "조건에 맞는 파일이 없습니다."
    return "\n".join(results)


# ─────────────────────────────────────────────
# Tool: read_file
# ─────────────────────────────────────────────

@registry.register(
    name="read_file",
    description=(
        "작업 폴더 내 파일의 내용을 읽어서 반환합니다. "
        "인코딩 자동 감지를 시도합니다."
    ),
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "작업 폴더 기준 상대 경로 (예: data/report.txt)",
            },
            "start_line": {
                "type": "integer",
                "description": "읽기 시작 줄 (1-based, 기본: 1)",
                "default": 1,
            },
            "end_line": {
                "type": "integer",
                "description": "읽기 종료 줄 (포함, 기본: 전체)",
                "default": -1,
            },
        },
        "required": ["path"],
    },
)
def read_file(path: str, start_line: int = 1, end_line: int = -1) -> str:
    target = _safe_path(path)
    if not target.exists():
        return f"파일을 찾을 수 없습니다: {path}"

    for enc in ("utf-8", "utf-8-sig", "cp949", "euc-kr"):
        try:
            lines = target.read_text(encoding=enc).splitlines()
            break
        except UnicodeDecodeError:
            continue
    else:
        return f"파일 인코딩을 인식할 수 없습니다: {path}"

    total = len(lines)
    s = max(0, start_line - 1)
    e = total if end_line == -1 else min(end_line, total)
    selected = lines[s:e]

    header = f"[{path}] ({total}줄 중 {s+1}~{e}줄)\n{'─'*40}\n"
    return header + "\n".join(selected)


# ─────────────────────────────────────────────
# Tool: search_in_files
# ─────────────────────────────────────────────

@registry.register(
    name="search_in_files",
    description=(
        "작업 폴더 내 파일들에서 키워드 또는 정규식으로 텍스트를 검색합니다. "
        "파일명 패턴, 확장자, 재귀 탐색을 지원합니다."
    ),
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "검색할 키워드 또는 정규식 패턴",
            },
            "use_regex": {
                "type": "boolean",
                "description": "정규식 사용 여부 (False이면 단순 문자열 검색)",
                "default": False,
            },
            "case_sensitive": {
                "type": "boolean",
                "description": "대소문자 구분 여부",
                "default": False,
            },
            "extensions": {
                "type": "array",
                "items": {"type": "string"},
                "description": "검색할 파일 확장자 (예: ['.txt', '.md']). 빈 배열이면 전체.",
                "default": [],
            },
            "subdir": {
                "type": "string",
                "description": "검색 범위 하위 디렉터리",
                "default": "",
            },
            "max_results": {
                "type": "integer",
                "description": "최대 결과 수",
                "default": 50,
            },
            "context_lines": {
                "type": "integer",
                "description": "매칭 줄 전후로 보여줄 컨텍스트 줄 수",
                "default": 2,
            },
        },
        "required": ["query"],
    },
)
def search_in_files(
    query: str,
    use_regex: bool = False,
    case_sensitive: bool = False,
    extensions: list[str] = [],
    subdir: str = "",
    max_results: int = 50,
    context_lines: int = 2,
) -> str:
    base = _safe_path(subdir) if subdir else _work_dir
    exts = {e.lower() if e.startswith(".") else f".{e.lower()}" for e in extensions}

    flags = 0 if case_sensitive else re.IGNORECASE
    try:
        pattern = re.compile(query if use_regex else re.escape(query), flags)
    except re.error as e:
        return f"정규식 오류: {e}"

    hits: list[str] = []
    count = 0

    for filepath in sorted(base.glob("**/*")):
        if not filepath.is_file():
            continue
        if exts and filepath.suffix.lower() not in exts:
            continue

        for enc in ("utf-8", "utf-8-sig", "cp949", "euc-kr"):
            try:
                lines = filepath.read_text(encoding=enc).splitlines()
                break
            except UnicodeDecodeError:
                continue
        else:
            continue

        rel = str(filepath.relative_to(_work_dir))
        for i, line in enumerate(lines):
            if pattern.search(line):
                count += 1
                if count > max_results:
                    hits.append(f"\n... 결과가 {max_results}개를 초과하여 잘렸습니다.")
                    return "\n".join(hits)

                start = max(0, i - context_lines)
                end = min(len(lines), i + context_lines + 1)
                ctx_lines = []
                for j in range(start, end):
                    marker = ">>>" if j == i else "   "
                    ctx_lines.append(f"  {marker} {j+1:4d}: {lines[j]}")
                block = f"\n[{rel}] 줄 {i+1}\n" + "\n".join(ctx_lines)
                hits.append(block)

    if not hits:
        return f"'{query}' 검색 결과 없음."
    header = f"'{query}' 검색 결과: {count}건\n{'═'*50}"
    return header + "".join(hits)


# ─────────────────────────────────────────────
# Tool: write_file
# ─────────────────────────────────────────────

@registry.register(
    name="write_file",
    description="작업 폴더 내에 파일을 생성하거나 내용을 씁니다.",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "작업 폴더 기준 상대 경로",
            },
            "content": {
                "type": "string",
                "description": "저장할 내용",
            },
            "append": {
                "type": "boolean",
                "description": "True이면 기존 내용에 이어 씁니다",
                "default": False,
            },
        },
        "required": ["path", "content"],
    },
)
def write_file(path: str, content: str, append: bool = False) -> str:
    target = _safe_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if append else "w"
    target.write_text(content, encoding="utf-8") if not append else \
        open(target, "a", encoding="utf-8").write(content)
    action = "추가" if append else "저장"
    return f"파일 {action} 완료: {path} ({len(content)}자)"
