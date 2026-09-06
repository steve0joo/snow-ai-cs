# Step 0: project-setup

## 읽어야 할 파일
먼저 아래를 읽고 아키텍처·설계 의도를 파악하라:
- `/CLAUDE.md` (CRITICAL 보안 규칙, 명령어)
- `/docs/ARCHITECTURE.md` (디렉토리 구조, 대상 앱, config.py 역할)
- `/docs/ADR.md` (ADR-006 Harness 번안, ADR-007 견고성 최소화)
- `/requirements.txt`

## 작업
Python 실행 환경과 공통 설정 모듈을 준비한다.

1. 가상환경 + 의존성 설치:
   ```bash
   python3 -m venv .venv
   .venv/bin/pip install --upgrade pip
   .venv/bin/pip install -r requirements.txt
   ```
2. 데이터 폴더가 없으면 생성: `data/raw/`, `data/processed/`. (이미 있으면 그대로 둔다)
3. `src/config.py`를 작성한다 — 이후 모든 step이 import 하는 공통 설정. 아래 인터페이스를 제공하라(내부 구현은 재량):
   - 경로 상수(pathlib 사용): `ROOT`, `DATA_RAW`(= ROOT/"data"/"raw"), `DATA_PROCESSED`(= ROOT/"data"/"processed"), `TAXONOMY_PATH`(= ROOT/"taxonomy.json"), `DOCS`(= ROOT/"docs")
   - 대상 앱 상수(값을 그대로 사용하라. 검증된 패키지명이다):
     ```python
     APPS = [
         {"name": "snow", "gp_id": "com.campmobile.snow"},
         {"name": "b612", "gp_id": "com.linecorp.b612.android"},
     ]
     ```
   - `load_api_key() -> str | None`: `.env`의 `ANTHROPIC_API_KEY`를 python-dotenv로 읽어 반환한다. 없으면 None.

## Acceptance Criteria
```bash
.venv/bin/python -m py_compile src/config.py
.venv/bin/python -c "import google_play_scraper, anthropic, pandas, dotenv, openpyxl; print('deps ok')"
.venv/bin/python -c "import sys; sys.path.insert(0,'src'); import config; print(config.DATA_RAW); print([a['name'] for a in config.APPS])"
test -d data/raw && test -d data/processed && echo "dirs ok"
```

## 검증 절차
1. 위 AC 커맨드를 모두 실행해 에러가 없는지 확인한다.
2. 아키텍처 체크리스트:
   - ARCHITECTURE.md 디렉토리 구조를 따르는가?
   - `src/config.py` 외에 파이프라인 로직(수집/태깅 등)을 미리 만들지 않았는가?
3. `phases/0-mvp/index.json`의 step 0을 업데이트한다:
   - 성공 → `"status": "completed"`, `"summary"`에 산출물 요약(생성 파일 목록)
   - 3회 시도 후 실패 → `"status": "error"`, `"error_message"`
   - 사용자 개입 필요 → `"status": "blocked"`, `"blocked_reason"`

## 금지사항
- collect/preprocess/tag/analyze 로직을 여기서 만들지 마라. 이유: step 0은 환경 준비만 담당한다.
- `.env` 파일을 커밋하거나 그 내용을 stdout/로그에 출력하지 마라. 이유: 비밀키 유출은 되돌릴 수 없다.
- `docs/`, `taxonomy.json` 등 기존 파일을 수정하지 마라.
- 시스템 python에 전역 설치하지 마라. 반드시 `.venv`를 사용하라. 이유: 이후 step이 `.venv/bin/python`으로 실행된다.
