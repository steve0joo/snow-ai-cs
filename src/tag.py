"""3. LLM 태깅 — data/processed/sample.csv → data/processed/tagged.csv.

taxonomy.json 기준으로 각 리뷰를 배치(10~20건/콜)로 태깅한다. 재현성을 위해
temperature=0, 출력은 JSON 강제 + try/except 파싱 + 코드 범위(1~7,0) 검증.
범위 밖·파싱 실패는 type_code=null(검수큐)로 둔다. 견고성은 최소화한다(ADR-007):
배치를 append 저장해 중단 시 부분 결과가 남게 하고, 재실행이 곧 복구다.
"""
import json
import math

import pandas as pd
import anthropic

import config

MODEL = "claude-haiku-4-5-20251001"  # 가성비 태깅용 (step 지정 ID)
BATCH_SIZE = 15                       # 10~20건/콜 (개별 호출 금지)
VALID_TYPES = {0, 1, 2, 3, 4, 5, 6, 7}

# sample.csv 컬럼 뒤에 붙는 태깅 컬럼 (ARCHITECTURE.md 스키마)
TAG_COLS = ["type_code", "type_sub", "bot_grade", "product_issue", "tagged_by", "note"]


def build_prompt(taxonomy: dict, batch: list[dict]) -> str:
    """taxonomy 전문 + 경계 케이스 few-shot + 구분자로 감싼 리뷰로 프롬프트 구성."""
    tx = json.dumps(taxonomy, ensure_ascii=False, indent=2)
    reviews = "\n".join(
        f'<review id="{r["review_id"]}">{r["content"]}</review>' for r in batch
    )
    return f"""너는 카메라·AI 앱(SNOW, B612) 구글플레이 리뷰를 CS 문의 유형으로 분류하는 태거다.
아래 분류 체계(taxonomy)에 따라 각 리뷰를 태깅하라.

## 분류 체계 (taxonomy.json)
{tx}

## 태깅 규칙
- type_code: 주 유형 1개. 1~7 중 하나. 문의로 볼 수 없는 단순 칭찬/비난/무내용은 0.
- type_sub: 부 유형 1개(선택). 복합 문의일 때만 1~7 중 하나, 없으면 "".
- bot_grade: 챗봇 대응 가능성 A/B/C. type_code=0이면 "".
- product_issue: 앱을 고쳐야 하는 이슈면 Y, 아니면 N.
- note: 경계 케이스일 때만 15자 이내의 짧은 사유. 리뷰 원문을 인용하지 마라. 평이하면 "".
- 확신이 없으면 억지로 분류하지 말고 type_code를 null로 두고 note에 짧은 사유를 남겨라.

## few-shot (경계 케이스)
- "생성 실패했는데 크레딧/돈이 빠졌어요" → type_code=3, type_sub=5, bot_grade=B, product_issue=Y (AI생성 실패 + 결제 엉킴)
- "얼굴이 저를 하나도 안 닮았어요" → type_code=3, type_sub="", bot_grade=C, product_issue=N (취향 불만, 판정 불가 → 사람 필수)
- "구독 어떻게 해지해요?" → type_code=5, type_sub="", bot_grade=A, product_issue=N (정답 고정 FAQ)
- "너무 좋아요!!" → type_code=0, type_sub="", bot_grade="", product_issue=N (무내용)

## 대상 리뷰
{reviews}

## 출력
아래 형식의 JSON 배열만 출력하라. 설명·코드블록 없이 JSON만.
[{{"review_id": "...", "type_code": 3, "type_sub": 5, "bot_grade": "B", "product_issue": "Y", "note": ""}}]
각 review의 id를 review_id에 그대로 넣고, 배치의 모든 리뷰를 빠짐없이 포함하라.
"""


def _null_result(review_id: str, note: str) -> dict:
    """검수큐로 보낼 결과 — type_code=null."""
    return {
        "review_id": review_id, "type_code": None, "type_sub": "",
        "bot_grade": "", "product_issue": "", "note": note,
    }


