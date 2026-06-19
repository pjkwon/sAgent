# CLI AI Agent

파일 검색 + DB 조회를 결합한 경량 AI 에이전트입니다.  
Claude의 native tool_use(function calling)를 기반으로 동작합니다.

---

## 설치

```bash
pip install -r requirements.txt

# DB 드라이버는 필요한 것만 설치
pip install psycopg2-binary   # PostgreSQL
pip install pymysql           # MySQL
pip install pyodbc            # MSSQL
```

환경 변수 설정:
```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

---

## 빠른 시작

```bash
# 설정 파일 복사
cp config.yaml.example config.yaml

# 대화형 모드
python main.py

# 단일 질문
python main.py -q "data 폴더에서 '불량률' 키워드가 포함된 파일 찾아줘"

# 작업 폴더 지정
python main.py --work-dir ./data

# 출력 형식 변경
python main.py --format plain
```

---

## 프로젝트 구조

```
agent/
├── main.py               # CLI 진입점
├── config.yaml.example   # 설정 파일 예시
├── requirements.txt
│
├── core/
│   ├── agent.py          # 에이전트 루프 (핵심)
│   ├── llm.py            # Claude API 래퍼
│   └── config.py         # 설정 관리
│
├── tools/
│   ├── registry.py       # Tool 레지스트리 (데코레이터 기반)
│   ├── file_tools.py     # 파일 관련 Tool
│   └── db_tools.py       # DB 관련 Tool
│
├── prompts/
│   └── system.md         # 시스템 프롬프트 (커스터마이징 가능)
│
├── workspace/            # 기본 작업 폴더
└── logs/                 # 세션 로그
```

---

## 에이전트 동작 흐름

```
사용자 입력
    ↓
Claude API (tool_use 모드)
    ↓ tool_use 블록 반환
Tool 실행 (file_tools / db_tools)
    ↓ tool_result 반환
Claude API (결과 분석)
    ↓ 필요 시 추가 tool 호출 반복
최종 답변 생성
    ↓
사용자 출력
```

---

## 내장 Tool 목록

| Tool | 기능 |
|------|------|
| `list_files` | 작업 폴더 파일/디렉터리 목록 조회 |
| `read_file` | 파일 내용 읽기 (범위 지정 가능) |
| `search_in_files` | 키워드/정규식으로 파일 내 검색 |
| `write_file` | 파일 생성/추가 쓰기 |
| `db_query` | SQL 실행 (SELECT/DML) |
| `db_schema` | 테이블 스키마 조회 |

---

## 커스텀 Tool 추가

`tools/` 폴더에 새 파일을 만들고 데코레이터로 등록합니다:

```python
# tools/my_tools.py
from tools.registry import registry

@registry.register(
    name="my_tool",
    description="이 Tool이 하는 일을 Claude가 이해할 수 있게 설명하세요.",
    parameters={
        "type": "object",
        "properties": {
            "input_text": {"type": "string", "description": "처리할 텍스트"},
        },
        "required": ["input_text"],
    },
)
def my_tool(input_text: str) -> str:
    # 처리 로직
    return f"결과: {input_text}"
```

그리고 `tools/__init__.py`에 import 추가:
```python
from tools import file_tools, db_tools, my_tools  # noqa: F401
```

---

## 대화형 모드 명령어

| 명령어 | 설명 |
|--------|------|
| `reset` | 대화 히스토리 초기화 |
| `format markdown\|plain\|json` | 출력 형식 변경 |
| `workdir <경로>` | 작업 폴더 변경 |
| `tools` | 사용 가능한 Tool 목록 |
| `save` | 세션 로그 저장 |
| `verbose` | 상세 모드 토글 |
| `help` | 도움말 |
| `exit` | 종료 |

---

## 설정 파일 (config.yaml)

```yaml
model: "claude-sonnet-4-6"
max_tokens: 8192
max_iterations: 15      # 에이전트 루프 최대 횟수
work_dir: "workspace"
output_format: "markdown"
verbose: false
log_session: true

db:
  type: "sqlite"        # sqlite | postgresql | mysql | mssql
  path: "workspace/agent.db"
```

---

## 시스템 프롬프트 커스터마이징

`prompts/system.md`를 편집하여 에이전트의 역할과 행동 방침을 변경할 수 있습니다.  
파일이 없으면 코드 내 기본 프롬프트가 사용됩니다.
