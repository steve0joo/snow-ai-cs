# 아키텍처

## 개요
웹앱이 아닌 **1회성 데이터 파이프라인**. 각 단계는 독립 실행 스크립트이며, 파일(JSON/CSV)로 단계 간 데이터를 넘긴다.

## 대상 앱
| name | google play package | 비고 |
|---|---|---|
| snow | `com.campmobile.snow` | AI 생성/결제 문의 본류 |
| b612 | `com.linecorp.b612.android` | 글로벌 사용자 기반, 앱 간 비교용 |

두 앱 모두 SNOW Corporation. `src/config.py`의 `APPS` 상수에 정의한다.

## 디렉토리 구조
```
snow-ai-cs/
├── src/
│   ├── config.py        # 경로 상수 + APPS + .env 키 로드 (공통)
│   ├── collect.py       # 1. 수집:   google-play-scraper → data/raw/
│   ├── preprocess.py    # 2. 전처리+층화: data/raw/ → data/processed/sample.csv
│   ├── tag.py           # 3. LLM 태깅: sample.csv → tagged.csv
│   └── analyze.py       # 4. 집계+리포트: tagged.csv → docs/report.md (+ report.xlsx)
├── taxonomy.json        # 분류 체계 정의 (2축 + 플래그) — 코드가 읽어 들인다
├── data/
│   ├── raw/             # 수집 원본 (gitignore, 재배포 금지)
│   └── processed/       # 샘플·태깅 결과 (gitignore)
├── docs/                # PRD, ARCHITECTURE, ADR, USER_JOURNEY, report
└── phases/              # Harness 실행 단위(step 파일) — execute.py가 순차 실행
```

## 데이터 흐름
```
google-play-scraper
  → data/raw/{app}_reviews.json      (collect.py; app ∈ {snow, b612})
  → data/processed/sample.csv        (preprocess.py: 정규화 + PII 제거 + 층화)
  → data/processed/tagged.csv        (tag.py: LLM 태깅, review_id 유지)
  → docs/report.md (+ report.xlsx)   (analyze.py: 크로스탭·집계)
```

## 데이터 스키마 (sample.csv / tagged.csv)
| 컬럼 | 값 | 비고 |
|---|---|---|
| review_id | 원본 ID | 조인 키 (위치 아님) |
| app | snow / b612 | 속성 컬럼(축 아님) |
| store | google | |
| lang | ko | |
| rating | 1~5 | |
| date | YYYY-MM | |
| app_version | 결측 허용 | 구글플레이 일부만 제공 |
| content | 리뷰 본문 | PII 마스킹 후 |
| type_code | 1~7, 0 | 주 유형 (tag 단계) |
| type_sub | 1~7, 공란 | 부 유형(선택) |
| bot_grade | A / B / C | 0번은 공란 |
| product_issue | Y / N | |
| tagged_by | llm / human | 검수 신뢰도 근거 |
| note | 경계 케이스 사유 | |

- `userName`은 수집되더라도 preprocess에서 **드롭**한다 (PII).

## 태깅 방식
- Anthropic API 배치 호출(10~20건/콜), `temperature=0`.
- 프롬프트에 `taxonomy.json` 전문 + few-shot(경계 케이스) 포함. 리뷰 본문은 구분자(태그)로 감싸 지시와 분리한다.
- 출력 JSON 강제 → `try/except` 파싱 + 코드 범위 검증. 실패 시 `type_code=null` → 검수큐로.

## 검증(AC) 방식 — Harness 번안
이 프로젝트는 npm build/test가 없다. step의 Acceptance Criteria는 아래로 대체한다:
- `.venv/bin/python -m py_compile src/<파일>.py` (문법/임포트)
- 스크립트 실행 후 기대 산출물 파일 존재 + 행 수·컬럼 확인 (스모크)
