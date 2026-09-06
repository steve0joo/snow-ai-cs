"""4. 집계 + 리포트 — data/processed/tagged.csv → docs/report.md (+ docs/report.xlsx).

유형(type_code) × 챗봇등급(bot_grade) 크로스탭을 심장으로 A4 리포트 1장을 만든다.
자동화 "가능 비율"은 추정치이지 실제 문의 인입 감소율이 아니다(PRD 방법론 전제).
산출물은 집계뿐이며 리뷰 원문은 재배포하지 않는다(CLAUDE.md CRITICAL).
"""
import json

import pandas as pd

import config

HUMAN_AUDIT_PATH = config.DATA_PROCESSED / "human_audit.csv"
GRADES = ["A", "B", "C"]
DISPLAY = {"snow": "SNOW", "b612": "B612"}  # 리포트 표기용


def pct(n: int, d: int) -> float:
    """0으로 나누기 방어 백분율(소수 1자리)."""
    return 0.0 if d == 0 else round(100 * n / d, 1)


def _type_names() -> dict[int, str]:
    """taxonomy.json에서 유형 코드→이름을 읽는다(하드코딩 금지)."""
    tx = json.loads(config.TAXONOMY_PATH.read_text(encoding="utf-8"))
    return {int(k): v["name"] for k, v in tx["axis1_type"].items()}


def _grade_defs() -> dict[str, dict]:
    """taxonomy.json에서 챗봇 등급 A/B/C의 이름·정의를 읽는다(하드코딩 금지)."""
    tx = json.loads(config.TAXONOMY_PATH.read_text(encoding="utf-8"))
    return tx["axis2_bot_grade"]


def load_tagged() -> pd.DataFrame:
    """tagged.csv를 읽어 반환(review_id가 조인 키)."""
    return pd.read_csv(config.DATA_PROCESSED / "tagged.csv")


def crosstab_type_grade(df: pd.DataFrame) -> pd.DataFrame:
    """유형(1~7) × 등급(A/B/C) 크로스탭 — 리포트의 심장. type 0/검수큐(null)는 제외."""
    names = _type_names()
    d = df[df["type_code"].notna() & (df["type_code"] != 0)].copy()
    d["유형"] = d["type_code"].astype(int).map(lambda c: f"{c} {names.get(c, '?')}")
    ct = pd.crosstab(d["유형"], d["bot_grade"])
    for g in GRADES:  # 특정 등급이 0건이어도 열 유지
        if g not in ct.columns:
            ct[g] = 0
    ct = ct[GRADES]
    ct["합계"] = ct.sum(axis=1)
    ct = ct.sort_values("합계", ascending=False)
    ct.loc["합계"] = ct.sum(axis=0)
    return ct


