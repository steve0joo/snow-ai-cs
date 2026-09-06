# Step 3: tag

## 읽어야 할 파일
- `/docs/ARCHITECTURE.md` (태깅 방식, 스키마)
- `/docs/USER_JOURNEY.md` (few-shot 예시로 쓸 use case 카탈로그)
- `/docs/ADR.md` (ADR-004 태깅, ADR-007 견고성 최소화)
- `/taxonomy.json` (분류 체계 — 코드가 로드)
- `/src/config.py` (load_api_key, TAXONOMY_PATH, DATA_PROCESSED)
- 이전 step 산출물: `data/processed/sample.csv`

## 작업
`sample.csv`의 각 리뷰를 `taxonomy.json` 기준으로 LLM 배치 태깅하고 `tagged.csv`로 저장한다.

파일: `src/tag.py`
시그니처(내부 구현은 재량):
- `build_prompt(taxonomy: dict, batch: list[dict]) -> str`
- `tag_batch(client, taxonomy, batch) -> list[dict]` : 각 리뷰의 `{review_id, type_code, type_sub, bot_grade, product_issue, note}` 반환
- `main()`

핵심 규칙:
- 모델: `claude-haiku-4-5-20251001` (가성비 태깅용). `temperature=0`. 배치 출력 JSON이 잘리지 않도록 `max_tokens`를 넉넉히(예: 4096) 잡아라. 모델 사용법/최신 ID가 불확실하면 `claude-api` 스킬을 호출해 확인하라.
- API 키: `config.load_api_key()`로 로드한다. None이면 **즉시 blocked 처리**(`"blocked_reason": "ANTHROPIC_API_KEY 미설정"`) 후 중단하라. 이유: 사용자 개입 필요.
- 배치 크기 **10~20건/콜** (개별 1건 호출 금지 — 30분 timeout·비용). 각 배치 결과를 `tagged.csv`에 append 저장한다(헤더는 최초 1회만 쓴다). 이유: 중단돼도 재실행으로 이어갈 수 있게.
- 리뷰 본문은 구분자(예: `<review id="...">...</review>`)로 감싸 지시와 분리한다. 이유: 프롬프트 인젝션/혼선 방지.
- 출력은 JSON으로 강제한다. `try/except`로 파싱하고, `type_code`가 taxonomy 범위(1~7,0) 밖이거나 파싱 실패면 `type_code=null`로 두고 `note`에 사유를 남긴다. 이유: 환각 억지 분류 방지 → 검수큐.
- `type_code=0`이면 `bot_grade`는 공란. 다중 유형은 주(`type_code`) + 부(`type_sub`) 1개로만.
- `tagged_by="llm"`을 기록한다.
- 실행 시작 시 "예상 호출 수 × 대략 단가" 한 줄을 stdout에 출력한다. (정교한 비용 상한 로직은 만들지 마라 — ADR-007)
- 저장: `data/processed/tagged.csv` (sample.csv 컬럼 + 태깅 컬럼, `review_id`로 정렬).

## Acceptance Criteria
```bash
.venv/bin/python -m py_compile src/tag.py
.venv/bin/python src/tag.py
.venv/bin/python -c "import pandas as pd; d=pd.read_csv('data/processed/tagged.csv'); print(d.shape); assert 'type_code' in d.columns; filled=d['type_code'].notna().mean(); print('type_code 채움율', round(filled,3)); assert filled>0.5"
```

## 검증 절차
1. 위 AC를 실행한다. `tagged.csv` 존재 + `type_code` 채움율(> 0.5) 확인.
2. 체크리스트: 배치 호출인가 / temp=0 / null 검수큐 처리 / `review_id` 보존.
3. `phases/0-mvp/index.json`의 step 3 업데이트. **키가 없으면 blocked.** summary에 채움율과 null(검수큐) 건수를 기록하라.

## 금지사항
- 개별(1건씩) 호출을 하지 마라. 이유: 30분 timeout·비용. 반드시 배치로.
- 확신 없는 리뷰를 억지로 분류하지 마라. `type_code=null`로 두어라. 이유: 오분류가 리포트를 오염시킨다.
- 리뷰 원문을 커밋하거나 리포트/로그에 대량 인용하지 마라. 이유: 재배포(CLAUDE.md CRITICAL).
- 정교한 재시도 백오프/체크포인트 재개 로직을 만들지 마라. append 저장 + 재실행으로 충분하다(ADR-007).
