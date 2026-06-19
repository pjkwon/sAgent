"""
DB Tools: SQLite / PostgreSQL / MySQL / MSSQL 쿼리 Tool 모음.
드라이버는 설치된 경우에만 사용 가능합니다.
"""
from __future__ import annotations
import json
from typing import Any

from tools.registry import registry
from core.config import DBConfig

_db_config: DBConfig = DBConfig()


def set_db_config(cfg: DBConfig) -> None:
    global _db_config
    _db_config = cfg


# ─────────────────────────────────────────────
# 연결 팩토리
# ─────────────────────────────────────────────

def _get_connection():
    cfg = _db_config
    db_type = cfg.type.lower()

    if db_type == "sqlite":
        import sqlite3
        return sqlite3.connect(cfg.path)

    elif db_type == "postgresql":
        import psycopg2
        return psycopg2.connect(
            host=cfg.host, port=cfg.port,
            dbname=cfg.database, user=cfg.user, password=cfg.password,
        )

    elif db_type == "mysql":
        import pymysql
        return pymysql.connect(
            host=cfg.host, port=cfg.port,
            database=cfg.database, user=cfg.user, password=cfg.password,
            charset="utf8mb4",
        )

    elif db_type in ("mssql", "sqlserver"):
        import pyodbc
        if cfg.dsn:
            conn_str = f"DSN={cfg.dsn};UID={cfg.user};PWD={cfg.password}"
        else:
            conn_str = (
                f"DRIVER={{ODBC Driver 17 for SQL Server}};"
                f"SERVER={cfg.host},{cfg.port};"
                f"DATABASE={cfg.database};"
                f"UID={cfg.user};PWD={cfg.password}"
            )
        return pyodbc.connect(conn_str)

    else:
        raise ValueError(f"지원하지 않는 DB 타입: {cfg.type}")


def _rows_to_text(columns: list[str], rows: list[tuple], max_rows: int = 200) -> str:
    if not rows:
        return "결과 없음 (0 rows)"

    truncated = len(rows) > max_rows
    display_rows = rows[:max_rows]

    # 컬럼 너비 계산
    widths = [len(c) for c in columns]
    for row in display_rows:
        for i, val in enumerate(row):
            widths[i] = max(widths[i], len(str(val) if val is not None else "NULL"))

    sep = "+" + "+".join("-" * (w + 2) for w in widths) + "+"
    header = "|" + "|".join(f" {c:<{widths[i]}} " for i, c in enumerate(columns)) + "|"
    lines = [sep, header, sep]
    for row in display_rows:
        cells = [str(v) if v is not None else "NULL" for v in row]
        lines.append("|" + "|".join(f" {cells[i]:<{widths[i]}} " for i in range(len(columns))) + "|")
    lines.append(sep)

    summary = f"\n{len(rows)}건"
    if truncated:
        summary += f" (최대 {max_rows}건만 표시)"
    return "\n".join(lines) + summary


# ─────────────────────────────────────────────
# Tool: db_query
# ─────────────────────────────────────────────

@registry.register(
    name="db_query",
    description=(
        "데이터베이스에 SELECT 쿼리를 실행하고 결과를 반환합니다. "
        "INSERT/UPDATE/DELETE 등 DML도 실행 가능합니다."
    ),
    parameters={
        "type": "object",
        "properties": {
            "sql": {
                "type": "string",
                "description": "실행할 SQL 문",
            },
            "params": {
                "type": "array",
                "items": {},
                "description": "바인딩 파라미터 목록 (? 또는 %s 플레이스홀더)",
                "default": [],
            },
            "max_rows": {
                "type": "integer",
                "description": "최대 반환 행 수",
                "default": 200,
            },
        },
        "required": ["sql"],
    },
)
def db_query(sql: str, params: list = [], max_rows: int = 200) -> str:
    conn = None
    try:
        conn = _get_connection()
        cur = conn.cursor()
        cur.execute(sql, params or [])

        if cur.description:  # SELECT
            columns = [d[0] for d in cur.description]
            rows = cur.fetchall()
            return _rows_to_text(columns, rows, max_rows)
        else:  # DML
            conn.commit()
            return f"실행 완료 (영향 행: {cur.rowcount})"
    finally:
        if conn:
            conn.close()


# ─────────────────────────────────────────────
# Tool: db_schema
# ─────────────────────────────────────────────

@registry.register(
    name="db_schema",
    description="데이터베이스의 테이블 목록과 컬럼 정보(스키마)를 조회합니다.",
    parameters={
        "type": "object",
        "properties": {
            "table_name": {
                "type": "string",
                "description": "특정 테이블 스키마만 조회 (생략하면 전체 테이블 목록)",
                "default": "",
            },
        },
        "required": [],
    },
)
def db_schema(table_name: str = "") -> str:
    conn = None
    try:
        conn = _get_connection()
        cur = conn.cursor()
        db_type = _db_config.type.lower()

        if db_type == "sqlite":
            if table_name:
                cur.execute(f"PRAGMA table_info('{table_name}')")
                rows = cur.fetchall()
                if not rows:
                    return f"테이블 '{table_name}'을 찾을 수 없습니다."
                return _rows_to_text(["cid", "name", "type", "notnull", "dflt_value", "pk"], rows)
            else:
                cur.execute("SELECT name, type FROM sqlite_master WHERE type IN ('table','view') ORDER BY name")
                rows = cur.fetchall()
                return _rows_to_text(["name", "type"], rows)

        elif db_type == "postgresql":
            if table_name:
                cur.execute("""
                    SELECT column_name, data_type, is_nullable, column_default
                    FROM information_schema.columns
                    WHERE table_name = %s ORDER BY ordinal_position
                """, (table_name,))
                rows = cur.fetchall()
                return _rows_to_text(["column", "type", "nullable", "default"], rows)
            else:
                cur.execute("""
                    SELECT table_name, table_type FROM information_schema.tables
                    WHERE table_schema = 'public' ORDER BY table_name
                """)
                rows = cur.fetchall()
                return _rows_to_text(["table", "type"], rows)

        else:
            return "이 DB 타입에서는 스키마 조회가 지원되지 않습니다. db_query로 직접 조회하세요."

    finally:
        if conn:
            conn.close()