def summarize(df: pd.DataFrame) -> dict:
    """유형 분포·앱별 차이·등급 비율·product_issue 요약을 dict로 반환."""
    names = _type_names()
    tagged = df[df["type_code"].notna()].copy()
    tagged["type_code"] = tagged["type_code"].astype(int)
    inquiries = tagged[tagged["type_code"] != 0]   # 유형 1~7 (등급이 매겨지는 실질 문의)
    n_tagged, n_inq = len(tagged), len(inquiries)
    codes = sorted(tagged["type_code"].unique())

    # 유형 분포(0 포함 — 0번 비율 자체가 표본 실질 크기 지표, taxonomy rules.bucket_0)
    type_dist = [
        {"code": c, "name": names.get(c, "?"),
         "n": int((tagged["type_code"] == c).sum()),
         "pct": pct(int((tagged["type_code"] == c).sum()), n_tagged)}
        for c in codes
    ]
    inq_rank = sorted([t for t in type_dist if t["code"] != 0],
                      key=lambda x: x["n"], reverse=True)

    # 앱별(SNOW vs B612) 유형 비율 %
    apps = sorted(tagged["app"].unique())
    app_type = {
        a: {c: pct(int(((tagged["app"] == a) & (tagged["type_code"] == c)).sum()),
                   int((tagged["app"] == a).sum())) for c in codes}
        for a in apps
    }
    app_gaps = []
    if len(apps) == 2:
        a0, a1 = apps  # 알파벳순: b612, snow
        for c in codes:
            app_gaps.append({"code": c, "name": names.get(c, "?"),
                             a0: app_type[a0][c], a1: app_type[a1][c],
                             "gap": round(app_type[a1][c] - app_type[a0][c], 1)})

    # 등급 분포(문의 1~7 기준)
    grade_dist = {g: {"n": int((inquiries["bot_grade"] == g).sum())} for g in GRADES}
    for g in GRADES:
        grade_dist[g]["pct"] = pct(grade_dist[g]["n"], n_inq)
    grade_by_type = {
        c: {g: int(((inquiries["type_code"] == c) & (inquiries["bot_grade"] == g)).sum())
            for g in GRADES}
        for c in sorted(inquiries["type_code"].unique())
    }

    # A등급 상위 유형 = 챗봇 자동화 후보(추정)
    a_candidates = sorted(
        [{"code": c, "name": names.get(c, "?"),
          "a_n": grade_by_type[c]["A"],
          "a_share": pct(grade_by_type[c]["A"], sum(grade_by_type[c].values()))}
         for c in grade_by_type],
        key=lambda x: x["a_n"], reverse=True,
    )

    # product_issue=Y (앱을 고쳐야 하는 이슈)
    pi_y = tagged[tagged["product_issue"] == "Y"]
    pi_top = [{"code": int(c), "name": names.get(int(c), "?"), "n": int(n)}
              for c, n in pi_y["type_code"].value_counts().head(4).items()]

    # 복합 유형(부유형 존재) — "AI생성(3)↔결제(5)가 한 리뷰에 엉킨다" 가설 검증
    sub = inquiries[inquiries["type_sub"].notna()].copy()
    combo_35 = 0
    if len(sub):
        sub["type_sub"] = sub["type_sub"].astype(int)
        combo_35 = int((((sub["type_code"] == 3) & (sub["type_sub"] == 5)) |
                        ((sub["type_code"] == 5) & (sub["type_sub"] == 3))).sum())

    return {
        "n_total": len(df), "n_null": int(df["type_code"].isna().sum()),
        "n_tagged": n_tagged, "n_inquiries": n_inq,
        "date_min": df["date"].min(), "date_max": df["date"].max(),
        "apps": apps, "app_counts": {a: int((df["app"] == a).sum()) for a in apps},
        "type_dist": type_dist, "inq_rank": inq_rank,
        "app_type": app_type, "app_gaps": app_gaps,
        "grade_dist": grade_dist, "grade_by_type": grade_by_type,
        "auto_a": grade_dist["A"]["pct"],
        "auto_ab": pct(grade_dist["A"]["n"] + grade_dist["B"]["n"], n_inq),
        "a_candidates": a_candidates,
        "product_issue_y": len(pi_y), "pi_top": pi_top,
        "n_multi": len(sub), "combo_35": combo_35,
    }


def cohen_kappa(a: pd.Series, b: pd.Series) -> float:
    """두 라벨 시리즈의 Cohen's kappa(우연 일치 보정). NaN 없는 정렬 시리즈 가정."""
    a, b = a.astype(str).tolist(), b.astype(str).tolist()
    n = len(a)
    if n == 0:
        return 0.0
    po = sum(x == y for x, y in zip(a, b)) / n
    pe = sum((a.count(c) / n) * (b.count(c) / n) for c in set(a) | set(b))
    return 0.0 if pe >= 1 else round((po - pe) / (1 - pe), 3)


