"""
Config: config.yaml 또는 기본값으로 에이전트 설정을 관리합니다.
"""
from __future__ import annotations
import os
import yaml
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class DBConfig:
    type: str = "sqlite"          # sqlite | postgresql | mysql | mssql
    path: str = "agent.db"        # sqlite 전용
    host: str = "localhost"
    port: int = 5432
    database: str = ""
    user: str = ""
    password: str = ""
    dsn: str = ""                 # pyodbc DSN (mssql 전용)


@dataclass
class Config:
    # 작업 환경
    work_dir: str = "workspace"
    system_prompt_path: str = "prompts/system.md"
    log_dir: str = "logs"
    log_session: bool = True

    # LLM
    provider: str = "anthropic"   # anthropic | gemini
    model: str = "claude-sonnet-4-6"
    max_tokens: int = 8192
    max_iterations: int = 15      # 에이전트 루프 최대 횟수

    # 출력
    output_format: str = "markdown"   # markdown | plain | json
    stream: bool = True

    # 디버그
    verbose: bool = False

    # API 키 (config.yaml 또는 .env에서 로드)
    api_key: str = ""
    gemini_api_key: str = ""

    # DB
    db: DBConfig = field(default_factory=DBConfig)

    @classmethod
    def load(cls, path: str = "config.yaml") -> "Config":
        # 1) .env 파일 로드 (있으면)
        _load_dotenv()

        raw: dict = {}
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                raw = yaml.safe_load(f) or {}

        db_raw = raw.pop("db", {})
        valid = {k: v for k, v in raw.items() if k in cls.__dataclass_fields__}
        cfg = cls(**valid)
        if db_raw:
            cfg.db = DBConfig(**{k: v for k, v in db_raw.items() if k in DBConfig.__dataclass_fields__})

        # 2) API 키 우선순위: config.yaml > .env > 환경변수
        if not cfg.api_key:
            cfg.api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if cfg.api_key:
            os.environ["ANTHROPIC_API_KEY"] = cfg.api_key

        if not cfg.gemini_api_key:
            cfg.gemini_api_key = os.environ.get("GOOGLE_API_KEY", "")
        if cfg.gemini_api_key:
            os.environ["GOOGLE_API_KEY"] = cfg.gemini_api_key

        return cfg


def _load_dotenv(path: str = ".env") -> None:
    """경량 .env 파서. python-dotenv 없이도 동작합니다."""
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            # 이미 환경변수에 있으면 덮어쓰지 않음
            os.environ.setdefault(key, value)

    @property
    def work_path(self) -> Path:
        return Path(self.work_dir).resolve()
