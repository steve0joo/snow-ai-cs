# Step 1: collect

## 읽어야 할 파일
- `/docs/ARCHITECTURE.md` (대상 앱, 데이터 흐름, 스키마)
- `/docs/ADR.md` (ADR-005 층화, ADR-007 견고성 최소화)
- `/src/config.py` (APPS, DATA_RAW)

이전 step에서 만든 `src/config.py`를 읽고 그 상수(APPS, DATA_RAW)를 재사용하라.

## 작업
`google-play-scraper`로 SNOW·B612의 한국어 리뷰를 별점 층화 수집해 앱별 원본 JSON으로 저장한다.

파일: `src/collect.py`
시그니처(내부 구현은 재량):
- `fetch_app_reviews(gp_id: str) -> tuple[list[dict], dict]` : 층화 수집한 리뷰 리스트와 원본 별점 분포(dict)를 반환
- `main()` : `config.APPS`를 순회하며 저장

핵심 규칙:
- `google_play_scraper.reviews(gp_id, lang="ko", country="kr", sort=Sort.NEWEST, count=N, filter_score_with=S)`를 사용한다.
- 층화 비율(앱당 목표 ~250건): **1점 40% / 2~3점 40% / 4~5점 20%**. `filter_score_with`(1~5)로 별점별 수집.
- 특정 별점이 요청한 `count`보다 적게 반환돼도 정상이다(error로 처리하지 마라). 실제 반환된 만큼만 저장하고 건수를 기록하라.
- 원본 별점 분포도 기록한다(`google_play_scraper.app()`의 히스토그램 또는 무필터 소량 샘플). 이유: 나중에 가중치 복원·방법론 방어.
- 요청 간 `time.sleep(1)` 이상 딜레이. 이유: 차단 예방.
- 저장: `data/raw/{name}_reviews.json` (수집 원본 필드 유지 — `userName` 포함해도 됨, 다음 step에서 드롭). 별점 분포는 `data/raw/{name}_rating_dist.json`.
- **JSON 저장 시 datetime 직렬화 주의(데이터 무결성 핵심 규칙)**: google-play-scraper 결과의 `at`·`repliedAt`은 datetime 객체다. 반드시 `json.dump(..., default=str, ensure_ascii=False)`처럼 datetime을 문자열로 변환해 저장하라. 이유: 기본 `json.dump`는 datetime을 직렬화하지 못해 저장 자체가 `TypeError`로 실패한다.
- 앱별 실제 수집 건수와 별점 분포를 stdout에 출력한다.

## Acceptance Criteria
```bash
.venv/bin/python -m py_compile src/collect.py
.venv/bin/python src/collect.py
.venv/bin/python -c "import json,glob; fs=sorted(glob.glob('data/raw/*_reviews.json')); assert len(fs)>=2, fs; [print(f, len(json.load(open(f)))) for f in fs]; assert all(len(json.load(open(f)))>0 for f in fs)"
```

## 검증 절차
1. 위 AC를 실행한다. `data/raw/`에 `snow_reviews.json`, `b612_reviews.json`이 생기고 각 건수 > 0인지 확인한다.
2. 체크리스트: 앱 2개만 수집했는가 / 층화·딜레이를 적용했는가 / raw를 커밋하지 않는가(.gitignore).
3. `phases/0-mvp/index.json`의 step 1 업데이트 (completed+summary / error / blocked). summary에 앱별 실제 수집 건수를 기록하라.

## 금지사항
- 5개 앱을 다 긁지 마라. **SNOW, B612 2개만.** 이유: 스코프(ADR-001).
- 무한/과대 수집을 하지 마라. 앱당 목표(~250) 상한을 지켜라. 이유: 검수 가능 상한.
- 원본 리뷰를 커밋하거나 재배포하지 마라. 이유: 저작물·개인정보(CLAUDE.md CRITICAL).
- 특정 별점 표본이 부족해도 조용히 넘기지 마라. 실제 수집 건수를 summary에 남겨라. 이유: 후속 분석의 표본 신뢰도 판단 근거.