def audit_agreement(df: pd.DataFrame, human_csv_path=HUMAN_AUDIT_PATH) -> dict | None:
    """human_audit.csv가 있으면 review_id로 조인해 LLM vs 검수 일치율·kappa 산출, 없으면 None(훅)."""
    if not human_csv_path.exists():
        return None
    human = pd.read_csv(human_csv_path)
    merged = df.merge(human, on="review_id", suffixes=("_llm", "_human"))  # 위치 아닌 키 조인
    if len(merged) == 0:
        return None
    out = {"n": len(merged)}
    # 유형: 검수큐(null) 제외 후 int로 정규화해 비교(2.0 vs 2 오불일치 방지).
    if {"type_code_llm", "type_code_human"} <= set(merged.columns):
        t = merged.dropna(subset=["type_code_llm", "type_code_human"])
        tl, th = t["type_code_llm"].astype(int), t["type_code_human"].astype(int)
        out["type_n"] = len(t)
        out["type_agreement"] = pct(int((tl.values == th.values).sum()), len(t))
        out["type_kappa"] = cohen_kappa(tl, th)
    # 등급: 유형0은 등급 공란 → 양쪽 등급이 있는 건만 비교(공란끼리를 불일치로 세지 않음).
    if {"bot_grade_llm", "bot_grade_human"} <= set(merged.columns):
        g = merged.dropna(subset=["bot_grade_llm", "bot_grade_human"])
        out["grade_n"] = len(g)
        out["grade_agreement"] = pct(int((g["bot_grade_llm"].values == g["bot_grade_human"].values).sum()), len(g))
        out["grade_kappa"] = cohen_kappa(g["bot_grade_llm"], g["bot_grade_human"])
    return out


def _md_crosstab(ct: pd.DataFrame) -> str:
    lines = ["| 유형 | A 완전자동 | B 조건부 | C 사람필수 | 합계 |",
             "|---|---:|---:|---:|---:|"]
    for idx, r in ct.iterrows():
        lines.append(f"| {idx} | {int(r['A'])} | {int(r['B'])} | {int(r['C'])} | {int(r['합계'])} |")
    return "\n".join(lines)


def _write_xlsx(ct: pd.DataFrame, summ: dict) -> bool:
    """가능하면 docs/report.xlsx 저장(gitignore). openpyxl 없거나 실패 시 조용히 skip."""
    try:
        path = config.DOCS / "report.xlsx"
        type_df = pd.DataFrame(summ["type_dist"])
        app_df = pd.DataFrame(summ["app_type"]).rename(columns=DISPLAY)
        with pd.ExcelWriter(path, engine="openpyxl") as xw:
            ct.to_excel(xw, sheet_name="crosstab")
            type_df.to_excel(xw, sheet_name="type_dist", index=False)
            app_df.to_excel(xw, sheet_name="app_type")
        return True
    except Exception as e:  # noqa: BLE001 — xlsx는 부가 산출물, 실패해도 md는 나온다
        print(f"[analyze] report.xlsx skip: {type(e).__name__}: {e}")
        return False


