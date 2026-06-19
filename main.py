#!/usr/bin/env python3
"""
main.py: CLI 기반 AI Agent 진입점.

사용법:
    python main.py                    # 대화형 모드
    python main.py -q "질문 내용"     # 단일 질문 모드
    python main.py --work-dir ./data  # 작업 폴더 지정
    python main.py --format plain     # 출력 형식 지정
    python main.py --verbose          # 상세 로그 출력
"""
from __future__ import annotations
import argparse
import sys
import os
# 화살표 키·히스토리 지원: Unix는 readline, Windows는 pyreadline3 (없으면 무시)
try:
    import readline  # Unix/macOS
except ImportError:
    try:
        import pyreadline3  # Windows: pip install pyreadline3
    except ImportError:
        pass  # 없어도 동작은 함

# Windows ANSI 컬러 활성화
try:
    import colorama
    colorama.init()
except ImportError:
    pass

from core.config import Config
from core.agent import Agent
from tools import file_tools, db_tools


# ─────────────────────────────────────────────
# ANSI 컬러 헬퍼
# ─────────────────────────────────────────────

def supports_color() -> bool:
    if not hasattr(sys.stdout, "isatty") or not sys.stdout.isatty():
        return False
    # Windows: colorama가 init된 경우 ANSI 지원
    if sys.platform == "win32":
        try:
            import colorama  # noqa
            return True
        except ImportError:
            return False
    return True

RESET = "\033[0m" if supports_color() else ""
BOLD  = "\033[1m" if supports_color() else ""
CYAN  = "\033[36m" if supports_color() else ""
GREEN = "\033[32m" if supports_color() else ""
GRAY  = "\033[90m" if supports_color() else ""
YELLOW= "\033[33m" if supports_color() else ""


def print_banner(config: Config) -> None:
    print(f"""
{CYAN}{BOLD}╔══════════════════════════════════════╗
║        CLI AI Agent  v1.0            ║
╚══════════════════════════════════════╝{RESET}
  프로바이더: {config.provider}
  모델    : {config.model}
  작업폴더: {config.work_dir}
  출력형식: {config.output_format}
  {GRAY}종료: 'exit' | 히스토리 초기화: 'reset' | 도움말: 'help'{RESET}
""")


def print_help() -> None:
    print(f"""
{BOLD}── 명령어 ──────────────────────────────────────────{RESET}
  {GREEN}reset{RESET}           대화 히스토리 초기화
  {GREEN}format <타입>{RESET}   출력 형식 변경 (markdown / plain / json)
  {GREEN}workdir <경로>{RESET}  작업 폴더 변경
  {GREEN}tools{RESET}           사용 가능한 Tool 목록 출력
  {GREEN}save{RESET}            현재 세션 로그 저장
  {GREEN}verbose{RESET}         상세 모드 토글
  {GREEN}help{RESET}            이 도움말 출력
  {GREEN}exit / quit{RESET}     종료
""")


