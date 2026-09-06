# Step 4: analyze

## 읽어야 할 파일
- `/docs/ARCHITECTURE.md` (스키마)
- `/docs/USER_JOURNEY.md` (가설 v0 — 실측과 비교할 대상)
- `/docs/PRD.md` (성공 기준, 방법론 전제, 한계)
- `/taxonomy.json`
- `/src/config.py`
- 이전 step 산출물: `data/processed/tagged.csv`

## 작업
`tagged.csv`를 집계해 리포트를 생성한다.

파일: `src/analyze.py`
시그니처(내부 구현은 재량):
- `load_tagged() -> pd.DataFrame`
- `crosstab_type_grade(df) -> pd.DataFrame` : 축1(`type_code`) × 축2(`bot_grade`) 크로스탭
- `summarize(df) -> dict` : 유형 분포, 앱별(SNOW vs B612) 분포, 등급별(A/B/C) 비율, `product_issue=Y` 건 요약
- `audit_agreement(df, human_csv_path) -> dict | None` : `data/processed/human_audit.csv`(선택)가 있으면 `review_id`로 조인해 일치율을 계산, 없으면 None (검수 훅)
- `write_report(...)` : `docs/report.md` 작성 (+ 가능하면 `report.xlsx`)
- `main()`

핵심 규칙:
- 리포트 필수 섹션: (1) 요약 3줄, (2) 방법(표본·기간·태깅·검수), (3) 유형 분포 + 앱별 차이, (4) **유형 × 등급 크로스탭**(리포트의 심장), (5) A등급 상위 유형 = 챗봇 자동화 후보, (6) `product_issue=Y` 요약, (7) 가설(v0) vs 실측, (8) 한계 4가지.
- 한계 4가지(PRD 방법론 전제 반영): ① 리뷰는 문의의 proxy이며 결제·환불 과소추정, ② 한국어·2개 앱 편중, ③ A등급 비율은 자동화 "가능성 추정치"이지 실제 인입 감소율이 아님, ④ LLM 불일치가 특정 경계 유형에 집중.
- 0으로 나누기를 방어하라(특정 유형 0건일 때). 조인은 `review_id` 기준(위치 아님).
- **"자동화 가능 비율은 추정치"** 문구를 반드시 리포트에 넣어라.

## Acceptance Criteria
```bash
.venv/bin/python -m py_compile src/analyze.py
.venv/bin/python src/analyze.py
test -f docs/report.md && grep -qiE "크로스탭|crosstab|등급" docs/report.md && echo "report ok"
.venv/bin/python -c "print(open('docs/report.md',encoding='utf-8').read()[:500])"
```

## 검증 절차
1. 위 AC를 실행한다. `docs/report.md` 존재 + 크로스탭/등급 포함 확인.
2. 체크리스트: 한계 4가지 포함 / 추정치 문구 포함 / 0으로 나누기 방어.
3. `phases/0-mvp/index.json`의 step 4 업데이트. summary에 핵심 수치(총 표본, A/B/C 비율)를 기록하라.

## 금지사항
- 없는 수치를 지어내지 마라. 특히 "문의 N% 감소" 같은 인입 감소율. 이유: 내부 티켓 데이터 없이 산출 불가하며, 꼬리질문에 무너진다(PRD 방법론 전제).
- 리뷰 원문을 리포트에 대량 인용하지 마라. 유형당 짧은 예시 1개까지, 필요시 마스킹. 이유: 재배포(CLAUDE.md CRITICAL).
- 대시보드/시각화 라이브러리 등 추가 산출물을 만들지 마라. 이유: 스코프(MVP).