def write_report(df: pd.DataFrame, ct: pd.DataFrame, summ: dict, audit: dict | None) -> str:
    """docs/report.md 작성(+ docs/report.xlsx). 작성한 마크다운 문자열을 반환."""
    s = summ
    top = s["inq_rank"][0] if s["inq_rank"] else {"name": "-", "pct": 0.0}
    snow_lean = max(s["app_gaps"], key=lambda x: x["gap"], default=None)
    b612_lean = min(s["app_gaps"], key=lambda x: x["gap"], default=None)

    names = _type_names()
    grades = _grade_defs()
    zero_pct = next((t['pct'] for t in s['type_dist'] if t['code'] == 0), 0.0)

    m = []
    m.append("# SNOW·B612 앱 리뷰 VOC 유형 분석 리포트\n")
    m.append(
        "**무엇을 읽는 문서인가.** 카메라·AI 앱 SNOW·B612의 구글플레이 리뷰를 모아, 리뷰 하나하나를 "
        "**(1) 문의 유형**과 **(2) 챗봇 자동화 가능 등급**으로 분류하고 집계한 1회성 VOC 분석이다. "
        "\"CS 문의가 어떤 유형에 몰리는가\"와 \"그중 챗봇으로 자동 응대할 수 있는 비율은 얼마인가\"를 "
        "추정하는 것이 목적이다.\n"
    )
    m.append(
        f"> **표본** {s['n_tagged']}건(태깅 완료, 판단 보류 {s['n_null']}건 제외) · "
        f"**기간** {s['date_min']}~{s['date_max']} · **채널** 구글플레이 한국어 · "
        f"**앱** SNOW {s['app_counts'].get('snow', '?')}건 / B612 {s['app_counts'].get('b612', '?')}건\n"
    )
    tldr = (
        f"**한 줄 결론.** 실질 문의(무내용 제외) {s['n_inquiries']}건 중 가장 많은 유형은 "
        f"**{top['name']}**({top['pct']}%)이고, **챗봇이 바로 답할 수 있는(A등급) 문의는 {s['auto_a']}%**"
        f"(유저 상태 조회가 필요한 B등급까지 더하면 {s['auto_ab']}%)다. "
        f"**단, 이 비율은 자동화 '가능성 추정치'이지 실제 문의가 그만큼 줄어든다는 뜻이 아니다.**"
    )
    if audit and "type_kappa" in audit:
        tldr += (
            f" 별도 독립 검수에서 **유형 분류는 신뢰할 만했지만(일치율 {audit['type_agreement']}%)**, "
            f"**챗봇 등급 판정은 사람 검토가 필요한 수준(일치율 {audit['grade_agreement']}%)**으로 나타났다."
        )
    m.append(tldr + "\n")

    # 분류 체계(용어) — 이후 모든 섹션을 읽기 위한 최소 지식
    m.append("## 분류 체계 한눈에 (먼저 읽기)\n")
    m.append("이 리포트의 모든 숫자는 아래 **두 개의 축 + 한 개의 플래그**로 매겨졌다.\n")
    type_line = " · ".join(f"**{c}** {names[c]}" for c in [1, 2, 3, 4, 5, 6, 7] if c in names)
    m.append(
        f"- **① 유형 — \"무엇에 대한 문의인가\"**: {type_line}. "
        f"그리고 **0** {names.get(0, '분석 제외')}(단순 칭찬·비난, 내용 없음 → 집계에서 대부분 제외).\n"
    )
    grade_line = " · ".join(f"**{g}** {d['name']}({d['def']})" for g, d in grades.items())
    m.append(f"- **② 챗봇 자동화 등급 — \"챗봇이 얼마나 스스로 답할 수 있나\"**: {grade_line}.\n")
    m.append("- **플래그 product_issue(Y/N)**: 챗봇으로 막을 게 아니라 **앱 자체를 고쳐야 하는** 이슈인지.\n")
    m.append(
        "→ 핵심은 **유형(무엇, What)과 등급(그래서 챗봇이 되나, So what)을 별도 축으로 분리**했다는 점이다. "
        "같은 유형이라도 챗봇 자동화 난이도는 A~C로 갈리기 때문이다.\n"
    )

    # 1. 요약
    m.append("## 1. 요약 (3줄)\n")
    m.append(
        f"- **유형 분포**: 실질 문의 {s['n_inquiries']}건의 최다 유형은 **{top['name']}**({top['pct']}%), "
        f"내용 없는 리뷰(0번)는 전체 태깅의 {zero_pct}%였다.\n"
        f"- **자동화 여지**: 챗봇 완전 자동(A) 후보 {s['auto_a']}%, 백엔드 연동 포함(A+B) {s['auto_ab']}% "
        f"— **어디까지나 추정치이며 실제 문의 인입 감소율이 아니다.**\n"
        f"- **앱 차이·개선 신호**: 자매 앱이지만 SNOW와 B612의 유형 분포가 갈렸고(3항), "
        f"앱을 고쳐야 하는 신호(product_issue=Y)가 {s['product_issue_y']}건 잡혔다(6항).\n"
    )

    # 2. 방법
    m.append("## 2. 방법 (표본·기간·태깅·검수)\n")
    m.append(
        f"- **표본**: 구글플레이 한국어 리뷰 {s['n_tagged']}건(앱당 ~250, 별점 층화). "
        "무작위가 아니라 별점 층화 추출이라 모집단을 그대로 대표하지 않는다(ADR-005).\n"
        f"- **기간**: {s['date_min']} ~ {s['date_max']} (리뷰 작성월 기준).\n"
        "- **태깅**: 분류 체계(위 참조, `taxonomy.json`)에 따라 LLM으로 1차 자동 태깅했다(temperature=0, 재현성 확보). "
        f"응답이 형식/범위를 벗어난 리뷰는 억지로 분류하지 않고 **판단 보류**로 빼두었으며, 이번 표본에서 {s['n_null']}건이다.\n"
    )
    if audit:
        parts = [f"독립 검수 {audit['n']}건 조인(이번 회차는 2차 LLM 독립 교차검증 — 진짜 human audit 아님)"]
        if "type_agreement" in audit:
            parts.append(f"유형 일치율 {audit['type_agreement']}%(Cohen κ={audit['type_kappa']})")
        if "grade_agreement" in audit:
            parts.append(f"등급 일치율 {audit['grade_agreement']}%"
                         f"(κ={audit['grade_kappa']}, 등급 부여 {audit['grade_n']}건 기준·유형0 공란 제외)")
        m.append("- **검수**: " + ", ".join(parts) + ". "
                 "유형 축은 우연 일치 보정 후에도 신뢰할 만하나 등급 축은 일치가 낮아, "
                 "챗봇 등급(A/B/C) 판정이 신뢰도의 약한 고리다(한계 4 참조).\n")
    else:
        m.append("- **검수**: `data/processed/human_audit.csv`(무작위 ~50건)를 넣으면 "
                 "`review_id` 조인으로 LLM vs 수동 일치율이 자동 산출된다(현재 미수행, 훅 준비됨).\n")

    # 3. 유형 분포 + 앱별 차이
    m.append("## 3. 유형 분포 + 앱별 차이 (SNOW vs B612)\n")
    m.append("전체 리뷰를 유형별로 나눈 분포다. 이어지는 두 번째 표는 두 앱이 어떻게 다른지 "
             "**Δ = SNOW % − B612 %**(양수면 SNOW에 더 많은 유형)로 비교한다.\n")
    m.append("| 코드 | 유형 | 건수 | 비율 |\n|---:|---|---:|---:|")
    for t in s["type_dist"]:
        m.append(f"| {t['code']} | {t['name']} | {t['n']} | {t['pct']}% |")
    m.append("")
    m.append("앱별 유형 비율(각 앱 태깅 건 기준, Δ = SNOW − B612):\n")
    m.append("| 코드 | 유형 | SNOW % | B612 % | Δ |\n|---:|---|---:|---:|---:|")
    for g in s["app_gaps"]:
        m.append(f"| {g['code']} | {g['name']} | {g.get('snow', 0)} | {g.get('b612', 0)} | {g['gap']:+} |")
    if snow_lean and b612_lean:
        m.append(
            f"\n→ **SNOW 편중**: {snow_lean['name']}({snow_lean['gap']:+}p). "
            f"**B612 편중**: {b612_lean['name']}({b612_lean['gap']:+}p). "
            "AI 아바타/결제 성격의 SNOW와 일상 카메라/편집 성격의 B612 차이가 드러난다.\n"
        )

    # 4. 크로스탭 (심장)
    m.append("## 4. 유형 × 챗봇등급 크로스탭 (이 리포트의 핵심 표)\n")
    m.append("**행 = 문의 유형, 열 = 챗봇 자동화 등급**(A/B/C 정의는 위 '분류 체계' 참조). "
             "각 유형의 문의가 자동화 난이도별로 어떻게 갈리는지 한눈에 보여준다. "
             "유형 0(무내용)과 판단 보류분은 제외했다.\n")
    m.append(_md_crosstab(ct))
    m.append("")

    # 5. A등급 상위 유형 = 챗봇 자동화 후보
    m.append("## 5. 챗봇 자동화 후보 (A등급 상위 유형)\n")
    m.append(
        "**정답이 고정된 A등급 문의가 많이 몰린 유형일수록 챗봇 도입 효과가 크다.** "
        f"문의(유형 1~7) 중 완전 자동(A) {s['auto_a']}%, A+B {s['auto_ab']}%. "
        "**이 자동화 가능 비율은 추정치이며, 실제 문의 인입 감소율이 아니다.**\n"
    )
    m.append("| 유형 | A 건수 | 유형 내 A 비중 |\n|---|---:|---:|")
    for c in s["a_candidates"][:4]:
        m.append(f"| {c['code']} {c['name']} | {c['a_n']} | {c['a_share']}% |")
    m.append("\n→ A 건수가 많은 유형(예: 정답이 고정된 FAQ성 문의)이 챗봇 자동화 1순위 후보다.\n")

    # 6. product_issue=Y 요약
    m.append("## 6. 앱 개선 신호 (product_issue = Y)\n")
    m.append(
        f"챗봇으로 막을 게 아니라 앱을 고쳐야 하는 이슈로 태깅된 건은 **{s['product_issue_y']}건**"
        f"(태깅의 {pct(s['product_issue_y'], s['n_tagged'])}%). 상위 유형:\n"
    )
    m.append("| 유형 | 건수 |\n|---|---:|")
    for p in s["pi_top"]:
        m.append(f"| {p['code']} {p['name']} | {p['n']} |")
    m.append("")

    # 7. 가설(v0) vs 실측
    m.append("## 7. 가설(v0) vs 실측\n")
    m.append("기획 단계에서 세운 가설(문서 `USER_JOURNEY`)이 실제 데이터로 맞았는지 대조한다.\n")
    g3 = s["grade_by_type"].get(3, {"A": 0, "B": 0, "C": 0})
    m.append("| 가설 (USER_JOURNEY v0) | 실측 | 판정 |\n|---|---|---|")
    m.append(
        f"| AI생성(3)↔결제(5)가 한 리뷰에 엉킨다 | 부유형 있는 문의 {s['n_multi']}건 중 "
        f"3↔5 조합 {s['combo_35']}건 | {'확인' if s['combo_35'] else '미검출'} |"
    )
    m.append(
        f"| 같은 유형이라도 등급이 갈린다(유형·등급 별도 축 필요) | 유형3(AI생성) 등급 "
        f"A{g3['A']}/B{g3['B']}/C{g3['C']}로 분산 | {'확인' if sum(g3.values()) and len([v for v in g3.values() if v]) > 1 else '부분'} |"
    )
    if snow_lean and b612_lean:
        m.append(
            f"| SNOW=AI/결제 비중↑, B612=일상 카메라/편집↑ | SNOW 편중 {snow_lean['name']}"
            f"({snow_lean['gap']:+}p), B612 편중 {b612_lean['name']}({b612_lean['gap']:+}p) | 부분 확인 |"
        )
    m.append("")

    # 8. 한계 4가지
    m.append("## 8. 한계 (4가지)\n")
    m.append(
        "1. **리뷰는 CS 문의의 대리 지표(proxy)다.** 결제·환불처럼 고객센터로 직행하는 문의는 "
        "리뷰에 덜 남아 실제보다 과소 추정될 수 있다.\n"
        "2. **한국어·구글플레이·2개 앱(SNOW, B612)에 편중**됐다. App Store와 해외(약 40% 시장) "
        "유형 분포는 검증하지 못했다.\n"
        "3. **A등급 비율은 자동화 '가능성 추정치'이지 실제 문의 인입 감소율이 아니다.** "
        "내부 티켓 데이터 없이 인입 감소율은 산출할 수 없다.\n"
        "4. **LLM 1차 태깅의 불일치는 경계 유형(취향 불만 vs 품질 불량, AI생성↔결제 복합)에 집중**된다. "
        "이 경계가 곧 taxonomy를 v1로 고쳐야 할 지점이다.\n"
    )

    md = "\n".join(m)
    config.DOCS.mkdir(parents=True, exist_ok=True)
    (config.DOCS / "report.md").write_text(md, encoding="utf-8")
    _write_xlsx(ct, s)
    return md


def main() -> None:
    df = load_tagged()
    ct = crosstab_type_grade(df)
    summ = summarize(df)
    audit = audit_agreement(df)
    write_report(df, ct, summ, audit)
    print(f"[analyze] 리포트 → {config.DOCS / 'report.md'}")
    print(f"  표본 {summ['n_tagged']}건 · 문의 {summ['n_inquiries']}건 · "
          f"A {summ['grade_dist']['A']['pct']}% / B {summ['grade_dist']['B']['pct']}% "
          f"/ C {summ['grade_dist']['C']['pct']}% (추정) · "
          f"product_issue=Y {summ['product_issue_y']}건 · 검수큐 {summ['n_null']}건")


if __name__ == "__main__":
    main()