def handle_command(cmd: str, agent: Agent) -> bool:
    """
    특수 명령어를 처리합니다.
    반환값: True이면 루프 계속, False이면 종료.
    """
    parts = cmd.strip().split(maxsplit=1)
    keyword = parts[0].lower()

    if keyword in ("exit", "quit"):
        path = agent.save_session()
        if path:
            print(f"{GRAY}세션 로그 저장됨: {path}{RESET}")
        print(f"{CYAN}종료합니다.{RESET}")
        return False

    elif keyword == "reset":
        agent.reset()
        print(f"{YELLOW}대화 히스토리가 초기화되었습니다.{RESET}")

    elif keyword == "help":
        print_help()

    elif keyword == "tools":
        print(f"\n{BOLD}── 사용 가능한 Tool ─────────────────────────{RESET}")
        from tools.registry import registry
        for name in registry.names():
            tool = registry.get(name)
            print(f"  {GREEN}{name}{RESET}: {tool.description[:60]}...")
        print()

    elif keyword == "format" and len(parts) > 1:
        fmt = parts[1].strip()
        if fmt in ("markdown", "plain", "json"):
            agent.set_output_format(fmt)
            print(f"{YELLOW}출력 형식 변경됨: {fmt}{RESET}")
        else:
            print(f"{YELLOW}지원 형식: markdown / plain / json{RESET}")

    elif keyword == "workdir" and len(parts) > 1:
        new_dir = parts[1].strip()
        agent.config.work_dir = new_dir
        file_tools.set_work_dir(new_dir)
        print(f"{YELLOW}작업 폴더 변경됨: {new_dir}{RESET}")

    elif keyword == "save":
        path = agent.save_session()
        if path:
            print(f"{YELLOW}세션 로그 저장됨: {path}{RESET}")
        else:
            print(f"{GRAY}저장할 로그가 없습니다.{RESET}")

    elif keyword == "verbose":
        agent.config.verbose = not agent.config.verbose
        state = "ON" if agent.config.verbose else "OFF"
        print(f"{YELLOW}상세 모드: {state}{RESET}")

    else:
        return None  # 명령어 아님 → 일반 입력으로 처리

    return True


# ─────────────────────────────────────────────
# 메인
# ─────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="CLI 기반 AI Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("-q", "--query", help="단일 질문 (비대화형 모드)")
    parser.add_argument("-c", "--config", default="config.yaml", help="설정 파일 경로")
    parser.add_argument("--work-dir", help="작업 폴더 경로")
    parser.add_argument("--format", choices=["markdown", "plain", "json"], help="출력 형식")
    parser.add_argument("--provider", choices=["anthropic", "gemini"], help="LLM 프로바이더")
    parser.add_argument("--model", help="모델 이름 (프로바이더에 따라 다름)")
    parser.add_argument("--verbose", action="store_true", help="상세 로그 출력")
    parser.add_argument("--no-color", action="store_true", help="컬러 출력 비활성화")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    # 컬러 비활성화
    if args.no_color:
        global RESET, BOLD, CYAN, GREEN, GRAY, YELLOW
        RESET = BOLD = CYAN = GREEN = GRAY = YELLOW = ""

    # 설정 로드
    config = Config.load(args.config)
    if args.work_dir:
        config.work_dir = args.work_dir
    if args.format:
        config.output_format = args.format
    if args.provider:
        config.provider = args.provider
    if args.model:
        config.model = args.model
    if args.verbose:
        config.verbose = True

    # 작업 폴더 초기화
    os.makedirs(config.work_dir, exist_ok=True)
    file_tools.set_work_dir(config.work_dir)
    db_tools.set_db_config(config.db)

    # 에이전트 초기화
    agent = Agent(config)

    # API 키 확인
    if config.provider == "anthropic" and not config.api_key:
        print(f"{YELLOW}⚠ ANTHROPIC_API_KEY가 설정되지 않았습니다.")
        print(f"  .env 또는 config.yaml의 api_key 항목을 설정하세요.{RESET}\n")
    elif config.provider == "gemini" and not config.gemini_api_key:
        print(f"{YELLOW}⚠ GOOGLE_API_KEY가 설정되지 않았습니다.")
        print(f"  .env 또는 config.yaml의 gemini_api_key 항목을 설정하세요.{RESET}\n")

    # 단일 질문 모드
    if args.query:
        response = agent.run(args.query)
        print(response)
        agent.save_session()
        return

    # 대화형 모드
    print_banner(config)

    while True:
        try:
            raw = input(f"{CYAN}You>{RESET} ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            agent.save_session()
            break

        if not raw:
            continue

        # 특수 명령어 처리
        result = handle_command(raw, agent)
        if result is False:
            break
        if result is True:
            continue

        # 에이전트 실행
        print(f"\n{BOLD}Agent>{RESET}")
        try:
            answer = agent.run(raw)
            print(answer)
        except Exception as e:
            if config.verbose:
                import traceback
                traceback.print_exc()
            print(f"{YELLOW}오류: {e}{RESET}")

        print()


if __name__ == "__main__":
    main()
