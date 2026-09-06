# Step 2: preprocess

## 읽어야 할 파일
- `/docs/ARCHITECTURE.md` (데이터 스키마, PII 규칙)
- `/src/config.py` (DATA_RAW, DATA_PROCESSED)
- `/src/collect.py` (raw 저장 형식 확인)
- 이전 step 산출물: `data/raw/*_reviews.json`

먼저 `data/raw/`의 실제 JSON 한 건을 열어 필드 구조를 파악한 뒤 작업하라. google-play-scraper 원본 → 스키마 매핑 힌트: `reviewId→review_id`, `score→rating`, `at→date`(YYYY-MM로 변환), `reviewCreatedVersion→app_version`(결측 허용), `content→content`, `userName→(드롭)`. 실제 필드명은 raw로 최종 확인하라.

## 작업
raw JSON들을 표준 스키마로 정규화·정제하고 층화 샘플을 확정해 `sample.csv`로 저장한다.

파일: `src/preprocess.py`
시그니처(내부 구현은 재량):
- `load_raw() -> pd.DataFrame` : `data/raw`의 앱별 JSON을 읽어 `app` 컬럼을 붙여 합침
- `clean(df) -> pd.DataFrame` : 중복(`review_id`) 제거, 빈/공백 리뷰 제거, `userName` 드롭, `date`→`YYYY-MM`, 스키마 컬럼 정렬
- `build_sample(df) -> pd.DataFrame` : 층화 샘플(앱당 ~250, 전체 목표 ~500) 확정. **collect가 이미 별점 층화 수집을 했으므로, 여기서는 정제로 줄어든 표본의 별점 비율을 유지·보정하는 수준이면 된다(재수집 아님).**
- `main()`

핵심 규칙:
- ARCHITECTURE.md의 스키마 컬럼을 따른다: `review_id, app, store(=google), lang(=ko), rating, date, app_version(결측 허용), content`. 태깅 컬럼(`type_code` 등)은 여기서 만들지 않는다 — tag step 담당.
- `userName` 등 작성자 식별 정보는 **반드시 드롭**한다. 이유: PII(CLAUDE.md CRITICAL).
- `review_id`는 조인 키이므로 반드시 보존한다.
- 저장: `data/processed/sample.csv` (utf-8). 원본 별점 분포 파일이 있으면 `data/processed/rating_dist.json`로 옮기거나 그대로 둔다.

## Acceptance Criteria
```bash
.venv/bin/python -m py_compile src/preprocess.py
.venv/bin/python src/preprocess.py
.venv/bin/python -c "import pandas as pd; d=pd.read_csv('data/processed/sample.csv'); print(d.shape); print(list(d.columns)); assert 'userName' not in d.columns; assert 'review_id' in d.columns; assert len(d)>0"
```

## 검증 절차
1. 위 AC를 실행한다. `sample.csv` 존재 + `userName` 없음 + `review_id` 있음 + 행 수 > 0 확인.
2. 체크리스트: 스키마 일치 / PII 제거 / 층화 반영.
3. `phases/0-mvp/index.json`의 step 2 업데이트. summary에 최종 샘플 행 수와 앱별 분포를 기록하라.

## 금지사항
- `userName`(또는 유사 작성자 식별자)을 `sample.csv`에 남기지 마라. 이유: PII, 되돌릴 수 없는 노출 위험.
- 태깅(`type_code`/`bot_grade` 등)을 여기서 하지 마라. 이유: tag step 담당.
- 정교한 봇 탐지/언어 감지 모델을 넣지 마라. `country`/`lang` 필터 + 빈 리뷰 제거로 충분하다(ADR-007).
