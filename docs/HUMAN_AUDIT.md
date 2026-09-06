# Human 검수 인수인계 (새 세션용)

이 문서 하나로 **새 Claude 세션이 human 검수를 자기완결적으로 이어받을 수 있게** 만든 인수인계서다. 앞선 대화 맥락 없이도 진행 가능하다.

## 0. 현황 (한 줄)
`0-mvp` 파이프라인(collect→preprocess→tag→analyze)이 완료됐다. `data/processed/tagged.csv`에 LLM 1차 태깅 500건이 있고, 이제 그 신뢰도를 사람 검수로 측정하는 단계다.

## 1. 목적
LLM 태깅의 신뢰도를 **무작위 50건을 taxonomy로 독립 태깅**해 일치율로 측정한다. 면접 방어의 핵심("AI로 운영 리소스를 줄이되 그 한계까지 안다")을 완성하는 산출물이다.

## 2. 새 세션 시작하는 법
1. **같은 머신, `feat-0-mvp` 브랜치**에서 진행한다 (`src/`, `data/processed/`가 이 브랜치 워킹트리에 있다). 먼저 `git branch --show-current`로 `feat-0-mvp`인지 확인.
2. 프로젝트 루트에서 `claude` 실행.
3. 첫 프롬프트: **"docs/HUMAN_AUDIT.md를 읽고 human 검수를 진행해줘"**

## 3. 먼저 읽을 파일
- `taxonomy.json` — 분류 체계(유형 1~7/0, 등급 A/B/C, product_issue, 주+부 유형 규칙)
- `docs/USER_JOURNEY.md` — use case 카탈로그(태깅 기준 감각)
- `docs/ARCHITECTURE.md` — 데이터 스키마
- `data/processed/human_audit_template.csv` — **검수할 무작위 50건** (review_id, app, rating, date, content + 빈 태그 컬럼). LLM 태그는 독립성을 위해 일부러 빼뒀다.

## 4. 검수 주체 — 둘 중 선택
- **(A) 사람이 직접** — `human_audit_template.csv`를 에디터/엑셀로 열어 직접 태깅. **진짜 human audit(가장 강력).**
- **(B) 다른 Claude 세션이 독립 태깅** — 가능하면 다른 모델(예: Sonnet)로. 엄밀히는 "2차 LLM 교차검증"이지 human은 아니다. 리포트에 그 사실을 명시해야 한다.
- **독립성 원칙(공통)**: `data/processed/tagged.csv`의 LLM 태그(`type_code`/`bot_grade`)를 **보지 말 것.** 보고 나서 매기면 일치율이 부풀려져 검수의 의미가 사라진다.

## 5. 절차
1. `human_audit_template.csv`의 각 행(`content`)을 `taxonomy.json` 기준으로 태깅한다:
   - `type_code`(1~7 또는 0), `type_sub`(선택, 1~7), `bot_grade`(A/B/C; type_code=0이면 공란), `product_issue`(Y/N), `note`(경계 케이스면 사유)
2. 채운 결과를 **`data/processed/human_audit.csv`로 저장**한다.
   - **필수 컬럼: `review_id`, `type_code`.** `bot_grade`가 있으면 등급 일치율도 자동 산출된다.
3. `.venv/bin/python src/analyze.py` 재실행 → `docs/report.md`의 "2. 방법 · 검수" 줄에 일치율이 자동 반영된다.
4. 확인: report.md에 `수동 검수 N건 조인, 유형 일치율 X%` 문구가 뜨면 성공.

## 6. 일치율 해석 (`src/analyze.py`의 `audit_agreement`)
- `review_id`로 `tagged.csv`와 조인 → `type_code_llm == type_code_human` 비율 = 유형 일치율.
- **불일치 건을 유형별로 묶어 보라.** 특정 경계(예: AI생성 3 ↔ 결제 5, 취향 불만 vs 품질 불량)에 몰리면 이는 LLM 성능 문제가 아니라 **taxonomy 자체의 문제** → v1 재설계 근거(report.md 한계 4번).
- 참고로 순수 일치율 외에 Cohen's kappa를 더하면 "우연 일치 보정" 질문을 방어할 수 있다(선택).

## 7. 마무리
- 검수 후 갱신된 `docs/report.md`는 커밋 대상(`docs/`는 추적됨). `human_audit.csv`·`human_audit_template.csv`는 `.gitignore`(원문 보호)라 미커밋.
- 이 검수는 자동 `execute.py` 파이프라인이 아니다(사람/독립 판단이 개입). **수동으로** 진행한다.