def _normalize(review_id: str, o: dict) -> dict:
    """LLM 객체 1건을 검증·정규화. type_code 범위 밖이면 null(검수큐)."""
    raw = o.get("type_code")
    tc = None
    if not isinstance(raw, bool):
        try:
            tc = int(raw)
        except (TypeError, ValueError):
            tc = None
    note = str(o.get("note") or "")[:60]

    if tc not in VALID_TYPES:
        return _null_result(review_id, note or f"type_code 무효: {raw!r}")

    # 부 유형: 1~7만 허용(0/무효는 공란)
    sub_raw = o.get("type_sub")
    try:
        sub = int(sub_raw)
        type_sub = sub if sub in VALID_TYPES and sub != 0 else ""
    except (TypeError, ValueError):
        type_sub = ""

    grade = o.get("bot_grade") if o.get("bot_grade") in ("A", "B", "C") else ""
    if tc == 0:
        grade = ""  # 0번은 등급 공란 (taxonomy rules.grade_for_0)
    product_issue = o.get("product_issue") if o.get("product_issue") in ("Y", "N") else ""

    return {
        "review_id": review_id, "type_code": tc, "type_sub": type_sub,
        "bot_grade": grade, "product_issue": product_issue, "note": note,
    }


def tag_batch(client, taxonomy: dict, batch: list[dict]) -> list[dict]:
    """배치를 1콜로 태깅하고 리뷰별 태깅 dict 리스트를 반환(입력 순서 유지)."""
    resp = client.messages.create(
        model=MODEL,
        max_tokens=4096,  # 배치 JSON이 잘리지 않게 넉넉히
        extra_body={"temperature": 0},  # 재현성 (이 SDK는 temperature를 최상위 인자로 안 받음)
        messages=[{"role": "user", "content": build_prompt(taxonomy, batch)}],
    )
    text = "".join(b.text for b in resp.content if b.type == "text")
    ids = [r["review_id"] for r in batch]

    # JSON 배열만 추출해 파싱 (설명이 섞여도 방어)
    try:
        start, end = text.index("["), text.rindex("]")
        parsed = json.loads(text[start:end + 1])
        by_id = {str(o.get("review_id")): o for o in parsed}
    except (ValueError, json.JSONDecodeError) as e:
        return [_null_result(rid, f"파싱 실패: {type(e).__name__}") for rid in ids]

    results = []
    for rid in ids:
        o = by_id.get(str(rid))
        results.append(_normalize(rid, o) if o else _null_result(rid, "응답 누락"))
    return results


def main() -> None:
    api_key = config.load_api_key()
    if not api_key:
        # 사용자 개입 필요 — index.json은 실행자가 blocked 처리
        print("[tag] BLOCKED: ANTHROPIC_API_KEY 미설정 (.env 확인)")
        return

    client = anthropic.Anthropic(api_key=api_key)
    taxonomy = json.loads(config.TAXONOMY_PATH.read_text(encoding="utf-8"))
    sample = pd.read_csv(config.DATA_PROCESSED / "sample.csv")
    out_cols = list(sample.columns) + TAG_COLS

    records = sample.to_dict("records")
    batches = [records[i:i + BATCH_SIZE] for i in range(0, len(records), BATCH_SIZE)]
    # 예상 비용 한 줄 (Haiku 4.5 대략 콜당 ~$0.006, 정교한 상한 로직 없음 — ADR-007)
    print(f"[tag] {len(records)}건 · 예상 {len(batches)}콜 × 배치{BATCH_SIZE} "
          f"· Haiku 4.5 콜당 ~$0.006 → 총 ~${len(batches) * 0.006:.2f}")

    out_path = config.DATA_PROCESSED / "tagged.csv"
    all_rows = []
    for i, batch in enumerate(batches, 1):
        tags = {t["review_id"]: t for t in tag_batch(client, taxonomy, batch)}
        rows = []
        for rec in batch:
            t = tags[rec["review_id"]]
            rows.append({**rec, **{c: t.get(c, "") for c in TAG_COLS if c != "tagged_by"},
                         "tagged_by": "llm"})
        # 배치별 append 저장(헤더는 최초 1회) — 중단 시 부분 결과 보존
        pd.DataFrame(rows, columns=out_cols).to_csv(
            out_path, mode="w" if i == 1 else "a", header=(i == 1),
            index=False, encoding="utf-8",
        )
        all_rows.extend(rows)
        print(f"  배치 {i}/{len(batches)} 태깅 완료")

    # review_id로 정렬해 최종 재저장
    final = pd.DataFrame(all_rows, columns=out_cols).sort_values("review_id")
    final.to_csv(out_path, index=False, encoding="utf-8")

    filled = final["type_code"].notna().mean()
    null_n = int(final["type_code"].isna().sum())
    print(f"[tag] {len(final)}건 → {out_path} | type_code 채움율 {filled:.3f} | 검수큐(null) {null_n}건")


if __name__ == "__main__":
    main()
